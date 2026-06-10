from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
import logging

from core_apps.subscriptions.models import Payment, Subscription
from core_apps.plan_tools.models import PlanTool
from core_apps.tools.models import ToolUsage

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def handle_successful_payment(sender, instance, created, **kwargs):
    if instance.status == "Completed" and not instance.subscription:
        user = instance.user
        plan = instance.plan

        # Create Subscription
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            status="Active"
        )

        # Link the new subscription to the payment
        instance.subscription = subscription
        instance.save(update_fields=["subscription"])

        # Send confirmation email to user
        user_email = getattr(user, "email", None)
        send_to_email = getattr(user, "email", None)
        if send_to_email:
            plan_name = getattr(plan, "name", "your plan")
            user_name = getattr(user, "first_name", None) or getattr(user, "username", str(user))
            subject = f"Your {plan_name} subscription is active"
            message = (
                f"Hi Rami,\n\n"
                f"There is a user subscribed '{plan_name}' is active from {start_date} to {end_date}.\n\n"
                f"name of user {user_name} and email {user_email}.\n\n"
                "Thanks,\n"
                "The Team"
            )
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
            try:
                send_mail(subject, message, from_email, [send_to_email], fail_silently=False)
            except Exception as exc:
                logger.exception("Failed to send subscription confirmation to %s: %s", send_to_email, exc)

        # Initialize ToolUsage based on PlanTool
        plan_tools = PlanTool.objects.filter(plan=plan)

        for pt in plan_tools:
            tool_usage, created = ToolUsage.objects.get_or_create(
                user=user,
                tool=pt.tool,
                defaults={
                    "max_trials": pt.max_trials
                }
            )
            if not created:
                tool_usage.max_trials += pt.max_trials
                tool_usage.save(update_fields=["max_trials"])

        