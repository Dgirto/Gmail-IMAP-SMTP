"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_GMAIL_IMAP_.

Los servidores IMAP/SMTP de Gmail son fijos (no configurables): este
conector es específicamente para Gmail, no un cliente IMAP genérico.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_GMAIL_IMAP_"


def _read_timeout(default: int = 30) -> int:
    """Lee REQUEST_TIMEOUT tratando el string vacío como ausente: la
    plataforma envía "" cuando el campo opcional queda en blanco."""
    raw = (os.environ.get(f"{ENV_PREFIX}REQUEST_TIMEOUT") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(
            f"{ENV_PREFIX}REQUEST_TIMEOUT debe ser un número entero de segundos, no {raw!r}."
        ) from None
    if value <= 0:
        raise ValueError(f"{ENV_PREFIX}REQUEST_TIMEOUT debe ser mayor que 0, no {value}.")
    return value

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


@dataclass(frozen=True)
class ImapSmtpConfig:
    """Credenciales de acceso a Gmail vía IMAP/SMTP.

    La "contraseña" NUNCA es la contraseña normal de la cuenta de Google:
    Gmail exige una Contraseña de aplicación (16 caracteres, generada en
    myaccount.google.com/apppasswords), lo cual a su vez requiere tener
    la verificación en 2 pasos activada en la cuenta.
    """

    email: str
    app_password: str
    request_timeout: int = 30

    @classmethod
    def from_env(cls) -> "ImapSmtpConfig":
        """Construye la configuración desde las variables RUVIC_GMAIL_IMAP_*.

        Raises:
            ValueError: si falta alguna variable obligatoria.

        Ejemplo:
            >>> config = ImapSmtpConfig.from_env()
            >>> config.email
            'soporte@tuempresa.com'
        """
        missing = [
            f"{ENV_PREFIX}{name}"
            for name in ("EMAIL", "APP_PASSWORD")
            if not os.environ.get(f"{ENV_PREFIX}{name}")
        ]
        if missing:
            raise ValueError(
                "Faltan variables de entorno del conector gmail_imap: "
                + ", ".join(missing)
                + ". Configura el conector en Settings -> Conectores."
            )

        return cls(
            email=os.environ[f"{ENV_PREFIX}EMAIL"],
            app_password=os.environ[f"{ENV_PREFIX}APP_PASSWORD"],
            request_timeout=_read_timeout(),
        )
