import uuid
from django.db import models
from customers.models import Customer


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('PAID', 'Paid'),
        ('VOID', 'Void'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='invoices')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    total_cents = models.BigIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    payment_idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['customer', 'period_start'])]
        unique_together = [('customer', 'period_start', 'period_end')]

    def __str__(self):
        return f"Invoice {self.id} – {self.customer}"


PRICE_TIERS = [
    (10_000,       0),
    (100_000, 100_000),
    (None,     50_000),
]


def compute_invoice_cents(total_units: int) -> int:
    """
    Apply tiered pricing. Returns amount in integer cents.

    Pricing:
      First 10,000 units  → free
      Next  90,000 units  → $0.001/unit  = 0.1 cents  = 100,000 micro-cents/unit
      Beyond 100,000      → $0.0005/unit = 0.05 cents =  50,000 micro-cents/unit

    Accumulates in micro-cents (1 cent = 1,000,000 micro-cents) to avoid
    float arithmetic, then ceiling-divides to whole cents at the end.

    Examples:
      10,000 units  →      0 cents  (all free)
      11,000 units  →    100 cents  (1,000 x $0.001 = $1.00)
      100,000 units →  9,000 cents  (90,000 x $0.001 = $90.00)
      200,000 units → 14,000 cents  ($90.00 + $50.00 = $140.00)
    """
    tiers = [
        (10_000,       0),  # free
        (100_000, 100_000),  # $0.001/unit  → 100,000 micro-cents/unit
        (None,     50_000),  # $0.0005/unit →  50,000 micro-cents/unit
    ]
    micro_cents = 0
    remaining = total_units
    prev_limit = 0
    for limit, rate in tiers:
        if limit is None:
            bucket = remaining
        else:
            bucket = min(remaining, limit - prev_limit)
        micro_cents += bucket * rate
        remaining -= bucket
        if limit is not None:
            prev_limit = limit
        if remaining <= 0:
            break
    # Ceiling division: round up to nearest whole cent
    return (micro_cents + 999_999) // 1_000_000 if micro_cents > 0 else 0


class InvoiceLineItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=500)
    units = models.BigIntegerField(default=0)
    unit_price_micro_cents = models.BigIntegerField(default=0)
    amount_cents = models.BigIntegerField(default=0)
    is_overridden = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} – {self.amount_cents}¢"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('credit_issued',      'Credit Issued'),
        ('line_item_override', 'Line Item Override'),
        ('invoice_voided',     'Invoice Voided'),
        ('invoice_paid',       'Invoice Paid'),
        ('webhook_received',   'Webhook Received'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    actor = models.CharField(max_length=255)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise PermissionError("AuditLog entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("AuditLog entries cannot be deleted.")

    def __str__(self):
        return f"{self.action} by {self.actor} on {self.target_type}:{self.target_id}"
