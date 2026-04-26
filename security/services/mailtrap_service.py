# services/mailtrap_service.py
import requests
from django.conf import settings


def check_mailtrap_suppression(email: str):
    url = f"https://mailtrap.io/api/accounts/{settings.MAILTRAP_ACCOUNT_ID}/suppressions"

    headers = {
        "Authorization": f"Bearer {settings.EMAIL_HOST_PASSWORD}",
        "Content-Type": "application/json",
    }

    params = {
        "email": email
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        suppressions = response.json()

        if suppressions:
            suppression = suppressions[0]
            if suppression.get("type", "").lower() == "hard bounce":
                return suppression

        return None

    except requests.RequestException as e:
        print(f"Error consultando Mailtrap: {e}")
        return None