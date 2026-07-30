# Deployment & runbook

Everything here has been kept to what one person can operate. A single VM with
Docker runs the whole system; there is no Kubernetes, no managed service
dependency, and nothing that needs a specialist to restart at 2am.

---

## 1. What you need

- A Linux VM with Docker Engine and the Compose plugin. **2 vCPU / 4 GB RAM /
  40 GB disk** is comfortable for a desk handling a few hundred enquiries a
  month. The database is small; the disk is mostly uploaded documents.
- A domain name with an **A record pointing at the VM's public IP**. Do this
  first — Caddy cannot obtain a certificate for a name that does not resolve.
- Ports **80 and 443** open. Nothing else needs to be reachable from outside,
  and Postgres and Redis are deliberately not published at all.
- An API key for your LLM provider.

## 2. Configure

```bash
git clone <your-fork> freight-ai-ops && cd freight-ai-ops
cp .env.example .env
```

Set these in `.env` — the stack refuses to start without the ones marked
required:

| Variable | Notes |
|---|---|
| `DOMAIN` | **Required.** e.g. `ops.yourcompany.com`, no scheme, no trailing slash |
| `ACME_EMAIL` | **Required.** Where Let's Encrypt sends expiry warnings |
| `SECRET_KEY` | **Required.** `openssl rand -hex 32`. Changing it logs everyone out |
| `POSTGRES_PASSWORD` | **Required.** `openssl rand -hex 24` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | The first administrator, created on first start |
| `MAILBOX_ENCRYPTION_KEY` | Encrypts stored mailbox credentials — see the warning below |
| `ANTHROPIC_API_KEY` | Or the key for whichever `LLM_PROVIDER` you set |

Generate the mailbox key explicitly rather than letting it derive from
`SECRET_KEY`, so the two can be rotated independently:

```bash
docker run --rm python:3.12-alpine sh -c \
  "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())'"
```

> ⚠️ **Rotating `MAILBOX_ENCRYPTION_KEY` makes stored mailbox passwords
> unreadable.** Nothing is lost except the credentials; each mailbox simply
> needs its password re-entered. Rotating `SECRET_KEY` invalidates every login
> token. Neither is destructive, but do them deliberately.

## 3. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

On first start the API container runs the migrations and creates the
administrator, then begins serving. Caddy requests a certificate as soon as the
domain resolves to this host.

```bash
docker compose -f docker-compose.prod.yml ps          # all healthy?
docker compose -f docker-compose.prod.yml logs -f caddy   # certificate issued?
curl https://$DOMAIN/api/health
```

Then sign in at `https://$DOMAIN` and **change the administrator password**.

## 4. Verify it actually works

```bash
# The real provider path (costs a few cents):
docker compose -f docker-compose.prod.yml exec backend python -m app.smoke_llm

# The extraction harness (free, no API key):
docker compose -f docker-compose.prod.yml exec backend python -m app.eval_extraction --stub
```

Then connect the mailbox under **Settings → Mailbox** and press **Check now**.
If mail arrives but nothing appears, the answer is in the worker log.

---

## Routine operations

### Upgrading

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on the API container before it serves. **Take a
backup first** (below) — a migration is the one routine operation that can lose
data if it goes wrong.

### Backups

A `pg_dump` runs nightly at 02:00 UTC into the `storage` volume
(`storage/backups/`), keeping the newest 14. That protects against mistakes
inside the database, **not** against losing the VM.

Copy them off the machine — this is the step people skip:

```bash
# From the VM, to wherever you keep backups:
docker compose -f docker-compose.prod.yml exec backend \
  ls -lh storage/backups
docker cp $(docker compose -f docker-compose.prod.yml ps -q backend):/app/storage/backups ./backups
```

Uploaded documents live in the same `storage` volume and are **not** in the
database dump. Back up the whole volume, not just the dumps.

### Restoring

```bash
docker compose -f docker-compose.prod.yml stop backend worker
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U freight -d freight_ai_ops --clean --if-exists < backup.dump
docker compose -f docker-compose.prod.yml start backend worker
```

Practise this once on a throwaway VM before you need it. A backup that has
never been restored is a hypothesis.

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker   # mailbox polling lives here
```

Logs are structured JSON in production (`APP_ENV=production`), so they can be
shipped to any log service without reformatting.

---

## When something is wrong

| Symptom | Where to look |
|---|---|
| Certificate not issued | `logs caddy`. Almost always DNS not yet pointing at this host, or port 80 blocked |
| Dashboard loads, API calls fail | `DOMAIN` must match the `NEXT_PUBLIC_API_BASE_URL` the frontend was **built** with. Rebuild the frontend after changing the domain |
| Mail not being read | `logs worker`; then **Settings → Mailbox → Test connection**. `last_error` on the mailbox row records the last failure |
| "Refusing to persist … without an organization" | A background job ran without a tenant scope. This is a bug, not a misconfiguration — the guard is doing its job |
| Everything is slow | `docker stats`. Postgres is the usual answer; give the VM more RAM before anything else |
| Disk full | Uploaded documents and old backups. `storage/backups` keeps 14 dumps; the rest is customer files |

## Before you scale beyond one node

The worker runs Celery **beat inside the worker process**. That is correct for
one node and wrong for two: each replica would run its own scheduler and every
mailbox would be polled once per replica. Before adding a second worker, split
beat into its own single-replica service:

```yaml
  beat:
    <<: *worker-base
    command: celery -A app.workers.celery_app.celery_app beat --loglevel=info
  worker:
    command: celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

The API itself is stateless and can be replicated freely — paused quote
approvals live in Postgres via the LangGraph checkpointer, not in process
memory, so a request can be served by any instance.

## Security notes

- Postgres and Redis are not published to the host. Reach them through
  `docker compose exec`, not an exposed port.
- Mailbox credentials are encrypted at rest; mailbox access is read-only and
  the system never sends, deletes or flags mail.
- Uploaded files are stored per organization and reads verify the owning
  organization, so a tampered path cannot cross tenants.
- The API sends `X-Content-Type-Options: nosniff` on downloads and Caddy adds
  HSTS, `X-Frame-Options` and a referrer policy.
- Deactivating a user invalidates their existing token immediately.
- There is **no** rate limiting on the login endpoint yet. If this is exposed to
  the public internet rather than a company VPN, put a rate limiter in front of
  `/api/auth/login` before onboarding real customers.
