import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("nexmedia")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
 
app.conf.update(
    task_time_limit=3600,  # 60 minutes hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit (gives time to cleanup)
    worker_prefetch_multiplier=1,  # Process one task at a time for long-running tasks
)