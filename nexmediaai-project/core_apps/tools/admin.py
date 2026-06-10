from django.contrib import admin
from .models import Tool, ToolUsage, ToolUsageSummary, ToolUsageHistory

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)

@admin.register(ToolUsage)
class ToolUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'tool', 'usage_count', 'max_trials', 'last_used')
    search_fields = ('user__email', 'tool__name')

@admin.register(ToolUsageSummary)
class ToolUsageSummaryAdmin(admin.ModelAdmin):
    list_display = ('tool', 'total_usage')

@admin.register(ToolUsageHistory)
class ToolUsageHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'tool', 'processed_date', 'additional_data_id')
