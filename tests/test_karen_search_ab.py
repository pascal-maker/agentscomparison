"""Offline tests: no live search or Fetch calls."""

import pytest

from experiments.karen_search_ab import benchmark, providers


def test_benchmark_set_covers_regions_and_topics():
    cases = benchmark.load_cases()
    assert len(cases) == 38
    assert {item["region"] for item in cases} == {"flanders", "brussels", "wallonia", "federal"}
    assert {item["topic"] for item in cases} >= {
        "contracts", "bills", "prices", "solar", "digital_meter", "heating", "subsidies", "consumer_rights"
    }
    assert all("@" not in item["query"] and "EAN" not in item["query"] for item in cases)


def test_perplexity_sends_raw_search_parameters_without_a_model(monkeypatch):
    observed = {}

    def fake_post(url, body, headers, **kwargs):
        observed.update(url=url, body=body, headers=headers)
        return {"results": [{"title": "CREG", "url": "https://www.creg.be/nl/info",
                             "snippet": "Zoekfragment", "date": "2026-01-01", "last_updated": "2026-02-01"}]}

    monkeypatch.setattr(providers, "_post_json", fake_post)
    response = providers.PerplexitySearch("test-key").search("sociaal tarief", scope_domains=("creg.be",))
    assert observed["url"] == "https://api.perplexity.ai/search"
    assert observed["body"] == {
        "query": "sociaal tarief", "country": "BE", "search_language_filter": ["nl", "fr"],
        "max_results": 5, "max_tokens": 1500, "max_tokens_per_page": 300, "search_type": "web"
    }
    assert "search_domain_filter" not in observed["body"]
    assert response.results[0].last_updated == "2026-02-01"
    assert response.results[0].snippet == "Zoekfragment"


def test_perplexity_domain_filter_is_explicit_opt_in(monkeypatch):
    observed = {}
    monkeypatch.setattr(providers, "_post_json", lambda url, body, headers: observed.update(body) or {"results": []})
    providers.PerplexitySearch("test-key", domain_filter=True).search("warmtepomp", scope_domains=("vlaanderen.be",))
    assert observed["search_domain_filter"] == ["vlaanderen.be"]


def test_browserbase_mirrors_site_scoped_query_and_keeps_five_ranks(monkeypatch):
    observed = {}

    def fake_post(url, body, headers):
        observed.update(body)
        return {"results": [{"title": str(i), "url": f"https://www.creg.be/{i}"} for i in range(6)]}

    monkeypatch.setattr(providers, "_post_json", fake_post)
    response = providers.BrowserbaseSearch("test-key").search("dynamisch contract", scope_domains=("creg.be", "economie.fgov.be"))
    assert observed == {"query": "dynamisch contract site:creg.be OR site:economie.fgov.be", "numResults": 5}
    assert len(response.results) == 5


def test_french_escalation_only_without_regional_official_result():
    registry = benchmark.load_domains()

    class Stub:
        name = "perplexity"

        def __init__(self):
            self.calls = []

        def search(self, query, *, scope_domains=()):
            self.calls.append(query)
            url = "https://www.creg.be/info" if len(self.calls) == 1 else "https://www.brugel.brussels/fr/info"
            return providers.SearchResponse(self.name, query, (providers.SearchResult("x", url),), 4, 0.005)

    stub = Stub()
    row = benchmark.search_case({"id": "x", "question": "x", "region": "brussels", "topic": "x",
                                 "query": "slimme meter", "fr_query": "compteur intelligent"}, stub, registry)
    assert stub.calls == ["slimme meter", "compteur intelligent"]
    assert row["search_rounds"] == 2
    assert row["candidates"][1]["organization"] == "BRUGEL"


def test_known_official_url_skips_paid_search():
    class NeverSearch:
        name = "perplexity"

        def search(self, *args, **kwargs):
            raise AssertionError("Known URL must bypass search")

    row = benchmark.search_case({"id": "x", "question": "x", "region": "federal", "topic": "x"},
                                NeverSearch(), benchmark.load_domains(), known_url="https://www.creg.be/nl/a-z-index")
    assert row["search_rounds"] == 0
    assert row["candidates"][0]["organization"] == "CREG"


