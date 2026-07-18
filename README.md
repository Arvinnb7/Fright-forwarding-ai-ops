# Freight AI Ops

A private, **local-first AI operations system** for a Freight Forwarding Sales &
Operations Coordinator. It turns messy customer inquiries, partner replies,
quotes, follow-ups and shipment events into structured operational output — so
one person can operate like a highly organized commercial operations team.

The AI agents are orchestrated with **LangGraph**, the API is **FastAPI**, and the
dashboard is **Next.js**. The whole system runs on your own machine via Docker
Compose — no public server, no cloud required.

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
| Background jobs | Celery + Redis (follow-up reminders, reports, backups) |
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

- `backend: pytest` — unit suite (no DB needed; integration auto-skips).
- `RUN_INTEGRATION=1 pytest tests/integration` — full HTTP flow against a live
  Postgres (self-bootstrapping: migrates + creates the admin).
- GitHub Actions runs unit, integration (Postgres+Redis services), and the
  production frontend build on every push.
- Daily `pg_dump` backups are written to `storage/backups/` (worker keeps the
  newest 14).

## Path to SaaS

This ships as a local-first single-operator tool by design, but the
architecture was chosen so a multi-user cloud deployment is configuration, not
a rewrite:

- **PostgreSQL** (not SQLite) with Alembic migrations from day one.
- **JWT auth** with a users table — adding users/roles extends the existing
  model instead of introducing auth late.
- **Stateless API + Celery workers** — horizontal scaling is a compose/K8s
  concern, not a code change.
- **Durable agent state in Postgres** (LangGraph checkpointer) — paused
  approvals survive restarts and load-balanced instances.
- Per-provider LLM abstraction — keys and models are environment config.

The remaining productization items are tracked honestly: e-mail ingestion
(Gmail/Outlook), role-based access, extraction-accuracy evaluation on real
customer emails, and a cloud deployment guide.

## Safety & control rules

- The AI **never** auto-sends emails, quotes, or commitments.
- Pricing, margin, contractual terms, DG decisions and shipment commitments
  require explicit human approval (enforced via human-in-the-loop interrupts in
  the agent graphs).
- Every AI output is editable before it is saved, copied, or used.

## License

Private / internal use.
