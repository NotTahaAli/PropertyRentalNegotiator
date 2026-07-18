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
from .api import _get_or_404
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
            if not binding:
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


@tools_router.post("/log_quote")
def log_quote():
    raise HTTPException(status_code=501)


@tools_router.post("/get_leverage")
def get_leverage():
    raise HTTPException(status_code=501)


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
