from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiKey


class ApiKeyAuthentication(BaseAuthentication):
    """
    Authenticate via 'Authorization: ApiKey <raw_key>' header.
    Sets request.user to the associated Customer object.
    """

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('ApiKey '):
            return None  # fall through to next authenticator

        raw_key = auth_header[len('ApiKey '):]
        customer = ApiKey.authenticate(raw_key)
        if customer is None:
            raise AuthenticationFailed('Invalid or inactive API key.')

        # We return (principal, token); principal stored as request.user
        return (customer, raw_key)

    def authenticate_header(self, request):
        return 'ApiKey'
