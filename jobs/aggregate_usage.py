"""
Background job: roll UsageEvents into hourly UsageWindows.

Run via: python manage.py shell -c "from jobs.aggregate_usage import run; run()"
Or schedule with Celery Beat (see config/celery.py).

Concurrency-safe:
- SELECT FOR UPDATE on the window row prevents double-counting if two
  workers run simultaneously.
- Recomputation from raw events is idempotent: running twice produces
  the same result.

Late-arriving events:
- Events within the lookback window are picked up automatically.
- Events arriving after a window is invoiced are logged as warnings
  and require manual ops reconciliation.
"""
import logging
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncHour
from django.utils import timezone

from usage.models import UsageEvent, UsageWindow

logger = logging.getLogger(__name__)


def truncate_to_hour(dt):
    return dt.replace(minute=0, second=0, microsecond=0)


def run(lookback_hours=2):
    """
    Aggregate events from the last `lookback_hours` into UsageWindows.

    Uses TruncHour instead of raw date_trunc SQL — works on both
    PostgreSQL and SQLite, making local dev and tests consistent.
    """
    now = timezone.now()
    since = truncate_to_hour(now - timedelta(hours=lookback_hours))

    # Find all distinct (customer, hour) pairs in the lookback window.
    # TruncHour works on both PostgreSQL and SQLite.
    pairs = (
        UsageEvent.objects
        .filter(timestamp__gte=since)
        .annotate(hour=TruncHour('timestamp'))
        .values('customer_id', 'hour')
        .distinct()
    )

    windows_created = 0
    windows_updated = 0
    windows_skipped = 0

    for row in pairs:
        cid = row['customer_id']
        window_start = row['hour']

        # Recompute the true total from raw events for this (customer, hour).
        # This is idempotent — running twice gives the same number.
        agg = UsageEvent.objects.filter(
            customer_id=cid,
            timestamp__gte=window_start,
            timestamp__lt=window_start + timedelta(hours=1),
        ).aggregate(
            total=Sum('units_consumed'),
            count=Sum(1),
        )

        total_units = agg['total'] or 0
        event_count = agg['count'] or 0

        with transaction.atomic():
            window, created = UsageWindow.objects.select_for_update().get_or_create(
                customer_id=cid,
                window_start=window_start,
                defaults={
                    'total_units': total_units,
                    'event_count': event_count,
                },
            )

            if created:
                windows_created += 1

            elif not window.is_invoiced:
                # Recompute from source — safe to overwrite
                window.total_units = total_units
                window.event_count = event_count
                window.save()
                windows_updated += 1

            else:
                # Window already invoiced — late event arrived after billing.
                # Do NOT overwrite. Ops must reconcile manually.
                logger.warning(
                    'Late event for customer=%s window=%s (already invoiced). '
                    'Manual reconciliation required.',
                    cid, window_start,
                )
                windows_skipped += 1

    logger.info(
        '[aggregate_usage] done at %s — created=%d updated=%d skipped=%d',
        now.isoformat(), windows_created, windows_updated, windows_skipped,
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()