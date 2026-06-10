# context_processors.py

from django.conf import settings

def paypal_settings(request):
    """Make PayPal settings available in templates"""
    return {
        'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
    }
