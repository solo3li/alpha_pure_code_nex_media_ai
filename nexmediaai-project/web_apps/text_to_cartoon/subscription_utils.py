# backend/utils/subscription_utils.py
import json
from datetime import date, datetime
from core_apps.tools.models import Tool, ToolUsage, User
from core_apps.plan_tools.models import Plan
from core_apps.subscriptions.models import Subscription 
 
def has_active_subscription(user_id):
    return Subscription.objects.filter(
        user_id=user_id,
        status='Active',
        start_date__lte=date.today(),
        end_date__gte=date.today()
    ).exists()

def is_trial_available(user_id, tool_name):
    tool = Tool.objects.filter(name=tool_name).first()
    if not tool:
        return False, {"status": "error", "message": "Tool not found"}

    usage = ToolUsage.objects.filter(user_id=user_id, tool_id=tool.id).first()
    if not usage:
        return True, 0

    return usage.max_trials > 0, usage.max_trials

def increment_tool_usage(user_id, tool_name):
    tool = Tool.objects.filter(name=tool_name).first()
    if not tool:
        return {"status": "error", "message": "Tool not found"}

    usage = ToolUsage.objects.filter(user_id=user_id, tool_id=tool.id).first()
    if usage and usage.max_trials > 0:
        usage.usage_count += 1
        usage.max_trials -= 1
        usage.last_used = datetime.utcnow()
        usage.save()
        return {"status": "success", "message": "Usage updated successfully"}
    return {"status": "error", "message": "No remaining trials or record not found"}

def get_trials_left(user_id, tool_name="text-to-cartoon"):
    tool = Tool.objects.filter(name=tool_name).first()
    if not tool:
        return {"status": "error", "message": "Tool not found"}

    usage = ToolUsage.objects.filter(user_id=user_id, tool_id=tool.id).first()
    if not usage:
        user = User.objects.filter(id=user_id).first()
        if not user:
            return {"status": "error", "message": "User not found"}

        plan = Plan.objects.filter(id=user.plan_id).first()
        if not plan:
            return {"status": "error", "message": "Plan not found"}

        trials_per_tool = json.loads(plan.trials_per_tool)
        max_trials = trials_per_tool.get(tool_name, 0)

        ToolUsage.objects.create(
            user_id=user_id,
            tool_id=tool.id,
            usage_count=0,
            max_trials=max_trials
        )
        return max_trials

    return usage.max_trials
