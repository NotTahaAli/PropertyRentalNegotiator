import asyncio
import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
from .bridge import derive_outcome, finalize_call, request_stop, run_bridge
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


class QuoteCreate(BaseModel):
    call_id: str
    dealer_id: str
    monthly_rent: float
    advance_months: Optional[float] = None
    commission: Optional[float] = None
    maintenance: Optional[float] = None
    annual_increment_pct: Optional[float] = None
    other_fees: Optional[dict[str, Any]] = None
    # Tri-state on purpose: True = written quote confirmed, False = dealer would
    # not commit in writing, None = not established. Defaulting to False made
    # "unknown" indistinguishable from "refused" and tripped the no_written_quote
    # red flag on every quote that omitted the field.
    binding: Optional[bool] = None
    notes: Optional[str] = None
    flagged: bool = False
    flag_reason: Optional[str] = None


def _total_first_year(body: QuoteCreate) -> float:
    other_fees_total = sum(body.other_fees.values()) if body.other_fees else 0
    return (
        12 * body.monthly_rent
        + (body.advance_months or 0) * body.monthly_rent
        + (body.commission or 0)
        + 12 * (body.maintenance or 0)
        + other_fees_total
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


def _dynamic_variables(spec: dict[str, Any], call_id: str, dealer_id: str) -> dict[str, Any]:
    config = load_vertical()
    return {
        **spec["spec_json"],
        "currency": config.currency,
        "call_id": call_id,
        "dealer_id": dealer_id,
        "spec_id": spec["id"],
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


def _dealer_dynamic_variables(spec: dict[str, Any], persona: str) -> dict[str, Any]:
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
    asking_rent = _round1000(base_rent * random.uniform(*band["rent"]))
    return {
        "asking_rent": asking_rent,
        "advance_months": round(random.uniform(*band["advance"])),
        "commission": _round1000(asking_rent * random.uniform(*band["commission_mo"])),
        "maintenance": _round1000(asking_rent * random.uniform(*band["maint_pct"])),
        "annual_increment_pct": round(random.uniform(*band["increment"])),
        "currency": config.currency,
        "location": spec_json.get("location") or "the area",
        "area_sqft": area if area is not None else "",
        "floor": spec_json.get("floor") or "",
    }


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
    dynamic_vars = _dynamic_variables(spec, call_id, body.dealer_id)

    if body.mode == "roleplay":
        return {
            "call_id": call_id,
            "negotiator_agent_id": agents["negotiator"],
            "dynamic_variables": dynamic_vars,
        }

    dealer_vars = _dealer_dynamic_variables(spec, dealer["persona"])
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
                "outcome": derive_outcome(call.get("transcript_json") or []),
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
            "outcome": derive_outcome(transcript),
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
    _require_call_owner(body.call_id, user_id)
    row = {**body.model_dump(), "total_first_year": _total_first_year(body)}
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
