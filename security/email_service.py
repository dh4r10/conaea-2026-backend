# security/email_service.py

import qrcode
import io
import mailtrap as mt
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from participant.models import PartnerUniversity
from django.core.mail import EmailMultiAlternatives
from email.mime.image import MIMEImage


def get_sender_address():
    """Obtiene la dirección del remitente desde settings."""
    return mt.Address(
        email=settings.DEFAULT_FROM_EMAIL,
        name=settings.EMAIL_SENDER_NAME,
    )

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
    <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:40px 0;">
        <tr>
          <td align="center">
            <table width="600" cellpadding="0" cellspacing="0"
              style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

              <!-- Header -->
              <tr>
                <td style="background:#111111;padding:32px 40px;text-align:center;">
                  <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:3px;
                    text-transform:uppercase;color:#fbba0e;">
                    XXXII CONAEA · Tarapoto 2026
                  </p>
                  <h1 style="margin:0;font-size:26px;font-weight:900;color:#ffffff;">
                    ¡Bienvenido al congreso!
                  </h1>
                </td>
              </tr>

              <!-- Saludo -->
              <tr>
                <td style="padding:32px 40px 0;">
                  <p style="margin:0;font-size:15px;color:#333;">
                    Hola, <strong>{full_name}</strong>
                  </p>
                  <p style="margin:12px 0 0;font-size:14px;color:#666;line-height:1.6;">
                    Tu participación ha sido <strong style="color:#16a34a;">validada exitosamente</strong>
                    en el XXXII Congreso Nacional de Estudiantes de Agronomía.
                    A continuación encontrarás tus datos de acceso y tu código QR personal.
                  </p>
                </td>
              </tr>

              <!-- Datos -->
              <tr>
                <td style="padding:24px 40px 0;">
                  <table width="100%" cellpadding="0" cellspacing="0"
                    style="background:#f9f9f9;border-radius:10px;border:1px solid #e5e5e5;overflow:hidden;">
                    <tr style="background:#fbba0e;">
                      <td colspan="2" style="padding:12px 20px;">
                        <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:2px;
                          text-transform:uppercase;color:#111;">
                          Datos del participante
                        </p>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:12px 20px;font-size:13px;color:#888;width:40%;
                        border-bottom:1px solid #eee;">
                        UUID de registro
                      </td>
                      <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
                        border-bottom:1px solid #eee;font-family:monospace;">
                        {qr_data['uuid']}
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:12px 20px;font-size:13px;color:#888;
                        border-bottom:1px solid #eee;">
                        Tipo de documento
                      </td>
                      <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
                        border-bottom:1px solid #eee;">
                        {participant.document_type}
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:12px 20px;font-size:13px;color:#888;
                        border-bottom:1px solid #eee;">
                        Número de documento
                      </td>
                      <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
                        border-bottom:1px solid #eee;">
                        {participant.identity_document}
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:12px 20px;font-size:13px;color:#888;
                        border-bottom:1px solid #eee;">
                        Nombre completo
                      </td>
                      <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
                        border-bottom:1px solid #eee;">
                        {full_name}
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:12px 20px;font-size:13px;color:#888;">
                        Universidad
                      </td>
                      <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;">
                        {university_name}
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <!-- QR -->
              <tr>
                <td style="padding:32px 40px;text-align:center;">
                  <p style="margin:0 0 16px;font-size:13px;color:#888;">
                    Presenta este código QR el día del evento para tu registro de ingreso.
                  </p>
                  <img
                    src="cid:qr_code"
                    alt="Código QR"
                    width="200"
                    height="200"
                    style="border-radius:8px;border:4px solid #fbba0e;"
                  />
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="background:#111111;padding:24px 40px;text-align:center;">
                  <p style="margin:0;font-size:11px;color:#555;letter-spacing:1px;">
                    XXXII CONAEA · Tarapoto 2026 · Sistema de Gestión
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    # html_content = f"""
    # <!DOCTYPE html>
    # <html lang="es">
    # <body style="font-family: Arial, sans-serif; text-align: center;">
    #     <h2>¡Bienvenido al CONAEA 2026!</h2>
    #     <p>Hola <strong>{full_name}</strong>,</p>
    #     <p>Presenta este código QR el día del evento para tu registro de ingreso.</p>
    #     <img src="cid:qr_code" alt="Código QR" width="200" height="200"
    #          style="border-radius:8px;border:4px solid #fbba0e;" />
    # </body>
    # </html>
    # """

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

    email.send(fail_silently=False)

