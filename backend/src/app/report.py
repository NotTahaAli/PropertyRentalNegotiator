"""K10 report generation — the Closer's output.

Ranks every dealer of a spec by `total_first_year` (the single comparison key
that makes incomparable fee structures comparable) and backs the recommendation
with a transcript citation the user can click through to.

Two rules that are product decisions, not implementation details:

1. **Flagged quotes never rank #1.** Sort key is `(flagged, total_first_year)`,
   so a flagged quote is ranked *after* every clean one regardless of how low
   its headline number is. It is still shown, still ranked, never silently
   dropped — hiding it would be its own kind of dishonesty.
2. **The recommendation text is generated deterministically, not by an LLM.**
   It only ever states figures that came out of `quotes` rows and cites the
   transcript line they were spoken on. Same reasoning as the `get_leverage`
   guardrail: if the report generator could write free-form prose about the
   deals, it could invent a deal. Templating makes that impossible rather than
   merely discouraged.
"""

from typing import Any

from fastapi import APIRouter, Depends

from . import crud, storage
from .api import _require_spec_owner
from .auth import get_current_user_id
from .vertical import load_vertical

report_router = APIRouter(prefix="/report", tags=["report"])

# Outcomes that mean "this call produced a quote" — a quote row is proof of at
# least this much regardless of what's stored, but an already-quote-family
# outcome (set explicitly by the negotiator's log_call_status tool) carries
# more information than the generic "quote" and should survive into the
# report rather than being flattened.
QUOTE_OUTCOMES = {"quote", "final_quote", "vague_quote"}


def _call_sort_key(call: dict[str, Any]) -> tuple[str, str]:
    # started_at is set by /calls/start; fall back to id so ordering is always
    # total and stable even for rows created directly via POST /calls.
    return (call.get("started_at") or "", str(call.get("id")))


def _citation_line(transcript: Any, quote: dict[str, Any] | None) -> int:
    """Line number backing this row's claim.

    Prefers the last dealer line that actually says the rent figure — that is
    the line a user clicking the citation wants to land on. Falls back to the
    dealer's last line, then to 1 for empty transcripts.
    """
    lines = transcript if isinstance(transcript, list) else []
    dealer_lines = [ln for ln in lines if ln.get("speaker") == "dealer" and ln.get("line")]
    if quote and quote.get("monthly_rent") is not None:
        rent = int(quote["monthly_rent"])
        needles = {f"{rent:,}", str(rent)}
        for line in reversed(dealer_lines):
            text = line.get("text") or ""
            if any(n in text for n in needles):
                return int(line["line"])
    if dealer_lines:
        return int(dealer_lines[-1]["line"])
    return 1


def _signed_recording(call: dict[str, Any]) -> str | None:
    path = call.get("recording_url")
    if not path:
        return None
    try:
        return storage.signed_recording_url(path)
    except Exception:
        # A missing object or an expired bucket must not take the whole report
        # down — the row is still useful without playable audio.
        return None


def _money(value: float | None, currency: str) -> str:
    return "unknown" if value is None else f"{currency} {value:,.0f}"


def meets_deadline(quote: dict[str, Any], client_deadline: str | None) -> bool:
    if not client_deadline:
        return True  # no deadline means no gate
    available = quote.get("available_from")
    if not available:
        return False  # unconfirmed = miss
    return str(available) <= str(client_deadline)


def _report_row(
    dealer: dict[str, Any],
    call: dict[str, Any],
    quote: dict[str, Any] | None,
    call_number: dict[str, int],
) -> dict[str, Any]:
    property_ref = (quote or {}).get("property_ref")
    return {
        "dealer_id": dealer["id"],
        "dealer_name": dealer["name"],
        "persona": dealer["persona"],
        "property_ref": property_ref,
        # Stable per-property key: distinguishes a dealer's several matching
        # shops in the frontend (React key, recommendation highlight) without
        # depending on quote id, which is None for a never-quoted dealer.
        "row_id": f'{dealer["id"]}:{property_ref or ""}',
        "rank": None,  # assigned below
        "total_term": (quote or {}).get("total_term"),
        "available_from": (quote or {}).get("available_from"),
        "meets_deadline": None,  # assigned during ranking
        "quote": quote,
        "round": call.get("round", 1),
        # A quote row on the call is proof of at least a plain "quote", so it
        # outranks a stale/missing stored outcome — but a richer quote-family
        # outcome the negotiator explicitly logged (final_quote/vague_quote)
        # is kept rather than flattened back down to "quote".
        "outcome": (
            call.get("outcome")
            if call.get("outcome") in QUOTE_OUTCOMES
            else ("quote" if quote else (call.get("outcome") or "failed"))
        ),
        "call_number": call_number[call["id"]],
        "citation_line": _citation_line(call.get("transcript_json"), quote),
        "recording_url": _signed_recording(call),
    }


