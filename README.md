# Freight AI Ops

An **AI operations system for freight forwarding sales & operations**. It reads
the enquiries arriving in your mailbox and turns them — along with partner
replies, quotes, follow-ups and shipment events — into structured operational
output, so a small desk can answer every enquiry quickly instead of answering a
third of them days late.

The AI agents are orchestrated with **LangGraph**, the API is **FastAPI**, and the
dashboard is **Next.js**. The whole stack comes up with one Docker Compose
command — on your own machine, your own server, or a hosted deployment serving
several forwarders side by side (see *Path to SaaS*).

> This is built to be a stable daily-use internal tool, not a demo. Pricing,
> customer communication and shipment confirmation always stay under human
> control — the AI produces editable drafts; you approve and send.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| AI agents | LangGraph + provider abstraction (Anthropic default, OpenAI/Gemini optional) |
| Database | PostgreSQL (+ Alembic migrations) |
| Email intake | IMAP polling (read-only), per-organization, credentials encrypted at rest |
| Background jobs | Celery + Redis (mailbox polling, follow-up reminders, reports, backups) |
| Deployment | Docker Compose |

## Quick start

1. **Install Docker Desktop** (Windows/Mac) or Docker Engine + Compose (Linux).
2. Copy the env template and fill it in:
   ```bash
   cp .env.example .env
   ```
   Set at least `ANTHROPIC_API_KEY` and a real `ADMIN_PASSWORD`.
3. Start everything:
   ```bash
   docker compose up -d --build
   ```
   On Windows you can double-click **`Start System.bat`** instead.
4. Open:
   - Frontend dashboard: <http://localhost:3000>
   - Backend API docs: <http://localhost:8000/docs>

The backend container automatically runs database migrations and creates the
bootstrap admin account (from `ADMIN_EMAIL` / `ADMIN_PASSWORD`) on first start.

## Verify the AI path (recommended after setup)

Everything in CI runs against a deterministic fake LLM; this one command proves
the **real** provider path (structured RFQ extraction, drafts, constrained rate
analysis) with your API key. It costs a few cents:

```bash
docker compose exec backend python -m app.smoke_llm
```

## Connect a mailbox (automatic RFQ intake)

The system reads the mailbox where enquiries arrive and turns each new RFQ into
a structured record on its own, so response time is bounded by the polling
interval (minutes) rather than by when somebody opens their inbox.

1. In the dashboard go to **Email Inbox → Connect a mailbox** (or
   `/settings/mailbox`).
2. Enter the IMAP server, the address and a password. Accounts with two-factor
   authentication need an **app password**, not the account password.
3. Press **Test connection**, then **Connect**.

Incoming mail is triaged into *new RFQ*, *partner rate reply*, *customer reply*
and *not relevant*:

- a **new RFQ** is parsed and appears in RFQs already structured, with its
  `received_at` set to when the customer actually wrote;
- a **rate reply** is attached to the RFQ it answers (by thread, or by the
  reference quoted in the body);
- a **customer reply** stops that quotation's follow-up cadence, so nobody is
  chased after they have answered;
- attachments are stored and downloadable from the message.

What it never does: send, delete, or mark mail as read. The mailbox is opened
read-only (`EXAMINE` + `BODY.PEEK`) and left exactly as the user left it, and
every draft still needs human approval. Credentials are encrypted at rest
(`MAILBOX_ENCRYPTION_KEY`) and are never returned by the API.

Polling runs in the Celery worker every `EMAIL_POLL_INTERVAL_MINUTES` (default
3); **Check now** on the inbox page polls immediately.

## Measuring whether it works (Performance page)

Speed is the thing being sold, so it is measured rather than asserted. The
**Performance** page and `GET /api/reports/performance` report, from the
database and with no model involved:

- **response rate** — the share of enquiries that ever received a quotation;
- **median and p90 response time** — from the customer's email to the *first*
  quotation sent (a revised quote later cannot make a slow answer look fast);
