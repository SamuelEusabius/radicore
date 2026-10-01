"""
Celery configuration for the School MS project.

Scheduled tasks:
    - send_daily_fee_reminders   (8:00 AM daily)
    - run_smart_scan             (6:00 AM daily — Smart Alerts fraud detection)

To run Celery locally:
    Terminal 1:  celery -A config worker -l info
    Terminal 2:  celery -A config beat -l info
    Terminal 3:  python manage.py runserver
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Create the Celery app
app = Celery('school_ms')

# Read config from Django settings, using the `CELERY_` prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


# ==========================================================
# PERIODIC TASKS (Celery Beat)
# ==========================================================

app.conf.beat_schedule = {
    # Daily fee reminders — every morning at 8:00 AM
    'send-fee-reminders-daily': {
        'task': 'apps.notifications.tasks.send_daily_fee_reminders',
        'schedule': crontab(hour=8, minute=0),
    },

    # Smart Alerts scan — every morning at 6:00 AM
    'run-smart-scan-daily': {
        'task': 'apps.notifications.tasks.run_smart_scan',
        'schedule': crontab(hour=6, minute=0),
    },
}


# ==========================================================
# OPTIONAL — Debug task
# ==========================================================

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Simple test task — used to verify Celery worker is running."""
    print(f'Celery worker is alive. Request: {self.request!r}')