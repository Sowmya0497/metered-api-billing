import uuid
from django.db import models
from customers.models import Customer


class UsageEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.CharField(max_length=255, unique=True, db_index=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='usage_events')
    api_key_id = models.UUIDField(null=True, blank=True)  # denormalised for reporting
    endpoint = models.CharField(max_length=255)
    units_consumed = models.PositiveIntegerField()
    timestamp = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['customer', 'timestamp']),
            models.Index(fields=['customer', '-timestamp']),
        ]

    def __str__(self):
        return self.request_id


class UsageWindow(models.Model):
    """
    Pre-aggregated hourly buckets: one row per (customer × hour).
    Populated by the aggregation job; used as the source for billing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='usage_windows')
    window_start = models.DateTimeField()   # truncated to the hour
    total_units = models.PositiveBigIntegerField(default=0)
    event_count = models.PositiveIntegerField(default=0)
    is_invoiced = models.BooleanField(default=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('customer', 'window_start')]
        indexes = [
            models.Index(fields=['customer', 'window_start']),
            models.Index(fields=['is_invoiced', 'window_start']),
        ]

    def __str__(self):
        return f"{self.customer} @ {self.window_start}"
