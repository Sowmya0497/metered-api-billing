# Metered API Billing — Design Document

## 1. Data Model

### Schema Overview

**customers_customer**
- `id` UUID PK
- `name`, `email` (unique)
- `created_at`
- Index: `email` (unique lookup on auth)

**customers_apikey**
- `id` UUID PK
- `customer_id` FK → customer
- `key_prefix` CHAR(8) — first 8 chars stored plain for display
- `key_hash` CHAR(64) — SHA-256 of full key, used for verification
- `label`, `created_at`, `last_used_at`
- Index: `key_hash` (every inbound request verifies here)

**usage_usageevent**
- `id` UUID PK
- `request_id` VARCHAR(255) UNIQUE — global dedup key
- `customer_id` FK
- `api_key_id` UUID (denormalised, nullable)
- `endpoint` VARCHAR(255)
- `units_consumed` PositiveInt
- `timestamp` DateTimeField
- Indexes: `(customer_id, timestamp)`, `(customer_id, -timestamp)`, `request_id` UNIQUE

**usage_usagewindow**
- `id` UUID PK
- `customer_id` FK
- `window_start` DateTimeField (truncated to hour)
- `total_units` BigInt
- `event_count` Int
- `is_invoiced` Bool
- Unique: `(customer_id, window_start)`
- Indexes: `(customer_id, window_start)`, `(is_invoiced, window_start)`

**invoices_invoice**
- `id` UUID PK
- `customer_id` FK
- `period_start`, `period_end` DateTimeField
- `total_cents` BigInt (integer minor units — never floats)
- `status` ENUM(DRAFT, ISSUED, PAID, VOID)
- `payment_idempotency_key` VARCHAR(255) indexed
- `issued_at`, `paid_at`, `created_at`
- Index: `(customer_id, period_start)`

**invoices_invoicelineitem**
- `id` UUID PK
- `invoice_id` FK
- `description`, `units` BigInt
- `amount_cents` BigInt
- `is_overridden` Bool, `override_reason` Text

**invoices_auditlog**
- `id` UUID PK
- `action` ENUM
- `actor` VARCHAR (username or "system")
- `target_type`, `target_id`
- `before` JSON, `after` JSON
- `reason` Text
- `created_at` (auto, immutable)
- Save/delete overridden to raise PermissionError — append-only by design

**ops_credit**
- `id` UUID PK
- `customer_id` FK
- `amount_cents` BigInt
- `reason` Text
- `idempotency_key` VARCHAR unique (nullable)
- `actor`, `created_at`

### Why These Indexes

- `request_id` UNIQUE: the primary dedup guard. Every inbound event does a single-row lookup.
- `(customer_id, timestamp)`: the most common query — "give me this customer's events in a date range". Composite index avoids a seq scan on the full event table.
- `(is_invoiced, window_start)`: the invoice generation job filters `is_invoiced=False` ordered by time. Without this, it table-scans all windows every month.
- `payment_idempotency_key` on Invoice: webhook replay check is a single indexed lookup.
- `key_hash` on ApiKey: every API request does `WHERE key_hash = sha256(incoming_key)`.

### At 10× Scale (50M events/month)
- Partition `usage_usageevent` by month (PostgreSQL declarative partitioning on `timestamp`).
- Add covering index `(customer_id, timestamp) INCLUDE (units_consumed)` to avoid heap fetch on aggregation queries.
- Read replicas for ops dashboard queries.

### At 100× Scale (500M events/month)
- Shard `usage_usageevent` by `customer_id` range into separate schemas or databases.
- Move aggregation to a streaming system (Kafka + Flink) writing directly to `usage_usagewindow`.
- Keep `invoices_*` on a single OLTP database — invoices are low-volume, correctness-critical.

---

## 2. Idempotency & Concurrency

### Event Ingestion Replay

`request_id` has a UNIQUE constraint at the database level. A duplicate delivery hits an `IntegrityError` which is caught and counted as a duplicate — no double billing. Concurrent workers racing on the same `request_id` both attempt INSERT; one wins, one gets `IntegrityError`. This is safe without application-level locking.

### Aggregation Job Running Twice

The job uses `SELECT FOR UPDATE` on the `UsageWindow` row inside a transaction:

```python
window, created = UsageWindow.objects.select_for_update().get_or_create(
    customer_id=cid, window_start=window_start,
    defaults={...}
)
if not created and not window.is_invoiced:
    window.total_units = total_units  # recomputed from raw events
    window.save()
```

