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
