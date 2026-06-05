import os
import django
import random
import uuid
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Model

from customers.models import Customer, ApiKey
from usage.models import UsageEvent, UsageWindow
from invoices.models import Invoice, InvoiceLineItem, AuditLog, compute_invoice_cents
from ops.models import Credit

CUSTOMERS = [
    {"name": "Acme Corp",       "email": "billing@acme.com",        "profile": "heavy"},
    {"name": "Startup Inc",     "email": "ops@startup.io",          "profile": "growing"},
    {"name": "Dev Tools LLC",   "email": "finance@devtools.io",     "profile": "steady"},
    {"name": "DataPipe Co",     "email": "accounts@datapipe.com",   "profile": "heavy"},
    {"name": "NanoSaaS",        "email": "hello@nanosass.com",      "profile": "light"},
    {"name": "Enterprise X",    "email": "proc@entx.com",           "profile": "heavy"},
    {"name": "Indie Hacker",    "email": "me@indiehacker.dev",      "profile": "light"},
    {"name": "Consulting Firm", "email": "billing@consultfirm.com", "profile": "steady"},
    {"name": "Scale-up Labs",   "email": "cfo@scalelabs.io",        "profile": "growing"},
    {"name": "Beta Tester Co",  "email": "test@betatester.com",     "profile": "anomaly"},
]

ENDPOINTS = [
    "/api/v1/infer",
    "/api/v1/embed",
    "/api/v1/classify",
    "/api/v1/summarize",
    "/api/v1/translate",
]

EVENTS_PER_DAY = {
    "heavy":   (2, 3),
    "growing": (1, 2),
    "steady":  (1, 2),
    "light":   (1, 2),
    "anomaly": (1, 2),
}

UNITS_PER_EVENT = {
    "heavy":   (50, 500),
    "growing": (10, 100),
    "steady":  (5,  50),
    "light":   (1,  20),
    "anomaly": (1,  10),
}


def clear_existing():
    print("Clearing existing data...")
    original_delete = AuditLog.delete
    AuditLog.delete = Model.delete
    try:
        AuditLog.objects.all().delete()
    finally:
        AuditLog.delete = original_delete
    Credit.objects.all().delete()
    InvoiceLineItem.objects.all().delete()
    Invoice.objects.all().delete()
    UsageWindow.objects.all().delete()
    UsageEvent.objects.all().delete()
    ApiKey.objects.all().delete()
    Customer.objects.all().delete()
    print("  Done")


def make_customers():
    print("Creating customers and API keys...")
    result = []
    for spec in CUSTOMERS:
        customer = Customer.objects.create(name=spec["name"], email=spec["email"])
        n_keys = random.randint(1, 2)
        keys = []
        for i in range(n_keys):
            _, raw = ApiKey.create_for_customer(customer, label=f"key-{i+1}")
            keys.append(raw)
        result.append((customer, keys, spec["profile"]))
        print(f"  {customer.name} ({n_keys} key(s))")
    return result


def make_events(customers_data, days=5):
    print(f"Generating {days} days of usage events...")
    now = timezone.now()
    total = 0
    for customer, keys, profile in customers_data:
        lo_epd, hi_epd = EVENTS_PER_DAY[profile]
        lo_u, hi_u = UNITS_PER_EVENT[profile]
        api_key_ids = list(
            ApiKey.objects.filter(customer=customer).values_list("id", flat=True)
        )
        batch = []
        for day_offset in range(days, 0, -1):
            day_start = now - timedelta(days=day_offset)
            if profile == "anomaly" and day_offset <= 1:
                n = random.randint(3, 5)
            else:
                n = random.randint(lo_epd, hi_epd)
            for _ in range(n):
                ts = day_start + timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59),
                )
                batch.append(UsageEvent(
                    request_id=str(uuid.uuid4()),
                    customer=customer,
                    api_key_id=random.choice(api_key_ids),
                    endpoint=random.choice(ENDPOINTS),
                    units_consumed=random.randint(lo_u, hi_u),
                    timestamp=ts,
                ))
        UsageEvent.objects.bulk_create(batch, batch_size=500)
        total += len(batch)
        print(f"  {customer.name}: {len(batch)} events")
    print(f"  Total: {total} events")


