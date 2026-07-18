"""Webhook tool endpoints called mid-call by ElevenLabs agents (K4).

Auth is a shared secret header, not a user JWT — these are machine-to-machine
calls carrying no user session. Ownership is implied by the ids the agent got
via dynamic variables at call start.
"""

import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException


def require_tools_secret(x_tools_secret: str | None = Header(default=None)) -> None:
    expected = os.environ.get("TOOLS_WEBHOOK_SECRET", "")
    if not expected or not secrets.compare_digest(x_tools_secret or "", expected):
        raise HTTPException(status_code=401, detail="bad tools secret")


tools_router = APIRouter(
    prefix="/tools", tags=["tools"], dependencies=[Depends(require_tools_secret)]
)


@tools_router.post("/log_quote")
def log_quote():
    raise HTTPException(status_code=501)


@tools_router.post("/get_leverage")
def get_leverage():
    raise HTTPException(status_code=501)


@tools_router.post("/check_redflag")
def check_redflag():
    raise HTTPException(status_code=501)


@tools_router.post("/get_benchmark")
def get_benchmark():
    raise HTTPException(status_code=501)
