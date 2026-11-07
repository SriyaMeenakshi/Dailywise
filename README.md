# Daywise

*Your day. Your priorities. Your progress.*

Daywise is a calm, AI-assisted personal productivity workspace. Capture everything you need to do,
see what deserves your attention today, break big goals into projects, plan a realistic day, and
reflect on what you actually got done.

It is built so that **the AI is optional**. Task management, priorities, project progress, the daily
planner and analytics are deterministic code. Gemini only adds two *suggestion* features
(capturing tasks from free text, and drafting project breakdowns), and nothing it suggests is saved
until you approve it.

## Features

| Area | What it does |
| --- | --- |
| **Tasks** | Quick capture (one line, Enter) or detailed entry: category, project/phase, importance, urgency, impact, deadline, estimate, actual time, energy, recurrence, notes. Search, filter, sort. |
| **Priority engine** | `P = 0.25·importance + 0.20·urgency + 0.25·deadline risk + 0.20·impact + 0.10·blocking`, every factor 0–100. Handles overdue, missing deadlines, dependencies and finished tasks. Weights are yours to change. Every score is explained, and you can override it manually. |
| **Projects** | Phases, subtasks, dependencies (loops are rejected), milestones, an effort-weighted progress bar, remaining effort, and a deadline timeline. |
| **Daily planner** | Deterministic scheduler: your hours minus fixed commitments, filled with the best task that fits, respecting dependencies and energy, with breaks. Reorder, retime, complete, postpone, recalculate. Anything you move is kept. |
| **AI capture** | Free text → suggested tasks (categories, explicit deadlines, outcomes, optional estimates, clarifying questions). Review and edit before saving. |
| **AI project breakdown** | A goal → phases, milestones, tasks, subtasks, dependencies, estimates. Untick, edit, then approve. Capped at 60 tasks per breakdown. |
| **Insights** | Completed/pending/overdue, per-day completions, category progress, on-time rate, estimate-vs-actual accuracy, project completion. Computed only from your own tasks. |
| **End-of-day review** | The facts of your day (completed, still due, blocked, top priorities next) beside four reflection prompts. |
| **AI cost controls** | Per-user daily request and token limits, response caching, duplicate-request prevention, retry with backoff, token/cost/model/prompt-version logging, and a live usage panel. |

## Screenshots

Screenshots are not committed yet. The interface changed through every phase and I would rather not
ship pictures that no longer match. To add them: run the app locally, capture the dashboard, task
list, planner, project page and insights, save them under `docs/screenshots/`, and link them here.

## Architecture

```
Browser (Next.js App Router)
  ├─ Supabase Auth ──► JWT
  └─ fetch + Bearer JWT ──► FastAPI ──► PostgreSQL (Supabase)
                               └─ AI gateway ──► Gemini (optional)
```

- **Frontend:** Next.js 16, TypeScript, Tailwind v4, shadcn/ui (Base UI), React Hook Form + Zod,
  Recharts, Framer Motion, Lucide.
- **Backend:** FastAPI, Pydantic, SQLAlchemy 2, Alembic. Business rules live in `services/`; routers
  are thin; the priority engine, progress and scheduler are pure functions with no I/O.
- **Auth and ownership:** the backend verifies the Supabase JWT (signature, expiry, audience,
  issuer) and takes the user id *only* from it. Every query is scoped to that id. Row-level security
  policies are also created on Postgres as defence in depth.
- **AI:** one gateway (`backend/app/ai/`) is the only code that talks to a model, with provider code
  isolated so another provider can be added without touching business logic.

