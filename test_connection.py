"""Prueba de conexión estándar del conector gmail_imap.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_GMAIL_IMAP_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Inicia sesión IMAP contra Gmail usando las env vars RUVIC_GMAIL_IMAP_*."""
    try:
        from ruvic_gmail_imap_connector import (
            ImapSmtpAuthError,
            ImapSmtpClient,
            ImapSmtpDataError,
            ImapSmtpNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-gmail-imap-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "Gmail-IMAP-SMTP.git#subdirectory=lib",
        )

    try:
        client = ImapSmtpClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except ImapSmtpAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except ImapSmtpNetworkError as exc:
        return False, f"Error de red: {exc}"
    except ImapSmtpDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (True, f"Conexión exitosa al buzón {client.config.email}")


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
