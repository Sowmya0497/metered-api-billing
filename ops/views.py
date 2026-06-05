from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from customers.models import Customer
from usage.models import UsageEvent
from invoices.models import Invoice, InvoiceLineItem, AuditLog
from .models import Credit


def ops_user(request):
    return getattr(request.user, 'username', str(request.user))


class CustomerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        customers = Customer.objects.all().order_by('created_at')
        return Response([
            {'id': str(c.id), 'name': c.name, 'email': c.email, 'created_at': c.created_at.isoformat()}
            for c in customers
        ])


class CustomerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, customer_id):
        try:
            c = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        since = timezone.now() - timezone.timedelta(days=30)
        total_units = (UsageEvent.objects.filter(customer=c, timestamp__gte=since).aggregate(s=Sum('units_consumed'))['s'] or 0)
        daily_avg = total_units / 30 if total_units else 0
        last_day = (UsageEvent.objects.filter(customer=c, timestamp__gte=timezone.now() - timezone.timedelta(days=1)).aggregate(s=Sum('units_consumed'))['s'] or 0)
        anomaly = last_day > (daily_avg * 10)
        invoices = Invoice.objects.filter(customer=c).order_by('-period_start')[:5]
        credits = Credit.objects.filter(customer=c).order_by('-created_at')[:10]
        return Response({
            'id': str(c.id), 'name': c.name, 'email': c.email,
            'usage_30d_units': total_units, 'anomaly_detected': anomaly,
            'recent_invoices': [{'id': str(i.id), 'total_cents': i.total_cents, 'status': i.status} for i in invoices],
            'credits': [{'id': str(cr.id), 'amount_cents': cr.amount_cents, 'reason': cr.reason} for cr in credits],
        })

    def put(self, request, customer_id):
        try:
            c = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        c.name = request.data.get('name', c.name)
        c.email = request.data.get('email', c.email)
        c.save()
        return Response({'id': str(c.id), 'name': c.name, 'email': c.email})

    def delete(self, request, customer_id):
        try:
            c = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        name = c.name
        c.delete()
        return Response({'message': f'{name} deleted successfully'}, status=200)


class IssueCreditView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=404)
        amount_cents = request.data.get('amount_cents')
        reason = request.data.get('reason', '')
        idempotency_key = request.data.get('idempotency_key')
        if amount_cents is None:
            return Response({'error': 'amount_cents is required'}, status=400)
        if idempotency_key:
            existing = Credit.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return Response({'id': str(existing.id), 'amount_cents': existing.amount_cents, 'reason': existing.reason, 'idempotent': True}, status=200)
        with transaction.atomic():
            credit = Credit.objects.create(
                customer=customer,
                amount_cents=int(amount_cents),
                reason=reason,
                idempotency_key=idempotency_key or None,
                actor=ops_user(request),
            )
            AuditLog.objects.create(
                action='credit_issued',
                actor=ops_user(request),
                target_type='Credit',
                target_id=str(credit.id),
                before=None,
                after={'customer_id': str(customer.id), 'amount_cents': credit.amount_cents, 'reason': credit.reason},
                reason=reason,
            )
        return Response({'id': str(credit.id), 'customer_id': str(customer.id), 'amount_cents': credit.amount_cents, 'reason': credit.reason}, status=201)


class LineItemOverrideView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, invoice_id, line_item_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            line_item = InvoiceLineItem.objects.get(id=line_item_id, invoice=invoice)
        except (Invoice.DoesNotExist, InvoiceLineItem.DoesNotExist):
            return Response({'error': 'Not found'}, status=404)
        if invoice.status == 'PAID':
            return Response({'error': 'Cannot modify a paid invoice'}, status=409)
        new_amount = request.data.get('amount_cents')
        override_reason = request.data.get('reason', '')
        if new_amount is None:
            return Response({'error': 'amount_cents is required'}, status=400)
        before = {'amount_cents': line_item.amount_cents, 'is_overridden': line_item.is_overridden}
        with transaction.atomic():
            line_item.amount_cents = int(new_amount)
            line_item.is_overridden = True
            line_item.override_reason = override_reason
            line_item.save()
            new_total = InvoiceLineItem.objects.filter(invoice=invoice).aggregate(t=Sum('amount_cents'))['t'] or 0
            invoice.total_cents = new_total
            invoice.save()
            AuditLog.objects.create(
                action='line_item_override',
                actor=ops_user(request),
                target_type='InvoiceLineItem',
                target_id=str(line_item.id),
                before=before,
                after={'amount_cents': line_item.amount_cents, 'reason': override_reason},
                reason=override_reason,
            )
        return Response({'id': str(line_item.id), 'invoice_id': str(invoice.id), 'amount_cents': line_item.amount_cents, 'override_reason': line_item.override_reason, 'invoice_total_cents': invoice.total_cents})


class AnomalyListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        flagged = []
        now = timezone.now()
        since_30d = now - timezone.timedelta(days=30)
        since_1d = now - timezone.timedelta(days=1)
        for customer in Customer.objects.all():
            total_30d = (UsageEvent.objects.filter(customer=customer, timestamp__gte=since_30d).aggregate(s=Sum('units_consumed'))['s'] or 0)
            total_1d = (UsageEvent.objects.filter(customer=customer, timestamp__gte=since_1d).aggregate(s=Sum('units_consumed'))['s'] or 0)
            daily_avg = total_30d / 30
            if daily_avg > 0 and total_1d > daily_avg * 10:
                flagged.append({'customer_id': str(customer.id), 'customer_name': customer.name, 'daily_avg_units': round(daily_avg, 2), 'last_1d_units': total_1d, 'ratio': round(total_1d / daily_avg, 1)})
        return Response(flagged)


class CreditListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        credits = Credit.objects.all().order_by('-created_at')
        return Response([
            {
                'id': str(c.id),
                'customer_id': str(c.customer.id),
                'customer_name': c.customer.name,
                'amount_cents': c.amount_cents,
                'reason': c.reason,
                'created_at': c.created_at.isoformat(),
            }
            for c in credits
        ])


class CreditDetailView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, credit_id):
        try:
            credit = Credit.objects.get(id=credit_id)
        except Credit.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        credit.amount_cents = request.data.get('amount_cents', credit.amount_cents)
        credit.reason = request.data.get('reason', credit.reason)
        credit.save()
        return Response({'id': str(credit.id), 'amount_cents': credit.amount_cents, 'reason': credit.reason})

    def delete(self, request, credit_id):
        try:
            credit = Credit.objects.get(id=credit_id)
        except Credit.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        credit.delete()
        return Response({'message': 'Credit deleted'}, status=200)


