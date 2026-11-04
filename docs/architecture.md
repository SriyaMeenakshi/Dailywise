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
