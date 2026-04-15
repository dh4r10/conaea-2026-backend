# security/email_service.py

import qrcode
import io
import os
import mailtrap as mt
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from participant.models import PartnerUniversity
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage


def get_mailtrap_client():
    if settings.MAILTRAP_ENV == 'sandbox':
        return mt.MailtrapClient(
            token=settings.MAILTRAP_API_TOKEN,
            api_host='sandbox.api.mailtrap.io',  # 👈 endpoint de sandbox
        )
    return mt.MailtrapClient(token=settings.MAILTRAP_API_TOKEN)

def generate_qr_bytes(data: dict) -> bytes:
    """Genera un QR con los datos del participante y lo devuelve como bytes."""
    qr_content = (
        f"UUID: {data['uuid']}\n"
        f"Documento: {data['document_type']}\n"
        f"Número de identidad: {data['identity_document']}\n"
        f"Nombre: {data['full_name']}\n"
        f"Universidad: {data['university_name']}"
    )

    qr = qrcode.QRCode(
        version=None,  # Ajuste automático del tamaño
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)

    img = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)

    return buffer.getvalue()


def send_welcome_email(participant):
    if not participant.email:
        raise ValueError("El participante no tiene un correo electrónico válido.")

    if not participant.registration:
        raise ValueError("El participante no tiene una inscripción válida.")

    full_name = (
        f"{participant.first_name} "
        f"{participant.paternal_surname} "
        f"{participant.maternal_surname}"
    )

    # Obtener el nombre de la universidad por coincidencia de código
    university = PartnerUniversity.objects.filter(
        code=participant.cod_university,
        is_active=True
    ).first()
    university_name = university.name if university else "Universidad no registrada"

    qr_data = {
        'uuid': str(participant.registration.uuid),
        'document_type': participant.document_type,
        'identity_document': participant.identity_document,
        'full_name': full_name,
        'university_name': university_name,
    }

    qr_bytes = generate_qr_bytes(qr_data)

    subject = "¡Bienvenido al XXXII CONAEA Tarapoto 2026!"
    from_email = f"{settings.EMAIL_SENDER_NAME} <{settings.DEFAULT_FROM_EMAIL}>"
    to = [participant.email]

    text_content = (
        f"Hola {full_name},\n\n"
        "Tu participación ha sido validada exitosamente en el "
        "XXXII Congreso Nacional de Estudiantes de Agronomía.\n"
        "Adjunto encontrarás tu código QR para el ingreso al evento."
    )

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background:#f0f0f0;font-family:'Arial',sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f0f0;padding:48px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
          style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.10);">

          <!-- ── TOP ACCENT BAR ── -->
          <tr>
            <td style="background:#fbba0e;height:5px;font-size:0;line-height:0;">&nbsp;</td>
          </tr>

          <!-- ── HEADER ── -->
          <tr>
            <td style="background:#0a1a0f;padding:40px;text-align:center;">
              <p style="margin:0 0 16px;font-size:10px;font-weight:700;letter-spacing:4px;
                text-transform:uppercase;color:#fbba0e;">
                XXXII CONAEA · Tarapoto 2026
              </p>
              <!-- LOGO -->
              <img
                src="cid:logo"
                alt="Logo CONAEA"
                style="display:block;margin:0 auto 20px;max-width:260px;width:100%;height:auto;"
              />
              <h1 style="margin:0 0 6px;font-size:28px;font-weight:900;color:#ffffff;
                letter-spacing:-0.5px;">
                ¡Participación confirmada!
              </h1>
              <p style="margin:0;font-size:13px;color:#888888;">
                31 Agosto — 04 Septiembre · UNSM, Tarapoto
              </p>
            </td>
          </tr>

          <!-- ── SALUDO ── -->
          <tr>
            <td style="padding:40px 40px 0;">
              <p style="margin:0 0 8px;font-size:16px;font-weight:900;color:#111111;">
                Hola, {full_name} 👋
              </p>
              <p style="margin:0;font-size:14px;color:#666666;line-height:1.7;">
                Tu participación en el <strong style="color:#111111;">XXXII Congreso Nacional
                de Estudiantes de Agronomía</strong> ha sido
                <strong style="color:#16a34a;">validada exitosamente</strong>.
                A continuación encontrarás tus datos de acceso y tu código QR personal
                para el ingreso al evento.
              </p>
            </td>
          </tr>

          <!-- ── BADGE TIPO ── -->
          <tr>
            <td style="padding:24px 40px 0;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:999px;
                    padding:6px 16px;">
                    <p style="margin:0;font-size:11px;font-weight:700;color:#16a34a;
                      letter-spacing:1px;text-transform:uppercase;">
                      ✓ &nbsp;Inscripción verificada
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── DATOS DEL PARTICIPANTE ── -->
          <tr>
            <td style="padding:28px 40px 0;">
              <p style="margin:0 0 12px;font-size:10px;font-weight:700;letter-spacing:3px;
                text-transform:uppercase;color:#aaaaaa;">
                Datos del participante
              </p>
              <table width="100%" cellpadding="0" cellspacing="0"
                style="border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">

                <tr style="background:#fafafa;">
                  <td style="padding:14px 20px;font-size:12px;color:#999999;
                    width:42%;border-bottom:1px solid #eeeeee;">
                    N° de registro
                  </td>
                  <td style="padding:14px 20px;font-size:12px;color:#111111;font-weight:700;
                    border-bottom:1px solid #eeeeee;font-family:monospace;letter-spacing:0.5px;">
                    {qr_data['uuid']}
                  </td>
                </tr>

                <tr>
                  <td style="padding:14px 20px;font-size:12px;color:#999999;
                    border-bottom:1px solid #eeeeee;">
                    Tipo de documento
                  </td>
                  <td style="padding:14px 20px;font-size:12px;color:#111111;font-weight:700;
                    border-bottom:1px solid #eeeeee;">
                    {participant.document_type}
                  </td>
                </tr>

                <tr style="background:#fafafa;">
                  <td style="padding:14px 20px;font-size:12px;color:#999999;
                    border-bottom:1px solid #eeeeee;">
                    Número de documento
                  </td>
                  <td style="padding:14px 20px;font-size:12px;color:#111111;font-weight:700;
                    border-bottom:1px solid #eeeeee;">
                    {participant.identity_document}
                  </td>
                </tr>

                <tr>
                  <td style="padding:14px 20px;font-size:12px;color:#999999;
                    border-bottom:1px solid #eeeeee;">
                    Nombre completo
                  </td>
                  <td style="padding:14px 20px;font-size:12px;color:#111111;font-weight:700;
                    border-bottom:1px solid #eeeeee;">
                    {full_name}
                  </td>
                </tr>

                <tr style="background:#fafafa;">
                  <td style="padding:14px 20px;font-size:12px;color:#999999;">
                    Universidad
                  </td>
                  <td style="padding:14px 20px;font-size:12px;color:#111111;font-weight:700;">
                    {university_name}
                  </td>
                </tr>

              </table>
            </td>
          </tr>

          <!-- ── QR ── -->
          <tr>
            <td style="padding:36px 40px;text-align:center;">
              <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:3px;
                text-transform:uppercase;color:#aaaaaa;">
                Tu código de acceso
              </p>
              <p style="margin:0 0 20px;font-size:13px;color:#888888;line-height:1.6;">
                Presenta este QR el día del evento para registrar tu ingreso.
              </p>
              <img
                src="cid:qr_code"
                alt="Código QR de acceso"
                width="200"
                height="200"
                style="border-radius:12px;border:4px solid #fbba0e;display:block;margin:0 auto;"
              />
            </td>
          </tr>

          <!-- ── AVISO ── -->
          <tr>
            <td style="padding:0 40px 36px;">
              <table width="100%" cellpadding="0" cellspacing="0"
                style="background:#fffbeb;border:1px solid #fde68a;border-radius:12px;">
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#92400e;
                      letter-spacing:1px;text-transform:uppercase;">
                      ⚠ &nbsp;Importante
                    </p>
                    <p style="margin:0;font-size:12px;color:#78350f;line-height:1.6;">
                      Este código QR es personal e intransferible. No lo compartas con
                      terceros. En caso de pérdida, contáctanos a través de nuestros
                      canales oficiales.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── DIVIDER ── -->
          <tr>
            <td style="padding:0 40px;">
              <div style="height:1px;background:#eeeeee;"></div>
            </td>
          </tr>

          <!-- ── FOOTER ── -->
          <tr>
            <td style="padding:28px 40px;text-align:center;">
              <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#111111;">
                XXXII CONAEA · Tarapoto 2026
              </p>
              <p style="margin:0;font-size:11px;color:#aaaaaa;line-height:1.6;">
                Este correo fue generado automáticamente. Por favor no respondas a este mensaje.<br/>
                ¿Tienes dudas? Escríbenos al
                <a href="https://wa.me/51918689799" style="color:#16a34a;font-weight:700;
                  text-decoration:none;">
                  918 689 799
                </a>
              </p>
            </td>
          </tr>

          <!-- ── BOTTOM ACCENT BAR ── -->
          <tr>
            <td style="background:#0a1a0f;height:4px;font-size:0;line-height:0;">&nbsp;</td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
"""

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=to,
    )

    email.attach_alternative(html_content, "text/html")

    # Adjuntar la imagen como recurso embebido (CID)
    image = MIMEImage(qr_bytes, _subtype="png")
    image.add_header("Content-ID", "<qr_code>")
    image.add_header("Content-Disposition", "inline", filename="qr.png")
    email.attach(image)

    # ── LOGO ──
    logo_path = os.path.join('media/', 'logo.png')
    with open(logo_path, 'rb') as f:
        logo_img = MIMEImage(f.read(), _subtype='png')
        logo_img.add_header('Content-ID', '<logo>')
        logo_img.add_header('Content-Disposition', 'inline', filename='logo.png')
        email.attach(logo_img)

    email.send(fail_silently=False)
