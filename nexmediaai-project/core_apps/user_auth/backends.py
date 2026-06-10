from django.contrib.auth import backends
from .models import User

# core_apps/user_auth/backends.py

import logging
logger = logging.getLogger(__name__)

class EmailAuthBackend(backends.ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        logger.info(f"[AUTH BACKEND] Trying to authenticate user with email: {email}")
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                logger.info(f"[AUTH BACKEND] Successful authentication for {email}")
                return user
            else:
                logger.warning(f"[AUTH BACKEND] Password failed for {email}")
        except User.DoesNotExist:
            logger.warning(f"[AUTH BACKEND] No user found with email {email}")
        return None


    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None