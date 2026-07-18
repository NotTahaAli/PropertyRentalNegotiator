# Multi-tenant auth (K13) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every spec belongs to a Supabase Auth user; FastAPI verifies the caller's JWT and enforces ownership on every data endpoint, closing the current cross-tenant data leak.

**Architecture:** Frontend will eventually use `supabase-js` directly against Supabase Auth for signup/login (out of scope here — frontend is still an empty scaffold). FastAPI verifies the resulting JWT locally against the project's JWKS endpoint (no shared secret to manage) and extracts the user id (`sub` claim). `specs.user_id` is the one new ownership column; `dealers`/`calls`/`quotes` inherit ownership through `spec_id`/`call_id` chains.

**Tech Stack:** FastAPI, `PyJWT[crypto]` (JWKS + ES256/RS256 verification), Supabase Postgres + Auth, pytest.

## Global Constraints

- Still scoped to today's hackathon deadline and free-tier-only — no new paid services.
- Do not touch `backend/supabase/migrations/20260718201325_init.sql` (already applied) — new schema changes go in a new migration file.
- Do not touch the HTML plan doc's shift-board hour-by-hour schedule.
- `backend/.env` is never read/printed — if a task needs to confirm an env var exists, check `os.environ` presence in Python/test code, not by catting the file.
- All new Python code follows the existing style in `backend/src/app/`: plain functions, no unrequested abstractions, `dict[str, Any]` for Supabase row shapes.
- Every task's tests run via `cd backend && uv run pytest` with zero live network access (mock what talks to Supabase/JWKS), except the final live-verification task which intentionally hits the real project.

---

## File Structure

- `backend/src/app/auth.py` — **new**. `get_current_user_id` FastAPI dependency: verifies a Supabase JWT via JWKS, returns the user's UUID string.
- `backend/tests/test_auth.py` — **new**. Unit tests for the dependency using a locally-generated EC keypair (no network).
- `backend/supabase/migrations/0002_specs_user_id.sql` — **new**. Adds `specs.user_id`, drops pre-multi-tenant seed data (it has no owner).
- `backend/src/app/seed.py` — **modify**. `seed()` becomes `seed(user_id: str)`.
- `backend/src/app/api.py` — **modify**. Every route depends on `get_current_user_id`; ownership checks added; `SpecCreate` unchanged (still no `user_id` field — server sets it); `list_dealers`/`list_calls`/`list_quotes` filters become required, not optional.
- `backend/tests/test_api.py` — **modify**. Rewritten to use `app.dependency_overrides[get_current_user_id]` and cover cross-tenant isolation.
- `backend/pyproject.toml` / `uv.lock` — **modify**. Add `pyjwt[crypto]`.
- `CLAUDE.md`, `docs/negotiator-implementation-plan.html`, `backend/README.md` — **modify**. Doc updates per the design spec (Task 5).

---

### Task 1: Auth dependency (JWKS verification)

**Files:**
- Create: `backend/src/app/auth.py`
- Test: `backend/tests/test_auth.py`
- Modify: `backend/pyproject.toml` (add dependency)

**Interfaces:**
- Produces: `get_current_user_id(authorization: Annotated[Optional[str], Header()] = None) -> str`, raising `fastapi.HTTPException(401)` on any missing/invalid/malformed token. Later tasks import this as `from .auth import get_current_user_id` and use it as a FastAPI `Depends`.

- [ ] **Step 1: Add the JWT dependency**

Run: `cd backend && uv add "pyjwt[crypto]"`
Expected: `pyproject.toml` and `uv.lock` gain `pyjwt` (with the `cryptography` extra, needed for RS256/ES256 verification).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_auth.py`:

```python
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from app import auth


def _make_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


def _token(private_key, **claims: Any) -> str:
    payload = {"aud": "authenticated", "sub": "user-1", **claims}
    return jwt.encode(payload, private_key, algorithm="ES256")


class _FakeSigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJWKClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey(self._key)


