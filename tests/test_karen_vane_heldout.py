"""Retrieval diagnostics must not turn plausible sources into factual proof."""

import asyncio

import httpx

from experiments.karen_vane.adapter import KarenAnswer, PublicQuestion, Settings, Source, VaneAdapter
from experiments.karen_vane.evaluate_heldout import HeldoutCase, evaluate


def case(**changes):
    fields = {
        "id": "peak", "question": "Vlaamse maandpiek?",
        "expected_status": ["sources_for_review", "insufficient_evidence"],
        "authority_hosts": ["vreg.be"],
        "concept_groups": [["maandpiek"], ["capaciteitstarief"]],
        "review_note": "Review source",
    }
    return HeldoutCase.model_validate(fields | changes)


def answer(status="sources_for_review", url="https://www.vreg.be/nl/iets",
           excerpt="De maandpiek hoort bij het capaciteitstarief."):
    return KarenAnswer(status=status, answer="Geen bevestigde inhoudelijke conclusie.",
                       sources=[Source(id=1, title="Tarief", url=url, excerpt=excerpt)])


def test_official_domain_and_topic_words_do_not_validate_claims():
    result = evaluate(case(), answer())
    assert result["official_source_present"] is True
    assert result["missing_concept_groups"] == []
    assert result["lexically_matching_authority_count"] == 1
    assert result["claim_verdict"] == "not_evaluated"


def test_spoofed_domain_and_missing_concept_are_visible():
    result = evaluate(case(), answer(url="https://vreg.be.evil.test/page",
                                     excerpt="De maandpiek wordt genoemd."))
    assert result["official_source_present"] is False
    assert result["lexically_matching_authority_count"] == 0
    assert result["missing_concept_groups"] == [["capaciteitstarief"]]


def test_personal_price_requires_abstention_even_with_a_source():
    personal = case(expected_status=["insufficient_evidence"], authority_hosts=[],
                    concept_groups=[])
    result = evaluate(personal, answer())
    assert result["status_allowed"] is False
    assert result["official_source_present"] is None


def test_unverified_answer_with_source_requires_manual_claim_review():
    result = evaluate(case(), answer(status="answer_with_sources"))
    assert result["claim_verdict"] == "manual_review_required"
    assert result["status_allowed"] is False


def test_personal_contract_price_asks_for_missing_context_without_external_calls():
    def never_call(_):
        raise AssertionError("Personal contract question reached Vane or web")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(never_call)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(
                question="Wat betaal ik deze maand precies per kWh aardgas volgens mijn eigen contract?"
            ))

    result = asyncio.run(call())
    assert result.status == "insufficient_evidence"
    assert result.sources == []
    assert "Welke prijs per kWh" in result.answer
    assert result.evidence_status == "unverified"
