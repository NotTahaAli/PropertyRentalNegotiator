# backend

FastAPI + Supabase backend for **The Negotiator** (Hack-Nation Challenge 01, ElevenLabs). Full product plan lives in [`../docs/negotiator-implementation-plan.html`](../docs/negotiator-implementation-plan.html); component status is tracked in [`../CLAUDE.md`](../CLAUDE.md).

## Tech stack

- **Python 3.12**, managed with [uv](https://docs.astral.sh/uv/)
- **Pydantic v2** — vertical config validation, generated spec models
- **Supabase** (`supabase-py`) — Postgres data layer, service-role key (backend-only, RLS bypassed)
- **python-dotenv** — loads `backend/.env` for local dev
- **pytest** — test suite
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

## Running tests

```bash
uv run pytest
```

Tests mock the Supabase client — no live project or network access required.

## Status

See `../CLAUDE.md` for the full K1–K12 work breakdown. Currently done: K1 (vertical config), K2 (Supabase schema + data layer).
