# in a signals.py file
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from core_apps.subscriptions.models import Plan
from core_apps.plan_tools.models import PlanTool
from core_apps.tools.models import ToolUsage

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when user is created"""
    if created:
        # You can add any additional user setup here
        pass

@receiver(post_save, sender=User)
def initialize_user_tool_usage(sender, instance, created, **kwargs):
    """Initialize user tool usage from free plan when user is verified"""
    # Check if this is an update (not creation) and the user just got verified
    if not created and instance.is_verified:
        # Check if user already has tool usage records to avoid duplicates
        if not ToolUsage.objects.filter(user=instance).exists():
            try:
                # Get the free plan (assuming it's named 'Free' or has a specific identifier)
                free_plan = Plan.objects.get(name__iexact='free')  # Adjust this based on your free plan name
                
                # Get all tools available in the free plan
                plan_tools = PlanTool.objects.filter(plan=free_plan)
                
                # Create ToolUsage records for each tool in the free plan
                tool_usages = []
                for plan_tool in plan_tools:
                    tool_usage = ToolUsage(
                        user=instance,
                        tool=plan_tool.tool,
                        usage_count=0,
                        max_trials=plan_tool.max_trials
                    )
                    tool_usages.append(tool_usage)
                
                # Bulk create all tool usages for efficiency
                if tool_usages:
                    ToolUsage.objects.bulk_create(tool_usages)
                    print(f"Initialized {len(tool_usages)} tool usages for user {instance.email}")
                    
            except Plan.DoesNotExist:
                print("Free plan not found. Please create a free plan first.")
            except Exception as e:
                print(f"Error initializing tool usage for user {instance.email}: {str(e)}")

@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Handle user login events"""
    # You can add any login-related logic here
    pass