---
name: gmail_imap
description: >
  Usa la librería ruvic_gmail_imap_connector para leer y enviar correos en
  Gmail vía IMAP/SMTP - buscar/listar correos con filtros (list_messages),
  leer el detalle de un correo (get_message), enviar un correo (send_message)
  y enviar un correo con adjunto (send_message_with_attachment). Úsala
  cuando el usuario pida leer, buscar, filtrar o enviar correos por Gmail
  y el conector configurado sea el de IMAP/SMTP (no el de OAuth2).
triggers:
- gmail
- correo
- correos
- email
- enviar correo
- leer correos
- bandeja de entrada
- buzón
---

# Conector Gmail IMAP/SMTP (ruvic_gmail_imap_connector)

Librería Python para leer y enviar correos en Gmail vía IMAP/SMTP con usuario y Contraseña de aplicación. Está **preinstalada en el runtime** cuando el conector está configurado (si no, instálala con `pip install git+https://github.com/Dgirto/Gmail-IMAP.git#subdirectory=lib`). No usa OAuth2 ni requiere configuración en Google Cloud Console — solo depende de la biblioteca estándar de Python (`imaplib`, `smtplib`, `email`), sin dependencias externas.

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de variables de entorno, disponibles cuando el conector `gmail_imap` está configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_GMAIL_IMAP_EMAIL` | Correo de Gmail del buzón |
| `RUVIC_GMAIL_IMAP_APP_PASSWORD` | Contraseña de aplicación (16 caracteres, NO la contraseña normal) |
| `RUVIC_GMAIL_IMAP_REQUEST_TIMEOUT` | (opcional) timeout en segundos, default 30 |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en **Settings → Conectores**.

## Conexión (siempre igual)

```python
from ruvic_gmail_imap_connector import ImapSmtpClient

client = ImapSmtpClient()  # lee RUVIC_GMAIL_IMAP_* del entorno automáticamente
```

## Capacidad 1 — Buscar/listar correos con filtros

```python
# query usa la sintaxis de búsqueda de Gmail (vía la extensión IMAP X-GM-RAW):
# is:unread, from:x@y.com, subject:factura, after:2026/07/01, has:attachment, etc.
messages = client.list_messages(query="is:unread", max_results=20)
for m in messages:
    print(f"{m['date']} | {m['from']} | {m['subject']}")
```

`id` en el resultado es el UID IMAP del mensaje (no un ID de Gmail API).

## Capacidad 2 — Leer el detalle de un correo

```python
detail = client.get_message(messages[0]["id"])
print(detail["subject"], detail["from"], detail["body_text"])
```

## Capacidad 3 — Enviar un correo

```python
result = client.send_message(
    to="cliente@dominio.com",
    subject="Actualización del ticket",
    body_text="Buen día, le confirmamos que el ticket fue resuelto.",
    cc="supervisor@tuempresa.com",  # opcional
)
```

## Capacidad 4 — Enviar un correo con adjunto

```python
result = client.send_message_with_attachment(
    to="cliente@dominio.com",
    subject="Reporte mensual",
    body_text="Adjunto el reporte solicitado.",
    attachment_path="/tmp/reporte.pdf",  # máximo 20 MB
)
```

## Manejo de errores

```python
from ruvic_gmail_imap_connector import (
    ImapSmtpAuthError, ImapSmtpDataError, ImapSmtpNetworkError,
)

try:
    client.send_message("cliente@dominio.com", "Asunto", "Cuerpo")
except ImapSmtpAuthError:
    print("Credenciales inválidas — revisa el email y la Contraseña de aplicación")
except ImapSmtpNetworkError:
    print("No se pudo conectar a los servidores de Gmail")
except ImapSmtpDataError as e:
    print(f"Error de datos: {e}")  # ej. archivo adjunto inexistente
```

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_GMAIL_IMAP_*` (el constructor de `ImapSmtpClient` ya lo hace).
2. Nunca imprimas `RUVIC_GMAIL_IMAP_APP_PASSWORD` en logs ni en la salida.
3. Usa `max_results` razonable en `list_messages` (default 20, máximo 100) para no traer la bandeja completa.
4. Todos los correos se envían siempre desde `RUVIC_GMAIL_IMAP_EMAIL`; no es posible suplantar otro remitente.
5. `attachment_path` debe ser una ruta local accesible en el runtime; el conector rechaza archivos mayores a 20 MB.
6. Los servidores IMAP/SMTP son fijos a Gmail (`imap.gmail.com`, `smtp.gmail.com`); este conector no sirve para otros proveedores de correo.
