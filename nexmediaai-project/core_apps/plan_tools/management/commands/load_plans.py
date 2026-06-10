import json
from django.core.management.base import BaseCommand
from core_apps.plan_tools.models import PlanTool
from core_apps.tools.models import Tool
from core_apps.subscriptions.models import Plan


class Command(BaseCommand):
    help = 'Load plans and tools into the database'

    def handle(self, *args, **options):
        data = {
            "monthly_plans": [
                {
                    "duration_days": 30,
                    "id": 1,
                    "name": "Free",
                    "price_egp": "0.00",
                    "price_usd": "0.00",
                    "tools": [
                        {"max_trials": 5, "tool_name": "bg-remover", "unit": "photo"},
                        {"max_trials": 2, "tool_name": "make-my-trip", "unit": "Trip"},
                        {"max_trials": 500, "tool_name": "text-to-voice", "unit": "character"},
                        {"max_trials": 300, "tool_name": "video-caption", "unit": "minutes"},
                        {"max_trials": 300, "tool_name": "voice-to-text", "unit": "minutes"},
                        {"max_trials": 5, "tool_name": "text-to-cartoon", "unit": "prompt"},
                        {"max_trials": 60, "tool_name": "video-bg-remover", "unit": "seconds"},
                        {"max_trials": 500, "tool_name": "GPT-3.5", "unit": "Words"},
                        {"max_trials": 0, "tool_name": "GPT-4o", "unit": "Words"}
                    ]
                },
                {
                    "duration_days": 30,
                    "id": 2,
                    "name": "Pro",
                    "price_egp": "649.00",
                    "price_usd": "14.99",
                    "tools": [
                        {"max_trials": 10000, "tool_name": "GPT-4o", "unit": "Words"},
                        {"max_trials": 30000, "tool_name": "GPT-3.5", "unit": "Words"},
                        {"max_trials": 50, "tool_name": "bg-remover", "unit": "photo"},
                        {"max_trials": 100, "tool_name": "img-to-txt", "unit": "image"},
                        {"max_trials": 10, "tool_name": "make-my-trip", "unit": "Trip"},
                        {"max_trials": 15000, "tool_name": "text-to-voice", "unit": "character"},
                        {"max_trials": 90, "tool_name": "video-caption", "unit": "minutes"},
                        {"max_trials": 180, "tool_name": "voice-to-text", "unit": "minutes"},
                        {"max_trials": 20, "tool_name": "text-to-cartoon", "unit": "prompt"},
                        {"max_trials": 300, "tool_name": "video-bg-remover", "unit": "seconds"}
                    ]
                },
                {
                    "duration_days": 30,
                    "id": 3,
                    "name": "ProPlus",
                    "price_egp": "859.00",
                    "price_usd": "19.99",
                    "tools": [
                        {"max_trials": 20000, "tool_name": "GPT-4o", "unit": "Words"},
                        {"max_trials": 40000, "tool_name": "GPT-3.5", "unit": "Words"},
                        {"max_trials": 100, "tool_name": "bg-remover", "unit": "photo"},
                        {"max_trials": 200, "tool_name": "img-to-txt", "unit": "image"},
                        {"max_trials": 20, "tool_name": "make-my-trip", "unit": "Trip"},
                        {"max_trials": 20000, "tool_name": "text-to-voice", "unit": "character"},
                        {"max_trials": 120, "tool_name": "video-caption", "unit": "minutes"},
                        {"max_trials": 240, "tool_name": "voice-to-text", "unit": "minutes"},
                        {"max_trials": 40, "tool_name": "text-to-cartoon", "unit": "prompt"},
                        {"max_trials": 500, "tool_name": "video-bg-remover", "unit": "seconds"}
                    ]
                }
            ],
            "yearly_plans": [
                {
                    "duration_days": 365,
                    "id": 4,
                    "name": "Basic Annual",
                    "price_egp": "5199.00",
                    "price_usd": "119.99",
                    "tools": [
                        {"max_trials": 120000, "tool_name": "GPT-4o", "unit": "Words"},
                        {"max_trials": 360000, "tool_name": "GPT-3.5", "unit": "Words"},
                        {"max_trials": 600, "tool_name": "bg-remover", "unit": "photo"},
                        {"max_trials": 1200, "tool_name": "img-to-txt", "unit": "image"},
                        {"max_trials": 120, "tool_name": "make-my-trip", "unit": "Trip"},
                        {"max_trials": 180000, "tool_name": "text-to-voice", "unit": "character"},
                        {"max_trials": 1080, "tool_name": "video-caption", "unit": "minutes"},
                        {"max_trials": 2160, "tool_name": "voice-to-text", "unit": "minutes"},
                        {"max_trials": 240, "tool_name": "text-to-cartoon", "unit": "prompt"},
                        {"max_trials": 3600, "tool_name": "video-bg-remover", "unit": "seconds"}
                    ]
                },
                {
                    "duration_days": 365,
                    "id": 5,
                    "name": "Pro Annual",
                    "price_egp": "6999.00",
                    "price_usd": "149.99",
                    "tools": [
                        {"max_trials": 240000, "tool_name": "GPT-4o", "unit": "Words"},
                        {"max_trials": 480000, "tool_name": "GPT-3.5", "unit": "Words"},
                        {"max_trials": 1200, "tool_name": "bg-remover", "unit": "photo"},
                        {"max_trials": 2400, "tool_name": "img-to-txt", "unit": "image"},
                        {"max_trials": 240, "tool_name": "make-my-trip", "unit": "Trip"},
                        {"max_trials": 240000, "tool_name": "text-to-voice", "unit": "character"},
                        {"max_trials": 1440, "tool_name": "video-caption", "unit": "minutes"},
                        {"max_trials": 2880, "tool_name": "voice-to-text", "unit": "minutes"},
                        {"max_trials": 480, "tool_name": "text-to-cartoon", "unit": "prompt"},
                        {"max_trials": 6000, "tool_name": "video-bg-remover", "unit": "seconds"}
                    ]
                }
            ]
        }

        for plan_data in data['monthly_plans'] + data['yearly_plans']:
            plan = Plan.objects.create(
                id=plan_data['id'],
                name=plan_data['name'],
                duration_days=plan_data['duration_days'],
                price_egp=plan_data['price_egp'],
                price_usd=plan_data['price_usd']
            )

            for tool_data in plan_data['tools']:
                tool, _ = Tool.objects.get_or_create(name=tool_data['tool_name'])
                PlanTool.objects.create(plan=plan, tool=tool, max_trials=tool_data['max_trials'])

        self.stdout.write(self.style.SUCCESS('Successfully loaded plans and tools into the database!'))
