# plan_tools/models.py

from django.db import models
from core_apps.subscriptions.models import Plan
from core_apps.tools.models import Tool

class PlanTool(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='plantool_set')
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='plantool_set')
    max_trials = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.plan.name} - {self.tool.name}"
