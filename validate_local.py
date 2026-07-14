"""Validacion local del conector gmail_imap: ejercita las 4 capacidades.

Uso:
    python validate_local.py

Requiere las variables RUVIC_GMAIL_IMAP_* exportadas en el entorno.
"""

import pathlib
import tempfile

from ruvic_gmail_imap_connector import ImapSmtpClient, setup_logging

setup_logging("INFO")
client = ImapSmtpClient()

print("== 1. Listar correos (los 5 mas recientes) ==")
messages = client.list_messages(query="", max_results=5)
for m in messages:
    print(f"  [{m['id']}] {m['from']} - {m['subject']!r} ({m['date']})")

if messages:
    print("== 2. Leer detalle del primer correo ==")
    detail = client.get_message(messages[0]["id"])
    preview = (detail["body_text"] or "")[:200].replace("\n", " ")
    print(f"  De: {detail['from']}")
    print(f"  Asunto: {detail['subject']}")
    print(f"  Cuerpo (preview): {preview!r}")
else:
    print("== 2. Sin correos en la bandeja para leer detalle ==")

print("== 3. Enviar correo de prueba ==")
sent = client.send_message(
    to=client.config.email,
    subject="Prueba conector Gmail IMAP/SMTP Ruvic",
    body_text="Este es un correo de prueba enviado por validate_local.py",
)
print(f"  Enviado: {sent}")

print("== 4. Enviar correo con adjunto ==")
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".txt", delete=False, encoding="utf-8"
) as tmp:
    tmp.write("Archivo de prueba del conector Gmail IMAP/SMTP Ruvic.\n")
    tmp_path = tmp.name

try:
    sent_attach = client.send_message_with_attachment(
        to=client.config.email,
        subject="Prueba conector Gmail IMAP/SMTP Ruvic (con adjunto)",
        body_text="Este correo incluye un adjunto de prueba.",
        attachment_path=tmp_path,
    )
    print(f"  Enviado: {sent_attach}")
finally:
    pathlib.Path(tmp_path).unlink(missing_ok=True)
