import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'congress.settings')
django.setup()

from register.models import IndividualCup, PreSale
from participant.models import PartnerUniversity

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'universities_production.json'), encoding='utf-8') as f:
    data = json.load(f)

pre_sale = PreSale.objects.get(pk=1)
created, skipped = 0, []

for entry in data:
    code = entry['code']
    currency = entry['total_inscritos']

    try:
        university = PartnerUniversity.objects.get(code=code)
    except PartnerUniversity.DoesNotExist:
        skipped.append(code)
        continue

    IndividualCup.objects.create(
        pre_sale=pre_sale,
        partner_university=university,
        currency=currency,
        is_active=True,
    )
    created += 1
    print(f"  + {code}  partner_university_id={university.pk}  currency={currency}")

print(f"\nInsertados: {created}")
if skipped:
    print(f"Sin match en partner_universities: {skipped}")
