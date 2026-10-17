"""Opt-in, isolated A/B measurement of Karen public-source discovery."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

from .providers import BrowserbaseSearch, PerplexitySearch, SearchError, SearchProvider


HERE = Path(__file__).resolve().parent
MAX_ROUNDS = 3
MAX_PAGES_PER_CASE = 10
DEFAULT_PAGES_PER_PROVIDER = 2
SEARCH_PRICE = {"browserbase": 0.007, "perplexity": 0.005}
FETCH_MARKDOWN_PRICE = 0.004


def load_cases() -> list[dict]:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if not 30 <= len(cases) <= 50 or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Expected 30–50 benchmark cases with unique IDs")
    return cases


def load_domains() -> dict[str, dict[str, list[str]]]:
    return json.loads((HERE / "official_domains.json").read_text(encoding="utf-8"))


def hostname(url: str) -> str:
    parsed = urlparse(url)
    try:
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return ""
        return (parsed.hostname or "").lower()
    except ValueError:
        return ""


def official_organization(url: str, region: str, registry: dict) -> str:
    host = hostname(url)
    if not host:
        return ""
    scopes = ("federal",) if region == "federal" else (region, "federal")
    for scope in scopes:
        for organization, domains in registry[scope].items():
            if any(host == domain or host.endswith("." + domain) for domain in domains):
                return organization
    return ""


def regional_organization(url: str, region: str, registry: dict) -> str:
    if region == "federal":
        return official_organization(url, region, registry)
    host = hostname(url)
    for organization, domains in registry[region].items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return organization
    return ""


def scope_domains(region: str, registry: dict) -> tuple[str, ...]:
    # Reproduces the current site's regional/federal site: scoped search shape.
    return tuple(domain for group in registry[region].values() for domain in group)


def source_priority(candidate: dict, *, region: str, topic: str, registry: dict) -> tuple[int, int, int]:
    organization = candidate["organization"]
    operational = {"Fluvius", "Sibelga", "ORES"}
    if topic == "digital_meter" and organization in operational:
        priority = -1
    else:
        order = list(registry[region])
        if region != "federal":
            order += list(registry["federal"])
        priority = order.index(organization) if organization in order else 99
    return priority, candidate["round"], candidate["rank"]


_BOT_CHALLENGE = re.compile(
    r"testing whether you are a human visitor|what code is in the image|verify (?:that )?you are (?:a )?human"
    r"|checking your browser|enable javascript and cookies to continue|\bcaptcha\b"
    r"|your request is being verified",
    re.IGNORECASE,
)


def is_bot_challenge(content: str) -> bool:
    """FOD Economie (image CAPTCHA) and CWaPE (verification interstitial) answer Fetch with HTTP 200."""
    return bool(_BOT_CHALLENGE.search(content[:3000]))


def _extract_pdf_text(payload: dict, *, max_chars: int) -> str:
    """Decode Browserbase's PDF body and extract its text with pypdf."""
    encoded = payload.get("contentBase64")
    if encoded is None:
        encoded = payload.get("content")
    if isinstance(encoded, list) and all(isinstance(item, int) and 0 <= item <= 255 for item in encoded):
        pdf_bytes = bytes(encoded)
    elif isinstance(encoded, str):
        try:
            pdf_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise SearchError("Browserbase Fetch returned a PDF without a base64 body") from error
    else:
        raise SearchError("Browserbase Fetch returned a PDF without an extractable body")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise SearchError("Browserbase Fetch returned invalid PDF bytes")
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        content = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as error:
        raise SearchError("pypdf could not extract the official PDF") from error
    if not content:
        raise SearchError("pypdf extracted no readable text from the official PDF")
    return content[:max_chars]


def retrieve_official_page(url: str, *, api_key: str, registry: dict, max_chars: int = 10000) -> dict:
    """Use Browserbase Fetch Extract on a configured official HTTPS domain only."""
    if not any(official_organization(url, scope, registry) for scope in registry):
        raise SearchError("Fetch URL is not a configured official HTTPS source")
    if not api_key:
        raise SearchError("BROWSERBASE_API_KEY is missing for retrieval")
    payload = _post_json_fetch(url, api_key)
    status = payload.get("statusCode")
    content = payload.get("content")
    if status != 200 or not isinstance(content, str) or not content.strip():
        raise SearchError(f"Browserbase Fetch returned unusable content (status {status})")
    if "pdf" in str(payload.get("contentType", "")).casefold() or url.lower().split("?", 1)[0].endswith(".pdf"):
        content = _extract_pdf_text(payload, max_chars=max_chars)
        return {
            "content": content,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "retrieval": "browserbase_fetch_pdf_pypdf",
        }
    if is_bot_challenge(content):
        raise SearchError("Browserbase Fetch returned a bot-challenge page, not the original content")
    return {
        "content": content[:max_chars],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "retrieval": "browserbase_fetch_markdown",
    }


