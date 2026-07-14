"""Excepciones propias del conector Gmail IMAP/SMTP.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas de imaplib/smtplib.
"""


class ImapSmtpConnectorError(Exception):
    """Error base del conector."""


class ImapSmtpAuthError(ImapSmtpConnectorError):
    """Credenciales inválidas (email o contraseña de aplicación incorrectos)."""


class ImapSmtpNetworkError(ImapSmtpConnectorError):
    """No se pudo alcanzar el servidor IMAP/SMTP (red, timeout, TLS)."""


class ImapSmtpDataError(ImapSmtpConnectorError):
    """La operación es válida pero el recurso no existe o los datos son inválidos."""
