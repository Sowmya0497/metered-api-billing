import uuid
import secrets
import hashlib

from django.db import models
from django.utils import timezone


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    """
    API keys for customer authentication.
    The raw key is shown ONCE at creation time; only the SHA-256 hash is stored.
    Prefix (first 8 chars) is stored in plaintext to allow fast lookup.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='api_keys')
    key_prefix = models.CharField(max_length=8, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    label = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['key_prefix', 'is_active'])]

    def __str__(self):
        return f"{self.customer.name} – {self.key_prefix}..."

    @classmethod
    def create_for_customer(cls, customer, label=''):
        """Generate a new API key; returns (ApiKey instance, raw_key_string)."""
        raw = secrets.token_hex(32)  # 64-char hex
        prefix = raw[:8]
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        obj = cls.objects.create(
            customer=customer,
            key_prefix=prefix,
            key_hash=key_hash,
            label=label,
        )
        return obj, raw

    @classmethod
    def authenticate(cls, raw_key: str):
        """Return the Customer if key is valid and active, else None."""
        if not raw_key or len(raw_key) < 8:
            return None
        prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.select_related('customer').get(
                key_prefix=prefix,
                key_hash=key_hash,
                is_active=True,
            )
            # Update last_used without SELECT round-trip
            cls.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
            return api_key.customer
        except cls.DoesNotExist:
            return None
