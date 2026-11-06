# Daywise architecture (Phase 1)

```
Browser (Next.js, App Router)
  ├─ Supabase Auth (email + password) ──► Supabase: issues a signed JWT
  └─ fetch + "Authorization: Bearer <jwt>" ──► FastAPI ──► PostgreSQL (Supabase)
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `frontend/` | Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui |
| `backend/app/core` | Settings (env vars) and JWT verification |
| `backend/app/db` | SQLAlchemy engine, session, `Base` |
| `backend/app/models` | `User`, `Category`, `Task` |
| `backend/app/schemas` | Pydantic request/response models (validation lives here) |
| `backend/app/services` | Business logic (task queries, user provisioning) |
| `backend/app/api` | Thin FastAPI routers and the `get_current_user` dependency |
| `backend/alembic` | Migrations |
| `backend/tests` | pytest suite (SQLite in memory, signed test JWTs) |

## Authentication and data ownership

1. The browser signs in with Supabase Auth and receives a JWT.
2. Every API call carries it as a bearer token. The backend verifies the signature (JWKS for
   asymmetric signing keys, or `SUPABASE_JWT_SECRET` for legacy HS256 projects), expiry,
   audience (`authenticated`) and issuer.
3. `get_current_user` turns the verified `sub` claim into the application user, creating the
   profile and default categories on first sight.
4. **No endpoint accepts a user id from the client.** Every query filters by the verified id, and
   category ids on tasks are checked for ownership. Other users' rows return 404.
5. On Postgres the initial migration also enables row-level security with owner policies, as
   defense in depth in case Supabase's Data API is ever used.

## Frontend

* `proxy.ts` (Next.js 16's replacement for middleware) refreshes the Supabase session cookie,
  verifies it with `getClaims()`, and redirects between `/login` and the signed-in pages.
* `WorkspaceProvider` loads profile, categories and tasks once, and applies **optimistic**
  updates with rollback and toast on failure. Search, filter and sort run client-side.
* Design tokens (colour, radius, shadow, type scale) are in `src/app/globals.css`.

## Phase 2: projects, dependencies and priority

* **Priority engine** (`services/priority.py`) is pure Python with no database, network or AI:
  `P = 0.25·importance + 0.20·urgency + 0.25·deadline risk + 0.20·impact + 0.10·blocking`, every
  factor normalised to 0-100. Weights are per-user (`user_preferences`), validated and rescaled to
  sum to 1. Overdue = risk 100; no deadline = 15; finished tasks score 0 and are not ranked.
  A manual override (0-100) replaces the score but the calculated score and factors are kept, and
  the explanation states both.
* **Stored, but always fresh.** `priority_score`, `priority_computed` and `priority_factors` are
  persisted on `tasks` (`services/priority_store.py`). Deadline risk depends on the clock, so every
  read recomputes before returning or sorting and writes back only what changed.
* **Dependencies** (`task_dependencies`) form a graph; cycles and self-dependencies are rejected.
  Waiting on unfinished tasks is reported, not penalised. The blocking factor rewards tasks that
  unblock others.
* **Progress** (`services/progress.py`) weights tasks by estimated effort; unestimated tasks count
  as 30 minutes and are reported. Subtasks give partial credit to an unfinished task.
* **History** (`task_logs`) records creation, status/field changes, subtask and dependency events.
* Response datetimes are always UTC-aware (`schemas/common.py`) so browsers never guess a zone.

## Phase 3: AI gateway and the daily planner

**The app never depends on the model.** Tasks, priorities, projects, progress and the planner use no
AI. When the key is missing or the provider is down, AI screens say so and everything else works.

**Gateway (`app/ai/`)**, the only code that talks to a model:

| Module | Role |
| --- | --- |
| `ai_gateway.py` | Orchestrates every call (order below) |
| `providers/gemini.py` | The only Gemini-specific code; `providers/base.py` is the interface others implement |
| `model_router.py` | Economical model by default; optional stronger model for project breakdown |
| `prompt_manager.py` | Versioned prompts. The version is part of the cache key and every usage log |
| `cache_manager.py` | Per-user cache of validated output (`ai_cache`), keyed by feature, prompt version, model, input |
| `usage_tracker.py` | Per-user daily request/token quotas; tokens, estimated cost, model, prompt version in `ai_usage_logs` |
| `response_validator.py` | Strips code fences, parses JSON, validates with Pydantic |

Order of operations: reject oversized input → serve cache (free, works even with AI off) → refuse a
duplicate in-flight request → check quota → call the provider with exponential backoff on
rate-limit/timeout/5xx (a bad answer is retried too) → validate → cache → log.

**Suggestions only.** `parse-tasks` and `decompose-project` save nothing; the UI shows an editable
review and the user approves. `decompose-project/apply` creates the approved plan in one transaction
without calling the model. Guardrails after the model answers: deadlines are dropped if the note
never mentions a date, date-only deadlines become end of day in the user's timezone, estimates and
sizes are clamped, categories are matched to the user's own, and dependency loops are broken.

**Planner (`services/scheduler.py`)** is a pure function: availability window minus fixed/pinned
blocks gives free gaps; the earliest open time is filled with the best eligible task (priority,
nudged by energy), never before its prerequisites, with breaks between tasks. Tasks that do not fit
are reported with a reason. Deadlines stay separate from time blocks: a late block is flagged, not
moved. Blocks are stored as minutes from local midnight, so no timezone maths is needed.
Anything the user moves, completes or postpones is preserved when the day is recalculated.

## Decisions worth knowing

* **Cache Components is off.** Every signed-in screen is per-user and time-dependent, so there is
  nothing to prerender, and the feature rejects reading the current time at build time.
* **Native `<select>` for form fields.** Best behaviour on mobile and fully accessible.
* **Status/energy/recurrence are `VARCHAR` + CHECK constraints**, not Postgres enums, so later
  migrations stay simple.
* **SQLite is used only by tests** (foreign keys switched on to match Postgres behaviour).
  Application and migration behaviour on Postgres is the target.
* `projects`, `subtasks`, `task_dependencies`, `task_logs` and the AI tables arrive in later
  phases as new migrations; `tasks.project_id` is added with `projects`.
