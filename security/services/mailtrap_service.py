# services/mailtrap_service.py
import requests
from django.conf import settings


def check_mailtrap_suppression(email: str):
    """
    Consulta la API de Mailtrap y devuelve el registro de supresión si el email
    está bloqueado por cualquier motivo (hard bounce, unsubscription, spam complaint,
    manual import, etc.). Devuelve None si el email puede recibir correos.
    """
    url = f"https://mailtrap.io/api/accounts/{settings.MAILTRAP_ACCOUNT_ID}/suppressions"

    headers = {
        "Authorization": f"Bearer {settings.EMAIL_HOST_PASSWORD}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, params={"email": email}, timeout=10)
        response.raise_for_status()
        suppressions = response.json()

        if suppressions:
            return suppressions[0]

        return None

    except requests.RequestException as e:
        print(f"Error consultando Mailtrap suppressions: {e}")
        return None