def run_aggregation():
    print("Running aggregation...")
    from jobs.aggregate_usage import run
    run(lookback_hours=24 * 7)
    print("  Done")


def run_invoicing():
    print("Generating invoices for last 2 months...")
    from jobs.generate_invoices import run
    from dateutil.relativedelta import relativedelta
    now = timezone.now()
    for months_ago in [2, 1]:
        period_start = (now.replace(day=1) - relativedelta(months=months_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        period_end = period_start + relativedelta(months=1)
        run(period_start=period_start, period_end=period_end)


def simulate_payments():
    print("Simulating payments (~60%)...")
    invoices = list(Invoice.objects.filter(status="ISSUED"))
    if not invoices:
        print("  No invoices to pay")
        return
    to_pay = random.sample(invoices, k=max(1, int(len(invoices) * 0.6)))
    for invoice in to_pay:
        payment_event_id = f"evt_{uuid.uuid4().hex[:16]}"
        invoice.status = "PAID"
        invoice.paid_at = timezone.now()
        invoice.payment_idempotency_key = payment_event_id
        invoice.save()
        AuditLog.objects.create(
            action="invoice_paid",
            actor="webhook:payment-processor",
            target_type="Invoice",
            target_id=str(invoice.id),
            before={"status": "ISSUED"},
            after={"status": "PAID", "payment_event_id": payment_event_id},
            reason="Payment confirmed via webhook (seeded)",
        )
    print(f"  Marked {len(to_pay)}/{len(invoices)} invoices as PAID")


def make_credits(customers_data):
    print("Creating sample credits...")
    for customer, _, _ in random.sample(customers_data, k=3):
        amount = random.choice([500, 1000, 2500])
        credit = Credit.objects.create(
            customer=customer,
            amount_cents=amount,
            reason="Goodwill credit for service disruption",
            idempotency_key=f"seed-{customer.id}",
            actor="seed-script",
        )
        AuditLog.objects.create(
            action="credit_issued",
            actor="seed-script",
            target_type="Credit",
            target_id=str(credit.id),
            before=None,
            after={"customer_id": str(customer.id), "amount_cents": amount},
            reason=credit.reason,
        )
        print(f"  {amount}c credit for {customer.name}")


def make_overrides():
    print("Creating sample line item overrides...")
    items = list(
        InvoiceLineItem.objects.select_related("invoice")
        .filter(invoice__status="ISSUED")[:2]
    )
    for li in items:
        before = {"amount_cents": li.amount_cents}
        new_amount = max(0, li.amount_cents - random.randint(10, 50))
        li.amount_cents = new_amount
        li.is_overridden = True
        li.override_reason = "Negotiated discount"
        li.save()
        AuditLog.objects.create(
            action="line_item_override",
            actor="seed-script",
            target_type="InvoiceLineItem",
            target_id=str(li.id),
            before=before,
            after={"amount_cents": new_amount, "reason": li.override_reason},
            reason=li.override_reason,
        )
        print(f"  {before['amount_cents']}c -> {new_amount}c")


def create_ops_user():
    print("Creating ops superuser...")
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "admin")
        print("  Created admin / admin")
    else:
        print("  admin already exists")


def main():
    print("=" * 50)
    print("Seeding metered-billing database")
    print("=" * 50)
    clear_existing()
    customers_data = make_customers()
    make_events(customers_data, days=5)
    run_aggregation()
    run_invoicing()
    simulate_payments()
    make_credits(customers_data)
    make_overrides()
    create_ops_user()
    print("=" * 50)
    print("Seed complete!")
    print(f"  Customers:     {Customer.objects.count()}")
    print(f"  API Keys:      {ApiKey.objects.count()}")
    print(f"  Usage Events:  {UsageEvent.objects.count()}")
    print(f"  Usage Windows: {UsageWindow.objects.count()}")
    print(f"  Invoices:      {Invoice.objects.count()}")
    print(f"  Credits:       {Credit.objects.count()}")
    print(f"  Audit Logs:    {AuditLog.objects.count()}")
    print("=" * 50)
    print("Login:  admin / admin")
    print("API:    http://localhost:8000")
    print("UI:     http://localhost:5173")
    print("=" * 50)


if __name__ == "__main__":
    main()