# celery.py
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alx_travel_app.settings")

# Create a Celery application instance
app = Celery("alx_travel_app")

# Load task modules from all registered Django app configs.
# This will automatically discover tasks in the 'tasks.py' files of each app.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()