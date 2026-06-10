import random
import string
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import EmailVerification


def generate_otp(length=6) -> str:
    otp = "".join(random.choices(string.digits, k=length))
    print(f"Generated OTP: {otp}")
    return otp

def send_verification_email(user):
    """Send email verification to user"""
    print(f"Starting email verification for user: {user.email}")
    
    # Debug Django settings
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"EMAIL_BACKEND: {getattr(settings, 'EMAIL_BACKEND', 'Not set')}")
    print(f"EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
    print(f"EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
    print(f"EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
    print(f"EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'Not set')}")
    
    verification = EmailVerification.create_verification(user)
    print(f"Created verification record with token: {verification.token}")
    
    # Build verification URL
    verification_url = f"{settings.BASE_URL}accounts/confirm-email/{verification.token}/"
    print(f"Verification URL: {verification_url}")
    
    # Email context
    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': getattr(settings, 'SITE_NAME', 'NexMedia AI'),
    }
    
    # Render email templates
    html_message = render_to_string('auth/email_verification.html', context)
    plain_message = strip_tags(html_message)
    subject = f'Verify your email address - {context["site_name"]}'
    
    print(f"Email subject: {subject}")
    print(f"Recipient: {user.email}")
    print(f"From email: {settings.DEFAULT_FROM_EMAIL}")
    print(f"Plain message length: {len(plain_message)}")
    print(f"HTML message length: {len(html_message)}")
    
    # Send email
    try:
        result = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"send_mail() returned: {result}")
        print("Email sent successfully (Django reported success)")
        
        # Check if it's going to console/terminal (for development)
        if getattr(settings, 'EMAIL_BACKEND', '').endswith('ConsoleEmailBackend'):
            print("NOTE: Using ConsoleEmailBackend - emails are printed to console, not actually sent!")
        elif getattr(settings, 'EMAIL_BACKEND', '').endswith('LocmemEmailBackend'):
            print("NOTE: Using LocmemEmailBackend - emails are stored in memory, not actually sent!")
            
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None
    
    return verification

def verify_email_token(token):
    """Verify email token and activate user"""
    print(f"Verifying token: {token}")
    
    try:
        verification = EmailVerification.objects.get(token=token, is_used=False)
        print(f"Found verification record for user: {verification.user.email}")
        
        if verification.is_expired():
            print("Token has expired")
            return False, "Verification link has expired. Please request a new one."
        
        print("Token is valid, activating user...")
        
        # Activate user
        user = verification.user
        user.is_active = True
        user.is_verified = True
        user.save()
        
        print(f"User {user.email} activated and verified successfully")
        
        # Mark verification as used
        verification.is_used = True
        verification.save()
        
        print("Verification record marked as used")
        
        return True, user
        
    except EmailVerification.DoesNotExist:
        print("Invalid token - no matching verification record found")
        return False, "Invalid verification link."
    except Exception as e:
        print(f"Unexpected error during verification: {e}")
        return False, "An error occurred during verification."