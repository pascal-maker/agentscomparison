import asyncio

import httpx
import pytest

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.brussels_boiler_answer import (
    ARTICLE_URL, REQUIRED_PASSAGES, checked_answer_from_html,
    is_residential_frequency_question,
)


QUESTION = "Hoe vaak moet een gasketel in Brussel gecontroleerd worden? Zoek de officiële regels op."
PAGE = "<html><body>" + " ".join(f"<p>{p}.</p>" for p in REQUIRED_PASSAGES) + "</body></html>"


def answer_with_page(page=PAGE, *, offsite=False, status=200):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if offsite and str(request.url) == ARTICLE_URL:
            return httpx.Response(302, headers={"location": "https://example.com/"})
        return httpx.Response(status, text=page)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=QUESTION))

    return asyncio.run(run()), calls


def test_official_page_answers_with_natural_gas_scope_without_search():
    result, calls = answer_with_page()
    assert result.status == "answer_with_sources"
    assert result.evidence_status == "passage_checked"
    assert "op aardgas" in result.answer
    assert "om de twee jaar" in result.answer
    assert "erkende technicus" in result.answer
    assert [str(source.url) for source in result.sources] == [ARTICLE_URL]
    assert result.sources[0].excerpt == REQUIRED_PASSAGES[1]
    assert calls == [ARTICLE_URL]


def test_missing_source_passage_abstains_without_paid_search():
    result, calls = answer_with_page(PAGE.replace(REQUIRED_PASSAGES[1], ""))
    assert result.status == "insufficient_evidence"
    assert result.evidence_status == "unverified"
    assert "twee jaar" not in result.answer
    assert calls == [ARTICLE_URL]


def test_official_page_error_abstains_without_paid_search():
    result, calls = answer_with_page(status=503)
    assert result.status == "insufficient_evidence"
    assert "twee jaar" not in result.answer
    assert calls == [ARTICLE_URL]


def test_redirect_and_hidden_text_cannot_verify():
    assert answer_with_page(offsite=True)[0].status == "insufficient_evidence"
    assert checked_answer_from_html("<script>" + PAGE + "</script>") is None


@pytest.mark.parametrize("question", [
    "Hoe vaak moet een gasketel in Vlaanderen gecontroleerd worden?",
    "Niet in Brussel: hoe vaak moet een gasketel gecontroleerd worden?",
    "Hoe vaak in Brussel en Wallonië moet een gasketel gecontroleerd worden?",
    "Hoe vaak moet een industriële gasketel in Brussel gecontroleerd worden?",
    "Hoe vaak moet een gasketel op propaan in Brussel gecontroleerd worden?",
    "Hoe vaak moet een stookolieketel in Brussel gecontroleerd worden?",
])
def test_route_rejects_other_regions_fuels_and_building_types(question):
    assert not is_residential_frequency_question(question)
