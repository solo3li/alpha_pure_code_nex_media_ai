from django.db import transaction
from .models import Plan
from core_apps.plan_tools.models import PlanTool
from core_apps.tools.models import ToolUsage


from datetime import datetime

def initialize_tool_usage(user_id, plan_name):
    """
    Initialize or update the tool_usage table with trial limits for a user based on the selected plan.
    :param user_id: ID of the user
    :param plan_name: Name of the plan to fetch trial limits
    :return: Dict containing the status and message
    """
    try:
        with transaction.atomic():  # Django's equivalent of SQLAlchemy's transaction
            # Fetch the plan details using the plan name
            try:
                plan = Plan.objects.get(name=plan_name)
            except Plan.DoesNotExist:
                return {"status": "error", "message": "Plan not found"}

            # Fetch all tools associated with the plan from the plan_tools table
            plan_tools = PlanTool.objects.filter(plan_id=plan.id)
            if not plan_tools.exists():
                return {"status": "error", "message": "No tools found for the plan"}

            for plan_tool in plan_tools:
                # Check if the row exists in tool_usage
                tool_usage, created = ToolUsage.objects.get_or_create(
                    user_id=user_id,
                    tool_id=plan_tool.tool_id,
                    defaults={
                        'usage_count': 0,
                        'max_trials': plan_tool.max_trials
                    }
                )

                if not created:
                    # Increment max_trials for the existing row
                    tool_usage.max_trials += plan_tool.max_trials
                    tool_usage.save()

            return {"status": "success", "message": "Tool usage initialized or updated successfully"}

    except Exception as ex:
        return {"status": "error", "message": f"Unexpected error: {str(ex)}"}