# backend

FastAPI + Supabase backend for **The Negotiator** (Hack-Nation Challenge 01, ElevenLabs). Full product plan lives in [`../docs/negotiator-implementation-plan.html`](../docs/negotiator-implementation-plan.html); component status is tracked in [`../CLAUDE.md`](../CLAUDE.md).

## Tech stack

- **Python 3.12**, managed with [uv](https://docs.astral.sh/uv/)
- **FastAPI** + **uvicorn[standard]** — HTTP API
- **Pydantic v2** — vertical config validation, generated spec models, request bodies
- **Supabase** (`supabase-py`) — Postgres data layer, service-role key (backend-only, RLS bypassed)
- **python-dotenv** — loads `backend/.env` for local dev
- **pytest** — test suite (`fastapi.testclient.TestClient` for API tests)
- Deploy target: Render free tier (not yet wired)

## Structure

```text
backend/
  config/vertical.json       vertical config (K1) — spec schema, fee taxonomy, red flags, agent prompts
  supabase/
    config.toml               supabase CLI project config
    migrations/                SQL migrations, applied with `supabase db push`
  src/app/
    vertical.py                loads vertical.json, builds pydantic Spec model from spec_schema
    db.py                      cached Supabase client (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
    crud.py                    create/get/list helpers for specs, dealers, calls, quotes
    seed.py                    seeds 1 sample spec + 4 dealer personas for a given user (from vertical.json)
    auth.py                    verifies a Supabase Auth JWT via JWKS, returns the caller's user id
    api.py                     FastAPI routers: CRUD endpoints for specs/dealers/calls/quotes, ownership-enforced
    main.py                    FastAPI app, mounts routers, /health endpoint
  tests/                       pytest suite (mocked Supabase client, no live DB needed)
  .env.example                 required env vars (placeholders)
```

## Setup

```bash
cd backend
uv sync
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

`.env` is gitignored and additionally blocked from being read by Claude Code (`.claude/settings.json` deny rules + `CLAUDE.md`) — see `.env.example` for the required keys.

## Database

Schema lives in `supabase/migrations/`, one table per row of the CLAUDE.md schema block: `specs`, `dealers`, `calls`, `quotes`.

```bash
supabase link --project-ref <your-project-ref>   # once, needs Supabase login
supabase db push                                  # applies migrations to the linked project
uv run python -m app.seed                         # inserts 1 sample spec + 4 dealer personas
```

`crud.py` currently exposes `create`/`get`/`list` only. `update`/`delete` for `quotes`/`calls` are added by K4 (tool webhooks) and K11 (red-flag engine), which are the first consumers that need them.

Every `specs` row has a `user_id` — see Auth below for how that's enforced.

## Auth

FastAPI verifies Supabase Auth JWTs via the project's JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) — no shared secret to manage, just `SUPABASE_URL`. Every request to `/specs`, `/dealers`, `/calls`, `/quotes` needs `Authorization: Bearer <supabase-access-token>`; `/health` is the only public route. Ownership: `specs` are scoped directly by `user_id`; `dealers`/`calls` are scoped through their `spec_id`'s owner; `quotes` through their `call_id`'s call's spec owner. Non-owned resources 404 (not 403 — existence isn't confirmed to other tenants).

There's no frontend login UI yet (frontend is still an empty scaffold). To get a token today:

```python
from app.db import get_client
client = get_client()
session = client.auth.sign_in_with_password({"email": "...", "password": "..."})
print(session.session.access_token)
```

## Running the API

```bash
uv run uvicorn app.main:app --reload
```

Serves at `http://127.0.0.1:8000`. `GET /health` for the Render pinger; `POST`/`GET /specs`, `/dealers`, `/dealers?spec_id=`, `/calls`, `/calls?spec_id=`, `/quotes`, `/quotes?call_id=`, plus `GET /{resource}/{id}` (404 if missing). Frontend talks to these, never to Supabase directly. Interactive docs at `/docs`.

## Running tests

```bash
uv run pytest
```

Data-layer tests mock the Supabase client; API tests use `fastapi.testclient.TestClient` with `crud` mocked — no live project or network access required for `uv run pytest`.

## Status

See `../CLAUDE.md` for the full K1–K13 work breakdown. Currently done: K1 (vertical config), K2 (Supabase schema + FastAPI data layer), K13 backend (Supabase Auth verification + per-user ownership — frontend signup/login pages not started).
