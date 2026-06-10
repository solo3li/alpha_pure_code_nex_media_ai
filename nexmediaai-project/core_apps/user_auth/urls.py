# urls.py (in your main project urls.py)
from django.urls import path, include
from core_apps.user_auth.auth_views import (
    CustomPasswordResetView,
    CustomPasswordResetDoneView, 
    CustomPasswordResetConfirmView,
    CustomPasswordResetCompleteView,
    CustomEmailConfirmView,
    CustomEmailConfirmationSentView
    
)
from django.contrib.auth.views import LogoutView

from .views import *

urlpatterns = [
    # Auth page views
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('accounts/logout/', LogoutView.as_view(), name='logout'),
    
    # Auth API endpoints
    path('auth/login/', custom_login_api, name='api_login'),
    path('auth/register/', custom_register_api, name='api_register'),
    
    # Google OAuth2
    path('accounts/google/login/', google_login_view, name='google_login'),
    path('accounts/google/callback/', google_callback_view, name='google_callback'),
    path('admin/export/phone-numbers/csv/', export_phone_numbers_csv, name='export_phone_numbers_csv'),
    # Custom auth URLs
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Email verification
    path('email-confirmation-sent/', email_verification_sent_view, name='account_email_verification_sent'),
    path('accounts/confirm-email/<str:token>/', email_verification_confirm_view, name='account_confirm_email'),
]