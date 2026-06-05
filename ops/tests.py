import uuid
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from customers.models import Customer, ApiKey
from invoices.models import Invoice, InvoiceLineItem, AuditLog
from ops.models import Credit
from usage.models import UsageEvent


def make_customer(name="Test", email=None):
    email = email or f"{uuid.uuid4().hex[:8]}@test.com"
    return Customer.objects.create(name=name, email=email)


def make_invoice(customer, status="ISSUED", total_cents=1000):
    return Invoice.objects.create(
        customer=customer,
        period_start=timezone.now().replace(day=1),
        period_end=timezone.now(),
        total_cents=total_cents,
        status=status,
        issued_at=timezone.now(),
    )


def get_ops_headers(client):
    """Create a superuser and return JWT auth headers."""
    if not User.objects.filter(username="opsuser").exists():
        User.objects.create_superuser("opsuser", "ops@test.com", "password")
    resp = client.post(
        "/api/token/",
        {"username": "opsuser", "password": "password"},
        content_type="application/json",
    )
    token = resp.json()["access"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


# -- Credit issuance -----------------------------------------------------------

class IssueCreditTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.headers = get_ops_headers(self.client)

    def test_issue_credit_creates_credit_and_audit_log(self):
        resp = self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            {"amount_cents": 500, "reason": "goodwill"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 201)
        # Credit row created
        self.assertEqual(Credit.objects.filter(customer=self.customer).count(), 1)
        # Audit log written in same transaction
        self.assertEqual(AuditLog.objects.filter(action="credit_issued").count(), 1)
        log = AuditLog.objects.get(action="credit_issued")
        self.assertEqual(log.after["amount_cents"], 500)
        self.assertEqual(log.actor, "opsuser")

    def test_issue_credit_idempotency_same_key_returns_existing(self):
        """Same idempotency_key sent twice must create exactly one credit."""
        ikey = str(uuid.uuid4())
        payload = {"amount_cents": 1000, "reason": "dup test", "idempotency_key": ikey}

        r1 = self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            payload,
            content_type="application/json",
            **self.headers,
        )
        r2 = self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            payload,
            content_type="application/json",
            **self.headers,
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json().get("idempotent"))
        # Still only one credit row
        self.assertEqual(Credit.objects.filter(customer=self.customer).count(), 1)
        # Still only one audit log entry
        self.assertEqual(AuditLog.objects.filter(action="credit_issued").count(), 1)

    def test_issue_credit_without_idempotency_key_creates_new_each_time(self):
        """Without an idempotency_key, each request is a new credit."""
        payload = {"amount_cents": 100, "reason": "no key"}
        self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            payload,
            content_type="application/json",
            **self.headers,
        )
        self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            payload,
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(Credit.objects.filter(customer=self.customer).count(), 2)

    def test_issue_credit_requires_amount_cents(self):
        resp = self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            {"reason": "missing amount"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_request_rejected(self):
        resp = self.client.post(
            f"/ops/customers/{self.customer.id}/credits/",
            {"amount_cents": 100, "reason": "test"},
            content_type="application/json",
        )
        self.assertIn(resp.status_code, [401, 403])

    def test_credit_for_nonexistent_customer_returns_404(self):
        resp = self.client.post(
            f"/ops/customers/{uuid.uuid4()}/credits/",
            {"amount_cents": 100, "reason": "ghost"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 404)


# -- Line item override --------------------------------------------------------

class LineItemOverrideTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.invoice = make_invoice(self.customer, status="ISSUED", total_cents=900)
        self.line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            description="API usage",
            units=100,
            amount_cents=900,
        )
        self.headers = get_ops_headers(self.client)

    def test_override_updates_amount_and_writes_audit(self):
        resp = self.client.patch(
            f"/ops/invoices/{self.invoice.id}/line-items/{self.line_item.id}/",
            {"amount_cents": 500, "reason": "negotiated discount"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 200)

        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.amount_cents, 500)
        self.assertTrue(self.line_item.is_overridden)
        self.assertEqual(self.line_item.override_reason, "negotiated discount")

        log = AuditLog.objects.get(action="line_item_override")
        self.assertEqual(log.before["amount_cents"], 900)
        self.assertEqual(log.after["amount_cents"], 500)
        self.assertEqual(log.reason, "negotiated discount")

    def test_override_updates_invoice_total(self):
        self.client.patch(
            f"/ops/invoices/{self.invoice.id}/line-items/{self.line_item.id}/",
            {"amount_cents": 400, "reason": "test"},
            content_type="application/json",
            **self.headers,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_cents, 400)

    def test_cannot_override_paid_invoice(self):
        self.invoice.status = "PAID"
        self.invoice.save()
        resp = self.client.patch(
            f"/ops/invoices/{self.invoice.id}/line-items/{self.line_item.id}/",
            {"amount_cents": 0, "reason": "fraud attempt"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 409)

    def test_override_requires_amount_cents(self):
        resp = self.client.patch(
            f"/ops/invoices/{self.invoice.id}/line-items/{self.line_item.id}/",
            {"reason": "missing amount"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 400)

    def test_override_nonexistent_line_item_returns_404(self):
        resp = self.client.patch(
            f"/ops/invoices/{self.invoice.id}/line-items/{uuid.uuid4()}/",
            {"amount_cents": 100, "reason": "ghost"},
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 404)


# -- Anomaly detection ---------------------------------------------------------

class AnomalyDetectionTest(TestCase):

    def setUp(self):
        self.headers = get_ops_headers(self.client)
        self.customer = make_customer()

    def test_anomaly_endpoint_returns_list(self):
        resp = self.client.get("/ops/anomalies/", **self.headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_customer_with_spike_is_flagged(self):
        now = timezone.now()
        # 30 days of low baseline: 10 units/day
        for day in range(30, 1, -1):
            UsageEvent.objects.create(
                request_id=str(uuid.uuid4()),
                customer=self.customer,
                endpoint="/api/test",
                units_consumed=10,
                timestamp=now - timezone.timedelta(days=day),
            )
        # Last day: 10x spike — 100 events x 10 units = 1000 units
        for _ in range(100):
            UsageEvent.objects.create(
                request_id=str(uuid.uuid4()),
                customer=self.customer,
                endpoint="/api/test",
                units_consumed=10,
                timestamp=now - timezone.timedelta(hours=1),
            )
        resp = self.client.get("/ops/anomalies/", **self.headers)
        flagged_ids = [r["customer_id"] for r in resp.json()]
        self.assertIn(str(self.customer.id), flagged_ids)

    def test_customer_with_normal_usage_not_flagged(self):
        now = timezone.now()
        # Steady usage — same amount every day, no spike
        for day in range(30, 0, -1):
            UsageEvent.objects.create(
                request_id=str(uuid.uuid4()),
                customer=self.customer,
                endpoint="/api/test",
                units_consumed=100,
                timestamp=now - timezone.timedelta(days=day),
            )
        resp = self.client.get("/ops/anomalies/", **self.headers)
        flagged_ids = [r["customer_id"] for r in resp.json()]
        self.assertNotIn(str(self.customer.id), flagged_ids)

    def test_unauthenticated_anomaly_request_rejected(self):
        resp = self.client.get("/ops/anomalies/")
        self.assertIn(resp.status_code, [401, 403])


# -- Customer detail -----------------------------------------------------------

class OpsCustomerDetailTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.headers = get_ops_headers(self.client)

    def test_customer_detail_returns_usage_and_invoices(self):
        resp = self.client.get(
            f"/ops/customers/{self.customer.id}/",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("usage_30d_units", data)
        self.assertIn("recent_invoices", data)
        self.assertIn("anomaly_detected", data)
        self.assertIn("credits", data)

    def test_nonexistent_customer_returns_404(self):
        resp = self.client.get(
            f"/ops/customers/{uuid.uuid4()}/",
            **self.headers,
        )
        self.assertEqual(resp.status_code, 404)
