# The Negotiator

**Voice agents that call, compare, and haggle — pick your market, never overpay again.**

Built for [Hack-Nation](https://hack-nation.ai)'s 6th Global AI Hackathon, Challenge 01 ("The Negotiator"), powered by [ElevenLabs](https://elevenlabs.io). Full challenge brief: [`docs/`](docs/1784382172163-01-ElevenLabs-The-Negotiator.docx.pdf).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Backend tests](https://img.shields.io/badge/backend%20tests-291%20passing-brightgreen)](backend/tests)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](backend/pyproject.toml)
[![Next.js 16](https://img.shields.io/badge/next.js-16-black)](frontend/package.json)

**Live demo:** backend [negotiator-backend.onrender.com](https://negotiator-backend.onrender.com) (Render, free tier — first request after idle may take ~30s to wake up) · frontend [negotiator-frontend-iota.vercel.app](https://negotiator-frontend-iota.vercel.app) (Vercel)

---

## The problem, and our vertical

The challenge brief opens with Daniel: real quotes for the same 45-mile move ranged from **$1,158 to $6,506** — a 5.6x spread for identical work — because nobody has the hours to call 5–8 companies, describe the same job every time, and negotiate. The same pattern holds in any phone-priced market.

**We picked commercial shop rentals in Pakistan** — a market that's just as opaque, just as phone-and-paper, and one none of us had to invent numbers for: real Lahore/Karachi/Islamabad rent listings, real dealer behavior, real haggling culture. A tenant looking to rent a shop faces the exact same problem as Daniel: call five dealers, get five incomparable verbal quotes, and hope you didn't get the one who bundles the commission into "the maintenance fee." The Negotiator closes that gap — for this vertical today, for any phone-priced market by config swap tomorrow (see [§ Swapping verticals](#swapping-verticals)).

## What it does

Three agents, one shared JSON spec, real ElevenLabs voice at every step:

1. **The Estimator** (intake) — a voice interview *or* a document upload (rent agreement, requirements list) builds a structured job spec: location, budget, business type, area, lease term, move-in date. Both paths produce the same schema; the user reviews and confirms it before any call goes out.
2. **The Caller** — the Negotiator agent phones every dealer, describes the job identically every time, and extracts an itemised quote (rent, advance, commission, maintenance, annual increment) via a tool call mid-conversation — never guessed from transcript prose afterward.
3. **The Closer** — round two calls use real leverage ("I have a quote for 65,000 — can you beat it?"), a config-driven red-flag engine catches quotes 30%+ under benchmark, and the final report ranks every dealer by true first-year cost with a templated (not LLM-written) recommendation, every claim citing a real `[call N, line M]` transcript line.

### The three negotiation styles, live

Per the brief, the "other end of the line" can be a real business, a human role-playing, or a built counter-agent — we ship **both** of the latter two:

- **Agent-to-agent** — an audio bridge cross-pipes the Negotiator's ElevenLabs WebSocket into four distinct counterparty personas' WebSockets in real time (not scripted dialogue): **Stonewaller** (evasive, "someone will call you back"), **Lowballer** (quotes low, hides fees), **Upseller** (anchors high, hard-sells), **Firm-but-Fair** (reasonable, but won't move without a real reason to). Recorded as a time-aligned stereo file (negotiator left, dealer right) and streamed live to the browser panned per leg.
- **Human role-play** — a person answers the same negotiator call live through the browser widget, playing any of those four counterparts, or improvising. This is the primary demo path — it sidesteps the audio-bridge's turn-taking complexity entirely and shows the exact same agent, prompts, and tools working against a real human voice.

Real businesses via Twilio/SIP is a listed stretch goal (see [§ Roadmap](#roadmap)) — not required by the brief, and deliberately out of scope for this submission per its own guidance: *"nothing stretch starts before a recorded end-to-end demo exists."*

### The Conversation Requirement

The brief asks four things to be addressed explicitly. Here's where each lives in the code:

| Requirement | Where |
|---|---|
| **AI disclosure** — does it admit to being an AI? | `vertical.json`'s `disclosure_policy`: *"admit_ai_if_asked; affirm real client; never name client; continue call."* Baked into the negotiator's system prompt, not a bolt-on. |
| **Survives friction** — interruptions, evasive answers, stalling | Prompt explicitly handles "someone will call you back" (demands a concrete callback time before accepting it as an outcome), vague answers ("depends", "around that much" get re-asked concretely), and hang-ups. Half-duplex turn-taking gate (`bridge.TurnGate`) plus a silence-feeder so ElevenLabs' turn detection actually commits utterances on the agent-to-agent path. |
| **The honesty line** | The agent's *only* source of competitor pricing is the `get_leverage` tool, which returns real logged quotes from Supabase — never free text. See [§ The honesty guardrail](#the-honesty-guardrail-why-this-cant-bluff) below; this is the core architectural bet of the whole project. |
| **Every call ends in a structured outcome** | `log_call_status` tool, called exactly once per call, right before hangup: `final_quote` / `vague_quote` / `quote` / `callback` (with a real timestamp) / `declined` — never a vague "they said around two thousand." |

### The honesty guardrail — why this can't bluff

The Negotiator has **no free-text knowledge of other dealers' bids.** Its only channel for competitive leverage is the `get_leverage` tool, which queries real `quotes` rows already written to Postgres by earlier calls. No quote logged anywhere → the tool returns nothing → the agent negotiates on fees and terms instead of inventing a rival offer. This isn't a prompt instruction the model could ignore under pressure — there is no other code path that puts a competing number in front of it. The same discipline extends to the report: the recommendation text is **templated over real quote rows**, not generated by an LLM, so every number and every `[call N, line M]` citation traces back to something actually said on a real call.

## Architecture

```
Estimator (intake)  →  spec_json (confirmed)  →  Negotiator calls dealer 1..N
                                                        │
                                    log_quote / get_leverage / check_redflag / get_benchmark / log_call_status
                                                        │
                                              Supabase (specs · dealers · calls · quotes)
                                                        │
                                     GET /report/{spec_id}  →  ranked, cited comparison
```

**Stack:** FastAPI (Render) + Next.js 16 (Vercel) + Supabase Postgres, ElevenLabs Agents for every voice interaction (no canned audio, no Twilio — web audio via WebSocket end to end), OpenAI for document parsing and benchmark extraction, Tavily for live market search. Everything vertical-specific — the spec schema, fee taxonomy, red-flag thresholds, dealer personas, all agent prompts — lives in one config file (`backend/config/vertical.json`); an agent factory script generates every ElevenLabs agent from it. Multi-tenant via Supabase Auth; the frontend never talks to Supabase for data, only through the FastAPI layer, so service-role keys stay server-side.

```
backend/
  config/vertical.json         spec schema, fee taxonomy, red-flag rules, agent prompts
  config/auto_repair_pk.json   second vertical, proves the config-swap claim (see below)
  src/app/
    vertical.py                 vertical.json → pydantic Spec model
    agent_factory.py            vertical.json → ElevenLabs agent/tool definitions
    make_agents.py               idempotent push of agents/tools to ElevenLabs
    api.py, main.py              FastAPI app: specs/dealers/calls/quotes CRUD, auth, ownership
    tools.py                     the 5 webhook tools the agents call mid-conversation
    bridge.py, storage.py, live.py   agent-to-agent audio relay, recording, live streaming
    parse.py                    document intake (PDF/image/DOCX → spec fields)
    benchmark.py                 Tavily market search + dealer discovery
    report.py                    ranked, cited comparison report generator
    auth.py                      Supabase JWT verification
  supabase/migrations/          SQL schema
  tests/                        291 tests, mocked Supabase — no live project needed

frontend/
  app/(auth)/                   login / signup
  app/intake/                   voice interview + document upload + spec confirmation
  app/calls/[spec_id]/          call center — per-dealer cards, live transcript/audio, round history
  app/report/[spec_id]/         ranked report, citations, re-check flags
  components/, lib/
```

### Database

```
specs   (id, created_at, vertical, status, spec_json jsonb, benchmark_json jsonb, confirmed bool, user_id uuid)
dealers (id, spec_id, name, persona, phone_label, source, status)
calls   (id, spec_id, dealer_id, round, status, started_at, ended_at, recording_url, transcript_json jsonb, outcome)
quotes  (id, call_id, dealer_id, monthly_rent, advance_months, commission, maintenance,
         annual_increment_pct, other_fees jsonb, total_first_year, binding, notes, flagged, flag_reason, property_ref)
```

`total_first_year` = 12×rent + advance + commission + 12×maintenance + other fees — the one number that makes structurally-different quotes comparable, which is the whole point.

## Swapping verticals

The brief's bar for "configuration, not code": *"switching your system from movers to auto body shops should mean swapping a config file, not rewriting your agents."* `backend/config/auto_repair_pk.json` is a second, complete vertical (auto body repair, Pakistan) that validates against the exact same pydantic model and drives the exact same agent factory, unchanged:

```bash
cd backend
uv run python -m app.make_agents --config config/auto_repair_pk.json
```

No code touched. This is what proves it — not a claim, a file you can diff against `vertical.json` and a real command you can run.

## Getting started

Requires: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, a Supabase project, and API keys for ElevenLabs, OpenAI, and Tavily.

### Backend

```bash
cd backend
uv sync
cp .env.example .env          # fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ELEVENLABS_API_KEY, etc.
supabase link --project-ref <your-project-ref>
supabase db push               # applies migrations in supabase/migrations/
uv run python -m app.seed <user-id>   # seeds 1 sample spec + 4 dealer personas
uv run python -m app.make_agents      # creates/updates the ElevenLabs agents + tools from vertical.json
uv run uvicorn app.main:app --reload  # http://127.0.0.1:8000, interactive docs at /docs
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local     # NEXT_PUBLIC_API_BASE, NEXT_PUBLIC_SUPABASE_URL/ANON_KEY, estimator agent id
npm run dev                    # http://localhost:3000
```

Set `NEXT_PUBLIC_USE_MOCKS=true` in `.env.local` to explore every screen — intake, call center, report, citations — against realistic mock data with zero backend or API keys required. This is the fastest way to see the whole product.

### Tests

```bash
cd backend && uv run pytest      # 291 tests, mocked Supabase client — no live project or network needed
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Meeting the success criteria

| Brief requirement | Status |
|---|---|
| Loop closed: intake → calls → negotiation → ranked recommendation with transcript evidence | Done, live-verified end to end |
| One structured spec, built by voice + at least one document type, confirmed by the user, reused verbatim across every call | Done — `vertical.py`'s pydantic model is the single schema for both intake paths |
| Live calls against ≥3 distinct negotiation styles, every quote structured and itemised | Done — 4 personas (agent-to-agent) + human role-play, all sharing one `log_quote` tool contract |
| At least one negotiation where price/terms measurably change from gathered leverage | Done — round-2 calls cite a real competing `get_leverage` quote; live-verified the negotiator using it to press for a concession |
| AI disclosure + honesty constraints hold under friction | Done — see [§ Conversation Requirement](#the-conversation-requirement) |
| Every call ends in a structured outcome | Done — `log_call_status`, 5-value taxonomy, live-verified for every value |
| Final report ranks all quotes, cites recordings/transcripts, explains the recommendation | Done — `GET /report/{spec_id}`, templated recommendation, `[call N, line M]` citations |

Full component-by-component build log (K1–K13) is in [`CLAUDE.md`](CLAUDE.md); the original hour-by-hour build plan is in [`docs/negotiator-implementation-plan.html`](docs/negotiator-implementation-plan.html).

## Roadmap

Explicitly out of scope for this submission, per the brief's own scope discipline ("nothing stretch starts before a recorded end-to-end demo exists"):

- Real outbound calls to real dealers over Twilio/PSTN (today's counterparties are built agents or a human role-playing, both explicitly valid per the brief)
- Urdu-language negotiation
- Automated call-list discovery at scale (Zameen/Google Places scraping beyond the current Tavily-based dealer discovery)

## Team

Ahmed Zuhair · Muhammad Taha Ali · Rayan Irfan · Hassan Shakil

## License

[MIT](LICENSE)