def test_missing_header_is_401():
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(authorization=None)
    assert exc_info.value.status_code == 401


def test_non_bearer_header_is_401():
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(authorization="Basic abc123")
    assert exc_info.value.status_code == 401


def test_valid_token_returns_sub(monkeypatch):
    private_key, public_key = _make_keypair()
    monkeypatch.setattr(auth, "_jwks_client", lambda: _FakeJWKClient(public_key))

    token = _token(private_key, sub="user-42")
    user_id = auth.get_current_user_id(authorization=f"Bearer {token}")

    assert user_id == "user-42"


def test_wrong_signing_key_is_401(monkeypatch):
    _, wrong_public_key = _make_keypair()
    signing_private_key, _ = _make_keypair()
    monkeypatch.setattr(auth, "_jwks_client", lambda: _FakeJWKClient(wrong_public_key))

    token = _token(signing_private_key)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


def test_wrong_audience_is_401(monkeypatch):
    private_key, public_key = _make_keypair()
    monkeypatch.setattr(auth, "_jwks_client", lambda: _FakeJWKClient(public_key))

    token = _token(private_key, aud="not-authenticated")

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: `ModuleNotFoundError` or `AttributeError` — `app.auth` doesn't exist yet.

- [ ] **Step 4: Write the implementation**

Create `backend/src/app/auth.py`:

```python
import os
from functools import lru_cache
from typing import Annotated, Optional

import jwt
from fastapi import Header, HTTPException


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def get_current_user_id(
    authorization: Annotated[Optional[str], Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    return payload["sub"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
cd backend && git add src/app/auth.py tests/test_auth.py pyproject.toml uv.lock
git commit -m "feat: add Supabase JWT verification dependency (K13)"
```

---

### Task 2: `specs.user_id` migration + seed script update

**Files:**
- Create: `backend/supabase/migrations/0002_specs_user_id.sql`
- Modify: `backend/src/app/seed.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `specs` table has a required `user_id` column (FK to `auth.users`, cascade delete). `seed(user_id: str) -> None` in `app.seed`, callable as `uv run python -m app.seed <user-id>`. Task 3 relies on `specs` rows always having `user_id`.

- [ ] **Step 1: Write the migration**

Create `backend/supabase/migrations/0002_specs_user_id.sql`:

```sql
-- Pre-multi-tenant seed data has no owner; safe to drop in this dev project.
delete from specs;

alter table specs
  add column user_id uuid not null references auth.users(id) on delete cascade;

create index specs_user_id_idx on specs(user_id);
```

- [ ] **Step 2: Push the migration to the live project**

Run: `cd backend && supabase db push`
Expected: prompts to confirm, applies `0002_specs_user_id.sql`. If it fails with an auth/link error, run `supabase migration list` first to confirm the project is still linked (it was linked during K2) — do not run `supabase link` again without asking the user, that requires their login.

- [ ] **Step 3: Verify the migration applied**

Run: `cd backend && supabase migration list`
Expected: JSON showing `"local":"0002_specs_user_id"` matching `"remote":"0002_specs_user_id"`.

- [ ] **Step 4: Update the seed script**

Read `backend/src/app/seed.py` first (existing content), then modify it — the only changes are the function signature and the `__main__` block:

```python
import sys

from . import crud
from .vertical import load_vertical

SAMPLE_SPEC_JSON = {
    "area_sqft": 800,
    "location": "Gulberg, Lahore",
    "floor": "ground",
    "business_type": "clothing boutique",
    "frontage_ft": 20,
    "lease_years": 3,
    "parking": True,
    "move_in": "2026-09-01",
    "current_rent": None,
    "budget_monthly_rent": 150000,
}


