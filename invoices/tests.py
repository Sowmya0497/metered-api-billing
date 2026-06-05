import uuid
import hashlib
import hmac
import json

from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from invoices.models import Invoice, InvoiceLineItem, AuditLog, compute_invoice_cents


def make_customer(email=None):
    email = email or f'{uuid.uuid4().hex[:8]}@test.com'
    return Customer.objects.create(name='Test', email=email)


def make_invoice(customer, status='ISSUED', total_cents=1000):
    return Invoice.objects.create(
        customer=customer,
        period_start=timezone.now().replace(day=1),
        period_end=timezone.now(),
        total_cents=total_cents,
        status=status,
        issued_at=timezone.now(),
    )


class TieredPricingTest(TestCase):

    def test_first_10k_free(self):
        # All 10,000 units fall in the free tier
        self.assertEqual(compute_invoice_cents(10_000), 0)

    def test_11k_units(self):
        # 1,000 units × $0.001 = $1.00 = 100 cents
        self.assertEqual(compute_invoice_cents(11_000), 100)

    def test_100k_units(self):
        # 90,000 units × $0.001 = $90.00 = 9,000 cents
        self.assertEqual(compute_invoice_cents(100_000), 9_000)

    def test_200k_units(self):
        # 90,000 × $0.001 + 100,000 × $0.0005 = $90 + $50 = $140 = 14,000 cents
        self.assertEqual(compute_invoice_cents(200_000), 14_000)


class AuditLogImmutabilityTest(TestCase):

    def test_audit_log_cannot_be_updated(self):
        log = AuditLog.objects.create(
            action='credit_issued',
            actor='ops',
            target_type='Credit',
            target_id='abc',
            reason='test',
        )
        with self.assertRaises(PermissionError):
            log.action = 'hacked'
            log.save()

    def test_audit_log_cannot_be_deleted(self):
        log = AuditLog.objects.create(
            action='credit_issued',
            actor='ops',
            target_type='Credit',
            target_id='abc',
            reason='test',
        )
        with self.assertRaises(PermissionError):
            log.delete()


class TenantIsolationInvoiceTest(TestCase):

    def setUp(self):
        from customers.models import ApiKey
        self.c1 = make_customer()
        self.c2 = make_customer()
        _, self.key1 = ApiKey.create_for_customer(self.c1)
        _, self.key2 = ApiKey.create_for_customer(self.c2)
        self.inv1 = make_invoice(self.c1)
        self.inv2 = make_invoice(self.c2)

    def test_customer_cannot_access_other_invoice(self):
        resp = self.client.get(
            f'/v1/invoices/{self.inv2.id}/',
            HTTP_AUTHORIZATION=f'ApiKey {self.key1}',
        )
        self.assertEqual(resp.status_code, 404)

    def test_customer_can_access_own_invoice(self):
        resp = self.client.get(
            f'/v1/invoices/{self.inv1.id}/',
            HTTP_AUTHORIZATION=f'ApiKey {self.key1}',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['id'], str(self.inv1.id))


class WebhookIdempotencyTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.invoice = make_invoice(self.customer, status='ISSUED')

    def _post_webhook(self, payment_event_id='evt-001'):
        payload = json.dumps({
            'invoice_id': str(self.invoice.id),
            'payment_event_id': payment_event_id,
        }).encode()
        from django.conf import settings
        secret = settings.WEBHOOK_SIGNING_SECRET.encode()
        sig = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return self.client.post(
            '/webhooks/payments/',
            data=payload,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=sig,
        )

    def test_first_delivery_marks_paid(self):
        resp = self._post_webhook()
        self.assertEqual(resp.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'PAID')

    def test_second_delivery_is_no_op(self):
        self._post_webhook()
        resp2 = self._post_webhook()
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(resp2.json()['status'], ['already_paid', 'already_processed'])

    def test_invalid_signature_rejected(self):
        payload = json.dumps({
            'invoice_id': str(self.invoice.id),
            'payment_event_id': 'x',
        }).encode()
        resp = self.client.post(
            '/webhooks/payments/',
            data=payload,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE='sha256=badbadbadbad',
        )
        self.assertEqual(resp.status_code, 401)