def build_report(spec_id: str) -> dict[str, Any]:
    config = load_vertical()
    currency = config.currency
    dealers = crud.list_dealers(spec_id=spec_id)
    calls = sorted(crud.list_calls(spec_id=spec_id), key=_call_sort_key)
    spec = crud.get_spec(spec_id)
    spec_json = (spec or {}).get("spec_json") or {}
    client_deadline = spec_json.get(config.deadline_field) if config.deadline_field else None
    n_years = spec_json.get(config.duration_field) if config.duration_field else None

    # Backend-assigned, stable 1-based citation numbers. Until now the only
    # call numbering was the frontend's MOCK_DEALERS index, which had no real
    # equivalent — this is what makes `[call N, line M]` citations resolvable
    # in real mode.
    call_number = {call["id"]: index for index, call in enumerate(calls, start=1)}
    quotes_by_call = {call["id"]: crud.list_quotes(call_id=call["id"]) for call in calls}

    rows: list[dict[str, Any]] = []
    for dealer in dealers:
        dealer_calls = [c for c in calls if c["dealer_id"] == dealer["id"]]
        if not dealer_calls:
            continue  # never dialled: nothing to report, not a null-quote row

        # One row per distinct property_ref (None = the dealer's single/only
        # property). Calls are already sorted ascending, so a dict overwrite
        # keeps the *latest* quote per property — a round-2 follow-up scoped
        # to one shop can't blank out a sibling shop's earlier quote.
        latest_by_prop: dict[str | None, tuple[dict[str, Any], dict[str, Any]]] = {}
        for c in dealer_calls:
            for q in quotes_by_call.get(c["id"], []):
                latest_by_prop[q.get("property_ref")] = (c, q)

        if not latest_by_prop:
            call = dealer_calls[-1]  # never quoted: one declined/failed row, as before
            rows.append(_report_row(dealer, call, None, call_number))
            continue

        for call, quote in latest_by_prop.values():
            rows.append(_report_row(dealer, call, quote, call_number))

    def _sort_key(r):
        q = r["quote"]
        term = q.get("total_term") or q["total_first_year"]
        return (
            bool(q.get("flagged")),
            not meets_deadline(q, client_deadline),
            term,
            q["total_first_year"],
        )
    ranked = sorted(
        (r for r in rows if r["quote"]),
        key=_sort_key,
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
        row["meets_deadline"] = meets_deadline(row["quote"], client_deadline)

    # Ranked rows first (in rank order), then the unranked (declined/no quote).
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["dealer_name"]))

    recommended = ranked[0] if ranked else None
    return {
        "spec_id": spec_id,
        "rows": rows,
        "recommended_dealer_id": recommended["dealer_id"] if recommended else None,
        "recommended_row_id": recommended["row_id"] if recommended else None,
        "recommendation_text": _recommendation_text(ranked, currency, client_deadline, n_years),
    }


def _dealer_label(row: dict[str, Any]) -> str:
    ref = row.get("property_ref")
    return f'{row["dealer_name"]} (shop {ref})' if ref else row["dealer_name"]


def _recommendation_text(ranked: list[dict[str, Any]], currency: str, client_deadline: str | None, n_years: float | None) -> str:
    if not ranked:
        return (
            "No dealer produced a quote, so there is nothing to rank yet. "
            "Run a round of calls and generate the report again."
        )

    top = ranked[0]
    quote = top["quote"]
    citation = f"[call {top['call_number']}, line {top['citation_line']}]"
    term_total_val = quote.get('total_term') or quote['total_first_year']
    n_str = f"{n_years:g}" if n_years is not None else "1"
    
    parts = [
        f"{_dealer_label(top)} offers the best verified deal at "
        f"{_money(term_total_val, currency)} over the full {n_str}-year term "
        f"(first year {_money(quote['total_first_year'], currency)}) {citation}."
    ]

    if client_deadline:
        if meets_deadline(quote, client_deadline):
            parts.append(f"They confirmed delivery by your target date of {client_deadline}.")
        else:
            parts.append(f"They did NOT confirm delivery by your target date of {client_deadline} — verify before committing.")

    parts.append(
        f"That is {_money(quote.get('monthly_rent'), currency)} per month"
        + (
            f", {quote['advance_months']:g} months advance"
            if quote.get("advance_months") is not None
            else ""
        )
        + (
            f", {_money(quote.get('commission'), currency)} commission"
            if quote.get("commission")
            else ", no commission"
        )
        + "."
    )

    runner_up = next((r for r in ranked[1:] if not r["quote"].get("flagged")), None)
    if runner_up:
        runner_term = runner_up["quote"].get("total_term") or runner_up["quote"]["total_first_year"]
        saving = runner_term - term_total_val
        parts.append(
            f"It comes in {_money(saving, currency)} under the next clean offer from "
            f"{_dealer_label(runner_up)}."
        )

    cheaper_flagged = [
        r
        for r in ranked[1:]
        if r["quote"].get("flagged")
        and (r["quote"].get("total_term") or r["quote"]["total_first_year"]) < term_total_val
    ]
    for row in cheaper_flagged:
        reason = row["quote"].get("flag_reason") or "failed a red-flag check"
        row_term = row["quote"].get("total_term") or row["quote"]["total_first_year"]
        parts.append(
            f"{_dealer_label(row)}'s headline number is lower at "
            f"{_money(row_term, currency)}, but it is flagged — {reason} — "
            f"so it is ranked below the clean offers rather than recommended "
            f"[call {row['call_number']}, line {row['citation_line']}]."
        )


    if not quote.get("binding"):
        parts.append(
            "Note: this dealer has not confirmed a written quote — get the terms in writing "
            "before committing."
        )
    return " ".join(parts)


@report_router.get("/{spec_id}")
def get_report(spec_id: str, user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    _require_spec_owner(spec_id, user_id)
    return build_report(spec_id)
