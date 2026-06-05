from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Customer, ApiKey


class CustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customers = Customer.objects.all().order_by('created_at')
        return Response([
            {'id': str(c.id), 'name': c.name, 'email': c.email}
            for c in customers
        ])

    def post(self, request):
        name = request.data.get('name')
        email = request.data.get('email')
        if not name or not email:
            return Response({'error': 'name and email required'}, status=400)
        c = Customer.objects.create(name=name, email=email)
        api_key_obj, raw_key = ApiKey.create_for_customer(c, label='default')
        return Response({
            'id': str(c.id),
            'name': c.name,
            'email': c.email,
            'api_key': raw_key,
        }, status=201)


class CustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, customer_id):
        try:
            c = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response({'id': str(c.id), 'name': c.name, 'email': c.email})

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
        c.delete()
        return Response({'message': 'Customer deleted'}, status=200)