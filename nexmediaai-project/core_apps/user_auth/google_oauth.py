import requests
import secrets
from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect
from django.urls import reverse
from .models import User
import logging

logger = logging.getLogger(__name__)

class GoogleOAuth2Client:
    def __init__(self):
        self.client_id = settings.GOOGLE_OAUTH2_CONFIG['client_id']
        self.client_secret = settings.GOOGLE_OAUTH2_CONFIG['client_secret']
        self.redirect_uri = settings.GOOGLE_OAUTH2_CONFIG['redirect_uri']
        self.scope = settings.GOOGLE_OAUTH2_CONFIG['scope']
        
    def get_authorization_url(self, state=None, next_url=None):
        """Get Google OAuth2 authorization URL"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': self.scope,
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'select_account',
        }
        if state:
            params['state'] = state
        if next_url:
            params['state'] = next_url  # Use state parameter to pass next URL
            
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        return f'https://accounts.google.com/o/oauth2/v2/auth?{query_string}'
    
    def get_access_token(self, code):
        """Exchange authorization code for access token"""
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get access token: {response.text}")
            return None
    
    def get_user_info(self, access_token):
        """Get user information from Google"""
        user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(user_info_url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get user info: {response.text}")
            return None

def handle_google_oauth_callback(request):
    """Handle Google OAuth2 callback"""
    try:
        code = request.GET.get('code')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"Google OAuth error: {error}")
            return redirect('login')
        
        if not code:
            logger.error("No authorization code received")
            return redirect('login')
        
        # Get access token
        client = GoogleOAuth2Client()
        token_data = client.get_access_token(code)
        
        if not token_data:
            logger.error("Failed to get access token")
            return redirect('login')
        
        # Get user info
        user_info = client.get_user_info(token_data['access_token'])
        
        if not user_info:
            logger.error("Failed to get user info")
            return redirect('login')
        
        # Get or create user
        email = user_info.get('email')
        if not email:
            logger.error("No email in user info")
            return redirect('login')
        
        try:
            user = User.objects.get(email=email)
            # Update user info if needed
            if not user.is_verified:
                user.is_verified = True
                user.is_active = True
            if not user.image and user_info.get('picture'):
                user.image = user_info['picture']
            user.save()
            logger.info(f"Existing user logged in via Google: {email}")
        except User.DoesNotExist:
            # Create new user with a random password for OAuth users
            random_password = secrets.token_urlsafe(32)
            user = User.objects.create_user(
                email=email,
                username=user_info.get('given_name', email.split('@')[0]),
                country='Unknown',  # You might want to get this from user or set default
                password=random_password,  # Set a random password for OAuth users
                is_verified=True,
                is_active=True,
                image=user_info.get('picture', ''),
            )
            logger.info(f"New user created via Google: {email}")
        
        # Log in user with specific backend
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        logger.info(f"User successfully logged in: {email}")
        
        # Always redirect to home page after login (ignore next parameter)
        return redirect('home:home')
        
    except Exception as e:
        logger.error(f"Error in Google OAuth callback: {str(e)}")
        return redirect('login')
