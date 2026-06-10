# bg_remover/tasks.py
from celery import shared_task
import requests
from django.conf import settings

@shared_task
def call_flask_bg_removal(filename, user_id):
    response = requests.post(
        f"{settings.FLASK_BG_REMOVER_URL}/process",
        json={'filename': filename},
        headers={
            'X-User-ID': str(user_id),
            'X-Api-Key': settings.FLASK_SERVICE_API_KEY
        },
        timeout=700
    )
    response.raise_for_status()
    return response.json()
