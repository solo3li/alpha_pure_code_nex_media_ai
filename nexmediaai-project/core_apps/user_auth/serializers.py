# core_apps/user_auth/serializers.py

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
import requests
User = get_user_model()

class CustomRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=True)
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    # recaptcha_token = serializers.CharField(write_only=True, required=True)

    def validate_email(self, email):
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(_("This email is already in use."))
        return email

    def validate_username(self, username):
        # We're not enforcing unique usernames
        return username

    # def validate_recaptcha_token(self, token):
    #     """Verify reCAPTCHA token with Google"""
    #     try:
    #         response = requests.post(
    #             'https://www.google.com/recaptcha/api/siteverify',
    #             data={
    #                 'secret': settings.RECAPTCHA_PRIVATE_KEY,
    #                 'response': token
    #             },
    #             timeout=10
    #         )
    #         result = response.json()
            
    #         if not result.get('success'):
    #             raise serializers.ValidationError(_("Invalid reCAPTCHA. Please try again."))
            
    #         # For reCAPTCHA v3, check the score
    #         if 'score' in result:
    #             score = result.get('score', 0)
    #             required_score = getattr(settings, 'RECAPTCHA_REQUIRED_SCORE', 0.5)
    #             if score < required_score:
    #                 raise serializers.ValidationError(
    #                     _("reCAPTCHA verification failed. Please try again.")
    #                 )
            
    #         return token
    #     except requests.RequestException:
    #         raise serializers.ValidationError(_("Could not verify reCAPTCHA. Please try again."))

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(_("The two password fields didn't match."))
        return data

    def create(self, validated_data):
        # Remove recaptcha_token before creating user
        validated_data.pop('recaptcha_token', None)
        
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data.get('username', ''),
            country=validated_data['country'],
            password=validated_data['password1'],
            is_active=False  # User needs to verify email first
        )
        return user
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'country', 'is_verified', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']
