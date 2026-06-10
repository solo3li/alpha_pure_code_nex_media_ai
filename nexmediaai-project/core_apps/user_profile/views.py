# views.py

import os
import cloudinary
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from core_apps.subscriptions.models import Subscription
User = get_user_model()

@login_required
def profile_view(request):
    user = request.user

    subscription = (
        Subscription.objects
        .filter(user=user, status='Active', end_date__gte=timezone.now())
        .select_related('plan')
        .order_by('-end_date')
        .first()
    )

    plan_name = subscription.plan.name if subscription else 'Free'
    request.session['plan_name'] = plan_name

    # Subscription date details
    sub_start = subscription.start_date if subscription else None
    sub_end   = subscription.end_date   if subscription else None
    days_left = None
    elapsed_pct = 0
    if sub_end:
        from django.utils.timezone import now as tz_now
        delta = sub_end - timezone.now().date()
        days_left = max(delta.days, 0)
        if subscription and subscription.plan.duration_days:
            elapsed = subscription.plan.duration_days - days_left
            elapsed_pct = max(0, min(100, round((elapsed / subscription.plan.duration_days) * 100)))


    # Tool usage per tool (use display names from home.utils)
    from core_apps.tools.models import ToolUsage
    from core_apps.home.utils import get_tool_display_name
    tool_usages = (
        ToolUsage.objects
        .filter(user=user)
        .select_related('tool')
        .order_by('tool__name')
    )
    tool_usage_data = []
    for tu in tool_usages:
        pct = 0
        if tu.max_trials > 0:
            pct = round((tu.usage_count / tu.max_trials) * 100)
        tool_usage_data.append({
            'name':        _(get_tool_display_name(tu.tool.name)),
            'used':        tu.usage_count,
            'max':         tu.max_trials,
            'percentage':  pct,
        })

    if user.image and user.image.startswith('http'):
        image_url = user.image
    else:
        image_url = settings.STATIC_URL + '/img/avatar.jpg'

    return render(request, 'user_profile/profile.html', {
        'username':         user.username,
        'email':            user.email,
        'is_verified':      user.is_verified,
        'profile_image_path': image_url,
        'plan_name':        plan_name,
        'subscribed':       subscription is not None,
        'sub_start':        sub_start,
        'sub_end':          sub_end,
        'days_left':        days_left,
        'elapsed_pct':      elapsed_pct,
        'tool_usage_data':  tool_usage_data,
    })




import cloudinary
import cloudinary.uploader
from urllib.parse import urlparse

@login_required
def upload_profile_image(request):
    if request.method == 'POST':
        file = request.FILES.get('profile_image')
        if not file:
            messages.error(request, 'No file selected')
            return redirect('profile')

        user = request.user

        # Step 1: Delete old Cloudinary image if exists and is from Cloudinary
        if user.image and 'res.cloudinary.com' in user.image:
            try:
                # Extract public_id from URL
                path = urlparse(user.image).path  # e.g. /v1234567890/profile_pics/123.jpg
                public_id = "/".join(path.split('/')[-2:])  # profile_pics/123.jpg
                public_id = public_id.rsplit('.', 1)[0]     # profile_pics/123

                cloudinary.uploader.destroy(public_id)
            except Exception as e:
                print(f"Failed to delete old Cloudinary image: {e}")

        try:
            # Step 2: Upload new image
            result = cloudinary.uploader.upload(
                file,
                folder="profile_pics",
                public_id=str(user.id),
                overwrite=True
            )
            image_url = result.get("secure_url")

            # Step 3: Save new Cloudinary URL to user
            user.image = image_url
            user.save()

            messages.success(request, 'Profile image uploaded successfully.')
        except Exception as e:
            messages.error(request, f'Cloudinary upload failed: {e}')

    return redirect('profile')


@login_required
def serve_profile_image(request, user_id):
    if str(request.user.id) != str(user_id):
        raise Http404()

    user = get_object_or_404(User, id=user_id)
    if user.image:
        file_path = os.path.join(settings.MEDIA_ROOT, user.image.name)
        if os.path.isfile(file_path):
            return FileResponse(open(file_path, 'rb'), content_type='image/jpeg')
    raise Http404()

from django.contrib.auth import logout

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')  # Adjust this to your login page URL name
