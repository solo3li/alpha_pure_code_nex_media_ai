# subscriptions/models.py

from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

from django.conf import settings
class Plan(models.Model):
    name = models.CharField(max_length=255, unique=True)
    duration_days = models.IntegerField()
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    price_egp = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Subscription(models.Model):
    STATUS_CHOICES = [('Active', 'Active'), ('Expired', 'Expired')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"

class Payment(models.Model):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Manually trigger signal-like behavior
        if obj.status == "Completed" and not obj.subscription:
            from core_apps.subscriptions.signals import handle_successful_payment
            handle_successful_payment(Payment, obj, False)

    METHOD_CHOICES = [
        ('PayPal', 'PayPal'), ('CreditCard', 'Credit Card'), ('Stripe', 'Stripe'),
        ('BankTransfer', 'Bank Transfer'), ('wallet', 'Wallet'), ('card', 'Card')
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'), 
        ('Completed', 'Completed'), 
        ('Refunded', 'Refunded'), 
        ('Failed', 'Failed')
    ]

    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    plan = models.ForeignKey(  
        Plan, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='payments'
    )
    subscription = models.ForeignKey(  
        Subscription, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='payments'
    )
    payment_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, null=True, max_length=300)  # Add this field
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.payment_id} - {self.status} ({self.amount} {self.currency})"