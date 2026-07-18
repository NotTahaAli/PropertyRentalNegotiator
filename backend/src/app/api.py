from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import crud
from .auth import get_current_user_id


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


class QuoteCreate(BaseModel):
    call_id: str
    dealer_id: str
    monthly_rent: float
    advance_months: Optional[float] = None
    commission: Optional[float] = None
    maintenance: Optional[float] = None
    annual_increment_pct: Optional[float] = None
    other_fees: Optional[dict[str, Any]] = None
    binding: bool = False
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


@specs_router.post("")
def create_spec(
    body: SpecCreate, user_id: str = Depends(get_current_user_id)
) -> dict[str, Any]:
    return crud.create_spec({**body.model_dump(), "user_id": user_id})


@specs_router.get("/{id}")
def get_spec(id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    return _require_spec_owner(id, user_id)


@specs_router.get("")
def list_specs(user_id: str = Depends(get_current_user_id)) -> list[dict[str, Any]]:
    return crud.list_specs(user_id=user_id)


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
