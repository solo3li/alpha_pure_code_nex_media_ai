from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core_apps.subscriptions"

    def ready(self):
        import core_apps.subscriptions.signals 