# html_body = f"""
    # <!DOCTYPE html>
    # <html lang="es">
    # <head>
    #   <meta charset="UTF-8" />
    #   <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    # </head>
    # <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
    #   <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:40px 0;">
    #     <tr>
    #       <td align="center">
    #         <table width="600" cellpadding="0" cellspacing="0"
    #           style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">

    #           <!-- Header -->
    #           <tr>
    #             <td style="background:#111111;padding:32px 40px;text-align:center;">
    #               <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:3px;
    #                 text-transform:uppercase;color:#fbba0e;">
    #                 XXXII CONAEA · Tarapoto 2026
    #               </p>
    #               <h1 style="margin:0;font-size:26px;font-weight:900;color:#ffffff;">
    #                 ¡Bienvenido al congreso!
    #               </h1>
    #             </td>
    #           </tr>

    #           <!-- Saludo -->
    #           <tr>
    #             <td style="padding:32px 40px 0;">
    #               <p style="margin:0;font-size:15px;color:#333;">
    #                 Hola, <strong>{full_name}</strong>
    #               </p>
    #               <p style="margin:12px 0 0;font-size:14px;color:#666;line-height:1.6;">
    #                 Tu participación ha sido <strong style="color:#16a34a;">validada exitosamente</strong>
    #                 en el XXXII Congreso Nacional de Estudiantes de Agronomía.
    #                 A continuación encontrarás tus datos de acceso y tu código QR personal.
    #               </p>
    #             </td>
    #           </tr>

    #           <!-- Datos -->
    #           <tr>
    #             <td style="padding:24px 40px 0;">
    #               <table width="100%" cellpadding="0" cellspacing="0"
    #                 style="background:#f9f9f9;border-radius:10px;border:1px solid #e5e5e5;overflow:hidden;">
    #                 <tr style="background:#fbba0e;">
    #                   <td colspan="2" style="padding:12px 20px;">
    #                     <p style="margin:0;font-size:11px;font-weight:700;letter-spacing:2px;
    #                       text-transform:uppercase;color:#111;">
    #                       Datos del participante
    #                     </p>
    #                   </td>
    #                 </tr>
    #                 <tr>
    #                   <td style="padding:12px 20px;font-size:13px;color:#888;width:40%;
    #                     border-bottom:1px solid #eee;">
    #                     UUID de registro
    #                   </td>
    #                   <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
    #                     border-bottom:1px solid #eee;font-family:monospace;">
    #                     {qr_data['uuid']}
    #                   </td>
    #                 </tr>
    #                 <tr>
    #                   <td style="padding:12px 20px;font-size:13px;color:#888;
    #                     border-bottom:1px solid #eee;">
    #                     Tipo de documento
    #                   </td>
    #                   <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
    #                     border-bottom:1px solid #eee;">
    #                     {participant.document_type}
    #                   </td>
    #                 </tr>
    #                 <tr>
    #                   <td style="padding:12px 20px;font-size:13px;color:#888;
    #                     border-bottom:1px solid #eee;">
    #                     Número de documento
    #                   </td>
    #                   <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
    #                     border-bottom:1px solid #eee;">
    #                     {participant.identity_document}
    #                   </td>
    #                 </tr>
    #                 <tr>
    #                   <td style="padding:12px 20px;font-size:13px;color:#888;
    #                     border-bottom:1px solid #eee;">
    #                     Nombre completo
    #                   </td>
    #                   <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;
    #                     border-bottom:1px solid #eee;">
    #                     {full_name}
    #                   </td>
    #                 </tr>
    #                 <tr>
    #                   <td style="padding:12px 20px;font-size:13px;color:#888;">
    #                     Universidad
    #                   </td>
    #                   <td style="padding:12px 20px;font-size:13px;color:#111;font-weight:600;">
    #                     {university_name}
    #                   </td>
    #                 </tr>
    #               </table>
    #             </td>
    #           </tr>

    #           <!-- QR -->
    #           <tr>
    #             <td style="padding:32px 40px;text-align:center;">
    #               <p style="margin:0 0 16px;font-size:13px;color:#888;">
    #                 Presenta este código QR el día del evento para tu registro de ingreso.
    #               </p>
    #               <img
    #                 src="data:image/png;base64,{qr_base64}"
    #                 alt="Código QR"
    #                 width="200"
    #                 height="200"
    #                 style="border-radius:8px;border:4px solid #fbba0e;"
    #               />
    #             </td>
    #           </tr>

    #           <!-- Footer -->
    #           <tr>
    #             <td style="background:#111111;padding:24px 40px;text-align:center;">
    #               <p style="margin:0;font-size:11px;color:#555;letter-spacing:1px;">
    #                 XXXII CONAEA · Tarapoto 2026 · Sistema de Gestión
    #               </p>
    #             </td>
    #           </tr>

    #         </table>
    #       </td>
    #     </tr>
    #   </table>
    # </body>
    # </html>
    # """