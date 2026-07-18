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
    seed.py                    seeds 1 sample spec + 4 dealer personas (from vertical.json)
    api.py                     FastAPI routers: CRUD endpoints for specs/dealers/calls/quotes
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

See `../CLAUDE.md` for the full K1–K12 work breakdown. Currently done: K1 (vertical config), K2 (Supabase schema + FastAPI data layer).
