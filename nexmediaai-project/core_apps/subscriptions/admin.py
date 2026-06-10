from django.contrib import admin
from .models import Plan, Subscription, Payment

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_days', 'price_usd', 'price_egp', 'created_at')
    search_fields = ('name',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__email', 'plan__name')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription', 'payment_id', 'amount', 'currency', 'method', 'status', 'created_at', 'plan')
    list_filter = ('status', 'method')
    search_fields = ('payment_id', 'user__email')


 
