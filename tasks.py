import logging
from config.celery import app

logger = logging.getLogger(__name__)


@app.task(name='billing.tasks.aggregate_usage', bind=True, max_retries=3)
def aggregate_usage(self):
    """Roll raw UsageEvents into hourly UsageWindows."""
    try:
        from jobs.aggregate_usage import run
        run(lookback_hours=2)
    except Exception as exc:
        logger.exception('aggregate_usage task failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@app.task(name='billing.tasks.generate_invoices', bind=True, max_retries=2)
def generate_invoices(self):
    """Generate monthly invoices for all customers."""
    try:
        from jobs.generate_invoices import run
        run()
    except Exception as exc:
        logger.exception('generate_invoices task failed: %s', exc)
        raise self.retry(exc=exc, countdown=300)
