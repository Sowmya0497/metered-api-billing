"""
Monthly invoice generation job.
For each customer, sum uninvoiced UsageWindows for the prior month,
apply tiered pricing, create Invoice + InvoiceLineItems.

Run on the 2nd of each month (gives 26hr grace for late events).

Concurrency-safe: unique_together on Invoice(customer, period_start, period_end)
plus get_or_create means two concurrent runs can't produce duplicate invoices.
"""
import logging
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from dateutil.relativedelta import relativedelta
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone

from customers.models import Customer
from usage.models import UsageWindow
from invoices.models import Invoice, InvoiceLineItem, compute_invoice_cents

logger = logging.getLogger(__name__)


def run(period_start=None, period_end=None):
    now = timezone.now()

    if period_start is None:
        period_start = (now.replace(day=1) - relativedelta(months=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if period_end is None:
        period_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    logger.info('[generate_invoices] period %s → %s', period_start.date(), period_end.date())

    for customer in Customer.objects.all():
        windows = UsageWindow.objects.filter(
            customer=customer,
            window_start__gte=period_start,
            window_start__lt=period_end,
            is_invoiced=False,
        )
        total_units = windows.aggregate(t=Sum('total_units'))['t'] or 0

        if total_units == 0:
            continue  # no activity this period, skip

        amount_cents = compute_invoice_cents(total_units)

        try:
            with transaction.atomic():
                # get_or_create is atomic against the unique_together constraint.
                # If two workers race here:
                #   - Worker A: INSERT succeeds, created=True
                #   - Worker B: INSERT fails with IntegrityError → caught below
                # No duplicate invoice is possible.
                invoice, created = Invoice.objects.get_or_create(
                    customer=customer,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        'total_cents': amount_cents,
                        'status': 'ISSUED',
                        'issued_at': now,
                    },
                )

                if not created:
                    logger.info('  skip %s: invoice already exists', customer.name)
                    continue

                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f'API usage {period_start.date()} – {period_end.date()}',
                    units=total_units,
                    unit_price_micro_cents=0,
                    amount_cents=amount_cents,
                )

                # Freeze windows so the aggregator does not overwrite them
                windows.update(is_invoiced=True)

                logger.info(
                    '  invoiced %s: %d units → %d cents',
                    customer.name, total_units, amount_cents,
                )

        except IntegrityError:
            # Two workers hit the exact same microsecond — one wins, one lands here.
            # The invoice was already created by the other worker. Safe to skip.
            logger.warning(
                '  IntegrityError for %s — invoice already created by concurrent worker',
                customer.name,
            )

    logger.info('[generate_invoices] done')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()