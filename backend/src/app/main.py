import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import calls_router, dealers_router, quotes_router, specs_router, webhooks_router
from .parse import parse_router
from .report import report_router
from .tools import tools_router

app = FastAPI(title="The Negotiator API")

# CORS_ORIGINS used to be read with os.environ[...], which turns a missing env
# var into an import-time KeyError — the whole service fails to boot rather
# than serving with a sane default. Local dev is the default; Vercel preview
# deploys get a regex because their subdomain changes on every push and can't
# be enumerated in an allowlist.
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
VERCEL_PREVIEW_ORIGIN_RE = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ],
    allow_origin_regex=VERCEL_PREVIEW_ORIGIN_RE,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse_router)
app.include_router(specs_router)
app.include_router(dealers_router)
app.include_router(calls_router)
app.include_router(quotes_router)
app.include_router(tools_router)
app.include_router(webhooks_router)
app.include_router(report_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
