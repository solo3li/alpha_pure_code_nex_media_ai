import os
from django.utils import timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden, Http404, FileResponse
from django.conf import settings
# from django.utils.timezone import now
from django.contrib.auth import get_user_model
from core_apps.subscriptions.models import Subscription, Plan
from core_apps.plan_tools.models import PlanTool
from core_apps.tools.models import Tool
from rest_framework.response import Response
from rest_framework import status
from .serializers import PlanSerializer
from core_apps.user_auth.models import PhoneNumber
User = get_user_model()

def home_view(request):
    if request.user.is_authenticated:
        print("User is authenticated")
        user = request.user

        try:
            # Determine username
            username = user.username
            if not username or username.lower() == "guest":
                username = user.email.split('@')[0]  # Fallback to email prefix

            # Get active subscription
            subscription = (
                Subscription.objects
                .filter(user=user, status='Active', end_date__gte=timezone.now())
                .order_by('-end_date')
                .first()
            )

            subscribed = subscription is not None
            plan_name = subscription.plan.name if subscribed else "Free"
            end_date = subscription.end_date if subscribed else None

            # Handle profile image
            if user.image and str(user.image).startswith('http'):
                profile_image_path = user.image
            elif user.image:
                profile_image_path = f'/profile/image/{user.id}/'
            else:
                profile_image_path = 'static/img/avatar.jpg'

            # Check if user has phone number
            has_phone_number = hasattr(user, 'phone_number') and user.phone_number is not None

            context = {
                'username': username,
                'email': user.email,
                'profile_image_path': profile_image_path,
                'subscribed': subscribed,
                'plan_name': plan_name,
                'end_date': end_date,
                'has_phone_number': has_phone_number,  # Add this to context
            }

            print(f"Context: {context}")
            return render(request, 'home/home.html', context)

        except Exception as e:
            return render(request, 'home/home.html', {
                'username': 'Guest',
                'error': str(e),
                'profile_image_path': 'static/img/avatar.jpg',
                'subscribed': False,
                'has_phone_number': False,
            })
    else:
        return render(request, 'home/home.html', {
            'username': 'Guest',
            'profile_image_path': 'static/img/avatar.jpg',
            'subscribed': False,
            'has_phone_number': False,
        })

def guest_home_view(request):
    return render(request, 'home/home.html', {'username': 'Guest', 'profile_image_path': 'static/img/avatar.jpg', 'subscribed': False})

from rest_framework.permissions import AllowAny

 
 
from rest_framework.views import APIView
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

import re
import phonenumbers
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings

@csrf_exempt 
@require_POST
def add_phone_number(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'User not authenticated'})
    
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        terms_accepted = data.get('terms_accepted')  # ✅ new field

        # ✅ Check agreement before proceeding
        if terms_accepted is not True:
            return JsonResponse({'success': False, 'error': 'You must agree to the terms and conditions before proceeding.'})
        
        if not phone_number:
            return JsonResponse({'success': False, 'error': 'Phone number is required'})
        
        # Validate phone number format for any country
        try:
            parsed_number = phonenumbers.parse(phone_number, None)
        except phonenumbers.NumberParseException:
            return JsonResponse({'success': False, 'error': 'Invalid phone number format'})
        
        if not phonenumbers.is_valid_number(parsed_number):
            return JsonResponse({'success': False, 'error': 'Invalid phone number'})
        
        formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        
        # Check if phone number already exists for another user
        if PhoneNumber.objects.filter(phone_number=formatted_number).exclude(user=request.user).exists():
            return JsonResponse({'success': False, 'error': 'This phone number is already registered with another account'})
        
        # Create or update phone number record
        phone_obj, created = PhoneNumber.objects.get_or_create(
            user=request.user,
            defaults={
                'phone_number': formatted_number,
                'terms_accepted': True,
                'terms_accepted_at': timezone.now()
            }
        )
        
        if not created:
            phone_obj.phone_number = formatted_number
            phone_obj.terms_accepted = True
            phone_obj.terms_accepted_at = timezone.now()
            phone_obj.created_at = request.user.created_at  # Preserve original creation date
            phone_obj.save()
        
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

class PlansAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Use the correct related name 'plan_tool_associations' instead of 'plantool_set'
            plans = Plan.objects.prefetch_related('plantool_set__tool').all()

            monthly_plans = plans.filter(duration_days=30)
            yearly_plans = plans.filter(duration_days=365)

            response_data = {
                'monthly_plans': PlanSerializer(monthly_plans, many=True, context={'request': request}).data,
                'yearly_plans': PlanSerializer(yearly_plans, many=True, context={'request': request}).data
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import uuid
def serve_profile_image(request, user_id):
    if not request.user.is_authenticated or request.user.id != user_id:
        return HttpResponseForbidden("Unauthorized")

    try:
        user = User.objects.get(id=user_id)
        image_path = user.image.path if user.image else None

        if image_path and image_path.startswith('http'):
            return redirect(image_path)  # Redirect to external image

        if image_path and os.path.isfile(image_path):
            return FileResponse(open(image_path, 'rb'), content_type='image/jpeg')

    except User.DoesNotExist:
        raise Http404("User not found")

    raise Http404("Image not found")


def terms_view(request):
    return render(request, 'home/terms.html')


@require_POST
def contact_view(request):
    """Receive contact form POST (JSON) and send email to support@nexmediaai.com

    Expects JSON: { email: string, message: string }
    Returns JsonResponse { success: True } or { success: False, error: '...' }
    """
    try:
        # parse JSON body
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            # fallback to POST form data
            data = request.POST.dict()

        email = (data.get('email') or '').strip()
        message = (data.get('message') or '').strip()

        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required'}, status=400)
        if not message:
            return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)

        subject = f"Website Contact Form - {email}"
        body = f"Message from: {email}\n\n{message}\n\nUser IP: {request.META.get('REMOTE_ADDR')}"

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or email

        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=['support@nexmediaai.com'],
            fail_silently=False,
        )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
