# Multi-tenant auth (K13) — design

## Why

The data model had no concept of a user: any spec, dealer, call, or quote was globally visible to anyone who could reach the API. The product is meant to be a multi-user SaaS (signup/login, each user's specs private to them), not a single hackathon demo run. This also reframes the counter-agent personas: they are a testing/demo stand-in for calling real dealers by phone (Twilio, already a listed stretch item), not the permanent product design.

Still scoped to today's hackathon deadline and free-tier-only constraint — no new paid services, no rewrite of the shift board's hour-by-hour schedule (that's a snapshot of an already-past morning).

## Auth

- **Supabase Auth**, email + password.
- Frontend uses `supabase-js` directly against Supabase Auth (anon key — public-safe) for signup/login/session/refresh. This is a scoped exception to "frontend never talks to Supabase directly": that rule now applies to *data* (specs/dealers/calls/quotes still only reachable through FastAPI), not auth.
- FastAPI never trusts a client-supplied user id. Every data endpoint depends on `get_current_user_id`, which verifies the `Authorization: Bearer <jwt>` header against Supabase's JWT secret and extracts `sub` (the user's UUID).

## Data model

- `specs.user_id uuid not null references auth.users(id)` — one new column, one new migration (applied live as `20260718210604_specs_user_id.sql`, timestamp-named to match the Supabase CLI's convention). Does not touch the already-applied `20260718201325_init.sql`.
- `dealers`, `calls`, `quotes` get no `user_id` column. Ownership is inherited through `spec_id` / `call_id` chains — one root of truth, no duplicated ownership data to drift out of sync.

## Enforcement (closes a real cross-tenant leak)

Before this change, `list_specs()`/`list_dealers()`/etc. with no filter returned every tenant's rows. Fix, applied uniformly:

- `create_spec` sets `user_id` from the verified token, ignoring any client-supplied value.
- `list_specs` always scoped to the caller's `user_id` — no unscoped listing.
- `get_spec` 404s (not 403 — don't confirm existence of other tenants' rows) if the spec isn't owned by the caller.
- `dealers`/`calls` endpoints require `spec_id` and validate the caller owns that spec before reading or writing.
- `quotes` endpoints require `call_id` and validate the caller owns the call's spec (same chain-check).

## Product framing (docs only, no new calling code)

Everywhere the counter-agent personas (stonewaller/lowballer/upseller/firm) or human-roleplay fallback are described as *the* product mechanism, reword to: production vision is the Negotiator calling real dealer phone numbers (Twilio/PSTN — stretch item, not built today); the personas/roleplay are an explicit testing stand-in for that call, used because outbound PSTN calling isn't in today's scope.

## Component breakdown

New **K13 — Auth & multi-tenancy**. Backend half (migration, JWT verification dependency, ownership enforcement across `crud.py`/`api.py`) ships as part of this work. Frontend half (signup/login pages, session/token handling, route gating) is the remaining to-do, tracked under K13 and added to K8's and K9's "Needs" column (both need a logged-in user before they're useful).

## Testing

- `get_current_user_id`: missing header → 401; invalid/expired JWT → 401; valid JWT → returns the `sub` claim.
- Cross-tenant isolation: user A cannot read or write user B's spec/dealer/call/quote (404, not leaked via a different status code).
- Existing CRUD/API tests updated for the new required ownership checks (mocked JWT verification + mocked Supabase client, no live network needed for `uv run pytest`).
- Live verification pass against the real Supabase project before calling K13's backend half done, same bar as K2.

## Explicitly out of scope for today

- Building the actual frontend signup/login pages (frontend is still an empty scaffold — no framework/layout decisions made yet to build on).
- Real PSTN/Twilio dealer calling.
- RLS policies on the Postgres tables (FastAPI is the only DB client — service-role key bypasses RLS anyway; enforcement lives in the API layer, not the database).
- Teams/organizations — one user owns their own specs, no shared/multi-seat accounts.