Two workers racing on the same window: one acquires the row lock, updates, commits. The second waits, then recomputes the same value from the same raw events and writes the same number. The result is identical — idempotent by recomputation from source.

### Webhook Delivered Three Times

Each payment webhook carries a `payment_event_id`. On receipt:
1. Verify HMAC-SHA256 signature.
2. Look up `invoice.payment_idempotency_key == payment_event_id` — if match, return 200 no-op.
3. If `invoice.status == 'PAID'` — return 200 no-op.
4. Otherwise, inside a transaction: set status=PAID, store `payment_event_id`, write AuditLog.

All three deliveries: first marks paid, second and third hit the idempotency check and return early. No double audit entries, no double state change.

### Ops Clicks "Issue Credit" Twice

The credit creation endpoint accepts an optional `idempotency_key`. If the client sends the same key twice, the second request finds the existing credit and returns it unchanged. The UI should generate a UUID per form submission and include it as `idempotency_key` in the POST body. Without an idempotency key, the endpoint creates a new credit each time — the UI is responsible for preventing double-clicks (disabled button after first click).

---

## 3. Aggregation Pipeline
UsageEvent (raw, immutable)
↓  [aggregate_usage job — runs every 5 min]
UsageWindow (one row per customer × hour, recomputable)
↓  [generate_invoices job — runs 1st of month]
InvoiceLineItem → Invoice

**State classification:**
- `UsageEvent`: immutable source of truth. Never updated after insert.
- `UsageWindow`: derived, recomputable. Can be recomputed from raw events at any time as long as `is_invoiced=False`. Once invoiced, the window is frozen.
- `Invoice` / `InvoiceLineItem`: immutable after `status=ISSUED`. Only ops override via audit-logged PATCH is allowed.

**Late-arriving events:**
- Events arriving within the aggregation lookback window (default 2 hours) are picked up on the next run — the job recomputes the window total from raw events.
- Events arriving after invoice issuance: the window is already `is_invoiced=True`. The raw event is stored but not reflected in the current invoice. The next month's invoice job processes it if it falls within the new period. For SLA-critical accuracy, ops can trigger a manual reconciliation that voids the old invoice and reissues with corrected totals — this is an explicit ops action with an audit trail, not automatic.

**Drift reconciliation:**
- At any time: `SELECT SUM(units_consumed) FROM usage_usageevent WHERE customer_id=X AND timestamp BETWEEN A AND B` should equal `SELECT SUM(total_units) FROM usage_usagewindow WHERE customer_id=X AND window_start BETWEEN A AND B`. A nightly reconciliation job compares these and alerts on divergence > 0.1%.

---

## 4. Failure Modes

### What breaks first at production scale:

**1. Single-writer bottleneck on UsageEvent inserts**
At 2,000 events/sec peak, a single PostgreSQL instance on modest hardware will saturate around 5,000–10,000 inserts/sec. Fix: connection pooling via PgBouncer first (buys 3–5×), then partition the table by month (reduces index size per partition), then introduce a write buffer (Redis sorted set or Kafka topic) with a batch consumer flushing to Postgres every 500ms.

**2. Aggregation job runtime grows linearly with active customers**
At 5,000 customers the hourly job processes each customer sequentially. At 10× it starts to overlap with the next scheduled run. Fix: parallelize by customer_id range across worker processes; use a job queue (Celery) with per-customer tasks so each runs independently and failures are isolated.

**3. Invoice generation accuracy under late events**
If the invoice job runs at midnight on the 1st and 3% of events from the prior month arrive late (network retry, clock skew), those units are missed. Fix: add a 24-hour grace period — run the invoice job at midnight+24h on the 2nd, accepting late events up to T+24h. Beyond that, flag for manual reconciliation. Document the SLA in customer contracts.

---

## 5. Threat Model

### Hostile Customer

**Worst case:** Customer A guesses Customer B's invoice UUID and retrieves it via `GET /v1/invoices/{id}`.

**What stops them:** The `InvoiceDetailView` scopes the query to the authenticated customer:
```python
inv = Invoice.objects.filter(id=invoice_id, customer=request.user).first()
```
The `request.user` on `/v1/` endpoints is always the `Customer` object from ApiKey authentication, never a Django User. UUID space (2^122 addressable IDs) makes guessing impractical even without scoping, but the scope is the hard guard. Tenant isolation is enforced in the authentication class, not in individual views — forgetting to add a filter in a new view doesn't automatically leak data.

