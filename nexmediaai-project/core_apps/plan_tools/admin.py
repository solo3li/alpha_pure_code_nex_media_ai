from django.contrib import admin
from .models import PlanTool

@admin.register(PlanTool)
class PlanToolAdmin(admin.ModelAdmin):
    list_display = ('plan', 'tool', 'max_trials')
