from datetime import date, datetime
from django.db.models import F
from core_apps.subscriptions.models import Subscription
from core_apps.tools.models import Tool, ToolUsage
import logging

logger = logging.getLogger(__name__)

class ToolUsageManager:
    @staticmethod
    def _get_default_trials(tool_name):
        """Returns default trials for each tool if not specified in DB."""
        defaults = {
            "voice-to-text": 300,
            "text-to-voice": 10000,
            "video-caption": 300,
            "video-bg-remover": 180,
            "v-bg-remover": 180,
            "bg-remover": 5,
            "make-my-trip": 5,
            "GPT-3.5": 10000,
            "GPT-4o": 5000,
            "text-to-cartoon": 5,
            "img-to-txt": 5,
        }
        return defaults.get(tool_name, 300)

    @staticmethod
    def has_active_subscription(user):
        """Check if user currently has an active, non-expired subscription."""
        if not user.is_authenticated:
            return False
            
        return Subscription.objects.filter(
            user=user,
            status='Active',
            start_date__lte=date.today(),
            end_date__gte=date.today()
        ).exists()

    @staticmethod
    def had_subscription_before(user):
        """Check if user has ever had a subscription in the past."""
        if not user.is_authenticated:
            return False
        return Subscription.objects.filter(user=user).exists()

    @staticmethod
    def get_trials_left(user, tool_name):
        """
        Get remaining trials for a tool.
        - If subscription ended: trials = 0.
        - If free tier (no sub before): return current DB trials or default.
        - If active sub: return current DB trials.
        """
        if not user.is_authenticated:
            return 0
            
        try:
            tool = Tool.objects.get(name=tool_name)
        except Tool.DoesNotExist:
            logger.error(f"Tool {tool_name} not found")
            return 0

        # Check subscription status
        is_active = ToolUsageManager.has_active_subscription(user)
        had_sub = ToolUsageManager.had_subscription_before(user)

        # If they had a subscription but it's not active anymore, their trials go to 0
        if had_sub and not is_active:
            # Optionally sync DB to 0
            ToolUsage.objects.filter(user=user, tool=tool).update(max_trials=0)
            return 0

        # For free tier or active sub, get from DB
        usage = ToolUsage.objects.filter(user=user, tool=tool).first()
        if usage:
            return usage.max_trials
        
        # If no DB entry yet, return default
        return ToolUsageManager._get_default_trials(tool_name)

    @staticmethod
    def is_trial_available(user, tool_name, amount=1):
        """Check if user has enough trials to perform an action of size `amount`."""
        trials_left = ToolUsageManager.get_trials_left(user, tool_name)
        return trials_left >= amount

    @staticmethod
    def decrement_trials(user, tool_name, amount=1):
        """
        Decrement the trials by amount.
        If the user has 0 trials due to expired sub, this won't decrement below 0.
        """
        if not user.is_authenticated:
            return False

        # If they aren't allowed because sub expired, don't decrement, just return False
        if not ToolUsageManager.is_trial_available(user, tool_name, amount):
            return False

        try:
            tool = Tool.objects.get(name=tool_name)
            usage, created = ToolUsage.objects.get_or_create(
                user=user,
                tool=tool,
                defaults={'max_trials': ToolUsageManager._get_default_trials(tool_name)}
            )
            
            usage.max_trials = max(0, usage.max_trials - amount)
            usage.usage_count += amount
            usage.last_used = datetime.now()
            usage.save()
            return True
        except Exception as e:
            logger.error(f"Error decrementing usage for {tool_name}: {e}")
            return False

    @staticmethod
    def has_valid_subscription_or_trial(user, tool_name, amount=1):
        """
        Combined check: is trial available according to our unified logic?
        """
        return ToolUsageManager.is_trial_available(user, tool_name, amount)
