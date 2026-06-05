import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('billing')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Roll raw events into hourly windows every 5 minutes.
    # The job is idempotent so running it more often is safe.
    'aggregate-usage-every-5-min': {
        'task': 'billing.tasks.aggregate_usage',
        'schedule': crontab(minute='*/5'),
    },
    # Generate invoices on the 2nd of each month at 02:00 UTC.
    # The 2nd gives a 26-hour grace period for late-arriving events.
    'generate-invoices-monthly': {
        'task': 'billing.tasks.generate_invoices',
        'schedule': crontab(day_of_month='2', hour='2', minute='0'),
    },
}
