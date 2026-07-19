"""Webhook tool endpoints called mid-call by ElevenLabs agents (K4).

Auth is a shared secret header, not a user JWT — these are machine-to-machine
calls carrying no user session. Ownership is implied by the ids the agent got
via dynamic variables at call start.
"""

import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from . import crud
from .agent_factory import CALL_OUTCOMES
from .api import QuoteCreate, _get_or_404, _total_first_year
from .bridge import set_call_outcome
from .vertical import load_vertical


def require_tools_secret(x_tools_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("TOOLS_WEBHOOK_SECRET", "")
    if not expected or not secrets.compare_digest(x_tools_secret or "", expected):
        raise HTTPException(status_code=401, detail="bad tools secret")


tools_router = APIRouter(
    prefix="/tools", tags=["tools"], dependencies=[Depends(require_tools_secret)]
)


def _benchmark(spec: dict[str, Any]) -> dict[str, Any]:
    config = load_vertical()
    cached = spec.get("benchmark_json") or {}
    if "per_sqft_low" in cached and "per_sqft_high" in cached:
        low, high, source = cached["per_sqft_low"], cached["per_sqft_high"], "cached"
    else:
        low, high, source = (
            config.benchmark_fallback.per_sqft_low,
            config.benchmark_fallback.per_sqft_high,
            "fallback",
        )
    area = spec.get("spec_json", {}).get("area_sqft")
    return {
        "currency": config.currency,
        "per_sqft_low": low,
        "per_sqft_high": high,
        "area_sqft": area,
        "monthly_low": low * area if area else None,
        "monthly_high": high * area if area else None,
        "source": source,
    }


def evaluate_red_flags(
    spec: dict[str, Any],
    monthly_rent: float | None = None,
    advance_months: float | None = None,
    binding: bool | None = None,
) -> dict[str, Any]:
    benchmark = _benchmark(spec)
    reasons: list[str] = []
    confirm = False
    for rule in load_vertical().red_flags:
        if rule.rule == "below_market_pct":
            low = benchmark["monthly_low"]
            if monthly_rent is not None and low is not None and monthly_rent < (1 - rule.threshold / 100) * low:
                reasons.append(
                    f"monthly rent {monthly_rent:g} is more than {rule.threshold:g}% below the expected low {low:g}"
                )
                confirm = confirm or rule.action == "confirm_then_flag"
        elif rule.rule == "no_written_quote":
            # `binding is False` only — not `not binding`. The old check fired on
            # None too, which conflates "the dealer refused a written quote" with
            # "nobody asked yet", and flagged every quote logged without the
            # field. That is what made an *above*-market dealer come back flagged.
            # The log_quote tool schema requires `binding`, so the agent path
            # always supplies it; unknown stays unjudged.
            if binding is False:
                reasons.append("dealer has not confirmed a written quote")
                confirm = confirm or rule.action == "confirm_then_flag"
        elif rule.rule == "advance_months_gt":
            if advance_months is not None and advance_months > rule.threshold:
                reasons.append(f"advance of {advance_months:g} months exceeds {rule.threshold:g}")
                confirm = confirm or rule.action == "confirm_then_flag"
        # unknown rule names: skipped (config may grow ahead of code)

    action = "confirm_then_flag" if confirm else ("flag" if reasons else "clear")
    confirm_question = None
    if action == "confirm_then_flag":
        confirm_question = (
            f"This rent is well below the market range of {benchmark['monthly_low']:g}-"
            f"{benchmark['monthly_high']:g} {benchmark['currency']} per month. Ask the dealer to "
            "confirm the shop's exact size, condition, floor, and what the rent includes before accepting."
        )
    return {
        "action": action,
        "reasons": reasons,
        "benchmark": benchmark,
        "confirm_question": confirm_question,
    }


def _norm_property_ref(ref: str | None) -> str | None:
    # "" and None are the same "no identifier" bucket (single-property dealer).
    return ref or None


@tools_router.post("/log_quote")
def log_quote(body: QuoteCreate) -> dict[str, Any]:
    call = _get_or_404(crud.get_call(body.call_id))
    spec = _get_or_404(crud.get_spec(call["spec_id"]))
    # Upsert per (call, property): partial quotes get logged the moment the
    # first number lands and later calls for the *same* property merge in the
    # rest (agent tool prompts this flow). A different property_ref is a
    # different shop, so it gets its own row instead of overwriting.
    existing = next(
        (
            q
            for q in crud.list_quotes(call_id=body.call_id)
            if _norm_property_ref(q.get("property_ref")) == _norm_property_ref(body.property_ref)
        ),
        None,
    )
    if existing is not None:
        merged = {k: existing.get(k) for k in QuoteCreate.model_fields if k in existing}
        merged.update({k: v for k, v in body.model_dump().items() if v is not None})
        # ponytail: binding sticky-true — its schema default False is
        # indistinguishable from "not stated", so never un-confirm a written quote
        merged["binding"] = body.binding or bool(existing.get("binding"))
        body = QuoteCreate(**merged)
    verdict = evaluate_red_flags(
        spec,
        monthly_rent=body.monthly_rent,
        advance_months=body.advance_months,
        binding=body.binding,
    )
    total = _total_first_year(body)
    row = {
        **body.model_dump(),
        "total_first_year": total,
        "flagged": verdict["action"] != "clear",
        "flag_reason": "; ".join(verdict["reasons"]) or None,
    }
    quote = crud.update_quote(existing["id"], row) if existing else crud.create_quote(row)
    return {
        "quote_id": quote["id"],
        "total_first_year": total,
        "flagged": quote["flagged"],
        "flag_reason": quote["flag_reason"],
    }


class CallStatusUpdate(BaseModel):
    call_id: str
    outcome: str
    callback_at: str | None = None
    notes: str | None = None


@tools_router.post("/log_call_status")
def log_call_status(body: CallStatusUpdate) -> dict[str, Any]:
    """Explicit ground truth for how a call ended, set by the negotiator itself.

    Replaces guessing the outcome after the fact from transcript prose or from
    whether a quote row exists (bridge.derive_outcome) — that heuristic stays
    as a fallback for calls where the agent never calls this tool, but an
    explicit call here always wins (bridge.finalize_call preserves it).
    """
    if body.outcome not in CALL_OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {CALL_OUTCOMES}")
    _get_or_404(crud.get_call(body.call_id))
    fields: dict[str, Any] = {"outcome": body.outcome}
    if body.callback_at is not None:
        fields["callback_at"] = body.callback_at
    if body.notes is not None:
        fields["callback_note"] = body.notes
    call = set_call_outcome(body.call_id, fields)
    return {"call_id": call["id"], "outcome": call["outcome"]}


class LeverageRequest(BaseModel):
    spec_id: str
    dealer_id: str


LEVERAGE_COMPETITOR_CAP = 5


@tools_router.post("/get_leverage")
def get_leverage(body: LeverageRequest) -> dict[str, Any]:
    _get_or_404(crud.get_spec(body.spec_id))
    dealer_names = {d["id"]: d["name"] for d in crud.list_dealers(spec_id=body.spec_id)}
    quotes = [
        q
        for call in crud.list_calls(spec_id=body.spec_id)
        # ponytail: N+1 over ~4-8 calls, fine at demo scale
        for q in crud.list_quotes(call_id=call["id"])
    ]
    own = [q for q in quotes if q["dealer_id"] == body.dealer_id]
    # Own quotes are context, not leverage — always included, never capped.
    # Competitors are ranked cheapest-first and capped so the prompt stays
    # bounded; flagged competitor quotes stay in the pool (tagged) rather
    # than dropped, so the agent can judge reliability itself.
    competitors = sorted(
        (q for q in quotes if q["dealer_id"] != body.dealer_id),
        key=lambda q: q["total_first_year"],
    )[:LEVERAGE_COMPETITOR_CAP]
    selected = own + competitors
    return {
        "quotes": [
            {
                "dealer": dealer_names.get(q["dealer_id"], "unknown"),
                "property": q.get("property_ref"),
                "monthly_rent": q["monthly_rent"],
                "advance_months": q["advance_months"],
                "commission": q["commission"],
                "maintenance": q["maintenance"],
                "total_first_year": q["total_first_year"],
                "is_current_dealer": q["dealer_id"] == body.dealer_id,
                "flagged": q["flagged"],
            }
            for q in selected
        ]
    }


class RedflagCheck(BaseModel):
    spec_id: str
    monthly_rent: float | None = None
    advance_months: float | None = None
    binding: bool | None = None


@tools_router.post("/check_redflag")
def check_redflag(body: RedflagCheck) -> dict[str, Any]:
    spec = _get_or_404(crud.get_spec(body.spec_id))
    return evaluate_red_flags(
        spec,
        monthly_rent=body.monthly_rent,
        advance_months=body.advance_months,
        binding=body.binding,
    )


class SpecIdBody(BaseModel):
    spec_id: str


@tools_router.post("/get_benchmark")
def get_benchmark(body: SpecIdBody) -> dict[str, Any]:
    spec = _get_or_404(crud.get_spec(body.spec_id))
    return _benchmark(spec)