See [docs/architecture.md](docs/architecture.md) for the details and design decisions.

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- A free [Supabase](https://supabase.com) project (Auth + Postgres)
- Optional: a Gemini API key, for the two AI suggestion features

## Local setup

### 1. Supabase
Create a project and note: the **project URL**, the **anon/publishable key**, and the **Postgres
connection string** (Project Settings → Database; the *session pooler* string works everywhere).
Change the scheme to `postgresql+psycopg://`. For quick local testing you may turn off
*Authentication → Providers → Email → Confirm email*.

### 2. Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # fill in DATABASE_URL and SUPABASE_URL (see below)
alembic upgrade head              # creates the schema
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local        # fill in the Supabase URL and anon key
npm run dev                       # http://localhost:3000
```

## Environment variables

**Frontend** (`frontend/.env.local`), public by design:

| Name | Purpose |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase sign-in |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL (default `http://localhost:8000`) |

**Backend** (`backend/.env`), see `backend/.env.example` for the full annotated list:

| Name | Purpose |
| --- | --- |
| `APP_ENV` | `development` or `production`. Production refuses to start with SQLite, a missing `SUPABASE_URL`, or localhost/wildcard CORS origins, and hides the API docs. |
| `DATABASE_URL` | `postgresql+psycopg://…`. Defaults to a local SQLite file for development only. |
| `SUPABASE_URL` | Used to verify token issuer and fetch signing keys (JWKS). |
| `SUPABASE_JWT_SECRET` | Only for legacy projects that sign tokens with a shared HS256 secret. |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins allowed by CORS. |
| `GEMINI_API_KEY` | Optional. Leave empty to run without AI. **Server-side only.** |
| `AI_MODEL`, `AI_MODEL_COMPLEX` | Economical model for parsing; optional stronger model for breakdown. Check the names exist for your key. |
| `AI_DAILY_REQUEST_LIMIT`, `AI_DAILY_TOKEN_LIMIT` | Per-user daily allowance (UTC day). Cache hits are free. |
| `AI_PRICE_INPUT_PER_MTOK`, `AI_PRICE_OUTPUT_PER_MTOK` | Your provider's USD per million tokens. Left at 0, cost tracking is off rather than invented. |

Never commit `.env` files, and never put an AI key or a Supabase service-role key in a
`NEXT_PUBLIC_` variable.

## Database

```bash
cd backend
alembic upgrade head      # apply all migrations
alembic downgrade -1      # undo the latest
alembic revision --autogenerate -m "describe change"   # after editing models; review the file
alembic check             # fails if the models and migrations disagree
```

Migrations: `0001` users/categories/tasks · `0002` projects, phases, subtasks, dependencies,
history, priority · `0003` AI cache/usage, planner blocks, preferences · `0004` daily reviews.
On Postgres they also enable row-level security with owner policies.

## Commands

| Where | Command | Does |
| --- | --- | --- |
| `backend` | `uvicorn app.main:app --reload` | Run the API |
| `backend` | `pytest` | 295 tests (SQLite in memory, signed test JWTs, mocked AI) |
| `frontend` | `npm run dev` / `build` / `start` | Develop, build, serve |
| `frontend` | `npm run lint` | ESLint |
| `frontend` | `npm run typecheck` | `tsc --noEmit` |
| `frontend` | `npm test` | 57 component and unit tests (Vitest + Testing Library) |

## Testing notes

- Backend tests never call Gemini. A scripted fake provider covers success, caching, quotas,
  invalid JSON, rate limits with backoff, timeouts and duplicate requests. The Gemini adapter is
  tested against a mocked HTTP transport.
- A sweep test walks every endpoint in the OpenAPI schema and asserts it rejects missing or invalid
  credentials, so a new endpoint cannot silently skip auth. Another applies migrations up and down
  and checks they match the models.
- If Vitest or the Next.js build crashes with out-of-memory errors on a small machine, close other
  apps; the configs already cap worker counts.

## Deployment

1. **Supabase.** Create the project (above). Under *Authentication → URL Configuration* set the Site
   URL to your Vercel URL and add it to the redirect URLs.
2. **API on Render.** *New → Blueprint*, pick this repo (it reads `render.yaml`, which builds
   `backend/Dockerfile`). Fill in the secrets Render asks for: `DATABASE_URL`, `SUPABASE_URL`,
   `ALLOWED_ORIGINS` (your Vercel URL), and optionally `GEMINI_API_KEY`. The container runs
   `alembic upgrade head` and then serves; `/health` is the health check. Any host that runs a
   container or `uvicorn` works the same way.
3. **Frontend on Vercel.** Import the repo, set the *Root Directory* to `frontend`, and add
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `NEXT_PUBLIC_API_URL` (the Render
   URL). Deploy, then confirm `ALLOWED_ORIGINS` on the API matches the Vercel URL exactly.
4. **Check.** Sign up, add a task, open the planner. If sign-in works but data does not load, the
   cause is nearly always CORS (`ALLOWED_ORIGINS`) or a wrong `NEXT_PUBLIC_API_URL`.

## Known limitations

- Not yet exercised against a live Supabase project or the real Gemini API; development used
  SQLite, a stand-in auth server, and mocked/stand-in AI.
- The Dockerfile and `render.yaml` are written but unbuilt here (Docker was not available).
- The planner never splits a task: one longer than your longest free gap is reported, not scheduled.
- Duplicate-AI-request protection is per server process; several instances would need a shared lock.
- No password reset, social login, notifications, calendar sync or offline mode.
- Recurrence is stored but does not yet create the next occurrence.

## Roadmap

- Recurring tasks that spawn their next instance
- Splitting long tasks across the day automatically
- Calendar import/export for fixed commitments
- Resource library attached to tasks (with verifiable links)
- Weekly review digest and trends over longer periods
- Additional AI providers behind the existing gateway
- Shared-lock duplicate prevention for multi-instance deployments
