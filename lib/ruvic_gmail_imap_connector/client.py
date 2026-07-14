"""Cliente de Gmail vía IMAP/SMTP con usuario y Contraseña de aplicación.

Capacidades:
- list_messages():              buscar/listar correos con filtros (sintaxis
                                 de búsqueda de Gmail vía la extensión IMAP
                                 X-GM-RAW).
- get_message():                leer el detalle y cuerpo de un correo.
- send_message():                enviar un correo.
- send_message_with_attachment(): enviar un correo con un archivo adjunto.

Las credenciales SIEMPRE provienen de variables de entorno
RUVIC_GMAIL_IMAP_* (ver config.ImapSmtpConfig.from_env). Prohibido
hardcodearlas. Los servidores son fijos (imap.gmail.com / smtp.gmail.com):
este conector es específico para Gmail, no un cliente IMAP genérico.
"""

from __future__ import annotations

import imaplib
import mimetypes
import smtplib
from email import message_from_bytes
from email.header import decode_header
from email.message import Message
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from .config import IMAP_HOST, IMAP_PORT, SMTP_HOST, SMTP_PORT, ImapSmtpConfig
from .exceptions import (
    ImapSmtpAuthError,
    ImapSmtpDataError,
    ImapSmtpNetworkError,
)
from .logging_utils import get_logger

_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


def _imap_quote(value: str) -> str:
    """Escapa un literal de búsqueda para el protocolo IMAP."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _validate_no_header_injection(**fields: str | None) -> None:
    """Evita inyección de cabeceras de correo (CRLF) en campos que se
    interpolan directamente en el mensaje MIME (to/cc/bcc/subject)."""
    for name, value in fields.items():
        if value and ("\r" in value or "\n" in value):
            raise ImapSmtpDataError(
                f"El campo '{name}' contiene saltos de línea, lo cual no está "
                "permitido (previene inyección de cabeceras de correo)."
            )


def _decode_header_value(raw: str | None) -> str:
    """Decodifica un encabezado de correo (Subject/From/To) que puede venir
    en formato RFC 2047 (ej. "=?UTF-8?B?...?=") cuando contiene caracteres
    no ASCII (tildes, emojis, etc.)."""
    if not raw:
        return ""
    parts = []
    for text, charset in decode_header(raw):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts)


def _extract_plain_text(msg: Message) -> str:
    """Recorre las partes MIME de un mensaje y retorna el primer
    text/plain decodificado que encuentre."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    if msg.get_content_type() == "text/plain":
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


