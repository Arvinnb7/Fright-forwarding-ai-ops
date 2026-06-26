# Freight AI Ops — Frontend

Next.js (App Router) + TypeScript + Tailwind CSS dashboard.

## Run with Docker

It is started automatically by the root `docker compose up`. The dashboard is
served at <http://localhost:3000> and talks to the backend at the URL in
`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

## Local development

```bash
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` if your backend is not on `localhost:8000`.

## Structure

```
app/          App Router pages (dashboard, and future modules)
components/   Reusable UI (Sidebar, StatCard, StatusBadge, ...)
lib/          API client and shared types
```

## Conventions

- Every AI output is shown as an editable draft before it is saved or copied.
- Status is shown with badges; tables are dense but readable (B2B dashboard).
