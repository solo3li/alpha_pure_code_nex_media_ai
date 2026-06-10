import hashlib
import time
import secrets
from django.conf import settings

def generate_signature(data):
    """Generate HMAC signature for the given data."""
    return hashlib.sha256((data + settings.SIGNING_SECRET).encode()).hexdigest()

def validate_signature(data, signature):
    """Validate HMAC signature."""
    expected_signature = generate_signature(data)
    return secrets.compare_digest(expected_signature, signature)

def generate_nonce():
    """Generate a unique nonce."""
    return secrets.token_hex(16)

def get_timestamp():
    """Get current timestamp."""
    return str(int(time.time()))