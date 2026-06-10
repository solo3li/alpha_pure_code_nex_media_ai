# core_apps/user_auth/serializers.py

from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class CustomRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=True)
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_email(self, email):
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(_("This email is already in use."))
        return email

    def validate_username(self, username):
        # We're not enforcing unique usernames
        return username

    def validate(self, data):
        if data['password1'] != data['password2']:
            raise serializers.ValidationError(_("The two password fields didn't match."))
        return data

    def create(self, validated_data):
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
