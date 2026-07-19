"""K7 benchmark + dealer discovery: Tavily search -> OpenAI structured extraction.

Both entry points are best-effort: any failure (missing key, timeout, junk
results) returns None/[] so spec creation never breaks on external services.
"""

import os
from functools import lru_cache
from typing import Optional

import httpx
from openai import OpenAI
from pydantic import BaseModel

from .vertical import load_vertical

OPENAI_MODEL = "gpt-5.4-mini"
TAVILY_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT_S = 3.0
OPENAI_TIMEOUT_S = 8.0


@lru_cache
def _client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=OPENAI_TIMEOUT_S)


class _Benchmark(BaseModel):
    per_sqft_low: Optional[float] = None
    per_sqft_high: Optional[float] = None


class _Dealer(BaseModel):
    name: str
    url: Optional[str] = None


class _Dealers(BaseModel):
    dealers: list[_Dealer]


def _tavily_search(query: str, max_results: int = 5) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    response = httpx.post(
        TAVILY_URL,
        json={"query": query, "max_results": max_results},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=TAVILY_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json().get("results") or []


def _snippets(results: list[dict]) -> str:
    return "\n\n".join(f"{r.get('title', '')}\n{r.get('content', '')}" for r in results)


def _extract(results: list[dict], system: str, text_format: type[BaseModel]):
    return (
        _client()
        .responses.parse(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": _snippets(results)},
            ],
            text_format=text_format,
        )
        .output_parsed
    )


def fetch_benchmark(location: str) -> Optional[dict]:
    """Tavily rent search for `location` -> {"per_sqft_low", "per_sqft_high"} or None."""
    try:
        query = load_vertical().benchmark_query.format(location=location)
        results = _tavily_search(query)
        if not results:
            return None
        parsed = _extract(
            results,
            "Extract the commercial shop rent range in PKR per square foot per month "
            f"for {location} from these search snippets. Only use numbers the snippets "
            "explicitly state; leave a field null if unclear. Never guess.",
            _Benchmark,
        )
    except Exception:
        return None
    if parsed.per_sqft_low is None or parsed.per_sqft_high is None:
        return None
    if not 0 < parsed.per_sqft_low < parsed.per_sqft_high:
        return None
    return {"per_sqft_low": parsed.per_sqft_low, "per_sqft_high": parsed.per_sqft_high}


def discover_dealers(location: str, limit: int = 4) -> list[dict]:
    """Tavily dealer search for `location` -> dealer row dicts (persona 'human')."""
    try:
        query = load_vertical().dealer_search_query.format(location=location)
        results = _tavily_search(query)
        if not results:
            return []
        parsed = _extract(
            results,
            "Extract real property dealer / estate agency business names mentioned in "
            f"these search snippets for {location}. Include a website URL only when a "
            "snippet clearly ties it to that business. Skip property portals and "
            "marketplaces (Zameen, OLX, Graana), business directories, news articles, "
            "listicles, and generic sites. List each business once. Never invent names.",
            _Dealers,
        )
    except Exception:
        return []
    unique: dict[str, _Dealer] = {}
    for d in parsed.dealers:
        key = d.name.strip().casefold()
        if key and key not in unique:
            unique[key] = d
    return [
        {
            "name": d.name.strip(),
            "persona": "human",
            "phone_label": d.url or location,
            "source": "tavily",
        }
        for d in list(unique.values())[:limit]
    ]
