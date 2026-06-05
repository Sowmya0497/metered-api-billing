from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from customers.authentication import ApiKeyAuthentication
from customers.models import Customer
from .models import Invoice, InvoiceLineItem, AuditLog


class InvoiceListView(APIView):
    authentication_classes = [ApiKeyAuthentication, JWTAuthentication]
    permission_classes = []

    def get(self, request):
        customer = request.user
        if hasattr(customer, 'username'):
            cid = request.query_params.get('customer_id')
            if not cid:
                return Response({'error': 'customer_id required'}, status=400)
            customer = Customer.objects.get(id=cid)
        invoices = Invoice.objects.filter(customer=customer).order_by('-period_start')
        return Response([
            {
                'id': str(inv.id),
                'period_start': inv.period_start.isoformat(),
                'period_end': inv.period_end.isoformat(),
                'total_cents': inv.total_cents,
                'status': inv.status,
                'issued_at': inv.issued_at.isoformat() if inv.issued_at else None,
            }
            for inv in invoices
        ])


class InvoiceCountView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = []

    def get(self, request):
        if isinstance(request.user, AnonymousUser):
            return Response({'count': 0})
        count = Invoice.objects.count()
        return Response({'count': count})


class InvoiceDetailView(APIView):
    authentication_classes = [ApiKeyAuthentication, JWTAuthentication]
    permission_classes = []

    def get(self, request, invoice_id):
        customer = request.user
        if hasattr(customer, 'username'):
            inv = Invoice.objects.get(id=invoice_id)
        else:
            inv = Invoice.objects.filter(id=invoice_id, customer=customer).first()
            if not inv:
                return Response({'error': 'Not found'}, status=404)
        line_items = list(inv.line_items.all())
        return Response({
            'id': str(inv.id),
            'customer_id': str(inv.customer_id),
            'period_start': inv.period_start.isoformat(),
            'period_end': inv.period_end.isoformat(),
            'total_cents': inv.total_cents,
            'status': inv.status,
            'line_items': [
                {
                    'id': str(li.id),
                    'description': li.description,
                    'units': li.units,
                    'amount_cents': li.amount_cents,
                    'is_overridden': li.is_overridden,
                }
                for li in line_items
            ]
        })

    def put(self, request, invoice_id):
        try:
            inv = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        inv.status = request.data.get('status', inv.status)
        inv.total_cents = request.data.get('total_cents', inv.total_cents)
        inv.save()
        return Response({'id': str(inv.id), 'status': inv.status, 'total_cents': inv.total_cents})

    def delete(self, request, invoice_id):
        try:
            inv = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        inv.delete()
        return Response({'message': 'Invoice deleted'}, status=200)