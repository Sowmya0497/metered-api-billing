import uuid
from django.db import models


class Credit(models.Model):
    """Customer account credit. Reduces the next invoice total."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="credits"
    )
    amount_cents = models.BigIntegerField()   # integer minor units
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=255, blank=True, unique=True, null=True)
    actor = models.CharField(max_length=255, default='ops')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} – {self.amount_cents}¢"
