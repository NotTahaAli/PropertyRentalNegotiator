# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required skills

Always work with these active — not optional:

- **caveman** — ultra-compressed communication. Terse output, full technical substance, no filler. Code/commits/PRs written normal.
- **ponytail** — laziest working solution. Climb the ladder: skip it (YAGNI) → reuse existing → stdlib → native platform → installed dep → one line → minimum code. No unrequested abstractions.
- **superpowers** — invoke matching process skills before acting: `superpowers:brainstorming` before creative/feature work, `superpowers:systematic-debugging` before bug fixes, `superpowers:test-driven-development` before implementation, `superpowers:verification-before-completion` before claiming done.

## Project

"The Negotiator" — hackathon project (Hack-Nation Challenge 01, ElevenLabs). Voice agents call Pakistani property dealers about commercial shop rentals, extract itemised rent quotes, leverage bids against each other, and produce a ranked report with transcript citations. Full plan: `docs/negotiator-implementation-plan.html` — read it before making architectural decisions; it is the source of truth.

The repo is greenfield: `backend/` is a uv-managed Python package (`src/app/`) — run tests with `cd backend && uv run pytest`. `frontend/` is a Next.js app, no longer a bare scaffold — see K8 below.

## Status — work breakdown (K1–K13)

Keep this table and `docs/negotiator-implementation-plan.html`'s status fact tile + §05 Work Breakdown Status column in sync, always. The instant a K-component is finished (tests pass, committed), update its row here, update its row in the HTML table, and update the HTML status fact tile — same commit as the work. Never let this go stale.

