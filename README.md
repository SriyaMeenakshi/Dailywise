# Daywise

*Your day. Your priorities. Your progress.*

An AI-assisted personal productivity workspace, built in four phases. The full README (screenshots,
deployment, roadmap) is written in Phase 4. This is the Phase 1 setup guide.

**Status:** Phase 1 (foundation, auth, task management). No AI features yet.

## Prerequisites

* Node.js 20+ and npm
* Python 3.11+
* A free [Supabase](https://supabase.com) project (Auth + Postgres)

## Setup

### 1. Supabase
Create a project, then collect: the project URL, the anon/publishable key, and the Postgres
connection string (Project Settings → Database). For quick local testing, you may turn off
"Confirm email" under Authentication → Providers → Email.

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in DATABASE_URL and SUPABASE_URL
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local    # then fill in the Supabase URL and anon key
npm run dev
```
Open http://localhost:3000.

## Tests and checks

```bash
cd backend && pytest
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

## Environment variables

| Where | Name | Notes |
| --- | --- | --- |
| frontend | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | public by design |
| frontend | `NEXT_PUBLIC_API_URL` | defaults to `http://localhost:8000` |
| backend | `DATABASE_URL` | `postgresql+psycopg://…`; defaults to a local SQLite file for dev |
| backend | `SUPABASE_URL` | used to verify token issuer and fetch signing keys |
| backend | `SUPABASE_JWT_SECRET` | only for legacy HS256 projects |
| backend | `ALLOWED_ORIGINS` | comma-separated CORS origins |
| backend | `GEMINI_API_KEY`, `AI_MODEL` | reserved for Phase 3 |

Never commit `.env` files. Never put the service-role key or any AI key in a `NEXT_PUBLIC_` variable.

See [docs/architecture.md](docs/architecture.md) for the design.