class ImapSmtpClient:
    """Cliente de Gmail vía IMAP/SMTP para leer y enviar correos.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_GMAIL_IMAP_* (comportamiento
            estándar en el runtime de la plataforma).

    Ejemplo:
        >>> client = ImapSmtpClient()          # lee RUVIC_GMAIL_IMAP_* del entorno
        >>> client.list_messages(query="is:unread", max_results=5)
        [{'id': '12345', 'subject': 'Hola', 'from': 'a@b.com', ...}]
    """

    def __init__(self, config: ImapSmtpConfig | None = None) -> None:
        self.config = config or ImapSmtpConfig.from_env()
        self._logger = get_logger()

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        try:
            conn = imaplib.IMAP4_SSL(
                IMAP_HOST, IMAP_PORT, timeout=self.config.request_timeout
            )
        except OSError as exc:
            raise ImapSmtpNetworkError(
                f"No se pudo conectar a {IMAP_HOST}:{IMAP_PORT} "
                f"(timeout {self.config.request_timeout}s). Verifica la conexión "
                "de red."
            ) from exc
        try:
            conn.login(self.config.email, self.config.app_password)
        except imaplib.IMAP4.error as exc:
            raise ImapSmtpAuthError(
                "Autenticación fallida: verifica que el email sea correcto y que "
                "la contraseña sea una Contraseña de aplicación válida (no la "
                "contraseña normal de la cuenta). Genera una nueva en "
                "myaccount.google.com/apppasswords (requiere verificación en 2 "
                "pasos activada)."
            ) from exc
        return conn

    def ping(self) -> bool:
        """Verifica la conexión iniciando sesión IMAP y abriendo INBOX.

        Returns:
            True si las credenciales funcionan.

        Raises:
            ImapSmtpAuthError / ImapSmtpNetworkError según el fallo.
        """
        conn = self._connect_imap()
        try:
            conn.select("INBOX", readonly=True)
        finally:
            try:
                conn.logout()
            except Exception:
                pass
        self._logger.info("Ping exitoso a %s", self.config.email)
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: buscar/listar correos con filtros
    # ------------------------------------------------------------------ #

    def list_messages(
        self, query: str = "", max_results: int = 20, mailbox: str = "INBOX"
    ) -> list[dict[str, Any]]:
        """Busca correos usando la sintaxis de búsqueda de Gmail.

        Args:
            query: filtro de búsqueda de Gmail (ej. "is:unread",
                "from:cliente@dominio.com"). Cadena vacía = todos los
                correos del buzón. Usa la extensión IMAP X-GM-RAW de
                Gmail, que acepta la misma sintaxis que la web de Gmail.
            max_results: máximo de correos a retornar (default 20, máximo 100).
            mailbox: buzón/etiqueta a consultar (default "INBOX").

        Returns:
            Lista de dicts: {"id", "subject", "from", "date"}. El "id" es
            el UID IMAP, usable en get_message().

        Ejemplo:
            >>> client.list_messages(query="is:unread", max_results=5)
            [{'id': '18234', 'subject': 'Factura pendiente', 'from': 'a@b.com', ...}]
        """
        max_results = max(1, min(int(max_results), 100))
        conn = self._connect_imap()
        try:
            typ, _ = conn.select(mailbox, readonly=True)
            if typ != "OK":
                raise ImapSmtpDataError(f"El buzón '{mailbox}' no existe.")
            try:
                # None = sin charset explícito, sigue la misma convención que
                # conn.search(); el stub de imaplib no admite None aquí pero
                # imaplib.IMAP4._command sí lo filtra en tiempo de ejecución.
                if query:
                    typ, data = conn.uid("search", None, "X-GM-RAW", _imap_quote(query))  # type: ignore[arg-type]
                else:
                    typ, data = conn.uid("search", None, "ALL")  # type: ignore[arg-type]
            except imaplib.IMAP4.error as exc:
                raise ImapSmtpDataError(f"Consulta de búsqueda inválida: {exc}") from exc
            if typ != "OK":
                raise ImapSmtpDataError(f"Búsqueda IMAP fallida: {data}")

            uids = data[0].split()
            uids = uids[-max_results:]
            uids.reverse()  # más recientes primero

            results: list[dict[str, Any]] = []
            for uid in uids:
                typ, msg_data = conn.uid(
                    "fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])"
                )
                if typ != "OK" or not msg_data or msg_data[0] is None:
                    continue
                headers = message_from_bytes(msg_data[0][1])
                results.append(
                    {
                        "id": uid.decode(),
                        "subject": _decode_header_value(headers.get("Subject")),
                        "from": _decode_header_value(headers.get("From")),
                        "date": headers.get("Date", ""),
                    }
                )
        finally:
            try:
                conn.logout()
            except Exception:
                pass
        self._logger.info(
            "Se listaron %d mensajes de %s (query=%r)", len(results), mailbox, query
        )
        return results

    # ------------------------------------------------------------------ #
    # Capacidad 2: leer el detalle de un correo
    # ------------------------------------------------------------------ #

    def get_message(self, message_id: str, mailbox: str = "INBOX") -> dict[str, Any]:
        """Obtiene el detalle completo (incluido el cuerpo) de un correo.

        Args:
            message_id: UID IMAP del mensaje (obtenido de list_messages).
            mailbox: buzón donde buscar el mensaje (default "INBOX").

        Returns:
            Dict con: id, subject, from, to, date, body_text.

        Ejemplo:
            >>> client.get_message("18234")
            {'id': '18234', 'subject': 'Hola', 'body_text': 'Buen día...', ...}
        """
        conn = self._connect_imap()
        try:
            conn.select(mailbox, readonly=True)
            typ, msg_data = conn.uid("fetch", message_id, "(RFC822)")
            if typ != "OK" or not msg_data or msg_data[0] is None:
                raise ImapSmtpDataError(f"El mensaje '{message_id}' no existe.")
            msg = message_from_bytes(msg_data[0][1])
        finally:
            try:
                conn.logout()
            except Exception:
                pass
        return {
            "id": message_id,
            "subject": _decode_header_value(msg.get("Subject")),
            "from": _decode_header_value(msg.get("From")),
            "to": _decode_header_value(msg.get("To")),
            "date": msg.get("Date", ""),
            "body_text": _extract_plain_text(msg),
        }

    # ------------------------------------------------------------------ #
    # Capacidad 3: enviar un correo
    # ------------------------------------------------------------------ #

    def send_message(
        self,
        to: str,
        subject: str,
        body_text: str,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Envía un correo de texto plano desde el buzón configurado.

        Args:
            to: destinatario(s), separados por coma.
            subject: asunto del correo.
            body_text: cuerpo en texto plano.
            cc: copia (opcional).
            bcc: copia oculta (opcional).

        Returns:
            Dict con: to, subject (confirmación; SMTP no retorna un ID
            de mensaje como sí lo hace la API de Gmail).

        Ejemplo:
            >>> client.send_message("cliente@dominio.com", "Hola", "Buen día...")
            {'to': 'cliente@dominio.com', 'subject': 'Hola'}
        """
        _validate_no_header_injection(to=to, subject=subject, cc=cc, bcc=bcc)
        message = MIMEText(body_text, "plain", "utf-8")
        message["To"] = to
        message["From"] = self.config.email
        message["Subject"] = subject
        if cc:
            message["Cc"] = cc

        recipients = self._all_recipients(to, cc, bcc)
        self._send_via_smtp(recipients, message.as_string())
        self._logger.info("Correo enviado a %s", to)
        return {"to": to, "subject": subject}

    # ------------------------------------------------------------------ #
    # Capacidad 4: enviar un correo con adjunto
    # ------------------------------------------------------------------ #

    def send_message_with_attachment(
        self,
        to: str,
        subject: str,
        body_text: str,
        attachment_path: str,
        cc: str | None = None,
        bcc: str | None = None,
    ) -> dict[str, Any]:
        """Envía un correo de texto plano con un archivo adjunto.

        Args:
            to: destinatario(s), separados por coma.
            subject: asunto del correo.
            body_text: cuerpo en texto plano.
            attachment_path: ruta local del archivo a adjuntar (máx. 20 MB).
            cc: copia (opcional).
            bcc: copia oculta (opcional).

        Returns:
            Dict con: to, subject (confirmación de envío).

        Ejemplo:
            >>> client.send_message_with_attachment(
            ...     "cliente@dominio.com", "Reporte", "Adjunto el reporte.",
            ...     "/tmp/reporte.pdf",
            ... )
            {'to': 'cliente@dominio.com', 'subject': 'Reporte'}
        """
        _validate_no_header_injection(to=to, subject=subject, cc=cc, bcc=bcc)
        path = Path(attachment_path)
        if not path.is_file():
            raise ImapSmtpDataError(f"El archivo adjunto no existe: {attachment_path}")
        size = path.stat().st_size
        if size > _MAX_ATTACHMENT_BYTES:
            raise ImapSmtpDataError(
                f"El adjunto pesa {size / 1_048_576:.1f} MB, supera el límite de "
                f"{_MAX_ATTACHMENT_BYTES / 1_048_576:.0f} MB soportado por el conector."
            )

        message = MIMEMultipart()
        message["To"] = to
        message["From"] = self.config.email
        message["Subject"] = subject
        if cc:
            message["Cc"] = cc
        message.attach(MIMEText(body_text, "plain", "utf-8"))

        content_type, _ = mimetypes.guess_type(path.name)
        content_type = content_type or "application/octet-stream"
        _, subtype = content_type.split("/", 1)
        with path.open("rb") as f:
            attachment = MIMEApplication(f.read(), _subtype=subtype)
        attachment.add_header("Content-Disposition", "attachment", filename=path.name)
        message.attach(attachment)

        recipients = self._all_recipients(to, cc, bcc)
        self._send_via_smtp(recipients, message.as_string())
        self._logger.info("Correo con adjunto '%s' enviado a %s", path.name, to)
        return {"to": to, "subject": subject}

    # ------------------------------------------------------------------ #
    # Auxiliares
    # ------------------------------------------------------------------ #

    @staticmethod
    def _all_recipients(to: str, cc: str | None, bcc: str | None) -> list[str]:
        recipients = [addr.strip() for addr in to.split(",") if addr.strip()]
        if cc:
            recipients += [addr.strip() for addr in cc.split(",") if addr.strip()]
        if bcc:
            recipients += [addr.strip() for addr in bcc.split(",") if addr.strip()]
        return recipients

    def _send_via_smtp(self, recipients: list[str], raw_message: str) -> None:
        try:
            with smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, timeout=self.config.request_timeout
            ) as smtp:
                smtp.login(self.config.email, self.config.app_password)
                smtp.sendmail(self.config.email, recipients, raw_message)
        except smtplib.SMTPAuthenticationError as exc:
            raise ImapSmtpAuthError(
                "Autenticación fallida: verifica que el email sea correcto y que "
                "la contraseña sea una Contraseña de aplicación válida. Genera "
                "una nueva en myaccount.google.com/apppasswords."
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise ImapSmtpDataError(
                f"Uno o más destinatarios fueron rechazados: {exc.recipients}"
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise ImapSmtpNetworkError(
                f"No se pudo enviar el correo vía {SMTP_HOST}:{SMTP_PORT}: {exc}"
            ) from exc
