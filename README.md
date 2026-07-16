# Conector Gmail IMAP/SMTP (CON-005.1)

Conector Ruvic para Gmail vía **IMAP/SMTP con usuario y Contraseña de
aplicación**. Permite buscar/listar correos con filtros, leer el detalle
de un correo, enviar correos y enviar correos con adjunto — sin OAuth2,
sin configuración en Google Cloud Console.

Es la variante simplificada de [CON-005](../CON-005) (que usa OAuth2). Se
mantienen como conectores **separados**, no como dos modos dentro de uno
solo, para que el cliente final no tenga que elegir entre métodos de
autenticación al configurar — cada uno se presenta como una tarjeta
distinta en el catálogo de conectores.

## Instalación

```bash
pip install git+https://github.com/Dgirto/Gmail-IMAP-SMTP.git#subdirectory=lib
```

Python 3.10+. **Sin dependencias externas** — usa solo la librería
estándar (`imaplib`, `smtplib`, `email`).

## Obtener credenciales (el cliente lo hace solo, sin ayuda técnica)

1. El cliente debe tener **verificación en 2 pasos activada** en su cuenta
   de Google. Si no la tiene, actívala en
   [myaccount.google.com/security](https://myaccount.google.com/security).
2. Ir a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Crear una nueva contraseña de aplicación (nombre sugerido: "Ruvic").
4. Google genera una clave de 16 caracteres — copiarla tal cual (con o sin
   espacios, ambos formatos funcionan).
5. Pegar el correo y esa clave en el formulario del conector en Ruvic.

No hay paso de administrador, no hay Google Cloud Console, no hay
pantalla de consentimiento OAuth — es autoservicio completo para el
cliente.

## Variables de entorno (`RUVIC_GMAIL_IMAP_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_GMAIL_IMAP_EMAIL` | Sí | Correo de Gmail del buzón |
| `RUVIC_GMAIL_IMAP_APP_PASSWORD` | Sí | Contraseña de aplicación (16 caracteres) |
| `RUVIC_GMAIL_IMAP_REQUEST_TIMEOUT` | No (default `30`) | Timeout de conexión en segundos |

## Pruebas locales

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_GMAIL_IMAP_EMAIL=tu_correo@gmail.com
export RUVIC_GMAIL_IMAP_APP_PASSWORD="xxxx xxxx xxxx xxxx"

python test_connection.py
python validate_local.py
```

`validate_local.py` envía dos correos de prueba reales (uno con adjunto)
al propio buzón configurado — no requiere un buzón de destino externo.

Prueba también los casos de error (contraseña incorrecta, contraseña
normal de la cuenta en vez de una App Password, sin 2FA activado) y
verifica que los mensajes sean claros.

## Notas de integración

- **Sin OAuth2, sin Google Cloud**: a diferencia de CON-005, este
  conector no requiere que Ruvic tenga un flujo de callback OAuth
  construido en la plataforma — el `manifest.json` con dos campos de
  texto estáticos (`email`, `app_password`) es suficiente. Esa es la
  razón principal de tenerlo como alternativa.
- **Prerrequisito ineludible**: Gmail exige verificación en 2 pasos
  activada para poder generar Contraseñas de aplicación. Si el cliente no
  tiene 2FA, este método no está disponible para él — solo le queda la
  opción OAuth2 (CON-005).
- **Servidores fijos**: `imap.gmail.com:993` (IMAP) y
  `smtp.gmail.com:465` (SMTP, con SSL implícito). No configurables — este
  conector es específico para Gmail.
- **Remitente fijo**: todos los correos se envían desde
  `RUVIC_GMAIL_IMAP_EMAIL`; el conector no permite suplantar otro
  remitente.
- **Búsqueda con sintaxis de Gmail**: `list_messages` usa la extensión
  IMAP `X-GM-RAW` de Gmail, que acepta la misma sintaxis de búsqueda que
  la interfaz web (`is:unread`, `from:`, `subject:`, etc.) — a diferencia
  del `SEARCH` estándar de IMAP, mucho más limitado.
- **Límite de adjuntos**: 20 MB por archivo.
- **Revocación**: si la Contraseña de aplicación se compromete, se
  elimina desde [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
  y se genera una nueva — no afecta la contraseña principal de la cuenta.
- Los errores de autenticación IMAP/SMTP se clasifican como
  `ImapSmtpAuthError`; errores de red/TLS como `ImapSmtpNetworkError`;
  datos inválidos (adjunto inexistente, mensaje no encontrado) como
  `ImapSmtpDataError`.
