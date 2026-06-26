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

## Safety & control rules

- The AI **never** auto-sends emails, quotes, or commitments.
- Pricing, margin, contractual terms, DG decisions and shipment commitments
  require explicit human approval (enforced via human-in-the-loop interrupts in
  the agent graphs).
- Every AI output is editable before it is saved, copied, or used.

## License

Private / internal use.
