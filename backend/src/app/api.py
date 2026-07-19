import asyncio
import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from elevenlabs.client import ElevenLabs
from elevenlabs.errors import BadRequestError
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from . import crud, live, storage
from .auth import _decode, get_current_user_id
from .benchmark import discover_dealers, fetch_benchmark
from .bridge import derive_outcome, finalize_call, has_logged_quote, request_stop, run_bridge
from .seed import seed_dealers
from .vertical import load_vertical

AGENT_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "agents.generated.json"


class SpecCreate(BaseModel):
    vertical: str
    status: str
    spec_json: dict[str, Any]
    benchmark_json: Optional[dict[str, Any]] = None
    confirmed: bool = False


class DealerCreate(BaseModel):
    spec_id: str
    name: str
    persona: str
    phone_label: Optional[str] = None
    source: Optional[str] = None
    # Tavily-derived; commonly null — Tavily doesn't reliably return either.
    phone: Optional[str] = None
    rating: Optional[float] = None
    rating_source: Optional[str] = None


class DealerUpdate(BaseModel):
    persona: Optional[str] = None
    status: Optional[str] = None


class CallCreate(BaseModel):
    spec_id: str
    dealer_id: str
    round: int
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    recording_url: Optional[str] = None
    transcript_json: Optional[dict[str, Any]] = None
    outcome: Optional[str] = None


class CallStartRequest(BaseModel):
    spec_id: str
    dealer_id: str
    round: int = 1
    mode: str = "bridge"
    # Scopes a follow-up call to one of a dealer's several matching properties.
    focus_property_ref: Optional[str] = None


class QuoteCreate(BaseModel):
    call_id: str
    dealer_id: str
    monthly_rent: float
    advance_months: Optional[float] = None
    commission: Optional[float] = None
    maintenance: Optional[float] = None
    annual_increment_pct: Optional[float] = None
    other_fees: Optional[dict[str, Any]] = None
    # Identifies which of a dealer's several matching shops this quote is for.
    # None/"" both mean "no identifier" (single-property dealer) — see
    # tools.log_quote's upsert key.
    property_ref: Optional[str] = None
    # Tri-state on purpose: True = written quote confirmed, False = dealer would
    # not commit in writing, None = not established. Defaulting to False made
    # "unknown" indistinguishable from "refused" and tripped the no_written_quote
    # red flag on every quote that omitted the field.
    binding: Optional[bool] = None
    notes: Optional[str] = None
    flagged: bool = False
    flag_reason: Optional[str] = None
    available_from: Optional[str] = None


def _total_first_year(body: QuoteCreate) -> float:
    other_fees_total = sum(body.other_fees.values()) if body.other_fees else 0
    return (
        12 * body.monthly_rent
        + (body.advance_months or 0) * body.monthly_rent
        + (body.commission or 0)
        + 12 * (body.maintenance or 0)
        + other_fees_total
    )


def _total_over_term(body: QuoteCreate, periods: float | None, growth_pct: float | None) -> float:
    n = max(1, round(periods or 1))
    g = (growth_pct or 0) / 100
    rent = body.monthly_rent
    maint = body.maintenance or 0
    other = sum(body.other_fees.values()) if body.other_fees else 0
    primary_recurring = sum(12 * rent * (1 + g) ** y for y in range(n))
    return (
        primary_recurring
        + n * 12 * maint
        + (body.advance_months or 0) * rent
        + (body.commission or 0)
        + other
    )

