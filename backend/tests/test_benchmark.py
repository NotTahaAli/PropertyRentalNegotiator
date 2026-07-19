from types import SimpleNamespace

import httpx
import pytest

from app import benchmark

TAVILY_RESULTS = {
    "results": [
        {"title": "Shop rents in Gulberg", "content": "Rates run 200-400 PKR per sqft."},
        {"title": "Zameen averages", "content": "Commercial shops average PKR 300/sqft."},
    ]
}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    benchmark._client.cache_clear()


def _fake_httpx_post(payload=TAVILY_RESULTS, captured=None):
    def post(url, json=None, headers=None, timeout=None):
        if captured is not None:
            captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    return post


def _fake_openai(parsed):
    parse = lambda **kwargs: SimpleNamespace(output_parsed=parsed)
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))


# --- fetch_benchmark -----------------------------------------------------


def test_fetch_benchmark_happy_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post(captured=captured))
    monkeypatch.setattr(
        benchmark,
        "_client",
        lambda: _fake_openai(benchmark._Benchmark(per_sqft_low=200, per_sqft_high=400)),
    )

    result = benchmark.fetch_benchmark("Gulberg Lahore")

    assert result == {"per_sqft_low": 200.0, "per_sqft_high": 400.0}
    assert "Gulberg Lahore" in captured["json"]["query"]
    assert captured["headers"]["Authorization"] == "Bearer tvly-test"
    assert captured["timeout"] == benchmark.TAVILY_TIMEOUT_S


def test_fetch_benchmark_missing_key_skips_http(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY")
    monkeypatch.setattr(
        benchmark.httpx, "post", lambda *a, **k: pytest.fail("HTTP call with no key")
    )

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


def test_fetch_benchmark_tavily_timeout_returns_none(monkeypatch):
    def post(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(benchmark.httpx, "post", post)

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


def test_fetch_benchmark_empty_results_skips_openai(monkeypatch):
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post(payload={"results": []}))
    monkeypatch.setattr(
        benchmark, "_client", lambda: pytest.fail("OpenAI called with no results")
    )

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


def test_fetch_benchmark_null_fields_returns_none(monkeypatch):
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post())
    monkeypatch.setattr(
        benchmark,
        "_client",
        lambda: _fake_openai(benchmark._Benchmark(per_sqft_low=200, per_sqft_high=None)),
    )

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


def test_fetch_benchmark_low_not_below_high_returns_none(monkeypatch):
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post())
    monkeypatch.setattr(
        benchmark,
        "_client",
        lambda: _fake_openai(benchmark._Benchmark(per_sqft_low=400, per_sqft_high=400)),
    )

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


def test_fetch_benchmark_openai_error_returns_none(monkeypatch):
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post())

    def boom():
        raise RuntimeError("openai down")

    monkeypatch.setattr(benchmark, "_client", boom)

    assert benchmark.fetch_benchmark("Gulberg Lahore") is None


# --- discover_dealers ----------------------------------------------------


def _dealers_parsed(names_urls):
    return benchmark._Dealers(
        dealers=[benchmark._Dealer(name=n, url=u) for n, u in names_urls]
    )


def test_discover_dealers_happy_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post(captured=captured))
    monkeypatch.setattr(
        benchmark,
        "_client",
        lambda: _fake_openai(
            _dealers_parsed([("Alpha Estate", "https://alpha.pk"), ("Beta Property", None)])
        ),
    )

    dealers = benchmark.discover_dealers("Gulberg Lahore")

    assert dealers == [
        {
            "name": "Alpha Estate",
            "persona": "human",
            "phone_label": "https://alpha.pk",
            "source": "tavily",
        },
        {
            "name": "Beta Property",
            "persona": "human",
            "phone_label": "Gulberg Lahore",
            "source": "tavily",
        },
    ]
    assert "Gulberg Lahore" in captured["json"]["query"]


def test_discover_dealers_respects_limit(monkeypatch):
    monkeypatch.setattr(benchmark.httpx, "post", _fake_httpx_post())
    monkeypatch.setattr(
        benchmark,
        "_client",
        lambda: _fake_openai(_dealers_parsed([(f"Dealer {i}", None) for i in range(10)])),
    )

    assert len(benchmark.discover_dealers("Gulberg Lahore", limit=3)) == 3


def test_discover_dealers_missing_key_returns_empty(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY")
    monkeypatch.setattr(
        benchmark.httpx, "post", lambda *a, **k: pytest.fail("HTTP call with no key")
    )

    assert benchmark.discover_dealers("Gulberg Lahore") == []


def test_discover_dealers_tavily_error_returns_empty(monkeypatch):
    def post(*args, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(benchmark.httpx, "post", post)

    assert benchmark.discover_dealers("Gulberg Lahore") == []