**API key leakage:** Keys are SHA-256 hashed on creation. The plaintext is shown once and never stored. `key_hash` is compared using `hmac.compare_digest` to prevent timing attacks. An attacker with read access to the database gets only hashes — not usable as API keys.

### Hostile Internal User (Ops)

**Worst case:** Ops user issues a large credit to their own customer account, then deletes the audit log.

**What stops them:** `AuditLog.save()` raises `PermissionError` if the row already exists (append-only). `AuditLog.delete()` always raises `PermissionError`. Django admin write access to AuditLog is removed. Credit issuance always writes an audit entry inside the same transaction — if the audit write fails, the credit rolls back.

**Invoice tampering:** Line item overrides require a reason and create an immutable audit entry. The override endpoint checks `invoice.status != 'PAID'` before allowing changes. A paid invoice cannot be modified.

### Compromised Webhook Source

**Worst case:** Attacker sends a forged webhook marking an unpaid invoice as PAID.

**What stops them:** Every webhook request is verified with HMAC-SHA256 against `WEBHOOK_SIGNING_SECRET` loaded from the environment (never in the repo). The signature check happens before any database access. A forged request without the secret produces a different HMAC and is rejected with 401. Replay of a legitimate captured request is blocked by the `payment_event_id` idempotency key — the second delivery is detected and returns 200 no-op without re-applying.

---

## 6. Trade-offs

### Trade-off 1: SQLite for local dev vs PostgreSQL in production

**Chosen:** SQLite for local development, PostgreSQL for production (via `DATABASE_URL`).

**Alternative rejected:** PostgreSQL-only everywhere, enforced via Docker Compose.

**Why:** SQLite removes the Docker dependency for local development. New developers can `pip install` and run immediately. The risk is SQLite/PostgreSQL behavioral differences (e.g. `date_trunc` not available in SQLite, `SELECT FOR UPDATE` behavior differs). Mitigation: the aggregation job uses Django ORM abstractions that work on both; the one SQLite-incompatible function (`date_trunc`) has a fallback. The trade-off is developer velocity vs environment parity. At team scale, I'd switch to Docker Compose for all local dev.

### Trade-off 2: Recompute aggregation windows vs. incremental update

**Chosen:** On each aggregation run, recompute `UsageWindow.total_units` from the full set of raw events in the window, using `SELECT FOR UPDATE` to prevent races.

**Alternative rejected:** Incremental update — maintain a running total and add only new events since last run using a `last_processed_at` cursor.

**Why chosen:** Recomputation is idempotent by construction. No cursor state to manage or corrupt. Late-arriving events are automatically included on the next run without special handling. The cost is higher: each run re-reads all events in the lookback window. At current scale (2-hour lookback, 5,000 customers) this is fast. The alternative (incremental) is faster per run but requires careful cursor management and is not self-healing — a bug in cursor state silently underbills. For a billing system where accuracy is contractual, correctness beats performance until the cost becomes measurable.

---

## 7. What I Didn't Build and Would Build Next

### Not built:
- **Background job scheduler:** The jobs are runnable as management commands but there's no scheduler (cron/Celery). In production, I'd add Celery Beat with two periodic tasks: `aggregate_usage` every 5 minutes, `generate_invoices` on the 1st of each month.
- **Customer-facing dashboard separation:** The current frontend combines ops and customer views. A production system would have separate auth flows — customers log in with API keys, ops users with SSO/username-password.
- **Pagination on ops endpoints:** The customer list and credit list endpoints return all rows. At scale, these need cursor-based pagination.
- **Alerting hooks:** No metrics or alerting. Would add: Prometheus counters on event ingestion rate, invoice generation success/failure, anomaly detection triggers, and webhook verification failures.
- **Full reconciliation job:** The design describes it; implementation would be a management command that compares raw event sums to window sums and pages ops on divergence.
- **Price plan model:** Pricing tiers are hardcoded as Python constants. A production system needs a `PricePlan` model with effective dates so historical invoices remain correct after price changes.
- **Tests:** Priority tests missing: idempotency on concurrent event ingestion (two workers, same request_id), aggregation job running twice concurrently (SELECT FOR UPDATE validation), webhook replay (same payment_event_id twice), tenant isolation (customer A accessing customer B's invoice returns 404).

### Would build next (priority order):
1. Celery Beat scheduler for background jobs
2. Test suite covering correctness boundaries
3. Price plan model
4. Cursor-based pagination
5. Prometheus metrics + alerting thresholds
6. Reconciliation job
7. Separate customer auth flow
