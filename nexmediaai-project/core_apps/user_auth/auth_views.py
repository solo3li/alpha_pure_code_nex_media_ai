# views.py (in your core_apps.user_auth app)

from django.shortcuts import render, redirect
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth import login
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class CustomPasswordResetView(PasswordResetView):
    template_name = 'auth/password_reset.html'
    email_template_name = 'auth/password_reset_email.html'
    subject_template_name = 'auth/password_reset_email_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    form_class = PasswordResetForm
    
    def form_valid(self, form):
        form.save(
            domain_override="nexmediaai.com",
            use_https=True,
            request=self.request,
            subject_template_name=self.subject_template_name,
            email_template_name=self.email_template_name,
        )
        messages.success(self.request, 'Password reset email has been sent to your email address.')
        return redirect(self.success_url)

class CustomPasswordResetDoneView(TemplateView):
    template_name = 'auth/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'auth/password_reset_confirm.html'
    form_class = SetPasswordForm
    success_url = reverse_lazy('password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, 'Your password has been reset successfully.')
        return super().form_valid(form)

class CustomPasswordResetCompleteView(TemplateView):
    template_name = 'auth/password_reset_complete.html'

class CustomEmailConfirmView(TemplateView):
    template_name = 'auth/email_confirm.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['key'] = self.kwargs.get('key')
        return context

class CustomEmailConfirmationSentView(TemplateView):
    template_name = 'auth/email_confirmation_sent.html'