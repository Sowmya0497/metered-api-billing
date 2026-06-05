import uuid
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from customers.models import Customer, ApiKey
from usage.models import UsageEvent


def make_customer(name='Test', email=None):
    email = email or f'{uuid.uuid4().hex[:8]}@test.com'
    return Customer.objects.create(name=name, email=email)


class IdempotentEventIngestionTest(TransactionTestCase):
    """
    POST /v1/events is idempotent: re-delivering the same request_id
    must not create duplicate rows or double-count units.
    """

    def setUp(self):
        self.customer = make_customer()
        self.api_key_obj, self.raw_key = ApiKey.create_for_customer(self.customer)

    def _post_event(self, request_id, units=10):
        return self.client.post(
            '/v1/events/',
            data=[{
                'request_id': request_id,
                'endpoint': '/api/test',
                'units_consumed': units,
                'timestamp': timezone.now().isoformat(),
            }],
            content_type='application/json',
            HTTP_AUTHORIZATION=f'ApiKey {self.raw_key}',
        )

    def test_first_delivery_accepted(self):
        rid = str(uuid.uuid4())
        resp = self._post_event(rid)
        self.assertIn(resp.status_code, [200, 207])
        self.assertEqual(UsageEvent.objects.filter(request_id=rid).count(), 1)

    def test_duplicate_delivery_no_double_row(self):
        rid = str(uuid.uuid4())
        self._post_event(rid)
        resp2 = self._post_event(rid)
        self.assertIn(resp2.status_code, [200, 207])
        # Still only one row
        self.assertEqual(UsageEvent.objects.filter(request_id=rid).count(), 1)
        data = resp2.json()
        self.assertEqual(data['duplicates'], 1)
        self.assertEqual(data['accepted'], 0)

    def test_tenant_isolation_no_cross_customer_read(self):
        """Customer A cannot read Customer B's events."""
        customer_b = make_customer('B', 'b@test.com')
        _, key_b = ApiKey.create_for_customer(customer_b)

        rid = str(uuid.uuid4())
        self._post_event(rid)  # posted as customer A

        resp = self.client.get(
            '/v1/usage/',
            HTTP_AUTHORIZATION=f'ApiKey {key_b}',
        )
        self.assertEqual(resp.status_code, 200)
        request_ids = [e['request_id'] for e in resp.json()['results']]
        self.assertNotIn(rid, request_ids)


class BatchIngestionTest(TestCase):
    def setUp(self):
        self.customer = make_customer()
        _, self.raw_key = ApiKey.create_for_customer(self.customer)

    def test_batch_of_three(self):
        events = [
            {'request_id': str(uuid.uuid4()), 'endpoint': '/api/x', 'units_consumed': 5, 'timestamp': timezone.now().isoformat()},
            {'request_id': str(uuid.uuid4()), 'endpoint': '/api/y', 'units_consumed': 3, 'timestamp': timezone.now().isoformat()},
            {'request_id': str(uuid.uuid4()), 'endpoint': '/api/z', 'units_consumed': 1, 'timestamp': timezone.now().isoformat()},
        ]
        resp = self.client.post(
            '/v1/events/',
            data=events,
            content_type='application/json',
            HTTP_AUTHORIZATION=f'ApiKey {self.raw_key}',
        )
        self.assertEqual(resp.json()['accepted'], 3)
        self.assertEqual(UsageEvent.objects.filter(customer=self.customer).count(), 3)