def seed(user_id: str) -> None:
    config = load_vertical()

    spec = crud.create_spec(
        {
            "vertical": config.vertical,
            "status": "confirmed",
            "spec_json": SAMPLE_SPEC_JSON,
            "confirmed": True,
            "user_id": user_id,
        }
    )
    print(f"seeded spec {spec['id']}")

    for persona in config.persona_prompts:
        dealer = crud.create_dealer(
            {
                "spec_id": spec["id"],
                "name": f"{persona.capitalize()} Dealer",
                "persona": persona,
                "phone_label": f"Dealer ({persona})",
                "source": "seed",
            }
        )
        print(f"seeded dealer {dealer['id']} ({persona})")


if __name__ == "__main__":
    seed(sys.argv[1])
```

- [ ] **Step 5: Run the existing test suite to confirm nothing else broke**

Run: `cd backend && uv run pytest -q`
Expected: `test_crud.py` and `test_vertical.py` still pass (they don't touch `seed.py` or `specs.user_id`). `test_api.py` is expected to start failing here — that's Task 3's job, not this one's. Confirm the failures are only in `test_api.py`.

- [ ] **Step 6: Commit**

```bash
cd backend && git add supabase/migrations/0002_specs_user_id.sql src/app/seed.py
git commit -m "feat: add specs.user_id column, require it in seed script (K13)"
```

---

### Task 3: Ownership enforcement in the API layer

**Files:**
- Modify: `backend/src/app/api.py`
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `get_current_user_id` from `app.auth` (Task 1); `specs.user_id` column (Task 2).
- Produces: every route requires a valid bearer token; `list_dealers`/`list_calls`/`list_quotes` now take a **required** `spec_id`/`spec_id`/`call_id` query param respectively (previously optional).

- [ ] **Step 1: Write the failing tests**

Replace `backend/tests/test_api.py` entirely:

```python
from fastapi.testclient import TestClient

from app import crud
from app.auth import get_current_user_id
from app.main import app

client = TestClient(app)

USER_A = "user-a"
USER_B = "user-b"


def _as(user_id):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


def teardown_function():
    app.dependency_overrides.clear()


def test_health_does_not_require_auth():
    response = client.get("/health")
    assert response.status_code == 200


def test_specs_endpoints_require_auth():
    response = client.get("/specs")
    assert response.status_code == 401  # no dependency override, no header


def test_create_spec_sets_owner_from_token(monkeypatch):
    captured = {}

    def fake_create_spec(row):
        captured.update(row)
        return {"id": "s1", **row}

    monkeypatch.setattr(crud, "create_spec", fake_create_spec)
    _as(USER_A)

    response = client.post(
        "/specs",
        json={"vertical": "shop_rental", "status": "draft", "spec_json": {}},
    )

    assert response.status_code == 200
    assert captured["user_id"] == USER_A


def test_list_specs_scoped_to_caller(monkeypatch):
    captured = {}

    def fake_list_specs(**filters):
        captured.update(filters)
        return []

    monkeypatch.setattr(crud, "list_specs", fake_list_specs)
    _as(USER_A)

    client.get("/specs")

    assert captured == {"user_id": USER_A}


def test_get_spec_404s_for_non_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/specs/s1")

    assert response.status_code == 404


