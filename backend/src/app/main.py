from fastapi import FastAPI

from .api import calls_router, dealers_router, quotes_router, specs_router

app = FastAPI(title="The Negotiator API")

app.include_router(specs_router)
app.include_router(dealers_router)
app.include_router(calls_router)
app.include_router(quotes_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
