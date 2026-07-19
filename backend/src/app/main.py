import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import calls_router, dealers_router, quotes_router, specs_router, webhooks_router
from .parse import parse_router
from .tools import tools_router

app = FastAPI(title="The Negotiator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
