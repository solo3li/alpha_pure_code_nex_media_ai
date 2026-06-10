import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, username=None, country=None, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field is required')
        email = self.normalize_email(email)
        # Generate a unique username if not provided
        user = self.model(email=email, username=username, country=country, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username=None, country=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, username, country, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)  # Email remains unique
    username = models.CharField(max_length=255, unique=False) 
    country = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    image = models.URLField(max_length=500, null=True, blank=True) # media/laksjdlkasdnlkjansf.jpg
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'country']

    def __str__(self):
        return self.email

class PhoneNumber(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='phone_number'
    )
    phone_number = models.CharField(max_length=20, unique=True)
    country = models.CharField(max_length=255)  # Copy from user for quick access
    username = models.CharField(max_length=255)  # Copy from user for quick access
    email = models.EmailField()  # Copy from user for quick access
    created_at = models.DateTimeField(default=timezone.now)

    # ✅ New fields for terms agreement
    terms_accepted = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.phone_number} ({self.user.email})"
    
    def save(self, *args, **kwargs):
        # Automatically populate fields from the user model
        self.country = self.user.country
        self.username = self.user.username
        self.email = self.user.email
        super().save(*args, **kwargs)


        
class EmailVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Email verification for {self.user.email}"
    
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        expire_days = getattr(settings, 'EMAIL_VERIFICATION_EXPIRE_DAYS', 3)
        return timezone.now() > self.created_at + timedelta(days=expire_days)
    
    @classmethod
    def create_verification(cls, user):
        # Delete any existing unused verifications for this user
        cls.objects.filter(user=user, is_used=False).delete()
        
        # Create new verification
        token = get_random_string(64)
        return cls.objects.create(user=user, token=token)
    

