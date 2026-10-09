import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from experiments.karen_vane.invoice_answer import SUPPORTED_CLAIMS
from experiments.karen_vane.structured_claims import (
    ARTICLE_URL, CandidateBatch, fetch_invoice_section, propose_claims,
    render_checked_claims, verify_claims,
)


SOURCE_TEXT = ". ".join(p for _, passages in SUPPORTED_CLAIMS for p in passages)


def candidate(**overrides):
    value = {"entity": "eneco_be", "topic": "invoice", "claim_id": "underpaid",
             "source_url": ARTICLE_URL,
             "evidence_quote": SUPPORTED_CLAIMS[2][1][0]}
    value.update(overrides)
    return value


def test_verified_model_claim_uses_fixed_answer_text():
    batch = CandidateBatch.model_validate({"claims": [candidate()]})
    accepted = verify_claims(batch, SOURCE_TEXT, ARTICLE_URL)
    assert accepted == ["underpaid"]
    assert render_checked_claims(accepted) == SUPPORTED_CLAIMS[2][0] + " [1]"


@pytest.mark.parametrize("change", [
    {"entity": "eneco_sg"}, {"claim_id": "invented_price"}, {"extra": "claim"},
])
def test_schema_rejects_wrong_entity_unknown_claim_and_extra_field(change):
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate({"claims": [candidate(**change)]})


def test_quote_and_full_support_must_be_on_authorized_page():
    batch = CandidateBatch.model_validate({"claims": [candidate()]})
    assert verify_claims(batch, SOURCE_TEXT.replace(SUPPORTED_CLAIMS[2][1][1], ""), ARTICLE_URL) == []
    assert verify_claims(batch, SOURCE_TEXT, "https://eneco.nl/factuur") == []
    fabricated = CandidateBatch.model_validate({"claims": [candidate(evidence_quote="een verzonnen jaarlijks bedrag van 2000 euro")]})
    assert verify_claims(fabricated, SOURCE_TEXT, ARTICLE_URL) == []
    empty = CandidateBatch.model_validate({"claims": [candidate(evidence_quote="")]})
    assert verify_claims(empty, SOURCE_TEXT, ARTICLE_URL) == []


def test_local_ollama_request_uses_schema_and_validator_still_filters_claims():
    def respond(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["format"]["type"] == "object"
        assert "$defs" not in body["format"]
        assert body["options"]["temperature"] == 0
        return httpx.Response(200, json={"message": {"content": json.dumps({
            "claims": [candidate(evidence_quote="een verzonnen jaarlijks bedrag van 2000 euro")]
        })}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await propose_claims(client, SOURCE_TEXT)

    batch = asyncio.run(run())
    assert verify_claims(batch, SOURCE_TEXT, ARTICLE_URL) == []


def test_live_page_fetch_extracts_visible_official_section_only():
    page = ("<html><script>" + SOURCE_TEXT + "</script><body>Header "
            + "<p>" + "</p><p>".join(SOURCE_TEXT.split(". "))
            + "</p> Unrelated footer</body></html>")

    async def run():
        def respond(request):
            if str(request.url) == ARTICLE_URL:
                return httpx.Response(301, headers={"location": ARTICLE_URL + "/"})
            return httpx.Response(200, text=page)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await fetch_invoice_section(client)

    result = asyncio.run(run())
    assert result is not None
    text, url = result
    assert url == ARTICLE_URL + "/"
    assert "Unrelated footer" not in text
    assert verify_claims(CandidateBatch.model_validate({"claims": [
        candidate(source_url=url)]}), text, url) == ["underpaid"]


def test_live_page_fetch_rejects_offsite_redirect_and_hidden_passages():
    async def run(respond):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await fetch_invoice_section(client)

    assert asyncio.run(run(lambda _: httpx.Response(
        200, text="<script>" + SOURCE_TEXT + "</script>"))) is None

    def offsite(request):
        if request.url.host == "eneco.be":
            return httpx.Response(302, headers={"location": "https://example.com/"})
        return httpx.Response(200, text=SOURCE_TEXT)

    assert asyncio.run(run(offsite)) is None
