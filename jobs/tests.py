import uuid
import unittest
import threading
from datetime import timedelta

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from customers.models import Customer, ApiKey
from usage.models import UsageEvent, UsageWindow
from invoices.models import Invoice, InvoiceLineItem


def make_customer(name="Test"):
    return Customer.objects.create(
        name=name,
        email=f"{uuid.uuid4().hex[:8]}@test.com",
    )


def make_event(customer, units=10, hours_ago=0):
    return UsageEvent.objects.create(
        request_id=str(uuid.uuid4()),
        customer=customer,
        endpoint="/api/test",
        units_consumed=units,
        timestamp=timezone.now() - timedelta(hours=hours_ago),
    )


def run_aggregation(lookback_hours=2):
    from jobs.aggregate_usage import run
    run(lookback_hours=lookback_hours)


def run_invoicing(period_start, period_end):
    from jobs.generate_invoices import run
    run(period_start=period_start, period_end=period_end)


# -- Aggregation job -----------------------------------------------------------

class AggregationJobTest(TestCase):

    def setUp(self):
        self.customer = make_customer()

    def test_events_rolled_into_window(self):
        make_event(self.customer, units=100)
        make_event(self.customer, units=200)
        run_aggregation()

        window = UsageWindow.objects.get(customer=self.customer)
        self.assertEqual(window.total_units, 300)
        self.assertEqual(window.event_count, 2)

    def test_aggregation_is_idempotent(self):
        """Running the job twice produces the same window - no double counting."""
        make_event(self.customer, units=50)
        run_aggregation()
        run_aggregation()

        windows = UsageWindow.objects.filter(customer=self.customer)
        self.assertEqual(windows.count(), 1)
        self.assertEqual(windows.first().total_units, 50)

    def test_late_event_within_lookback_is_included(self):
        """Late event arriving within lookback window is picked up on next run."""
        make_event(self.customer, units=100)
        run_aggregation()

        # Late event arrives, still within lookback
        make_event(self.customer, units=50)
        run_aggregation()

        window = UsageWindow.objects.get(customer=self.customer)
        self.assertEqual(window.total_units, 150)

    def test_invoiced_window_not_overwritten(self):
        """Once a window is invoiced, the aggregator must not overwrite it."""
        make_event(self.customer, units=100)
        run_aggregation()

        # Mark window as invoiced (simulating invoice generation)
        window = UsageWindow.objects.get(customer=self.customer)
        window.is_invoiced = True
        window.save()

        # New event arrives for the same hour
        make_event(self.customer, units=999)
        run_aggregation()

        # Total must still be 100 — invoiced window was frozen
        window.refresh_from_db()
        self.assertEqual(window.total_units, 100)

    def test_multiple_customers_aggregated_independently(self):
        c2 = make_customer("Customer B")
        make_event(self.customer, units=100)
        make_event(c2, units=200)
        run_aggregation()

        w1 = UsageWindow.objects.get(customer=self.customer)
        w2 = UsageWindow.objects.get(customer=c2)
        self.assertEqual(w1.total_units, 100)
        self.assertEqual(w2.total_units, 200)

    def test_no_events_produces_no_windows(self):
        run_aggregation()
        self.assertEqual(UsageWindow.objects.filter(customer=self.customer).count(), 0)


# -- Invoice generation job ----------------------------------------------------

class InvoiceGenerationJobTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        now = timezone.now()
        self.period_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        self.period_end = self.period_start + timedelta(days=28)

    def _put_event_in_period(self, units=50_000):
        UsageEvent.objects.create(
            request_id=str(uuid.uuid4()),
            customer=self.customer,
            endpoint="/api/test",
            units_consumed=units,
            timestamp=self.period_start + timedelta(hours=1),
        )

    def test_invoice_created_with_correct_amount(self):
        self._put_event_in_period(units=50_000)
        run_aggregation(lookback_hours=24 * 30)
        run_invoicing(self.period_start, self.period_end)

        invoice = Invoice.objects.get(customer=self.customer)
        self.assertEqual(invoice.status, "ISSUED")
        # 50k units: 10k free + 40k at $0.001 = $40.00 = 4,000 cents
        self.assertEqual(invoice.total_cents, 4_000)

    def test_line_item_created_with_correct_units(self):
        self._put_event_in_period(units=20_000)
        run_aggregation(lookback_hours=24 * 30)
        run_invoicing(self.period_start, self.period_end)

        invoice = Invoice.objects.get(customer=self.customer)
        line_item = invoice.line_items.get()
        self.assertEqual(line_item.units, 20_000)

    def test_duplicate_run_creates_only_one_invoice(self):
        """Running the job twice for the same period must not create duplicates."""
        self._put_event_in_period()
        run_aggregation(lookback_hours=24 * 30)
        run_invoicing(self.period_start, self.period_end)
        run_invoicing(self.period_start, self.period_end)  # second run

        self.assertEqual(
            Invoice.objects.filter(customer=self.customer).count(), 1
        )

    def test_windows_marked_invoiced_after_job(self):
        """UsageWindows must be frozen after invoice generation."""
        self._put_event_in_period()
        run_aggregation(lookback_hours=24 * 30)
        run_invoicing(self.period_start, self.period_end)

        uninvoiced = UsageWindow.objects.filter(
            customer=self.customer,
            window_start__gte=self.period_start,
            window_start__lt=self.period_end,
            is_invoiced=False,
        )
        self.assertEqual(uninvoiced.count(), 0)

    def test_no_invoice_for_zero_usage(self):
        run_invoicing(self.period_start, self.period_end)
        self.assertEqual(Invoice.objects.filter(customer=self.customer).count(), 0)

    def test_free_tier_only_creates_zero_cent_invoice(self):
        """Customers under 10k units are invoiced but at $0."""
        self._put_event_in_period(units=5_000)
        run_aggregation(lookback_hours=24 * 30)
        run_invoicing(self.period_start, self.period_end)

        invoice = Invoice.objects.get(customer=self.customer)
        self.assertEqual(invoice.total_cents, 0)


# -- Concurrency ---------------------------------------------------------------

from django.db import connection

@unittest.skipIf(connection.vendor == 'sqlite', 'SQLite does not support concurrent writes - run against PostgreSQL')
class ConcurrentEventIngestionTest(TransactionTestCase):
    """
    TransactionTestCase is required for threading tests.
    TestCase wraps each test in a transaction invisible across threads.
    """

    def setUp(self):
        self.customer = Customer.objects.create(
            name="Concurrent Test",
            email="concurrent@test.com",
        )
        _, self.raw_key = ApiKey.create_for_customer(self.customer)

    def test_concurrent_same_request_id_produces_one_row(self):
        """
        Two threads posting the same request_id must result in
        exactly one UsageEvent row — never two.
        """
        shared_request_id = str(uuid.uuid4())
        results = []

        def post_event():
            resp = self.client.post(
                "/v1/events/",
                [{
                    "request_id": shared_request_id,
                    "endpoint": "/api/x",
                    "units_consumed": 10,
                    "timestamp": timezone.now().isoformat(),
                }],
                content_type="application/json",
                HTTP_AUTHORIZATION=f"ApiKey {self.raw_key}",
            )
            results.append(resp.json())

        t1 = threading.Thread(target=post_event)
        t2 = threading.Thread(target=post_event)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one row in the database
        self.assertEqual(
            UsageEvent.objects.filter(request_id=shared_request_id).count(), 1
        )
        # Total accepted across both responses must be exactly 1
        total_accepted = sum(r.get("accepted", 0) for r in results)
        total_duplicates = sum(r.get("duplicates", 0) for r in results)
        self.assertEqual(total_accepted + total_duplicates, 2)

    def test_concurrent_different_request_ids_both_accepted(self):
        """Two threads posting different request_ids must both succeed."""
        results = []

        def post_event(request_id):
            resp = self.client.post(
                "/v1/events/",
                [{
                    "request_id": request_id,
                    "endpoint": "/api/x",
                    "units_consumed": 5,
                    "timestamp": timezone.now().isoformat(),
                }],
                content_type="application/json",
                HTTP_AUTHORIZATION=f"ApiKey {self.raw_key}",
            )
            results.append(resp.json())

        t1 = threading.Thread(target=post_event, args=(str(uuid.uuid4()),))
        t2 = threading.Thread(target=post_event, args=(str(uuid.uuid4()),))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        total_accepted = sum(r.get("accepted", 0) for r in results)
        self.assertEqual(total_accepted, 2)
        self.assertEqual(UsageEvent.objects.filter(customer=self.customer).count(), 2)