def _get_or_404(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return row


def _require_spec_owner(spec_id: str, user_id: str) -> dict[str, Any]:
    spec = crud.get_spec(spec_id)
    if spec is None or spec["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="not found")
    return spec


def _require_call_owner(call_id: str, user_id: str) -> dict[str, Any]:
    call = _get_or_404(crud.get_call(call_id))
    _require_spec_owner(call["spec_id"], user_id)
    return call


specs_router = APIRouter(prefix="/specs", tags=["specs"])
dealers_router = APIRouter(prefix="/dealers", tags=["dealers"])
calls_router = APIRouter(prefix="/calls", tags=["calls"])
quotes_router = APIRouter(prefix="/quotes", tags=["quotes"])
webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@specs_router.post("")
def create_spec(
    body: SpecCreate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    row = {**body.model_dump(), "user_id": user_id}
    location = body.spec_json.get("location")
    discovered: list[dict[str, Any]] = []
    if location:
        # ponytail: blocking Tavily+OpenAI adds ~3-8s to spec create; queue it if that ever matters
        with ThreadPoolExecutor(max_workers=2) as pool:
            bench = None if body.benchmark_json else pool.submit(fetch_benchmark, location)
            deals = pool.submit(discover_dealers, location)
            if bench is not None:
                row["benchmark_json"] = bench.result()
            discovered = deals.result()
    spec = crud.create_spec(row)
    dealers = seed_dealers(spec["id"])
    for dealer in discovered:
        crud.create_dealer({**dealer, "spec_id": spec["id"]})
    return {**spec, "dealers_seeded": len(dealers), "dealers_discovered": len(discovered)}


@specs_router.get("/{id}")
def get_spec(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _require_spec_owner(id, user_id)


@specs_router.get("")
def list_specs(user_id: str = Depends(get_current_user_id)) -> list[dict[str, Any]]:
    return crud.list_specs(user_id=user_id)


@specs_router.post("/{id}/reflag")
def reflag_spec(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Re-run red-flag rules on every quote of a spec against the current benchmark.

    May unflag: the fresh verdict always wins (quotes judged on a fallback or by a
    client-supplied flagged value get corrected here).
    """
    from .tools import evaluate_red_flags  # local: tools.py imports from this module

    spec = _require_spec_owner(id, user_id)
    checked = updated = 0
    # ponytail: N+1 over ~4-8 calls, same scale as get_leverage, fine for demo
    for call in crud.list_calls(spec_id=id):
        for quote in crud.list_quotes(call_id=call["id"]):
            checked += 1
            verdict = evaluate_red_flags(
                spec,
                monthly_rent=quote.get("monthly_rent"),
                advance_months=quote.get("advance_months"),
                binding=quote.get("binding"),
            )
            flagged = verdict["action"] != "clear"
            reason = "; ".join(verdict["reasons"]) or None
            if flagged != quote.get("flagged") or reason != quote.get("flag_reason"):
                crud.update_quote(quote["id"], {"flagged": flagged, "flag_reason": reason})
                updated += 1
    return {"checked": checked, "updated": updated}


@specs_router.post("/{id}/dealers/discover")
def discover_more_dealers(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """On-demand Tavily dealer search, triggered from the Call Center header.

    Reuses discover_dealers() as-is; dedupes case-insensitively against dealers
    already on this spec (discover_dealers() only dedupes within one Tavily batch).
    """
    spec = _require_spec_owner(id, user_id)
    location = (spec.get("spec_json") or {}).get("location")
    if not location:
        return {"added": [], "skipped_duplicates": 0}
    existing_names = {d["name"].strip().casefold() for d in crud.list_dealers(spec_id=id)}
    added: list[dict[str, Any]] = []
    skipped = 0
    for dealer in discover_dealers(location):
        key = dealer["name"].strip().casefold()
        if key in existing_names:
            skipped += 1
            continue
        existing_names.add(key)
        added.append(crud.create_dealer({**dealer, "spec_id": id}))
    return {"added": added, "skipped_duplicates": skipped}


@dealers_router.post("")
def create_dealer(
    body: DealerCreate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    _require_spec_owner(body.spec_id, user_id)
    return crud.create_dealer(body.model_dump())


@dealers_router.get("/{id}")
def get_dealer(
    id: str, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    dealer = _get_or_404(crud.get_dealer(id))
    _require_spec_owner(dealer["spec_id"], user_id)
    return dealer


DEALER_STATUSES = {"active", "declined"}


@dealers_router.patch("/{id}")
def update_dealer(
    id: str, body: DealerUpdate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    dealer = _get_or_404(crud.get_dealer(id))
    _require_spec_owner(dealer["spec_id"], user_id)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422, detail="no fields to update")
    if "persona" in fields:
        valid_personas = set(load_vertical().persona_prompts) | {"human"}
        if fields["persona"] not in valid_personas:
            raise HTTPException(status_code=422, detail=f"persona must be one of {sorted(valid_personas)}")
    if "status" in fields and fields["status"] not in DEALER_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(DEALER_STATUSES)}")
    return crud.update_dealer(id, fields)


@dealers_router.get("")
def list_dealers(
    spec_id: str, user_id: str = Depends(get_current_user_id)
) -> list[dict[str, Any]]:
    _require_spec_owner(spec_id, user_id)
    return crud.list_dealers(spec_id=spec_id)


@calls_router.post("")
def create_call(
    body: CallCreate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    _require_spec_owner(body.spec_id, user_id)
    return crud.create_call(body.model_dump())


@calls_router.get("/{id}")
def get_call(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    call = _get_or_404(crud.get_call(id))
    _require_spec_owner(call["spec_id"], user_id)
    return call


@calls_router.get("")
def list_calls(
    spec_id: str, user_id: str = Depends(get_current_user_id)
) -> list[dict[str, Any]]:
    _require_spec_owner(spec_id, user_id)
    return crud.list_calls(spec_id=spec_id)


def _agent_manifest() -> dict[str, str]:
    return json.loads(AGENT_MANIFEST_PATH.read_text())["agents"]


# strong references to running bridge tasks — see start_call
_bridge_tasks: set[asyncio.Task] = set()


def _prior_calls(spec_id: str, dealer_id: str, exclude_call_id: str) -> list[dict[str, Any]]:
    """This dealer's earlier calls on this spec, oldest first."""
    calls = [
        c
        for c in crud.list_calls(spec_id=spec_id)
        if c["dealer_id"] == dealer_id and c["id"] != exclude_call_id
    ]
    return sorted(calls, key=lambda c: (c.get("started_at") or "", str(c["id"])))


def _latest_prior_quote(prior_calls: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The last quote this dealer actually gave, across earlier calls."""
    for call in reversed(prior_calls):
        quotes = crud.list_quotes(call_id=call["id"])
        if quotes:
            return quotes[-1]
    return None


def _prior_call_summary(prior_calls: list[dict[str, Any]], quote: dict[str, Any] | None) -> str:
    """Plain-text recap of this dealer's own history, for the negotiator's prompt.

    Only ever this dealer's own words and own figures. Other dealers' bids stay
    exclusively behind `get_leverage` — the honesty guardrail forbids competing-bid
    information reaching the agent by any other path, and this is another path.
    """
    if not prior_calls:
        return "This is your first call with this dealer. You have no prior history."

    config = load_vertical()
    parts = [f"You have already spoken to this dealer {len(prior_calls)} time(s)."]
    if quote:
        terms = [f"rent {quote['monthly_rent']:,.0f} {config.currency} a month"]
        if quote.get("advance_months") is not None:
            terms.append(f"{quote['advance_months']:g} months advance")
        if quote.get("commission") is not None:
            terms.append(f"commission {quote['commission']:,.0f}")
        if quote.get("maintenance") is not None:
            terms.append(f"maintenance {quote['maintenance']:,.0f} a month")
        if quote.get("annual_increment_pct") is not None:
            terms.append(f"{quote['annual_increment_pct']:g}% yearly increase")
        parts.append("They previously quoted: " + ", ".join(terms) + ".")
        parts.append(
            "Confirm with the dealer that this is still accurate before relying on it — "
            "availability, rent, or terms may have changed since. If they confirm nothing "
            "changed, log it again via log_quote so this call has its own record; if "
            "anything changed, log the updated numbers instead. Either way, push for an "
            "improvement on the current number."
        )
    else:
        parts.append("They did not give you a quote last time.")

    last = prior_calls[-1]
    transcript = last.get("transcript_json")
    if isinstance(transcript, list) and transcript:
        tail = [
            f"{line.get('speaker')}: {line.get('text')}"
            for line in transcript[-6:]
            if line.get("text")
        ]
        if tail:
            parts.append("How the last call ended — " + " | ".join(tail))
    return " ".join(parts)


def _dynamic_variables(
    spec: dict[str, Any],
    call_id: str,
    dealer_id: str,
    round_number: int = 1,
    prior_summary: str = "",
    focus_property_ref: str | None = None,
) -> dict[str, Any]:
    config = load_vertical()
    return {
        **spec["spec_json"],
        "currency": config.currency,
        "call_id": call_id,
        "dealer_id": dealer_id,
        "spec_id": spec["id"],
        "round_number": round_number,
        "prior_call_summary": prior_summary
        or "This is your first call with this dealer. You have no prior history.",
        # Always present (empty default) so the prompt's {{focus_property}}
        # placeholder always resolves — a missing dynamic variable can break
        # the ElevenLabs conversation.
        "focus_property": focus_property_ref or "",
    }


# ponytail: bands as code constants; move to vertical.json only if a second
# vertical needs different bands. rent/commission_mo/maint_pct are multipliers
# of the base rent; advance/increment are literal months/percent ranges.
PERSONA_BANDS = {
    "stonewaller": {"rent": (1.00, 1.15), "advance": (4, 6), "commission_mo": (0.8, 1.2), "maint_pct": (0.04, 0.07), "increment": (8, 12)},
    "lowballer": {"rent": (0.60, 0.75), "advance": (1, 2), "commission_mo": (0.4, 0.6), "maint_pct": (0.02, 0.04), "increment": (5, 8)},
    "upseller": {"rent": (1.00, 1.10), "advance": (5, 6), "commission_mo": (1.2, 1.6), "maint_pct": (0.08, 0.12), "increment": (10, 15)},
    "firm": {"rent": (0.95, 1.05), "advance": (2, 2), "commission_mo": (1.0, 1.0), "maint_pct": (0.03, 0.05), "increment": (5, 5)},
}


def _round1000(x: float) -> float:
    return round(x / 1000) * 1000


def _dealer_dynamic_variables(
    spec: dict[str, Any], persona: str, prior_quote: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Numbers for the dealer persona to quote.

    Generated from the persona's band on a first call, but **reused verbatim from
    the dealer's own last quote on any later call**. Regenerating them per call
    meant a dealer who said 151,000 in round 1 said something else in round 2 —
    the negotiator would then be citing a figure the dealer never recognises, and
    the whole leverage story falls apart. A real dealer remembers what they asked.
    """
    from .tools import _benchmark  # local: tools.py imports from api.py

    config = load_vertical()
    spec_json = spec.get("spec_json") or {}
    area = spec_json.get("area_sqft")
    bench = _benchmark(spec)
    if bench["monthly_low"] and bench["monthly_high"]:
        base_rent = (bench["monthly_low"] + bench["monthly_high"]) / 2
    elif spec_json.get("budget_monthly_rent"):
        base_rent = spec_json["budget_monthly_rent"]
    else:
        fallback_per_sqft = (config.benchmark_fallback.per_sqft_low + config.benchmark_fallback.per_sqft_high) / 2
        base_rent = fallback_per_sqft * (area or 500)

    band = PERSONA_BANDS.get(persona, PERSONA_BANDS["firm"])
    if prior_quote and prior_quote.get("monthly_rent") is not None:
        asking_rent = prior_quote["monthly_rent"]
        terms = {
            "asking_rent": asking_rent,
            "advance_months": prior_quote.get("advance_months")
            if prior_quote.get("advance_months") is not None
            else round(random.uniform(*band["advance"])),
            "commission": prior_quote.get("commission")
            if prior_quote.get("commission") is not None
            else _round1000(asking_rent * random.uniform(*band["commission_mo"])),
            "maintenance": prior_quote.get("maintenance")
            if prior_quote.get("maintenance") is not None
            else _round1000(asking_rent * random.uniform(*band["maint_pct"])),
            "annual_increment_pct": prior_quote.get("annual_increment_pct")
            if prior_quote.get("annual_increment_pct") is not None
            else round(random.uniform(*band["increment"])),
        }
        prior_note = (
            "You have spoken to this caller before and already quoted these exact "
            "terms. Stand by them. You may improve them if the caller gives you a "
            "real reason, but never pretend this is a fresh enquiry and never quote "
            "different numbers than the ones above."
        )
    else:
        asking_rent = _round1000(base_rent * random.uniform(*band["rent"]))
        terms = {
            "asking_rent": asking_rent,
            "advance_months": round(random.uniform(*band["advance"])),
            "commission": _round1000(asking_rent * random.uniform(*band["commission_mo"])),
            "maintenance": _round1000(asking_rent * random.uniform(*band["maint_pct"])),
            "annual_increment_pct": round(random.uniform(*band["increment"])),
        }
        prior_note = "This is your first call with this caller."
    
    deadline = spec_json.get(config.deadline_field) if config.deadline_field else None
    dealer_available_from = prior_quote.get("available_from") if prior_quote and prior_quote.get("available_from") else deadline
    if persona == "upseller" and not (prior_quote and prior_quote.get("available_from")) and deadline:
        try:
            d = datetime.strptime(str(deadline), "%Y-%m-%d")
            dealer_available_from = (d + timedelta(days=42)).strftime("%Y-%m-%d")
        except ValueError:
            pass
            
    dealer_available_from = dealer_available_from or "soon"

    out = {
        **terms,
        "prior_call_note": prior_note,
        "currency": config.currency,
        "location": spec_json.get("location") or "the area",
        "area_sqft": area if area is not None else "",
        "floor": spec_json.get("floor") or "",
        "dealer_available_from": str(dealer_available_from),
    }
    if deadline:
        out["deadline"] = str(deadline)
    return out


@calls_router.post("/start")
async def start_call(
    body: CallStartRequest, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    spec = _require_spec_owner(body.spec_id, user_id)
    dealer = _get_or_404(crud.get_dealer(body.dealer_id))
    if dealer["spec_id"] != body.spec_id:
        raise HTTPException(status_code=404, detail="not found")
    if dealer.get("status") == "declined":
        raise HTTPException(status_code=422, detail="dealer has declined; reactivate to call again")
    if body.mode != "roleplay" and dealer["persona"] not in _agent_manifest():
        raise HTTPException(
            status_code=422,
            detail="dealer persona has no agent; assign a persona or use roleplay mode",
        )

    call = crud.create_call(
        {
            "spec_id": body.spec_id,
            "dealer_id": body.dealer_id,
            "round": body.round,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    call_id = call["id"]
    agents = _agent_manifest()
    # History is an enhancement, not a precondition: if these reads fail the call
    # still goes out, just without memory. Logged loudly so a permanently broken
    # history doesn't quietly masquerade as "every call is the first call".
    try:
        prior_calls = _prior_calls(body.spec_id, body.dealer_id, call_id)
        prior_quote = _latest_prior_quote(prior_calls)
    except Exception as exc:  # pragma: no cover - exercised via the degraded path
        print(f"call {call_id}: prior-call history unavailable ({exc!r})")
        prior_calls, prior_quote = [], None
    dynamic_vars = _dynamic_variables(
        spec,
        call_id,
        body.dealer_id,
        round_number=body.round,
        prior_summary=_prior_call_summary(prior_calls, prior_quote),
        focus_property_ref=body.focus_property_ref,
    )

    if body.mode == "roleplay":
        return {
            "call_id": call_id,
            "negotiator_agent_id": agents["negotiator"],
            "dynamic_variables": dynamic_vars,
        }

    dealer_vars = _dealer_dynamic_variables(spec, dealer["persona"], prior_quote)
    # keep a strong reference: a bare create_task can be garbage-collected
    # mid-run, killing the bridge without its finalize (row stuck "running")
    task = asyncio.create_task(
        run_bridge(
            call_id,
            body.spec_id,
            body.dealer_id,
            agents["negotiator"],
            agents[dealer["persona"]],
            dynamic_vars,
            dealer_vars,
        )
    )
    _bridge_tasks.add(task)
    task.add_done_callback(_bridge_tasks.discard)
    return {"call_id": call_id, "status": "running"}


@calls_router.post("/{id}/end")
def end_call(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    call = _require_call_owner(id, user_id)
    stopping = request_stop(id)
    # No live bridge but the row still says "running" — the backend restarted
    # mid-call and the bridge's finalize never ran. Finalize here so the
    # frontend poll converges instead of showing LIVE forever.
    if not stopping and call.get("status") == "running":
        finalize_call(
            id,
            {
                "status": "completed",
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "outcome": derive_outcome(
                    call.get("transcript_json") or [], has_quote=has_logged_quote(id)
                ),
            },
        )
    return {"call_id": id, "stopping": stopping}


@webhooks_router.post("/post-call")
async def post_call_webhook(request: Request) -> dict[str, Any]:
    raw_body = (await request.body()).decode("utf-8")
    signature = request.headers.get("elevenlabs-signature", "")
    try:
        # Fail-closed: with ELEVENLABS_WEBHOOK_SECRET unset, construct_event rejects.
        event = ElevenLabs(api_key="webhook-verify-only").webhooks.construct_event(
            rawBody=raw_body,
            sig_header=signature,
            secret=os.environ.get("ELEVENLABS_WEBHOOK_SECRET", ""),
        )
    except BadRequestError:
        raise HTTPException(status_code=401, detail="bad webhook signature")

    if event.get("type") != "post_call_transcription":
        return {"status": "ignored"}
    data = event.get("data") or {}
    init_data = data.get("conversation_initiation_client_data") or {}
    call_id = (init_data.get("dynamic_variables") or {}).get("call_id")
    if not call_id:
        # Ack conversations we didn't start so ElevenLabs doesn't retry-hammer.
        return {"status": "ignored"}

    transcript = [
        {
            "line": line,
            "speaker": "negotiator" if turn["role"] == "agent" else "dealer",
            "text": turn["message"],
        }
        for line, turn in enumerate(
            (t for t in data.get("transcript") or [] if t.get("message")), start=1
        )
    ]
    finalize_call(
        call_id,
        {
            "transcript_json": transcript,
            # Same ground-truth rule as the bridge: a logged quote row beats any
            # reading of the prose. Matters most here — the roleplay path lands
            # its transcript through this webhook.
            "outcome": derive_outcome(
                transcript, has_quote=has_logged_quote(call_id)
            ),
            "status": "completed",
        },
    )
    return {"status": "ok"}


@calls_router.get("/{id}/recording")
def get_recording(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    call = _require_call_owner(id, user_id)
    return {"recording_url": storage.signed_recording_url(call["recording_url"])}


@calls_router.websocket("/{id}/stream")
async def stream_call(websocket: WebSocket, id: str, token: str = Query(...)) -> None:
    try:
        user_id = _decode(token)
        _require_call_owner(id, user_id)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = live.subscribe(id)
    try:
        while True:
            chunk = await queue.get()
            await websocket.send_text(chunk)
    except WebSocketDisconnect:
        pass
    finally:
        live.unsubscribe(id, queue)


@quotes_router.post("")
def create_quote(
    body: QuoteCreate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    call = _require_call_owner(body.call_id, user_id)
    config = load_vertical()
    spec = _get_or_404(crud.get_spec(call["spec_id"]))
    spec_json = spec.get("spec_json") or {}
    periods = spec_json.get(config.duration_field) if config.duration_field else None
    growth = getattr(body, config.increment_field, None) if config.increment_field else None
    row = {
        **body.model_dump(),
        "total_first_year": _total_first_year(body),
        "total_term": _total_over_term(body, periods, growth),
    }
    return crud.create_quote(row)


@quotes_router.get("/{id}")
def get_quote(
    id: str, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    quote = _get_or_404(crud.get_quote(id))
    _require_call_owner(quote["call_id"], user_id)
    return quote


@quotes_router.get("")
def list_quotes(
    call_id: str, user_id: str = Depends(get_current_user_id)
) -> list[dict[str, Any]]:
    _require_call_owner(call_id, user_id)
    return crud.list_quotes(call_id=call_id)
