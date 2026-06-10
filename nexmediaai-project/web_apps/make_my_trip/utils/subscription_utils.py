from datetime import date
import json
from core_apps.tools.models import Tool, ToolUsage
from core_apps.subscriptions.models import Plan, Subscription, User

def increment_tool_usage(user_id, tool_name):
    """
    Increment the usage count for a specific tool
    """
    try:
        tool = Tool.objects.filter(name=tool_name).first()
        if not tool:
            return False

        tool_usage = ToolUsage.objects.filter(user_id=user_id, tool_id=tool.id).first()
        
        if not tool_usage:
            # Create a new tool usage entry
            tool_usage = ToolUsage(
                user_id=user_id,
                tool_id=tool.id,
                usage_count=1,  # This is the first usage
                max_trials=5  # Default max trials
            )
        else:
            # Increment the current trials
            tool_usage.usage_count += 1
            tool_usage.max_trials -= 1  # Decrement the max trials
        
        tool_usage.save()
        return True

    except Exception as e:
        print(f"Error incrementing tool usage: {str(e)}")
        return False

def get_trials_left(user_id, tool_name="make-my-trip"):
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