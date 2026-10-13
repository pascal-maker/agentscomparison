"""Small common interface for raw public web-search results."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    published_date: str = ""
    last_updated: str = ""


@dataclass(frozen=True)
class SearchResponse:
    provider: str
    query: str
    results: tuple[SearchResult, ...]
    latency_ms: int
    estimated_search_usd: float | None

    def to_dict(self) -> dict:
        return {**asdict(self), "results": [asdict(item) for item in self.results]}


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, scope_domains: tuple[str, ...] = ()) -> SearchResponse: ...


def _post_json(url: str, body: dict, headers: dict[str, str], *, timeout: int = 20) -> dict:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as error:
        raise SearchError(f"HTTP {error.code} from {url.split('/')[2]}") from error
    except (TimeoutError, URLError, json.JSONDecodeError) as error:
        raise SearchError(f"Search request failed for {url.split('/')[2]}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SearchError("Search response has no results array")
    return payload


def _clean(value: object, limit: int = 1000) -> str:
    return value[:limit] if isinstance(value, str) else ""


class BrowserbaseSearch:
    """Mirror Karen's site-scoped Browserbase discovery request, retaining five raw ranks."""

    name = "browserbase"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("BROWSERBASE_API_KEY", "")

    def search(self, query: str, *, scope_domains: tuple[str, ...] = ()) -> SearchResponse:
        if not self.api_key:
            raise SearchError("BROWSERBASE_API_KEY is missing")
        if not scope_domains:
            raise SearchError("Browserbase baseline requires a scope")
        # Browserbase documents a 200-character query limit. Keep the existing
        # site-scoped shape but fail before silently clipping a search term.
        scoped = query.strip() + " " + " OR ".join(f"site:{host}" for host in scope_domains)
        if len(scoped) > 200:
            raise SearchError("Browserbase scoped query exceeds 200 characters")
        started = perf_counter()
        payload = _post_json(
            "https://api.browserbase.com/v1/search",
            {"query": scoped, "numResults": 5},
            {"X-BB-API-Key": self.api_key},
        )
        results = tuple(
            SearchResult(
                title=_clean(item.get("title"), 200),
                url=_clean(item.get("url"), 2000),
                published_date=_clean(item.get("publishedDate"), 50),
            )
            for item in payload["results"][:5] if isinstance(item, dict)
        )
        # Developer/Startup plan marginal price after included calls; actual
        # account billing may be zero while its monthly allowance remains.
        return SearchResponse(self.name, scoped, results, round((perf_counter() - started) * 1000), 0.007)


class PerplexitySearch:
    """Perplexity raw Search API; no Sonar/Agent answer generation."""

    name = "perplexity"

    def __init__(self, api_key: str | None = None, *, domain_filter: bool = False):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY", "")
        self.domain_filter = domain_filter

    def search(self, query: str, *, scope_domains: tuple[str, ...] = ()) -> SearchResponse:
        if not self.api_key:
            raise SearchError("PERPLEXITY_API_KEY is missing")
        body: dict[str, object] = {
            "query": query.strip(),
            "country": "BE",
            "search_language_filter": ["nl", "fr"],
            "max_results": 5,
            "max_tokens": 1500,
            "max_tokens_per_page": 300,
            "search_type": "web",
        }
        if self.domain_filter and scope_domains:
            body["search_domain_filter"] = list(scope_domains[:20])
        started = perf_counter()
        payload = _post_json(
            "https://api.perplexity.ai/search",
            body,
            {"Authorization": f"Bearer {self.api_key}"},
        )
        results = tuple(
            SearchResult(
                title=_clean(item.get("title"), 200),
                url=_clean(item.get("url"), 2000),
                snippet=_clean(item.get("snippet"), 1500),
                published_date=_clean(item.get("date"), 50),
                last_updated=_clean(item.get("last_updated"), 50),
            )
            for item in payload["results"][:5] if isinstance(item, dict)
        )
        return SearchResponse(self.name, query.strip(), results, round((perf_counter() - started) * 1000), 0.005)