| # | Component | Status |
| --- | --- | --- |
| K1 | vertical.json schema + shop_rental config | **Done** — `backend/config/vertical.json`, `backend/src/app/vertical.py` |
| K2 | Supabase schema + FastAPI data layer | **Done** — `backend/supabase/migrations/`, `backend/src/app/{db,crud,seed,api,main}.py`. 4 tables live, seeded (1 spec + 4 dealers), FastAPI app with `/health` + CRUD routes for specs/dealers/calls/quotes verified live. `crud.py`/`api.py` are create/get/list only; K4/K11 add update/delete for `quotes`/`calls`. No `update_spec`/PATCH route yet either — K6 (doc parser) and K8 (Intake UI) will need one to persist an edited/confirmed spec; known gap, deliberately not built until a caller needs it |
| K3 | Agent factory script | **Done** — `backend/src/app/agent_factory.py`, `backend/src/app/make_agents.py`. 4 webhook tools + 6 agents created live in ElevenLabs, idempotent via `backend/config/agents.generated.json` |
| K4 | Tool webhooks ×4 | **Done** — `backend/src/app/tools.py`, `backend/tests/test_tools.py`. `POST /tools/{log_quote,get_leverage,check_redflag,get_benchmark}` behind shared-secret header `X-Tools-Secret` (env `TOOLS_WEBHOOK_SECRET`, fail-closed; injected into ElevenLabs tool configs by `make_agents`). `log_quote` auto-runs config-driven red-flag rules at insert (`evaluate_red_flags`, reusable by K11); `get_leverage` returns ≤3 lowest `total_first_year` real quotes excluding flagged rows + the calling dealer's own (tool schema gained required `dealer_id`); `get_benchmark`/`check_redflag` read `specs.benchmark_json` else `benchmark_fallback` (K7 must cache `{per_sqft_low, per_sqft_high}` shape). `update_quote` deferred to K11. 132/132 tests green. **Live-verified** on Render against real Supabase rows: 401 without header; benchmark/redflag/log_quote/get_leverage all returned contract shapes; quote row written + returned as leverage to the other dealer only. Heads-up: data tables were empty at verify time (K2 seed gone, likely K13 migration) — re-run `seed.py` before next live call test |
| K5 | Agent-to-agent audio bridge | **Done, live-verified** — `backend/src/app/{bridge,storage,live}.py`, `api.py` `/calls/start` (bridge + roleplay modes), `/calls/{id}/stream`, `/calls/{id}/recording`, `/calls/{id}/transcript`. 76/76 `uv run pytest` green. Live-tested against real ElevenLabs agents + a real Supabase project (private `recordings` bucket created): confirmed real WS connect, audio relay, mixed-WAV upload with real audio, transcript capture, and structured outcome even when one side stays silent (silence guard). Three real bugs found and fixed by live testing: `start_call` had to become `async def` (bare `asyncio.create_task` has no event loop in FastAPI's sync-endpoint threadpool); dealer personas needed `platform_settings.overrides` enabling `first_message` override (ElevenLabs rejects unpermitted per-conversation overrides); and the dealer leg's suppressed `first_message` must be a single space `" "`, not `""` — an empty string never closes the agent's own turn, so it never starts listening for `user_audio_chunk` at all (silently dead connection, confirmed via isolated single-leg probes). First two are agent-level config (`make_agents.py` re-run live); the third is in `bridge._dealer_init()`. **Unresolved, needs follow-up (tracked in `TODO.md`):** even with a healthy, non-stuck connection (verified: dealer leg pings normally, its own turn is recorded), the `firm` persona still didn't produce a spoken reply to the negotiator's relayed audio within a 30s patient live probe — narrowed to specifically the audio-input path (text input to the same suppressed-init agent replies instantly and correctly, ruling out prompt/LLM/turn-state-after-suppression). Root cause not yet found (server-side VAD/ASR sensitivity to relayed synthetic audio vs. real mic input is the leading suspect); ElevenLabs docs don't cover ASR-input-format specifics. K4 endpoints built; full leverage/quote-logging path needs only K4 live wiring (`TODO.md`) plus this persona-reply fix |
| K6 | Doc parser | **Done** — `backend/src/app/parse.py`, `backend/tests/test_parse.py`. `POST /parse` (JWT-gated, stateless): PDF/PNG/JPEG sent to OpenAI (`gpt-5.4-mini`, structured outputs), DOCX text pulled via stdlib. Unknown fields omitted, never guessed — live-verified (blank image yields empty spec). Frontend `parseDoc` sends the bearer token (K13); Render needs `OPENAI_API_KEY` set |
| K7 | Benchmark service + dealer discovery | **Done** — `backend/src/app/benchmark.py`, `backend/tests/test_benchmark.py`. Both fire inside `POST /specs` (concurrent, best-effort, never block spec creation): `fetch_benchmark` Tavily-searches `benchmark_query` (httpx, 3s timeout, no SDK) and extracts `{per_sqft_low, per_sqft_high}` via OpenAI structured output (`gpt-5.4-mini`) into `specs.benchmark_json` (K4 cached-shape contract; body-provided value wins; None on any failure so tools fall back); `discover_dealers` Tavily-searches new config key `dealer_search_query`, extracts real dealer names, inserts rows `persona="human"`, `source="tavily"`, url in `phone_label`. Missing `TAVILY_API_KEY` fails soft (empty). New `PATCH /dealers/{id}` (persona only, config-validated + "human") + frontend persona dropdown on calls page so discovered dealers can be made bridge-callable; `/calls/start` bridge mode 422s on personas without an agent. 160/160 tests green. **Live Tavily/OpenAI run not yet verified** — needs `TAVILY_API_KEY` on Render + local (`TODO.md`) |
| K8 | Intake UI | **Done** — `frontend/app/intake/`, `frontend/components/intake/`. Voice wired live: `VoiceIntake.tsx` uses `@elevenlabs/react` (`ConversationProvider` + `useConversation`; v1.10 requires the provider — bare hook throws at SSR/prerender). Estimator agent has `set_spec_field` client tool (typed optional param per spec field, `expects_response: false`) + `end_call` system tool via `built_in_tools` (server needs `"type": "system"` discriminator; omit field entirely when unused, null is rejected). Fields stream into the form per answer; `onDisconnect` advances the step, so manual hang-up loses nothing. Mic click-through still pending (`TODO.md`) |
| K9 | Call Center UI | Not started — needs K13 for a logged-in user |
| K10 | Report generator + UI | Not started |
| K11 | Red-flag engine | **Done** — rules themselves live since K4 (`evaluate_red_flags` at `log_quote` insert). K11 added: `crud.update_quote`; `POST /specs/{id}/reflag` (JWT + ownership) re-runs `evaluate_red_flags` on every quote of a spec against current `benchmark_json` and may **unflag** (fresh verdict wins — fixes quotes judged on fallback or client-supplied `flagged` via `POST /quotes`, which never evaluates); `discover_dealers` now dedups names (case-insensitive, first wins), drops blanks, and prompt explicitly excludes portals/directories/news; DealerCard shows flagged badge (flag_reason as title) on quoted done-state. 169/169 tests green. No frontend reflag button yet (curl/K12 material) |
| K12 | Demo assets | Not started |
| K13 | Auth & multi-tenancy | **Done** — backend: `backend/src/app/auth.py`, `api.py` ownership checks, `backend/supabase/migrations/20260718210604_specs_user_id.sql`. Frontend: `frontend/app/(auth)/` login/signup, `frontend/components/auth/` (AuthProvider/Protected/AccountChip/NavAuth), supabase-js sessions, `/` + `/intake` route-guarded, API calls send Bearer token. Mock-mode verified + anon key probed live; full browser signup/login pass still to be clicked through |

Cross-component integration gaps that are blocked on secrets, live external calls, or an unbuilt K-component (not on missing understanding) live in `TODO.md`. Update it in the same commit as whatever resolves or adds an item — same rule as the table above, never let it go stale.

## Locked decisions — do not re-litigate

- Vertical: commercial shop rental, Pakistan. Everything vertical-specific lives in `vertical.json` (config, not code); an agent factory script generates all ElevenLabs agent prompts from it.
- Stack: FastAPI backend (Render free tier) + Next.js frontend (Vercel free tier) + Supabase Postgres. ElevenLabs Agents for all voice; web audio only (WebSocket/WebRTC) — no Twilio/PSTN.
- English only. Free tiers only (keys: ElevenLabs, OpenAI, Tavily).
- Frontend never talks to Supabase directly for data — all spec/dealer/call/quote reads/writes go through FastAPI (keys stay server-side). Auth (signup/login/session) is the one exception: frontend talks to Supabase Auth directly with the public anon key.
- Multi-tenant: Supabase Auth (email+password). Every spec has an owner (`specs.user_id`); FastAPI verifies the caller's JWT via JWKS and enforces ownership on every data endpoint.
- The 4 counter-agent personas (stonewaller, lowballer, upseller, firm) and the human-roleplay fallback are a testing/demo stand-in for calling real dealers by phone. Production vision is real outbound calls (Twilio/PSTN — already a listed stretch item, not built today); nothing about that changes today's implementation.
- Benchmarks: Tavily live search at intake with a 3s timeout, falling back to hand-checked `benchmark_fallback` values in config. Never fetch benchmarks per-call.

## Architecture

Three-beat pipeline, one shared JSON spec:

1. **Estimator** (intake): voice interview via ElevenLabs widget + doc upload (rent agreement / requirements). Both paths emit the same JSON job spec, validated by a pydantic model generated from `vertical.json`'s `spec_schema`. User confirms before any call.
2. **Caller**: Negotiator agent calls each dealer (4 counter-agent personas: stonewaller, lowballer, upseller, firm — or a human role-playing). Logs itemised quotes mid-call via tool webhooks.
3. **Closer**: second-round calls using leverage from logged bids; red-flag engine screens quotes; report ranks by `total_first_year` with transcript citations like `[call 3, line 41]`.

### Supabase schema (keep it this small)

```
specs   (id, created_at, vertical, status, spec_json jsonb, benchmark_json jsonb, confirmed bool, user_id uuid)
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
- `backend/.env` holds real secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ELEVENLABS_API_KEY`). Never read, cat, print, log, or otherwise surface its contents in any response, tool call, or file. Use `backend/.env.example` (placeholders only) as the reference for what keys exist. If a task seems to need the actual values, ask the user to paste what's needed instead of opening the file.
