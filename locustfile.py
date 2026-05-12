"""
Prueba de estrés para el flujo de inscripción de CONAEA.

Requisitos previos:
    pip install locust

Configuración (editar las constantes de abajo):
    UNIVERSITY_TYPE  → "Referido" o "General"
    CODE             → código de PartnerUniversity (Referido) o DynamicCode (General)

    La BD local debe tener:
      - Una PreSale activa en este momento
      - AvailableSlot con cupos suficientes para la categoría
      - Para Referido: un PartnerUniversity con is_active=True y su code
      - Para General:  un DynamicCode con status='Disponible'
                       (cada código solo sirve para 1 usuario; genera varios en el admin)

Ejecución:
    1. python manage.py runserver          (en otra terminal)
    2. locust -f locustfile.py --host http://localhost:8000
    3. Abrir http://localhost:8089
       → configurar usuarios concurrentes y ramp-up, luego Start

Interpretación:
    - RPS (requests/s) y latencia P95 en la pestaña Charts
    - Las respuestas 400 se marcan como éxito de negocio (sin cupos, duplicado, etc.)
    - Solo los 500 o errores de red cuentan como Failures
"""

import io
import random
import string
import threading

from locust import HttpUser, task, between, events
from PIL import Image


# ── Configuración ─────────────────────────────────────────────────────────────

UNIVERSITY_TYPE = "Referido"   # "Referido" | "General"
CODE            = "XD325"      # Reemplazar con un código válido de tu BD local

# ─────────────────────────────────────────────────────────────────────────────


_counter_lock = threading.Lock()
_counter = 0


def _next_id():
    global _counter
    with _counter_lock:
        _counter += 1
        return _counter


def _make_photo() -> io.BytesIO:
    """Imagen JPEG mínima válida (< 500 KB) generada en memoria."""
    buf = io.BytesIO()
    color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    Image.new("RGB", (200, 200), color=color).save(buf, format="JPEG", quality=60)
    buf.seek(0)
    return buf


def _make_pdf() -> bytes:
    """PDF mínimo válido generado en memoria."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f\n"
        b"0000000009 00000 n\n"
        b"0000000058 00000 n\n"
        b"0000000115 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )


class InscriptionUser(HttpUser):
    """
    Simula un participante que:
      1. Verifica el código de inscripción
      2. Envía el formulario de inscripción con foto (y ficha si es Referido)
    """
    wait_time = between(1, 3)

    @task
    def flujo_inscripcion(self):
        # ── 1. Verificar código ───────────────────────────────────────────────
        with self.client.post(
            "/api/register/verify-code/",
            json={"university_type": UNIVERSITY_TYPE, "code": CODE},
            catch_response=True,
            name="1. POST verify-code",
        ) as resp:
            if resp.status_code not in (200, 201):
                resp.failure(
                    f"verify-code inesperado {resp.status_code}: {resp.text[:200]}"
                )
                return
            resp.success()

        # ── 2. Inscripción ────────────────────────────────────────────────────
        uid = _next_id()
        suffix = ''.join(random.choices(string.digits, k=6))
        dni    = f"{uid:08d}"[:8]          # DNI único de 8 dígitos
        email  = f"load_{uid}_{suffix}@test.conaea.com"

        fields = {
            "university_type": (None, UNIVERSITY_TYPE),
            "code":            (None, CODE),
            "first_name":      (None, "Carga"),
            "paternal_surname":(None, "Test"),
            "maternal_surname":(None, "Locust"),
            "birthdate":       (None, "2000-06-15"),
            "identity_document":(None, dni),
            "document_type":   (None, "DNI"),
            "email":           (None, email),
            "cellphone":       (None, "999000000"),
            "academic_cycle":  (None, "5"),
            "photograph":      ("photo.jpg", _make_photo(), "image/jpeg"),
        }

        if UNIVERSITY_TYPE == "Referido":
            fields["archive"] = ("matricula.pdf", _make_pdf(), "application/pdf")

        with self.client.post(
            "/api/register/inscription/",
            files=fields,
            catch_response=True,
            name="2. POST inscription",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
            elif resp.status_code == 400:
                # Error de negocio (sin cupos, duplicado, código inválido):
                # no es un fallo del servidor, se registra como éxito para
                # no distorsionar las métricas de disponibilidad.
                resp.success()
            else:
                resp.failure(
                    f"inscription falló {resp.status_code}: {resp.text[:300]}"
                )
