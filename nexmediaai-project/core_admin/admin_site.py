from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from core_apps.subscriptions.models import Payment
from core_apps.subscriptions.models import Subscription
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class CustomAdminSite(AdminSite):
    site_header = "NexMediaAI Admin"
    site_title = "NexMediaAI Admin Portal"
    index_title = "Dashboard"
    
    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff
    def index(self, request, extra_context=None):
        # Stats
        total_payments = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
        recent_payments = Payment.objects.select_related('user').order_by('-created_at')[:5]
        latest_users = User.objects.order_by('-created_at')[:5]
        active_subscriptions = Subscription.objects.filter(status='active').count()

        context = {
            'total_payments': total_payments,
            'recent_payments': recent_payments,
            'latest_users': latest_users,
            'active_subscriptions': active_subscriptions,
        }

        if extra_context:
            context.update(extra_context)

        return TemplateResponse(request, "admin/custom_index.html", context)


from django.contrib import admin
from core_apps.subscriptions.models import Plan, Subscription, Payment

custom_admin_site = CustomAdminSite(name='custom_admin')

custom_admin_site.register(Plan)
custom_admin_site.register(Subscription)
custom_admin_site.register(Payment)
custom_admin_site.register(User)
