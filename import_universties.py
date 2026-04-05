import os
import django
import pandas as pd
import string
import random

# ==============================
# 🔹 CONFIGURA ESTO
# ==============================
DJANGO_SETTINGS = 'congress.settings'  # ⚠️ cambia esto
EXCEL_PATH = 'universidades.xlsx'    # ⚠️ ruta a tu archivo

# ==============================
# 🔹 SETUP DJANGO
# ==============================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DJANGO_SETTINGS)
django.setup()

from participant.models import PartnerUniversity
from register.models import QuotaType


# ==============================
# 🔹 GENERADOR DE CÓDIGO
# ==============================
def generate_partner_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits = ''.join(random.choices(string.digits, k=3))
    return letters + digits


def get_unique_code():
    while True:
        code = generate_partner_code()
        if not PartnerUniversity.objects.filter(code=code).exists():
            return code


# ==============================
# 🔹 MAIN
# ==============================
def main():
    print("📥 Leyendo Excel...")

    df = pd.read_excel(EXCEL_PATH)

    # limpiar columnas (por si hay espacios)
    df.columns = df.columns.str.strip()

    inserted = 0
    skipped = 0

    for index, row in df.iterrows():
        try:
            name = str(row.get('universidad', '')).strip()

            # 🔹 saltar filas vacías
            if not name or name.lower() == 'nan':
                continue

            abbreviation = str(row.get('Abreviación', '')).strip()
            country = str(row.get('pais', '')).strip()
            city = str(row.get('ciudad', '')).strip()
            region = str(row.get('region', '')).strip()
            quota_code = row.get('cod_cupo')

            # 🔹 validar quota
            if pd.isna(quota_code):
                print(f"⚠️ Fila {index}: sin cod_cupo")
                skipped += 1
                continue

            try:
                quota_type = QuotaType.objects.get(id=int(quota_code))
            except QuotaType.DoesNotExist:
                print(f"❌ Fila {index}: QuotaType {quota_code} no existe")
                skipped += 1
                continue

            # 🔹 evitar duplicados
            if PartnerUniversity.objects.filter(name=name).exists():
                print(f"⚠️ Ya existe: {name}")
                skipped += 1
                continue

            # 🔹 crear registro
            university = PartnerUniversity.objects.create(
                code=get_unique_code(),
                quota_type=quota_type,
                name=name,
                abbreviation=abbreviation,
                place=city,
                country=country,
                region=region
            )

            print(f"✅ Insertado: {university.name} ({university.code})")
            inserted += 1

        except Exception as e:
            print(f"❌ Error en fila {index}: {e}")
            skipped += 1

    print("\n📊 RESUMEN")
    print(f"✔ Insertados: {inserted}")
    print(f"⚠️ Omitidos: {skipped}")


if __name__ == "__main__":
    main()