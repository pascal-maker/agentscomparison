"""Original-source checks are deterministic and do not call paid services."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from experiments.karen_search_ab.benchmark import HERE
from experiments.karen_search_ab.claim_verification import (
    ClaimEvidence,
    case_verdict,
    pilot_pages,
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
    result = verify_claim(claim(), "Het tarief bedraagt 5,738 cent/kWh.", [page()], on_date=TODAY)
    assert case_verdict([result]) == "SELECTED_CLAIMS_NEED_REVIEW"
    assert case_verdict([]) == "UNASSESSED"


def test_five_saved_cases_have_expected_conservative_statuses() -> None:
    required = [
        HERE / "results" / "agent-pilot-2026-10-13.json",
        HERE / "results" / "wa-05-original-full.json",
        HERE / "results" / "be-01-vlaanderen-full.json",
        HERE / "results" / "creg-q4-2026-electricity.txt",
        HERE / "results" / "creg-q4-2026-gas.txt",
    ]
    if not all(path.exists() for path in required):
        pytest.skip("local, Git-ignored pilot evidence is unavailable")
    pilot = json.loads((HERE / "results" / "agent-pilot-2026-10-13.json").read_text(encoding="utf-8"))
    claims = [ClaimEvidence.model_validate(item) for item in json.loads(
        (HERE / "pilot_claims.json").read_text(encoding="utf-8")
    )]
    expected = {
        "fl-01": ["PASSAGE_MATCH_NEEDS_REVIEW"],
        "br-04": ["PASSAGE_MATCH_NEEDS_REVIEW"],
        "wa-05": ["EXPIRED_DEADLINE", "EXPIRED_DEADLINE"],
        "be-01": ["PASSAGE_MATCH_NEEDS_REVIEW"],
        "be-08": ["PASSAGE_MATCH_NEEDS_REVIEW"] * 3,
    }
    for row in pilot["rows"]:
        selected = [claim for claim in claims if claim.case_id == row["case_id"]]
        results = verify_claims(selected, row["answer"], pilot_pages(row), on_date=TODAY)
        assert [result["status"] for result in results] == expected[row["case_id"]]
