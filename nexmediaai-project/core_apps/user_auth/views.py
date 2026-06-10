from django.shortcuts import render, redirect
from django.middleware.csrf import get_token
from .forms import *
from django.contrib.auth import login, authenticate, get_user_model, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.urls import reverse_lazy
import json
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging
from .email_utils import send_verification_email, verify_email_token
from .google_oauth import GoogleOAuth2Client, handle_google_oauth_callback
from rest_framework.permissions import AllowAny
from rest_framework.decorators import permission_classes
import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from .models import PhoneNumber
from .serializers import CustomRegisterSerializer

# Get the custom User model
User = get_user_model()

# Set up logging to help debug
logger = logging.getLogger(__name__)


class CustomLoginView(DjangoLoginView):
    form_class = CustomLoginForm
    template_name = 'user_auth/login.html'
    success_url = reverse_lazy('home:home')


def staff_required(view_func):
    """Decorator that checks if user is staff, returns 403 if not"""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            return render(request, '403.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@login_required
@staff_required
def export_phone_numbers_csv(request):
    """
    Export PhoneNumber data as CSV file for staff users only
    """
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="phone_numbers_export.csv"'},
    )
    
    writer = csv.writer(response, dialect='excel')
    response.write('\ufeff')
    
    writer.writerow([
        'User ID',
        'Username', 
        'Email',
        'Phone Number',
        'Country',
        'Created At',
        'Phone Record ID'
    ])
    
    phone_numbers = PhoneNumber.objects.all().select_related('user')
    
    for phone in phone_numbers:
        writer.writerow([
            phone.user.id if phone.user else 'N/A',
            phone.username or 'N/A',
            phone.email or 'N/A',
            phone.phone_number or 'N/A',
            phone.country or 'N/A',
            phone.created_at.strftime('%Y-%m-%d %H:%M:%S') if phone.created_at else 'N/A',
            str(phone.id) if phone.id else 'N/A'
        ])
    
    return response


def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home:home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        messages.error(request, f"{field}: {error}")
    else:
        form = CustomLoginForm()
    
    return render(request, 'user_auth/login.html', {'form': form})


def signup_view(request):
    if request.method == 'POST':
        form = CustomRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()
            
            try:
                send_verification_email(user)
                messages.success(request, 'Registration successful! Please check your email to verify your account.')
                return redirect('account_email_verification_sent')
            except Exception as e:
                logger.error(f"Failed to send verification email: {e}")
                messages.error(request, 'Registration successful but failed to send verification email. Please contact support.')
                return redirect('login')
        else:
            # Handle form errors including reCAPTCHA errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    elif field == 'captcha':
                        messages.error(request, f"reCAPTCHA: {error}")
                    else:
                        messages.error(request, f"{field}: {error}")
    else:
        form = CustomRegistrationForm()
    
    return render(request, 'user_auth/signup.html', {'form': form})


def email_verification_sent_view(request):
    return render(request, 'auth/email_confirmation_sent.html')


def email_verification_confirm_view(request, token):
    success, result = verify_email_token(token)
    
    if success:
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('login')
    else:
        messages.error(request, result)
        return redirect('login')


def google_login_view(request):
    """Redirect to Google OAuth2 authorization"""
    client = GoogleOAuth2Client()
    next_url = request.GET.get('next')
    auth_url = client.get_authorization_url(next_url=next_url)
    return redirect(auth_url)


def google_callback_view(request):
    """Handle Google OAuth2 callback"""
    return handle_google_oauth_callback(request)


@api_view(['POST'])
@permission_classes([AllowAny])
def custom_login_api(request):
    """API endpoint for login"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return Response({
                    'message': 'Login successful',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'username': user.username,
                        'is_verified': user.is_verified
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Account is not active. Please verify your email.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Login API error: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def custom_register_api(request):
    """API endpoint for registration with reCAPTCHA"""
    try:
        data = json.loads(request.body)
        serializer = CustomRegisterSerializer(data=data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            try:
                send_verification_email(user)
                return Response({
                    'message': 'Registration successful! Please check your email to verify your account.',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'username': user.username
                    }
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Failed to send verification email: {e}")
                return Response({
                    'message': 'Registration successful but failed to send verification email.',
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'username': user.username
                    }
                }, status=status.HTTP_201_CREATED)
        else:
            errors = {}
            for field, error_list in serializer.errors.items():
                errors[field] = error_list[0] if error_list else 'Invalid data'
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError:
        return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Registration API error: {e}")
        return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')