- **win rate bucketed by response speed** — your own numbers, so the case for
  answering quickly is argued with your data, not a vendor's slide;
- **unanswered enquiries**, longest wait first — directly actionable;
- quotations per day and per person, and follow-up compliance.

Two deliberate choices: a rate with nothing to divide by reports *no data*
rather than `0%`, and the industry benchmarks shown alongside are labelled as
benchmarks, never mixed into your figures.

Run a pilot the honest way: measure the first week before changing anything,
then compare. `GET /api/reports/performance.csv` exports the daily series.

## Demo dataset (optional)

Load a story-driven dataset (customers, RFQs in every status, a paused quote
approval, an in-transit booking with documents and an open issue, a follow-up
due today) so every page has something to show:

```bash
docker compose exec backend python -m app.demo_data
```

Idempotent — running it twice does nothing. See `DEMO.md` for a scripted
5-minute walkthrough.

## Project layout

```
backend/    FastAPI app, SQLAlchemy models, LangGraph agents, Celery workers
frontend/   Next.js dashboard
docker-compose.yml
.env.example
Start System.bat
```

See `backend/README.md` and `frontend/README.md` for per-service details.

## Local development (without Docker)

You can run services individually — see `backend/README.md` for the backend
(needs a local Postgres + Redis) and `frontend/README.md` for the dashboard.

## Testing & CI

- `backend: pytest` — unit suite (no DB needed; integration auto-skips). Covers
  MIME parsing, credential encryption, tenant-scoped file storage, and the IMAP
  client against an in-process IMAP server that asserts the mailbox is never
  modified.
- `RUN_INTEGRATION=1 pytest tests/integration` — full HTTP flow against a live
  Postgres (self-bootstrapping: migrates + creates the admin), including email
  ingestion end to end with an injected fake mailbox and the cross-tenant
  isolation suite.
- GitHub Actions runs unit, integration (Postgres+Redis services), and the
  production frontend build on every push.
- Daily `pg_dump` backups are written to `storage/backups/` (worker keeps the
  newest 14).

## Path to SaaS

It runs perfectly well as a single-company install, but the foundation for a
hosted multi-customer deployment is in place rather than deferred:

- **Multi-tenancy is enforced by construction.** Every tenant-scoped table
  carries `org_id`, and a SQLAlchemy `do_orm_execute` listener filters *every*
  select — including relationship loads — by the active organization
  (`backend/app/core/tenancy.py`). Inserts without an organization are refused
  rather than written. Per-route filtering was rejected deliberately: in a SaaS,
  one forgotten `WHERE` is a cross-customer breach. A dedicated suite
  (`tests/integration/test_tenant_isolation.py`) attacks this on every route
  shape.
- **Self-serve signup** creates the organization and its first admin; reference
  numbers restart at 1 per organization so nobody sees our total volume.
- **PostgreSQL** (not SQLite) with Alembic migrations from day one, written
  defensively so both fresh installs and existing databases converge on the
  same schema.
- **Per-tenant background work** — Celery jobs iterate organizations and scope
  each pass explicitly, since a worker has no request context.
- **Durable agent state in Postgres** (LangGraph checkpointer) — paused
  approvals survive restarts and load-balanced instances.
- **Secrets encrypted at rest** (mailbox credentials, Fernet) with a rotatable
  key.
- Per-provider LLM abstraction — keys and models are environment config.

Still open, tracked honestly: role enforcement across endpoints and an audit
trail, per-lane rate reuse, a published extraction-accuracy number measured on
real customer emails, and a production deployment guide with TLS.

## Safety & control rules

- Connected mailboxes are **read-only**. Mail is never sent, deleted, moved or
  marked as read.
- The AI **never** auto-sends emails, quotes, or commitments.
- Pricing, margin, contractual terms, DG decisions and shipment commitments
  require explicit human approval (enforced via human-in-the-loop interrupts in
  the agent graphs).
- Every AI output is editable before it is saved, copied, or used.

## License

Private / internal use.
