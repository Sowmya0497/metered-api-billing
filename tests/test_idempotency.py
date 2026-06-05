import uuid
from django.test import TestCase
from customers.models import Customer, ApiKey
from usage.models import UsageEvent


class EventIdempotencyTest(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Test Co", email="test@test.com")
        _, self.raw_key = ApiKey.create_for_customer(self.customer, label="test")

    def test_duplicate_request_id_not_double_billed(self):
        rid = str(uuid.uuid4())
        response1 = self.client.post(
            '/v1/events/',
            data=[{"request_id": rid, "endpoint": "/api/test", "units_consumed": 10}],
            content_type='application/json',
            HTTP_AUTHORIZATION=f'ApiKey {self.raw_key}',
        )
        response2 = self.client.post(
            '/v1/events/',
            data=[{"request_id": rid, "endpoint": "/api/test", "units_consumed": 10}],
            content_type='application/json',
            HTTP_AUTHORIZATION=f'ApiKey {self.raw_key}',
        )
        self.assertEqual(UsageEvent.objects.filter(request_id=rid).count(), 1)
        self.assertEqual(response1.data['accepted'], 1)
        self.assertEqual(response2.data['duplicates'], 1)

    def test_tenant_isolation(self):
        other = Customer.objects.create(name="Other Co", email="other@test.com")
        _, other_key = ApiKey.create_for_customer(other, label="test")
        from invoices.models import Invoice
        from django.utils import timezone
        inv = Invoice.objects.create(
            customer=other,
            period_start=timezone.now(),
            period_end=timezone.now(),
            total_cents=1000,
            status='ISSUED',
            issued_at=timezone.now(),
        )
        response = self.client.get(
            f'/v1/invoices/{inv.id}/',
            HTTP_AUTHORIZATION=f'ApiKey {self.raw_key}',
        )
        self.assertEqual(response.status_code, 404)