def test_shared_original_retrieval_is_cached_but_remains_unverified():
    calls = []
    url = "https://www.creg.be/nl/info"
    rows = [{"case_id": "x", "region": "federal", "topic": "consumer_rights", "candidates": [{
        "url": url, "title": "CREG", "query": "sociaal tarief", "organization": "CREG", "round": 1, "rank": 1,
        "published_date": "", "last_updated": ""}], "evidence": []} for _ in range(2)]

    def fake_fetch(value, *, api_key, registry):
        calls.append(value)
        return {"content": "Originele CREG-passage", "retrieved_at": "2026-10-12T00:00:00Z"}

    count = benchmark.attach_shared_retrieval(rows, benchmark.load_domains(), "test-key", fake_fetch)
    assert count == 1 and calls == [url]
    assert all(row["evidence"][0]["verification_status"] == "UNVERIFIED" for row in rows)
    assert all(row["evidence"][0]["original_page_content"] == "Originele CREG-passage" for row in rows)


def test_operational_meter_question_prefers_network_manager_for_fetch():
    registry = benchmark.load_domains()
    regulator = {"organization": "Vlaamse Nutsregulator", "round": 1, "rank": 1}
    network = {"organization": "Fluvius", "round": 1, "rank": 3}
    assert benchmark.source_priority(network, region="flanders", topic="digital_meter", registry=registry) < \
        benchmark.source_priority(regulator, region="flanders", topic="digital_meter", registry=registry)
    assert benchmark.source_priority(regulator, region="flanders", topic="prices", registry=registry) < \
        benchmark.source_priority(network, region="flanders", topic="prices", registry=registry)


def test_review_metrics_require_completed_human_labels():
    row = {"case_id": "x", "provider": "perplexity", "error": "", "search_rounds": 1,
           "search_latency_ms": 100, "estimated_search_usd": 0.005, "evidence": [],
           "candidates": [{"organization": "CREG"}]}
    pending = benchmark.review_template([row])[0]
    assert benchmark.summarize([row], [pending])["perplexity"]["official_source_at_3"]["n"] == 0
    pending.update(review_status="COMPLETE", correct_official_ranks_first_round=[],
                   answerable=False, passage_verification=False, finding="NOT_FOUND")
    metrics = benchmark.summarize([row], [pending])["perplexity"]
    assert metrics["official_source_at_3"] == {"value": 0.0, "n": 1}
    assert metrics["passage_verification"] == {"value": 0.0, "n": 1}
    assert metrics["unsupported_claim_rate"]["value"] is None


def test_fetch_refuses_unconfigured_or_non_https_url():
    registry = benchmark.load_domains()
    for url in ("http://www.creg.be/info", "https://example.com/info", "https://creg.be.evil.test/",
                "https://user:password@creg.be/info"):
        with pytest.raises(providers.SearchError):
            benchmark.retrieve_official_page(url, api_key="test-key", registry=registry)


def test_verified_review_needs_exact_original_passage():
    row = {"case_id": "x", "provider": "browserbase", "error": "", "search_rounds": 1,
           "search_latency_ms": 3, "estimated_search_usd": 0.007, "candidates": [],
           "evidence": [{"url": "https://www.creg.be/info", "original_page_content": "Een originele passage over het tarief."}]}
    review = benchmark.review_template([row])[0]
    review.update(review_status="COMPLETE", finding="VERIFIED", answerable=True,
                  passage_verification=True, supporting_url="https://www.creg.be/info",
                  supporting_claim="Het tarief wordt toegelicht.", supporting_passage="Niet op de pagina")
    with pytest.raises(ValueError, match="exact passage"):
        benchmark.summarize([row], [review])
    review["supporting_passage"] = "Een originele passage over het tarief."
    assert benchmark.summarize([row], [review])["browserbase"]["passage_verification"]["value"] == 1.0
