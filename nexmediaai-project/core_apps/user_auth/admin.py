from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, PhoneNumber, EmailVerification
from core_apps.tools.models import ToolUsage
from core_apps.subscriptions.models import Payment, Subscription


class PhoneNumberInline(admin.StackedInline):
    model = PhoneNumber
    can_delete = False
    verbose_name_plural = 'Phone Number'
    fk_name = 'user'
    extra = 0


class ToolUsageInline(admin.TabularInline):
    """Inline to show and edit a user's tool usages from the User admin."""
    model = ToolUsage
    fk_name = 'user'
    extra = 0
    fields = ('tool', 'usage_count', 'max_trials', 'last_used')
    readonly_fields = ('last_used', 'usage_count',)
    verbose_name = 'Tool Usage'
    verbose_name_plural = 'Tool Usages'


class PaymentInline(admin.TabularInline):
    """Inline to show and add payments from the User admin."""
    model = Payment
    fk_name = 'user'
    extra = 1  # Shows one empty form to add new payment
    fields = ('plan', 'payment_id', 'amount', 'currency', 'method', 'status', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = 'Payment'
    verbose_name_plural = 'Payments'
    
    # Optionally show most recent payments first
    ordering = ('-created_at',)
    
    # Custom CSS to control column widths
    class Media:
        css = {
            'all': ('admin/css/custom_payment_inline.css',)
        }
    
    # If you want to limit the number of payments shown
    # max_num = 10


class SubscriptionInline(admin.TabularInline):
    """Inline to show user's subscriptions from the User admin."""
    model = Subscription
    fk_name = 'user'
    extra = 0
    fields = ('plan', 'start_date', 'end_date', 'status', 'created_at')
    readonly_fields = ('created_at',)
    verbose_name = 'Subscription'
    verbose_name_plural = 'Subscriptions'
    ordering = ('-created_at',)


@admin.action(description="Mark selected users as verified")
def mark_as_verified(modeladmin, request, queryset):
    queryset.update(is_verified=True)


@admin.action(description="Mark selected users as unverified")
def mark_as_unverified(modeladmin, request, queryset):
    queryset.update(is_verified=False)


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('email', 'username', 'country', 'is_verified', 'is_staff', 'is_active', 'created_at')
    list_filter = ('is_staff', 'is_active', 'is_verified', 'country')
    
    # Add PaymentInline and SubscriptionInline to show payments and subscriptions
    inlines = [PhoneNumberInline, ToolUsageInline, SubscriptionInline, PaymentInline]

    fieldsets = (
        (None, {'fields': ('email', 'username', 'country', 'password', 'image')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'is_verified', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('last_login', 'created_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'country', 
                'password1', 'password2', 
                'is_staff', 'is_active', 'is_verified'
            )}
        ),
    )
    search_fields = ('email', 'username', 'country')
    ordering = ('-created_at',)

    actions = [mark_as_verified, mark_as_unverified]
    readonly_fields = ('created_at', 'last_login')


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    model = PhoneNumber
    
    list_display = (
        'phone_number', 
        'user', 
        'country', 
        'username', 
        'email', 
        'terms_accepted',
        'terms_accepted_at',
        'created_at'
    )
    
    search_fields = ('phone_number', 'username', 'email')
    list_filter = ('country', 'created_at', 'terms_accepted')
    ordering = ('-created_at',)
    readonly_fields = ('terms_accepted', 'terms_accepted_at')


admin.site.register(User, CustomUserAdmin)