def test_get_spec_200s_for_owner(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/specs/s1")

    assert response.status_code == 200
    assert response.json()["id"] == "s1"


def test_create_dealer_requires_spec_ownership(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.post(
        "/dealers", json={"spec_id": "s1", "name": "D", "persona": "firm"}
    )

    assert response.status_code == 404


def test_list_dealers_requires_spec_id_query_param(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_A)

    response = client.get("/dealers")  # no spec_id

    assert response.status_code == 422


def test_list_dealers_scoped_to_owned_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    monkeypatch.setattr(crud, "list_dealers", lambda **filters: [{"id": "d1"}])
    _as(USER_A)

    response = client.get("/dealers", params={"spec_id": "s1"})

    assert response.status_code == 200
    assert response.json() == [{"id": "d1"}]


def test_get_quote_checks_ownership_through_call_and_spec(monkeypatch):
    monkeypatch.setattr(
        crud, "get_quote", lambda id: {"id": "q1", "call_id": "c1"}
    )
    monkeypatch.setattr(
        crud, "get_call", lambda id: {"id": "c1", "spec_id": "s1"}
    )
    monkeypatch.setattr(
        crud, "get_spec", lambda id: {"id": "s1", "user_id": USER_A}
    )
    _as(USER_B)

    response = client.get("/quotes/q1")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api.py -v`
Expected: multiple failures — routes don't require auth yet, `list_dealers` doesn't require `spec_id`, no ownership checks exist.

- [ ] **Step 3: Rewrite `api.py`**

Read the current `backend/src/app/api.py` first, then replace it with:

```python
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
    total_first_year: float
    binding: bool = False
    notes: Optional[str] = None
    flagged: bool = False
    flag_reason: Optional[str] = None


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
    return crud.create_quote(body.model_dump())


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass (`test_auth.py`, `test_crud.py`, `test_vertical.py`, `test_api.py`).

- [ ] **Step 5: Commit**

```bash
cd backend && git add src/app/api.py tests/test_api.py
git commit -m "feat: enforce per-user ownership on all data endpoints (K13)"
```

---

### Task 4: Live verification against the real Supabase project

**Files:** none (verification only — no code changes). If anything fails here, fix it in the relevant file from Task 1-3 and re-run this task from Step 1.

**Interfaces:**
- Consumes: everything from Tasks 1-3, plus the live Supabase project already linked from K2 (`backend/supabase/.temp/project-ref`).

- [ ] **Step 1: Confirm the full suite passes fresh**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass, 0 failures. Note the exact pass count in your report.

- [ ] **Step 2: Create two throwaway Auth users and sign in as each**

Run:
```bash
cd backend && uv run python3 <<'EOF'
from app.db import get_client

client = get_client()

user_a = client.auth.admin.create_user(
    {"email": "k13-verify-a@negotiator.test", "password": "verify-pass-a1!", "email_confirm": True}
)
user_b = client.auth.admin.create_user(
    {"email": "k13-verify-b@negotiator.test", "password": "verify-pass-b1!", "email_confirm": True}
)

session_a = client.auth.sign_in_with_password(
    {"email": "k13-verify-a@negotiator.test", "password": "verify-pass-a1!"}
)
session_b = client.auth.sign_in_with_password(
    {"email": "k13-verify-b@negotiator.test", "password": "verify-pass-b1!"}
)

with open("/tmp/k13_verify.env", "w") as f:
    f.write(f"USER_A_ID={user_a.user.id}\n")
    f.write(f"USER_B_ID={user_b.user.id}\n")
    f.write(f"TOKEN_A={session_a.session.access_token}\n")
    f.write(f"TOKEN_B={session_b.session.access_token}\n")

print("wrote /tmp/k13_verify.env")
EOF
```
Expected: prints `wrote /tmp/k13_verify.env`, no exceptions. If `sign_in_with_password` fails because the project requires email confirmation despite `email_confirm: True`, report the exact error — do not silently skip this task.

- [ ] **Step 3: Start the server**

Run: `cd backend && (uv run uvicorn app.main:app --port 8123 > /tmp/uvicorn_k13.log 2>&1 &) && sleep 3`
Expected: no output; server starts in the background.

- [ ] **Step 4: Exercise the full auth + ownership flow**

Run:
```bash
cd backend && source /tmp/k13_verify.env

echo "== unauthenticated GET /specs -> expect 401 =="
curl -s -o /dev/null -w "%{http_code}\n" localhost:8123/specs

echo "== user A creates a spec =="
SPEC=$(curl -s -X POST localhost:8123/specs \
  -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d '{"vertical":"k13_verify","status":"draft","spec_json":{"x":1}}')
echo "$SPEC"
SPEC_ID=$(echo "$SPEC" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "== user A can read it back -> expect 200 =="
curl -s -o /dev/null -w "%{http_code}\n" localhost:8123/specs/$SPEC_ID -H "Authorization: Bearer $TOKEN_A"

echo "== user B reads the same spec -> expect 404 =="
curl -s -o /dev/null -w "%{http_code}\n" localhost:8123/specs/$SPEC_ID -H "Authorization: Bearer $TOKEN_B"

echo "== user B lists specs -> expect empty list, not user A's spec =="
curl -s localhost:8123/specs -H "Authorization: Bearer $TOKEN_B"; echo

echo "== user B tries to create a dealer under user A's spec -> expect 404 =="
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8123/dealers \
  -H "Authorization: Bearer $TOKEN_B" -H 'Content-Type: application/json' \
  -d "{\"spec_id\":\"$SPEC_ID\",\"name\":\"x\",\"persona\":\"firm\"}"

echo "== user A creates a dealer under their own spec -> expect 200 =="
curl -s -X POST localhost:8123/dealers \
  -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d "{\"spec_id\":\"$SPEC_ID\",\"name\":\"x\",\"persona\":\"firm\"}"
echo
```
Expected: exactly the status codes/behavior each `echo` line says. If any diverge, this task is not done — go fix the code and restart from Step 1.

- [ ] **Step 5: Stop the server and clean up the throwaway users**

Run:
```bash
cd backend && pkill -f "uvicorn app.main:app --port 8123"
source /tmp/k13_verify.env
uv run python3 <<EOF
from app.db import get_client
client = get_client()
client.auth.admin.delete_user("$USER_A_ID")
client.auth.admin.delete_user("$USER_B_ID")
print("deleted verification users (specs cascade-deleted with them)")
EOF
rm -f /tmp/k13_verify.env /tmp/uvicorn_k13.log
```
Expected: prints the cascade-delete confirmation. Then confirm cleanup with:
`cd backend && uv run python -c "from app import crud; print(crud.list_specs(user_id='$USER_A_ID'))"` — expect `[]` (or skip if `$USER_A_ID` no longer in scope; the point is no leftover verification rows).

- [ ] **Step 6: Re-seed real demo data for a real dev user**

This step needs a real user id from the person running this plan (not a throwaway). Report back and ask: "Give me a Supabase Auth user id to seed demo data for (create one via the Supabase dashboard → Authentication → Add user, or reuse an existing one), or tell me to skip seeding for now." Do not fabricate a user id. Once given one, run:
`cd backend && uv run python -m app.seed <user-id>`
Expected: `seeded spec ...` and 4 `seeded dealer ...` lines.

---

### Task 5: Update docs and commit

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/negotiator-implementation-plan.html`
- Modify: `backend/README.md`

**Interfaces:** none — doc-only task, last in the plan.

- [ ] **Step 1: Update `CLAUDE.md`**

Read the current file first. Make these edits:

1. In "Locked decisions", add a line: `- Multi-tenant: Supabase Auth (email+password). Every spec has an owner (specs.user_id); FastAPI verifies the caller's JWT via JWKS and enforces ownership on every data endpoint. Frontend talks to Supabase Auth directly for signup/login/session (the only exception to "frontend never touches Supabase directly" — data still only via FastAPI).`
2. In the same section, reword the "Frontend never talks to Supabase directly" line to: `- Frontend never talks to Supabase directly for data — all spec/dealer/call/quote reads/writes go through FastAPI (keys stay server-side). Auth (signup/login/session) is the one exception: frontend talks to Supabase Auth directly with the public anon key.`
3. In the Supabase schema code block, update the `specs` line to: `specs   (id, created_at, vertical, status, spec_json jsonb, benchmark_json jsonb, confirmed bool, user_id uuid)`
4. Add a new bullet under "Locked decisions" or its own subsection: reframe the dealer personas — `- The 4 counter-agent personas (stonewaller, lowballer, upseller, firm) and the human-roleplay fallback are a testing/demo stand-in for calling real dealers by phone. Production vision is real outbound calls (Twilio/PSTN — already a listed stretch item, not built today); nothing about that changes today's implementation.`
5. Add a row to the status table: `| K13 | Auth & multi-tenancy | **Done (backend)** — \`backend/src/app/auth.py\`, \`api.py\` ownership checks, \`supabase/migrations/0002_specs_user_id.sql\`. Frontend signup/login pages not started (frontend is still an empty scaffold) |`
6. In K8 and K9's status rows, note the new dependency by appending to their existing detail text: ` Needs K13 for a logged-in user before intake/calls make sense.`

- [ ] **Step 2: Update `docs/negotiator-implementation-plan.html`**

Read the current file first. Make these edits:

1. In `<section id="locked">`, add a `<div class="lock">` matching the existing style: `<div class="lock">Multi-tenant: <b>Supabase Auth</b> (email+password); every spec has an owner; FastAPI enforces it via JWT</div>`
2. In the same section, reword the dealer-persona framing — find `<div class="lock">Counterparties: <b>counter-agents</b> (4 personas) + optional human role-play</div>` and replace with: `<div class="lock">Counterparties: <b>counter-agents</b> (4 personas) + optional human role-play — a testing stand-in for real dealer phone calls (Twilio/PSTN is the stretch item for that)</div>`
3. In `<section id="data">`, update the `specs` line in the `<pre><code>` schema block to include `, user_id uuid` after `confirmed bool`.
4. Add one sentence to the `<ul class="plain">` list right after it: `<li><code>specs.user_id</code> ties every spec to a Supabase Auth user — FastAPI enforces ownership on every read/write, closing the pre-multi-tenant cross-tenant leak.</li>`
5. In `<section id="agents">`, find the paragraph right after the `.agents` grid (`<h3>Negotiator tool belt...`) and add a sentence before it clarifying framing: `<p class="muted">The four dealer personas below simulate real property dealers for testing/demo — the SaaS product's real end-state calls actual dealer phone numbers (Twilio, a listed stretch item).</p>`
6. In the `<section id="components">` table, add a new row after K12 (or logically near K2/K8/K9 — after K12 is simplest since it's additive): `<tr><td>K13</td><td><b>Auth & multi-tenancy</b></td><td><span class="owner oc">C</span></td><td>1h</td><td>K2</td><td class="stat-done">Done (backend)</td><td>Supabase Auth (email+password); specs.user_id; FastAPI verifies JWT via JWKS and enforces ownership on every endpoint. Frontend signup/login pages not started.</td></tr>`
7. Update K8 and K9 rows' "Needs" column to include `K13` (e.g. K8's `K1 shape only` becomes `K1 shape only, K13`; K9's `K5 shape only` becomes `K5 shape only, K13`).
8. Update the status tile: change `K1 · K2 done · 10 pending` to `K1 · K2 · K13 (backend) done · 9 pending`.

- [ ] **Step 3: Update `backend/README.md`**

Read the current file first. Add a line to the "Status" section noting K13, and add a short "Auth" subsection after "Database" explaining: FastAPI verifies Supabase JWTs via JWKS (no shared secret needed, just `SUPABASE_URL`); every request to `/specs`, `/dealers`, `/calls`, `/quotes` needs `Authorization: Bearer <supabase-access-token>`; a token can be obtained today via `client.auth.sign_in_with_password(...)` in a Python shell (no frontend login UI yet).

- [ ] **Step 4: Verify docs build/render sanely**

Run: `cd /Users/nottahaali/Documents/Projects/NotTahaAli/PropertyRentalNegotiator && python3 -c "import html.parser; html.parser.HTMLParser().feed(open('docs/negotiator-implementation-plan.html').read())"`
Expected: no exception (catches unclosed-tag typos from the edits).

- [ ] **Step 5: Final full test run**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md docs/negotiator-implementation-plan.html backend/README.md
git commit -m "docs: reflect K13 multi-tenant auth + dealer-persona reframing"
```
