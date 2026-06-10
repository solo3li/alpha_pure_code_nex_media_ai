# tools/models.py

from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

class Tool(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ToolUsageSummary(models.Model):
    tool = models.OneToOneField(Tool, on_delete=models.CASCADE, related_name='usage_summary')
    total_usage = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.tool.name} summary"

class ToolUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tool_usages')
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='tool_usages')
    usage_count = models.IntegerField(default=0)
    max_trials = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.tool.name} usage"

class ToolUsageHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tool_usage_histories')
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE, related_name='tool_usage_histories')
    processed_date = models.DateTimeField(auto_now_add=True)
    additional_data_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.tool.name} history"
