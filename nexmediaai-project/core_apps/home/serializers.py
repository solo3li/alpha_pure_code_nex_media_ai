# core_apps/home/serializers.py

from rest_framework import serializers
from django.utils.translation import gettext as _
from core_apps.subscriptions.models import Plan
from core_apps.plan_tools.models import PlanTool
from core_apps.home.utils import get_tool_display_name, get_tool_unit

class PlanToolSerializer(serializers.ModelSerializer):
    tool_name = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()

    class Meta:
        model = PlanTool
        fields = ['tool_name', 'max_trials', 'unit']

    def get_tool_name(self, obj):
        return _(get_tool_display_name(obj.tool.name))

    def get_unit(self, obj):
        return _(get_tool_unit(obj.tool.name))

class PlanSerializer(serializers.ModelSerializer):
    tools = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ['id', 'name', 'display_name', 'duration_days', 'price_usd', 'price_egp', 'tools']

    def get_display_name(self, obj):
        return _(obj.name)

    def get_tools(self, obj):
        tools = obj.plantool_set.all()
        return PlanToolSerializer(tools, many=True, context=self.context).data
