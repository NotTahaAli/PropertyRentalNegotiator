# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required skills

Always work with these active — not optional:

- **caveman** — ultra-compressed communication. Terse output, full technical substance, no filler. Code/commits/PRs written normal.
- **ponytail** — laziest working solution. Climb the ladder: skip it (YAGNI) → reuse existing → stdlib → native platform → installed dep → one line → minimum code. No unrequested abstractions.
- **superpowers** — invoke matching process skills before acting: `superpowers:brainstorming` before creative/feature work, `superpowers:systematic-debugging` before bug fixes, `superpowers:test-driven-development` before implementation, `superpowers:verification-before-completion` before claiming done.

## Project

"The Negotiator" — hackathon project (Hack-Nation Challenge 01, ElevenLabs). Voice agents call Pakistani property dealers about commercial shop rentals, extract itemised rent quotes, leverage bids against each other, and produce a ranked report with transcript citations. Full plan: `docs/negotiator-implementation-plan.html` — read it before making architectural decisions; it is the source of truth.

The repo is greenfield: `frontend/` is a scaffold. `backend/` is a uv-managed Python package (`src/app/`) — run tests with `cd backend && uv run pytest`.

## Status — work breakdown (K1–K12)

Keep this table and `docs/negotiator-implementation-plan.html`'s status fact tile + §05 Work Breakdown Status column in sync, always. The instant a K-component is finished (tests pass, committed), update its row here, update its row in the HTML table, and update the HTML status fact tile — same commit as the work. Never let this go stale.

| # | Component | Status |
| --- | --- | --- |
| K1 | vertical.json schema + shop_rental config | **Done** — `backend/config/vertical.json`, `backend/src/app/vertical.py` |
| K2 | Supabase schema + FastAPI data layer | Not started |
| K3 | Agent factory script | Not started |
| K4 | Tool webhooks ×4 | Not started |
| K5 | Agent-to-agent audio bridge | Not started |
| K6 | Doc parser | Not started |
| K7 | Benchmark service | Not started |
| K8 | Intake UI | Not started |
| K9 | Call Center UI | Not started |
| K10 | Report generator + UI | Not started |
| K11 | Red-flag engine | Not started |
| K12 | Demo assets | Not started |

## Locked decisions — do not re-litigate

- Vertical: commercial shop rental, Pakistan. Everything vertical-specific lives in `vertical.json` (config, not code); an agent factory script generates all ElevenLabs agent prompts from it.
- Stack: FastAPI backend (Render free tier) + Next.js frontend (Vercel free tier) + Supabase Postgres. ElevenLabs Agents for all voice; web audio only (WebSocket/WebRTC) — no Twilio/PSTN.
- English only. Free tiers only (keys: ElevenLabs, OpenAI, Tavily).
- Frontend never talks to Supabase directly — all reads/writes go through FastAPI (keys stay server-side).
- Benchmarks: Tavily live search at intake with a 3s timeout, falling back to hand-checked `benchmark_fallback` values in config. Never fetch benchmarks per-call.

## Architecture

Three-beat pipeline, one shared JSON spec:

1. **Estimator** (intake): voice interview via ElevenLabs widget + doc upload (rent agreement / requirements). Both paths emit the same JSON job spec, validated by a pydantic model generated from `vertical.json`'s `spec_schema`. User confirms before any call.
2. **Caller**: Negotiator agent calls each dealer (4 counter-agent personas: stonewaller, lowballer, upseller, firm — or a human role-playing). Logs itemised quotes mid-call via tool webhooks.
3. **Closer**: second-round calls using leverage from logged bids; red-flag engine screens quotes; report ranks by `total_first_year` with transcript citations like `[call 3, line 41]`.

### Supabase schema (keep it this small)

```
specs   (id, created_at, vertical, status, spec_json jsonb, benchmark_json jsonb, confirmed bool)
dealers (id, spec_id, name, persona, phone_label, source)
calls   (id, spec_id, dealer_id, round int, status, started_at, ended_at,
         recording_url, transcript_json jsonb, outcome)
quotes  (id, call_id, dealer_id, monthly_rent, advance_months, commission, maintenance,
         annual_increment_pct, other_fees jsonb, total_first_year, binding, notes, flagged, flag_reason)
```

`total_first_year` = 12×rent + advance + commission + 12×maintenance + other fees — the single comparison key that makes incomparable fee structures comparable.

### Agent tools (webhooks → FastAPI)

- `log_quote` — writes itemised quote row mid-call; validates against fee taxonomy.
- `get_leverage` — returns best *real* logged bids for the spec; empty if none exist.
- `check_redflag` — quote vs benchmark; may return `confirm_then_flag` (agent asks scope question live on the call).
- `get_benchmark` — cached Tavily result for the spec's location.

### The honesty guardrail (core product thesis — never weaken it)

The Negotiator has no free-text knowledge of other bids. Its **only** source of leverage is `get_leverage`, which returns real quotes logged in Supabase. No bids logged → tool returns nothing → agent negotiates on fees/terms instead. Fabricating a competing bid must remain architecturally impossible, not merely prompted against. Do not add competing-bid info to prompts or contexts by any other path.

### Red-flag rules (config-driven, from `vertical.json`)

Quote 30%+ below benchmark → confirm scope live on-call, flag in report, never auto-rank #1. Also flag: no written quote, advance > 6 months.

### Agent-to-agent audio bridge

Highest-risk component: FastAPI asyncio task cross-pipes two ElevenLabs conversation WebSockets (Negotiator ↔ Dealer persona), saves mixed audio, streams it to the browser. Fallback if it fails: role-play mode — a human answers as the dealer via the same widget used for intake. The demo must never depend on the bridge working.

## Constraints

- Render free tier sleeps after 15 min idle — backend health endpoint must be registered on cron-job.org pinger at deploy time.
- ElevenLabs credits are finite: cap test conversations at 2–3 min, prefer text-mode agent testing for prompt iteration.
- Scope discipline: nothing stretch (Urdu, Twilio, Zameen scraping) starts before a recorded end-to-end demo exists. "A connected loop beats a polished fragment."
