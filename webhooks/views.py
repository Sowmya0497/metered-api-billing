import hashlib
import hmac
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from invoices.models import Invoice, AuditLog

logger = logging.getLogger(__name__)


def verify_signature(payload_bytes: bytes, sig_header: str) -> bool:
    """Verify HMAC-SHA256 signature. Constant-time compare prevents timing attacks."""
    secret = settings.WEBHOOK_SIGNING_SECRET.encode()
    expected = 'sha256=' + hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header or '')


class PaymentWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        sig = request.META.get('HTTP_X_WEBHOOK_SIGNATURE', '')
        if not verify_signature(request.body, sig):
            logger.warning('Webhook signature verification failed')
            return Response({'error': 'Invalid signature'}, status=401)

        invoice_id = request.data.get('invoice_id')
        payment_event_id = request.data.get('payment_event_id', '')

        if not invoice_id:
            return Response({'error': 'invoice_id required'}, status=400)

        try:
            with transaction.atomic():
                # select_for_update locks the row so concurrent webhook
                # deliveries queue up. The second one hits the
                # already_processed check after the first commits.
                invoice = Invoice.objects.select_for_update().get(id=invoice_id)

                # Idempotency: same payment_event_id already recorded
                if payment_event_id and invoice.payment_idempotency_key == payment_event_id:
                    logger.info(
                        'Webhook replay detected for payment_event_id=%s',
                        payment_event_id,
                    )
                    return Response({
                        'status': 'already_processed',
                        'invoice_id': str(invoice.id),
                    })

                # Already paid by a different event
                if invoice.status == 'PAID':
                    return Response({
                        'status': 'already_paid',
                        'invoice_id': str(invoice.id),
                    })

                before = {'status': invoice.status}

                invoice.status = 'PAID'
                invoice.paid_at = timezone.now()
                if payment_event_id:
                    invoice.payment_idempotency_key = payment_event_id
                invoice.save()

                AuditLog.objects.create(
                    action='invoice_paid',
                    actor='webhook:payment-processor',
                    target_type='Invoice',
                    target_id=str(invoice.id),
                    before=before,
                    after={
                        'status': 'PAID',
                        'payment_event_id': payment_event_id,
                    },
                    reason='Payment confirmed via webhook',
                )

                logger.info(
                    'Invoice %s marked PAID via webhook event %s',
                    invoice.id,
                    payment_event_id,
                )

        except Invoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        return Response({'status': 'paid', 'invoice_id': str(invoice.id)})