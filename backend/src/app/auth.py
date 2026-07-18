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
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="token missing sub claim")
    return user_id
