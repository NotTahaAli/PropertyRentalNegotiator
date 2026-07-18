from typing import Any

from .db import get_client


def _create(table: str, row: dict[str, Any]) -> dict[str, Any]:
    return get_client().table(table).insert(row).execute().data[0]


def _get(table: str, id: str) -> dict[str, Any] | None:
    rows = get_client().table(table).select("*").eq("id", id).execute().data
    return rows[0] if rows else None


def _list(table: str, **filters: Any) -> list[dict[str, Any]]:
    query = get_client().table(table).select("*")
    for column, value in filters.items():
        query = query.eq(column, value)
    return query.execute().data


def _update(table: str, id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return get_client().table(table).update(fields).eq("id", id).execute().data[0]


def create_spec(row: dict[str, Any]) -> dict[str, Any]:
    return _create("specs", row)


def get_spec(id: str) -> dict[str, Any] | None:
    return _get("specs", id)


def list_specs(**filters: Any) -> list[dict[str, Any]]:
    return _list("specs", **filters)


def create_dealer(row: dict[str, Any]) -> dict[str, Any]:
    return _create("dealers", row)


def get_dealer(id: str) -> dict[str, Any] | None:
    return _get("dealers", id)


def list_dealers(**filters: Any) -> list[dict[str, Any]]:
    return _list("dealers", **filters)


def create_call(row: dict[str, Any]) -> dict[str, Any]:
    return _create("calls", row)


def get_call(id: str) -> dict[str, Any] | None:
    return _get("calls", id)


def list_calls(**filters: Any) -> list[dict[str, Any]]:
    return _list("calls", **filters)


def update_call(id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return _update("calls", id, fields)


def create_quote(row: dict[str, Any]) -> dict[str, Any]:
    return _create("quotes", row)


def get_quote(id: str) -> dict[str, Any] | None:
    return _get("quotes", id)


def list_quotes(**filters: Any) -> list[dict[str, Any]]:
    return _list("quotes", **filters)
