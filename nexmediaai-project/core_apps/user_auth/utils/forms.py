from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class CustomRegistrationForm(forms.Form):
    username = forms.CharField(max_length=255, required=False)
    email = forms.EmailField(required=True)
    country = forms.CharField(max_length=255, required=True)
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        help_text="Enter the same password as before, for verification.",
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields didn't match.")
        return password2

    def save(self, commit=True):
        # Create user instance
        user = User(
            email=self.cleaned_data['email'],
            country=self.cleaned_data['country'],
            username=self.cleaned_data.get('username') or self.cleaned_data['email'].split('@')[0],
            is_active=False  # User needs to verify email first
        )
        user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()
        return user

class CustomLoginForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-data',
            'placeholder': 'Enter your email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-data',
            'placeholder': 'Enter your password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'

    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if email and password:
            # Try to authenticate with email directly
            user = authenticate(
                self.request, 
                email=email, 
                password=password
            )
            
            if user is None:
                raise forms.ValidationError("Invalid email or password.")
            elif not user.is_active:
                raise forms.ValidationError("Please verify your email address before logging in.")

            self.user_cache = user

        return self.cleaned_data