def _post_json_fetch(url: str, api_key: str) -> dict:
    # Fetch has a different response shape from Search, so use its own parser.
    import json as _json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    request = Request(
        "https://api.browserbase.com/v1/fetch",
        data=_json.dumps({"url": url, "format": "markdown", "allowRedirects": False}).encode(),
        headers={"X-BB-API-Key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            payload = _json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as error:
        raise SearchError(f"Browserbase Fetch HTTP {error.code}") from error
    except (TimeoutError, URLError, _json.JSONDecodeError) as error:
        raise SearchError("Browserbase Fetch request failed") from error
    if not isinstance(payload, dict):
        raise SearchError("Browserbase Fetch response is not an object")
    return payload


def search_case(case: dict, provider: SearchProvider, registry: dict, *, known_url: str = "") -> dict:
    """One query, then a French query only if no in-scope official source appears."""
    if known_url:
        organization = official_organization(known_url, case["region"], registry)
        if not organization:
            raise SearchError("Known URL must be a configured official source for this region")
        return {
            "case_id": case["id"], "question": case["question"], "region": case["region"],
            "topic": case["topic"], "provider": provider.name, "rounds": [],
            "candidates": [{"rank": 1, "round": 0, "query": "KNOWN_OFFICIAL_URL", "title": "",
                            "url": known_url, "snippet": "", "published_date": "",
                            "last_updated": "", "organization": organization}],
            "search_rounds": 0, "search_latency_ms": 0, "estimated_search_usd": 0.0,
            "evidence": [], "error": "",
        }
    queries = [case["query"]]
    if case.get("fr_query"):
        queries.append(case["fr_query"])
    rounds = []
    seen_urls: set[str] = set()
    candidate_urls: list[dict] = []
    for query in queries[:MAX_ROUNDS]:
        response = provider.search(query, scope_domains=scope_domains(case["region"], registry))
        rounds.append(response.to_dict())
        for rank, result in enumerate(response.results, start=1):
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                candidate_urls.append({
                    "rank": rank,
                    "round": len(rounds),
                    "query": response.query,
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "published_date": result.published_date,
                    "last_updated": result.last_updated,
                    "organization": official_organization(result.url, case["region"], registry),
                })
        if any(regional_organization(result.url, case["region"], registry) for result in response.results):
            break
    return {
        "case_id": case["id"],
        "question": case["question"],
        "region": case["region"],
        "topic": case["topic"],
        "provider": provider.name,
        "rounds": rounds,
        "candidates": candidate_urls,
        "search_rounds": len(rounds),
        "search_latency_ms": sum(item["latency_ms"] for item in rounds),
        "estimated_search_usd": len(rounds) * SEARCH_PRICE[provider.name],
        "evidence": [],
        "error": "",
    }


def attach_shared_retrieval(rows: list[dict], registry: dict, api_key: str, fetcher=retrieve_official_page) -> int:
    """Fetch selected original pages once for both arms; never trust a snippet as proof."""
    cache: dict[str, dict] = {}
    by_case: dict[str, set[str]] = defaultdict(set)
    fetch_calls = 0
    for row in rows:
        selected = sorted(
            (item for item in row["candidates"] if item["organization"]),
            key=lambda item: source_priority(item, region=row["region"], topic=row["topic"], registry=registry),
        )[:DEFAULT_PAGES_PER_PROVIDER]
        for candidate in selected:
            url = candidate["url"]
            if url not in by_case[row["case_id"]] and len(by_case[row["case_id"]]) >= MAX_PAGES_PER_CASE:
                break
            by_case[row["case_id"]].add(url)
            if url not in cache:
                try:
                    fetch_calls += 1
                    cache[url] = fetcher(url, api_key=api_key, registry=registry)
                except SearchError as error:
                    cache[url] = {"error": str(error)}
            page = cache[url]
            row["evidence"].append({
                "claim": "",
                "source_organization": candidate["organization"],
                "page_title": candidate["title"],
                "url": url,
                "passage": "",
                "search_published_date": candidate["published_date"],
                "search_last_updated": candidate["last_updated"],
                "original_published_date": "",
                "original_last_updated": "",
                "retrieved_at": page.get("retrieved_at", ""),
                "region": row["region"],
                "search_query": candidate["query"],
                "original_page_content": page.get("content", ""),
                "retrieval_error": page.get("error", ""),
                "verification_status": "UNVERIFIED",
            })
        row["evidence_status"] = "UNVERIFIED" if any(item["original_page_content"] for item in row["evidence"]) else "NOT_FOUND"
    return fetch_calls


def review_template(rows: list[dict]) -> list[dict]:
    """Human labels are required: official domain and keywords are not evidence."""
    return [{
        "case_id": row["case_id"],
        "provider": row["provider"],
        "review_status": "PENDING",
        "correct_official_ranks_first_round": [],
        "best_source_rank_first_round": None,
        "answerable": None,
        "passage_verification": None,
        "supporting_claim": "",
        "supporting_passage": "",
        "supporting_url": "",
        "original_published_date": "",
        "original_last_updated": "",
        "freshness": None,
        "regional_correctness": None,
        "multilingual_recall": None,
        "answer_text": "",
        "unsupported_claim": None,
        "finding": "PENDING",
        "notes": "",
    } for row in rows]


def validate_reviews(rows: list[dict], reviews: list[dict]) -> None:
    source_rows = {(row["case_id"], row["provider"]): row for row in rows}
    for review in reviews:
        if review.get("review_status") != "COMPLETE":
            continue
        key = (review["case_id"], review["provider"])
        row = source_rows.get(key)
        if row is None:
            raise ValueError(f"Review has no benchmark row: {key}")
        if review.get("finding") not in {"VERIFIED", "PARTIALLY_VERIFIED", "NOT_FOUND"}:
            raise ValueError(f"Completed review needs a finding: {key}")
        if review["finding"] == "VERIFIED" and review.get("passage_verification") is not True:
            raise ValueError(f"VERIFIED finding needs a verified original passage: {key}")
        ranks = review.get("correct_official_ranks_first_round", [])
        if not isinstance(ranks, list) or any(not isinstance(rank, int) or rank not in range(1, 6) for rank in ranks):
            raise ValueError(f"Invalid first-round source ranks: {key}")
        if ranks and (not row["rounds"] or max(ranks) > len(row["rounds"][0]["results"])):
            raise ValueError(f"First-round source rank is absent from search results: {key}")
        if review.get("passage_verification") is True:
            url = review.get("supporting_url", "")
            passage = review.get("supporting_passage", "")
            claim = review.get("supporting_claim", "")
            if not url or not passage or not claim or not any(
                item["url"] == url and passage in item["original_page_content"] for item in row["evidence"]
            ):
                raise ValueError(f"Verified review needs a claim and an exact passage from the original fetched page: {key}")
        if review.get("answerable") is True and not any(item["original_page_content"] for item in row["evidence"]):
            raise ValueError(f"Answerable review has no original page content: {key}")
        if isinstance(review.get("unsupported_claim"), bool) and not review.get("answer_text"):
            raise ValueError(f"Unsupported-claim label needs an answer text: {key}")


def summarize(rows: list[dict], reviews: list[dict] | None = None) -> dict:
    validate_reviews(rows, reviews or [])
    labels = {(item["case_id"], item["provider"]): item for item in (reviews or [])}
    summary = {}
    for provider in ("browserbase", "perplexity"):
        group = [row for row in rows if row["provider"] == provider]
        rated = [labels[(row["case_id"], provider)] for row in group
                 if (row["case_id"], provider) in labels
                 and labels[(row["case_id"], provider)].get("review_status") == "COMPLETE"]
        def rate(field: str):
            values = [item[field] for item in rated if isinstance(item.get(field), bool)]
            return {"value": sum(values) / len(values) if values else None, "n": len(values)}
        ranks = [item["best_source_rank_first_round"] for item in rated
                 if isinstance(item.get("best_source_rank_first_round"), int)]
        source_at_3 = [any(rank <= 3 for rank in item["correct_official_ranks_first_round"]) for item in rated]
        source_at_5 = [any(rank <= 5 for rank in item["correct_official_ranks_first_round"]) for item in rated]
        official_proxy = [any(candidate["organization"] for candidate in row["candidates"][:5]) for row in group]
        verified = [item for item in rated if item.get("passage_verification") is True]
        cost = sum(row["estimated_search_usd"] + len(row["evidence"]) * FETCH_MARKDOWN_PRICE for row in group)
        summary[provider] = {
            "cases": len(group),
            "errors": sum(bool(row["error"]) for row in group),
            "reviewed_cases": len(rated),
            "search_calls": sum(row["search_rounds"] for row in group),
            "estimated_search_usd_per_call": SEARCH_PRICE[provider],
            "estimated_fetch_markdown_usd_per_call": FETCH_MARKDOWN_PRICE,
            "search_rounds_mean": sum(row["search_rounds"] for row in group) / len(group) if group else None,
            "search_latency_ms_mean": sum(row["search_latency_ms"] for row in group) / len(group) if group else None,
            "estimated_marginal_usd": round(cost, 4),
            "estimated_usd_per_verified_question": round(cost / len(verified), 4)
            if verified and len(rated) == len(group) else None,
            "official_domain_proxy_at_5": {"value": sum(official_proxy) / len(official_proxy) if official_proxy else None, "n": len(official_proxy)},
            "official_source_at_3": {"value": sum(source_at_3) / len(source_at_3) if source_at_3 else None, "n": len(source_at_3)},
            "official_source_at_5": {"value": sum(source_at_5) / len(source_at_5) if source_at_5 else None, "n": len(source_at_5)},
            "best_source_rank_first_round_mean": sum(ranks) / len(ranks) if ranks else None,
            "answerable": rate("answerable"),
            "passage_verification": rate("passage_verification"),
            "freshness": rate("freshness"),
            "regional_correctness": rate("regional_correctness"),
            "multilingual_recall": rate("multilingual_recall"),
            "unsupported_claim_rate": {
                "value": (sum(item["unsupported_claim"] for item in rated
                              if item.get("answer_text") and isinstance(item.get("unsupported_claim"), bool)) /
                          sum(1 for item in rated if item.get("answer_text") and isinstance(item.get("unsupported_claim"), bool)))
                if any(item.get("answer_text") and isinstance(item.get("unsupported_claim"), bool) for item in rated) else None,
                "n": sum(1 for item in rated if item.get("answer_text") and isinstance(item.get("unsupported_claim"), bool)),
            },
        }
    return summary


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Permit paid Browserbase/Perplexity API calls")
    parser.add_argument("--score-existing", action="store_true", help="Score edited review labels without network requests")
    parser.add_argument("--out", type=Path, default=HERE / "results" / "latest")
    parser.add_argument("--limit", type=int, default=38, help="Case limit; full set is 38")
    parser.add_argument("--max-estimated-usd", type=float, default=2.0, help="Refuse a live run above this conservative marginal-cost ceiling")
    parser.add_argument("--perplexity-domain-filter", action="store_true", help="Separate restricted-domain experiment")
    args = parser.parse_args()
    if args.score_existing:
        rows = _read_jsonl(args.out.with_suffix(".jsonl"))
        reviews = _read_jsonl(args.out.with_name(args.out.name + "-review.jsonl"))
        summary = summarize(rows, reviews)
        summary["recommendation"] = "KEEP_BROWSERBASE"
        summary["recommendation_basis"] = "Provisional; inspect paired metrics and examples before any migration"
        path = args.out.with_name(args.out.name + "-summary.json")
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)
        return
    cases = load_cases()[:max(0, min(args.limit, 38))]
    registry = load_domains()
    if not args.live:
        print(f"Offline ready: {len(cases)} public questions, 2 providers, at most {MAX_ROUNDS} rounds and {MAX_PAGES_PER_CASE} pages per case. Add --live for API calls.")
        return
    worst_case_usd = len(cases) * (2 * SEARCH_PRICE["browserbase"] + 2 * SEARCH_PRICE["perplexity"] + 4 * FETCH_MARKDOWN_PRICE)
    if worst_case_usd > args.max_estimated_usd:
        parser.error(f"Conservative marginal-cost ceiling exceeded: ${worst_case_usd:.2f} > ${args.max_estimated_usd:.2f}")
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE.parents[1] / ".env", override=False)
    except ImportError:
        pass
    if not os.getenv("BROWSERBASE_API_KEY") or not os.getenv("PERPLEXITY_API_KEY"):
        parser.error("Live A/B requires BROWSERBASE_API_KEY and PERPLEXITY_API_KEY in the environment or local .env")
    providers: list[SearchProvider] = [BrowserbaseSearch(), PerplexitySearch(domain_filter=args.perplexity_domain_filter)]
    rows = []
    for case in cases:
        for provider in providers:
            try:
                row = search_case(case, provider, registry)
            except SearchError as error:
                row = {"case_id": case["id"], "question": case["question"], "region": case["region"],
                       "topic": case["topic"], "provider": provider.name, "rounds": [], "candidates": [],
                       "search_rounds": 0, "search_latency_ms": 0, "estimated_search_usd": 0.0,
                       "evidence": [], "error": str(error)}
            rows.append(row)
    fetch_calls = attach_shared_retrieval(rows, registry, os.environ["BROWSERBASE_API_KEY"])
    _write_jsonl(args.out.with_suffix(".jsonl"), rows)
    _write_jsonl(args.out.with_name(args.out.name + "-review.jsonl"), review_template(rows))
    summary = summarize(rows)
    summary["actual_unique_fetch_calls"] = fetch_calls
    summary["recommendation"] = "KEEP_BROWSERBASE"
    summary["recommendation_basis"] = "Provisional status quo until reviewed paired results show a clear win; not a measured quality conclusion"
    args.out.with_name(args.out.name + "-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cases": len(cases), "rows": len(rows), "fetch_calls": fetch_calls, "review_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
