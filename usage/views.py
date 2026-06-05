import logging
import hashlib

from django.db import IntegrityError
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.contrib.auth.models import User, AnonymousUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from customers.authentication import ApiKeyAuthentication
from customers.models import ApiKey
from .models import UsageEvent

logger = logging.getLogger(__name__)


class EventIngestionView(APIView):
    """
    POST /v1/events/  — batched, idempotent event ingestion.

    Accepts a JSON array of events. Each event must have a globally
    unique request_id. Duplicate request_ids are counted as duplicates
    and ignored — no error, no double billing.

    Stores api_key_id on each event for per-key reporting.
    """
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = []

    def post(self, request):
        customer = request.user

        # Resolve the api_key_id from the raw key in request.auth
        api_key_id = None
        raw_key = request.auth
        if raw_key:
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            try:
                api_key_id = ApiKey.objects.values_list('id', flat=True).get(
                    key_hash=key_hash
                )
            except ApiKey.DoesNotExist:
                pass

        events = request.data if isinstance(request.data, list) else [request.data]
        accepted = []
        duplicates = []
        errors = []

        for item in events:
            request_id = item.get('request_id')
            if not request_id:
                errors.append({'item': item, 'error': 'missing request_id'})
                continue
            try:
                ts = parse_datetime(item.get('timestamp', '')) or timezone.now()
                UsageEvent.objects.create(
                    request_id=request_id,
                    customer=customer,
                    api_key_id=api_key_id,
                    endpoint=item.get('endpoint', ''),
                    units_consumed=int(item.get('units_consumed', 0)),
                    timestamp=ts,
                )
                accepted.append(request_id)
            except IntegrityError:
                # Duplicate request_id — idempotent, not an error
                duplicates.append(request_id)
            except Exception as e:
                logger.error(
                    'Event ingestion error for request_id=%s: %s',
                    request_id, e,
                )
                errors.append({'request_id': request_id, 'error': str(e)})

        return Response({
            'accepted': len(accepted),
            'duplicates': len(duplicates),
            'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)


class UsageListView(APIView):
    """
    GET /v1/usage/  — paginated usage events.

    Customer-authed requests are always scoped to their own events.
    Ops users (JWT) can pass ?customer_id= to view any customer.

    Query params:
      since=<ISO datetime>
      until=<ISO datetime>
      api_key_id=<uuid>    filter by specific API key
      page_size=<int>      default 100, max 1000
      offset=<int>         default 0
    """
    authentication_classes = [JWTAuthentication, ApiKeyAuthentication]
    permission_classes = []

    def get(self, request):
        if isinstance(request.user, AnonymousUser):
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Ops (JWT) can query any customer; customers see only their own
        if isinstance(request.user, User):
            qs = UsageEvent.objects.all()
            customer_id = request.query_params.get('customer_id')
            if customer_id:
                qs = qs.filter(customer_id=customer_id)
        else:
            # Hard customer scope — never expose other customers' events
            qs = UsageEvent.objects.filter(customer=request.user)

        qs = qs.order_by('-timestamp')

        # Filters
        since = request.query_params.get('since')
        until = request.query_params.get('until')
        api_key_id = request.query_params.get('api_key_id')

        if since:
            qs = qs.filter(timestamp__gte=parse_datetime(since))
        if until:
            qs = qs.filter(timestamp__lte=parse_datetime(until))
        if api_key_id:
            qs = qs.filter(api_key_id=api_key_id)

        # Pagination
        page_size = min(int(request.query_params.get('page_size', 100)), 1000)
        offset = int(request.query_params.get('offset', 0))
        total = qs.count()
        items = list(qs[offset:offset + page_size])

        return Response({
            'total': total,
            'offset': offset,
            'page_size': page_size,
            'next_offset': offset + page_size if offset + page_size < total else None,
            'results': [
                {
                    'request_id': e.request_id,
                    'endpoint': e.endpoint,
                    'units_consumed': e.units_consumed,
                    'api_key_id': str(e.api_key_id) if e.api_key_id else None,
                    'timestamp': e.timestamp.isoformat(),
                }
                for e in items
            ],
        })

# NOTE: UsageEventDetailView (PUT/DELETE) intentionally removed.
# UsageEvents are immutable source of truth for billing.
# Mutations require a manual ops process with audit trail.