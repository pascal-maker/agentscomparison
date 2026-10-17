"""Original-source checks are deterministic and do not call paid services."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from experiments.karen_search_ab.benchmark import HERE
from experiments.karen_search_ab.claim_verification import (
    ClaimEvidence,
    NonClaim,
    RegimeStatus,
    SemanticReview,
    _load,
    apply_reviews,
    case_verdict,
    coverage,
    evaluate_case,
    load_snapshots,
    regime_validity,
    uncovered_text,
    verify_claim,
    verify_claims,
)

TODAY = date(2026, 10, 13)


def claim(**changes) -> ClaimEvidence:
    data = {
        "case_id": "be-08", "claim_key": "social_gas_2026q4", "region": "federal",
        "kind": "tariff", "answer_excerpt": "Het tarief bedraagt 5,738 cent/kWh.",
        "source_url": "https://www.creg.be/gas.pdf",
        "quote": "SOCIAAL TARIEF Totaal (c€/kWh) 5,738 exclusief btw",
        "amount": "5,738", "unit": "CENT_PER_KWH",
    }
    return ClaimEvidence.model_validate({**data, **changes})


def page(url="https://www.creg.be/gas.pdf", *, amount="5,738", period=True, stamp="2026-10-13") -> dict:
    text = f"SOCIAAL TARIEF Totaal (c€/kWh) {amount} exclusief btw"
    if period:
        text += "\n4de kwartaal 2026 (1 oktober 2026 - 31 december 2026)"
    return {"url": url, "content": text, "retrieved_at": stamp}


def test_pydantic_requires_amount_and_unit_together() -> None:
    with pytest.raises(ValidationError):
        claim(unit=None)


def test_wrong_region_and_missing_source_fail_closed() -> None:
    assert verify_claim(claim(region="brussels", source_url="https://www.vlaanderen.be/tarief"), "Het tarief bedraagt 5,738 cent/kWh.", [page()], on_date=TODAY)["status"] == "WRONG_REGION_OR_SOURCE"
    assert verify_claim(claim(), "Het tarief bedraagt 5,738 cent/kWh.", [], on_date=TODAY)["status"] == "SOURCE_MISSING"


def test_quote_and_amount_must_match_same_original_passage() -> None:
    assert verify_claim(claim(), "Het tarief bedraagt 5,738 cent/kWh.", [page(amount="6,082")], on_date=TODAY)["status"] == "QUOTE_NOT_FOUND"
    mismatched = claim(amount="6,082", answer_excerpt="Het tarief bedraagt 6,082 cent/kWh.")
    assert verify_claim(mismatched, "Het tarief bedraagt 6,082 cent/kWh.", [page()], on_date=TODAY)["status"] == "AMOUNT_OR_UNIT_NOT_IN_QUOTE"


def test_claim_must_actually_appear_in_answer() -> None:
    assert verify_claim(claim(), "Een ander antwoord.", [page()], on_date=TODAY)["status"] == "CLAIM_NOT_IN_ANSWER"


def test_tariff_period_and_retrieval_freshness() -> None:
    answer = "Het tarief bedraagt 5,738 cent/kWh."
    assert verify_claim(claim(), answer, [page(period=False)], on_date=TODAY)["status"] == "VALIDITY_UNKNOWN"
    assert verify_claim(claim(), answer, [page(stamp="2026-09-01")], on_date=TODAY)["status"] == "SOURCE_STALE"
    assert verify_claim(claim(), answer, [page(stamp="")], on_date=TODAY)["status"] == "RETRIEVAL_TIME_UNKNOWN"
    assert verify_claim(claim(), answer, [page()], on_date=date(2027, 1, 1))["status"] == "OUTSIDE_SOURCE_PERIOD"


def regime(**changes) -> RegimeStatus:
    data = {
        "scheme_id": "flanders_mijn_verbouwpremie_heat_pump", "region": "flanders",
        "description": "Vlaamse Mijn VerbouwPremie voor warmtepompen",
        "current_status": "open", "valid_from": None, "valid_until": date(2027, 12, 31),
        "source_url": "https://www.vlaanderen.be/", "checked_by": "pascal-maker",
        "checked_on": date(2026, 10, 13),
        "note": "Confirmed on a separate official page than the one the claim cites.",
    }
    return RegimeStatus.model_validate({**data, **changes})


def test_regime_validity_without_a_tracked_record_defers_to_the_old_heuristic() -> None:
    assert regime_validity(None, {"x": regime()}, TODAY) is None
    assert regime_validity("untracked_scheme", {"flanders_mijn_verbouwpremie_heat_pump": regime()}, TODAY) is None


def test_regime_validity_suspended_closed_and_window() -> None:
    by_id = {"r": regime()}
    assert regime_validity("r", {"r": regime(current_status="suspended")}, TODAY)["status"] == "SCHEME_SUSPENDED"
    assert regime_validity("r", {"r": regime(current_status="closed")}, TODAY)["status"] == "EXPIRED_DEADLINE"
    assert regime_validity("r", {"r": regime(valid_from=date(2027, 1, 1))}, TODAY)["status"] == "SCHEME_NOT_YET_OPEN"
    assert regime_validity("r", {"r": regime(valid_until=date(2026, 1, 1))}, TODAY)["status"] == "EXPIRED_DEADLINE"
    assert regime_validity("r", by_id, TODAY) is None  # open and on_date within [valid_from, valid_until]


def test_regime_status_rejects_an_inverted_validity_window() -> None:
    with pytest.raises(ValidationError):
        regime(valid_from=date(2027, 1, 1), valid_until=date(2026, 1, 1))


def test_a_tracked_suspended_scheme_blocks_even_without_a_textual_deadline() -> None:
    # The product page never says "suspended" in a date pattern a regex could catch;
    # only the separately tracked regime record knows that.
    subsidy = claim(kind="subsidy", region="brussels", source_url="https://renolution.brussels/j4",
                    answer_excerpt="In Brussel bestaat de RENOLUTION-premie J4.",
                    quote="RENOLUTION J4: categorie I 4.500 euro per woning.",
                    amount=None, unit=None, scheme_id="brussels_renolution_j4_heat_pump")
    source = {"url": "https://renolution.brussels/j4", "content": "RENOLUTION J4: categorie I 4.500 euro per woning."}
    suspended = {"brussels_renolution_j4_heat_pump": regime(
        scheme_id="brussels_renolution_j4_heat_pump", region="brussels",
        description="RENOLUTION J4", current_status="suspended", valid_from=None, valid_until=None)}
    result = verify_claim(subsidy, "In Brussel bestaat de RENOLUTION-premie J4.", [source],
                          on_date=TODAY, regime_status=suspended)
    assert result["status"] == "SCHEME_SUSPENDED"
    # Without the tracked record, the old heuristic cannot see the suspension at all.
    assert verify_claim(subsidy, "In Brussel bestaat de RENOLUTION-premie J4.", [source],
                        on_date=TODAY)["status"] == "VALIDITY_UNKNOWN"


def test_a_tracked_open_scheme_lets_review_proceed_past_validity_unknown() -> None:
    subsidy = claim(kind="subsidy", region="flanders", source_url="https://www.vlaanderen.be/premie",
                    answer_excerpt="| Geothermisch | €6.000 |", amount="6.000", unit="EUR",
                    quote="- geothermisch warmtepomp: 6.000 euro voor categorie 3",
                    scheme_id="flanders_mijn_verbouwpremie_heat_pump")
    source = {"url": "https://www.vlaanderen.be/premie",
             "content": "- geothermisch warmtepomp: 6.000 euro voor categorie 3",
             "retrieved_at": "2026-10-13"}
    open_scheme = {"flanders_mijn_verbouwpremie_heat_pump": regime()}
    assert verify_claim(subsidy, "| Geothermisch | €6.000 |", [source], on_date=TODAY,
                        regime_status=open_scheme)["status"] == "PASSAGE_MATCH_NEEDS_REVIEW"
    # Without the tracked record, the page's silence on a deadline is conservatively unknown.
    assert verify_claim(subsidy, "| Geothermisch | €6.000 |", [source],
                        on_date=TODAY)["status"] == "VALIDITY_UNKNOWN"


def test_conflicting_current_official_amounts_are_flagged() -> None:
    first = claim()
    second = claim(source_url="https://www.economie.fgov.be/other.pdf", amount="6,082",
                   answer_excerpt="Andere bron noemt 6,082 cent/kWh.",
                   quote="SOCIAAL TARIEF Totaal (c€/kWh) 6,082 exclusief btw")
    pages = [page(), page(second.source_url, amount="6,082")]
    results = verify_claims([first, second], "Het tarief bedraagt 5,738 cent/kWh. Andere bron noemt 6,082 cent/kWh.", pages, on_date=TODAY)
    assert [result["status"] for result in results] == ["CONFLICTING_OFFICIAL_AMOUNTS"] * 2
    assert case_verdict(results) == "BLOCKED"


def test_a_passage_match_never_auto_approves_an_answer() -> None:
    answer = "Het tarief bedraagt 5,738 cent/kWh."
    result = verify_claim(claim(), answer, [page()], on_date=TODAY)
    assert case_verdict([result]) == "INCOMPLETE_COVERAGE"
    assert case_verdict([result], coverage(answer, [claim()], [])) == "NEEDS_SEMANTIC_REVIEW"
    assert case_verdict([]) == "UNASSESSED"


def test_every_answer_word_needs_a_claim_or_an_explicit_exemption() -> None:
    answer = "Het tarief bedraagt 5,738 cent/kWh. Het geldt ook voor warmte.\n\nBron: [CREG](https://www.creg.be/x)"
    result = coverage(answer, [claim()], [])
    assert not result["complete"]
    assert result["uncovered"] == ["het geldt ook voor warmte", "bron creg"]
    exempt = [NonClaim(case_id="be-08", excerpt="Bron: CREG", reason="citation")]
    assert coverage(answer, [claim()], exempt)["uncovered"] == ["het geldt ook voor warmte"]
    stale = [NonClaim(case_id="be-08", excerpt="Niet in het antwoord", reason="hedge")]
    assert coverage(answer, [claim()], stale)["exemptions_not_in_answer"] == ["Niet in het antwoord"]
    # Bare connectives may remain unattributed; negations and content words may not.
    assert uncovered_text("Het tarief bedraagt 5,738 cent/kWh en niet meer.", [claim().answer_excerpt]) == ["niet meer"]


def test_claim_without_official_passage_fails_closed() -> None:
    with pytest.raises(ValidationError):
        claim(source_url=None, quote=None)
    with pytest.raises(ValidationError):
        claim(evidence_note="A note is only allowed when no official passage exists.")
    unsupported = claim(source_url=None, quote=None, amount=None, unit=None,
                        evidence_note="Only a commercial blog lists this amount.")
    result = verify_claim(unsupported, "Het tarief bedraagt 5,738 cent/kWh.", [page()], on_date=TODAY)
    assert result["status"] == "NO_OFFICIAL_PASSAGE"
    assert case_verdict([result], {"complete": True}) == "BLOCKED"


def test_bot_challenge_page_is_never_a_source() -> None:
    captcha = {"url": "https://www.creg.be/gas.pdf", "retrieved_at": "2026-10-13",
               "content": "This question is for testing whether you are a human visitor. What code is in the image?"}
    assert verify_claim(claim(), "Het tarief bedraagt 5,738 cent/kWh.", [captcha], on_date=TODAY)["status"] == "SOURCE_MISSING"


def test_kw_amounts_need_the_unit() -> None:
    general = {"kind": "general", "source_url": "https://www.fluvius.be/cap", "region": "flanders",
                   "quote": "Er wordt altijd minimaal 2,5 kW aangerekend voor het capaciteitstarief.",
                   "answer_excerpt": "Er geldt een minimum van 2,5 kW", "amount": "2,5", "unit": "KW"}
    assert claim(**general).unit == "KW"
    with pytest.raises(ValidationError):
        claim(**{**general, "answer_excerpt": "Er geldt een minimum van 2,5 kWh"})


def review(verdict="SUPPORTED", reviewer="independent-reviewer", reviewer_type="model") -> SemanticReview:
    return SemanticReview(claim_key="social_gas_2026q4", reviewer=reviewer, reviewer_type=reviewer_type,
                          verdict=verdict, rationale="The passage states the same amount and period.",
                          reviewed_on=TODAY)


def test_semantic_review_must_be_independent_and_negative_findings_block() -> None:
    answer = "Het tarief bedraagt 5,738 cent/kWh."
    full = coverage(answer, [claim()], [])
    matched = [verify_claim(claim(), answer, [page()], on_date=TODAY)]

    def status(reviews, extracted_by="claim-author"):
        return apply_reviews([claim(extracted_by=extracted_by)], matched, reviews)

    assert status([])[0]["status"] == "NEEDS_INDEPENDENT_REVIEW"
    assert status([review(reviewer="claim-author")])[0]["status"] == "NEEDS_INDEPENDENT_REVIEW"
    model = status([review()])
    assert model[0]["status"] == "MODEL_REVIEW_SUPPORTED"
    assert case_verdict(model, full) == "NEEDS_HUMAN_SIGNOFF"
    human = status([review(reviewer_type="human")])
    assert case_verdict(human, full) == "HUMAN_REVIEWED_SUPPORTED"
    # A self-review cannot approve, but its negative finding still blocks.
    negative = status([review(), review("PARTIALLY_SUPPORTED", reviewer="claim-author")])
    assert negative[0]["status"] == "REVIEW_PARTIALLY_SUPPORTED"
    assert case_verdict(negative, full) == "BLOCKED"
    # A review never rescues a failed deterministic check.
    expired = [{**matched[0], "status": "EXPIRED_DEADLINE"}]
    assert apply_reviews([claim()], expired, [review(reviewer_type="human")])[0]["status"] == "EXPIRED_DEADLINE"


def test_snapshot_fetch_skips_existing_and_reports_failures(tmp_path, monkeypatch) -> None:
    import experiments.karen_search_ab.claim_verification as module
    from experiments.karen_search_ab.providers import SearchError

    monkeypatch.setattr(module, "SOURCES", tmp_path)
    calls = []

    def fetcher(url, **kwargs):
        calls.append(url)
        if "fail" in url:
            raise SearchError("bot-challenge")
        return {"content": "Originele tekst", "retrieved_at": "2026-10-13T10:00:00+00:00"}

    urls = ["https://www.creg.be/a", "https://www.creg.be/fail"]
    assert module.fetch_snapshots(urls, api_key="k", fetcher=fetcher) == ["https://www.creg.be/fail: bot-challenge"]
    assert module.fetch_snapshots(urls, api_key="k", fetcher=fetcher) == ["https://www.creg.be/fail: bot-challenge"]
    assert calls.count("https://www.creg.be/a") == 1
    assert module.load_snapshots(urls) == [{"url": "https://www.creg.be/a", "content": "Originele tekst",
                                            "retrieved_at": "2026-10-13T10:00:00+00:00"}]


def test_official_pdf_is_extracted_with_pypdf(monkeypatch) -> None:
    import base64
    import experiments.karen_search_ab.benchmark as module

    class Page:
        def extract_text(self):
            return "Het officiële PDF-tarief bedraagt 5,738 cent per kWh."

    class Reader:
        pages = [Page()]

    monkeypatch.setattr(module, "PdfReader", lambda _stream: Reader())
    monkeypatch.setattr(
        module,
        "_post_json_fetch",
        lambda _url, _api_key: {
            "statusCode": 200,
            "contentType": "application/pdf",
            "content": base64.b64encode(b"%PDF-1.7\nfixture").decode("ascii"),
        },
    )

    page = module.retrieve_official_page(
        "https://www.creg.be/official.pdf", api_key="k", registry=module.load_domains()
    )
    assert page["retrieval"] == "browserbase_fetch_pdf_pypdf"
    assert "5,738 cent per kWh" in page["content"]


def test_official_pdf_without_extractable_text_is_reported_as_failure(monkeypatch) -> None:
    import base64
    import experiments.karen_search_ab.benchmark as module
    from experiments.karen_search_ab.providers import SearchError

    monkeypatch.setattr(
        module,
        "_post_json_fetch",
        lambda _url, _api_key: {
            "statusCode": 200,
            "contentType": "application/pdf",
            "content": base64.b64encode(b"%PDF-1.7\nfixture").decode("ascii"),
        },
    )
    monkeypatch.setattr(module, "PdfReader", lambda _stream: type("Reader", (), {"pages": []})())

    with pytest.raises(SearchError, match="no readable text"):
        module.retrieve_official_page(
            "https://www.creg.be/official.pdf", api_key="k", registry=module.load_domains()
        )


def test_five_saved_cases_have_expected_conservative_statuses() -> None:
    required = [
        HERE / "results" / "agent-pilot-2026-10-13.json",
        HERE / "results" / "wa-05-original-full.json",
        HERE / "results" / "be-01-vlaanderen-full.json",
        HERE / "results" / "creg-q4-2026-electricity.txt",
        HERE / "results" / "creg-q4-2026-gas.txt",
    ]
    claims = _load("pilot_claims.json", ClaimEvidence)
    snapshots = {claim.source_url for claim in claims if claim.source_url and "/Tarifs/" not in claim.source_url}
    if not all(path.exists() for path in required) or len(load_snapshots(snapshots)) < 6:
        pytest.skip("local pilot evidence and source snapshots are unavailable")
    pilot = json.loads((HERE / "results" / "agent-pilot-2026-10-13.json").read_text(encoding="utf-8"))
    non_claims = _load("pilot_non_claims.json", NonClaim)
    reviews = _load("semantic_reviews.json", SemanticReview)
    verdicts = {}
    for row in pilot["rows"]:
        evaluated = evaluate_case(row, claims, non_claims, reviews, on_date=TODAY)
        assert evaluated["coverage"]["complete"], (row["case_id"], evaluated["coverage"])
        assert not {result["status"] for result in evaluated["claims"]} & {
            "QUOTE_NOT_FOUND", "SOURCE_MISSING", "CLAIM_NOT_IN_ANSWER", "WRONG_REGION_OR_SOURCE"}
        verdicts[row["case_id"]] = evaluated["case_verdict"]
        if row["case_id"] == "wa-05":
            assert {result["status"] for result in evaluated["claims"]} == {"EXPIRED_DEADLINE"}
    assert verdicts == {"fl-01": "HUMAN_REVIEWED_SUPPORTED", "br-04": "HUMAN_REVIEWED_SUPPORTED",
                        "wa-05": "BLOCKED", "be-01": "BLOCKED", "be-08": "BLOCKED"}


def test_committed_claim_files_are_consistent() -> None:
    claims = _load("pilot_claims.json", ClaimEvidence) + _load("eval_claims.json", ClaimEvidence)
    reviews = _load("semantic_reviews.json", SemanticReview)
    _load("pilot_non_claims.json", NonClaim)
    _load("eval_non_claims.json", NonClaim)
    keys = [claim.claim_key for claim in claims]
    assert len(keys) == len(set(keys))
    assert {review.claim_key for review in reviews} <= set(keys)


def test_euro_word_and_list_markers() -> None:
    subsidy = claim(kind="general", region="flanders", source_url="https://www.vlaanderen.be/premie",
                    answer_excerpt="| Geothermisch | €6.000 |", amount="6.000", unit="EUR",
                    quote="- geothermisch warmtepomp: 6.000 euro voor categorie 3")
    source = {"url": "https://www.vlaanderen.be/premie", "content": "- geothermisch warmtepomp: 6.000 euro voor categorie 3"}
    assert verify_claim(subsidy, "| Geothermisch | €6.000 |", [source], on_date=TODAY)["status"] == "PASSAGE_MATCH_NEEDS_REVIEW"
    assert uncovered_text("1. Het tarief bedraagt 5,738 cent/kWh.\n- Het tarief bedraagt 5,738 cent/kWh.",
                          [claim().answer_excerpt]) == []


def test_agent_eval_fetches_only_official_non_pdf_sources() -> None:
    from experiments.karen_search_ab.agent_eval import official_sources
    from experiments.karen_search_ab.benchmark import load_domains

    sources = [{"url": "https://www.creg.be/a.pdf"}, {"url": "https://www.june.energy/blog"},
               {"url": "https://renolution.brussels/nl/premies"}, {"url": "https://www.cwape.be/node/148"}]
    assert official_sources(sources, load_domains()) == ["https://renolution.brussels/nl/premies",
                                                         "https://www.cwape.be/node/148"]


def test_held_out_eval_is_fully_covered_and_fails_closed() -> None:
    runs = [HERE / "results" / "agent-eval-2026-10-13.json", HERE / "results" / "agent-eval-2026-10-13-fl09-retry.json"]
    claims = _load("eval_claims.json", ClaimEvidence)
    snapshots = load_snapshots({claim.source_url for claim in claims if claim.source_url})
    if not all(path.exists() for path in runs) or len(snapshots) < 16:
        pytest.skip("local held-out evaluation evidence is unavailable")
    non_claims = _load("eval_non_claims.json", NonClaim)
    reviews = _load("semantic_reviews.json", SemanticReview)
    rows = {}
    for path in runs:
        for row in json.loads(path.read_text(encoding="utf-8"))["rows"]:
            if row["case_id"] not in rows or not row["agent_error"]:
                rows[row["case_id"]] = row
    verdicts = {}
    for case_id, row in rows.items():
        evaluated = evaluate_case(row, claims, non_claims, reviews, on_date=TODAY)
        assert evaluated["coverage"]["complete"], (case_id, evaluated["coverage"])
        assert not {result["status"] for result in evaluated["claims"]} & {
            "QUOTE_NOT_FOUND", "SOURCE_MISSING", "CLAIM_NOT_IN_ANSWER", "WRONG_REGION_OR_SOURCE"}
        verdicts[case_id] = evaluated["case_verdict"]
    assert sorted(case for case, verdict in verdicts.items() if verdict != "BLOCKED") == ["br-08", "fl-05", "wa-04"]
