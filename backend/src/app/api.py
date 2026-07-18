from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import crud


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
    total_first_year: float
    binding: bool = False
    notes: Optional[str] = None
    flagged: bool = False
    flag_reason: Optional[str] = None


def _get_or_404(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return row


specs_router = APIRouter(prefix="/specs", tags=["specs"])
dealers_router = APIRouter(prefix="/dealers", tags=["dealers"])
calls_router = APIRouter(prefix="/calls", tags=["calls"])
quotes_router = APIRouter(prefix="/quotes", tags=["quotes"])


@specs_router.post("")
def create_spec(body: SpecCreate) -> dict[str, Any]:
    return crud.create_spec(body.model_dump())


@specs_router.get("/{id}")
def get_spec(id: str) -> dict[str, Any]:
    return _get_or_404(crud.get_spec(id))


@specs_router.get("")
def list_specs() -> list[dict[str, Any]]:
    return crud.list_specs()


@dealers_router.post("")
def create_dealer(body: DealerCreate) -> dict[str, Any]:
    return crud.create_dealer(body.model_dump())


@dealers_router.get("/{id}")
def get_dealer(id: str) -> dict[str, Any]:
    return _get_or_404(crud.get_dealer(id))


@dealers_router.get("")
def list_dealers(spec_id: Optional[str] = None) -> list[dict[str, Any]]:
    filters = {"spec_id": spec_id} if spec_id else {}
    return crud.list_dealers(**filters)


@calls_router.post("")
def create_call(body: CallCreate) -> dict[str, Any]:
    return crud.create_call(body.model_dump())


@calls_router.get("/{id}")
def get_call(id: str) -> dict[str, Any]:
    return _get_or_404(crud.get_call(id))


@calls_router.get("")
def list_calls(spec_id: Optional[str] = None) -> list[dict[str, Any]]:
    filters = {"spec_id": spec_id} if spec_id else {}
    return crud.list_calls(**filters)


@quotes_router.post("")
def create_quote(body: QuoteCreate) -> dict[str, Any]:
    return crud.create_quote(body.model_dump())


@quotes_router.get("/{id}")
def get_quote(id: str) -> dict[str, Any]:
    return _get_or_404(crud.get_quote(id))


@quotes_router.get("")
def list_quotes(call_id: Optional[str] = None) -> list[dict[str, Any]]:
    filters = {"call_id": call_id} if call_id else {}
    return crud.list_quotes(**filters)
