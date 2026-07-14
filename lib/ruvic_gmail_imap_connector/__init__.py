"""Conector Ruvic para Gmail vía IMAP/SMTP (usuario + Contraseña de aplicación)."""

from .client import ImapSmtpClient
from .config import ENV_PREFIX, ImapSmtpConfig
from .exceptions import (
    ImapSmtpAuthError,
    ImapSmtpConnectorError,
    ImapSmtpDataError,
    ImapSmtpNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "ImapSmtpAuthError",
    "ImapSmtpClient",
    "ImapSmtpConfig",
    "ImapSmtpConnectorError",
    "ImapSmtpDataError",
    "ImapSmtpNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"
