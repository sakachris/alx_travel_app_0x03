import requests
from django.conf import settings

CHAPA_SECRET_KEY = settings.CHAPA_SECRET_KEY
CHAPA_BASE_URL = "https://api.chapa.co/v1"

def initiate_payment(data):
    url = f"{CHAPA_BASE_URL}/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def verify_payment(transaction_id):
    url = f"{CHAPA_BASE_URL}/transaction/verify/{transaction_id}"
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
    }
    response = requests.get(url, headers=headers)
    return response.json()
