import asyncio

import httpx
import pytest

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.wallonia_boiler_answer import (
    ARTICLE_URL, SUPPORTED_CLAIMS, checked_answer_from_html,
    is_residential_comparison,
)


QUESTION = ("Zoek de regels voor onderhoud en periodieke controle van een "
            "gasketel in Wallonië. Wat is het verschil?")
PAGE = "<html><body>" + " ".join(
    f"<p>{passage}.</p>" for _, passages in SUPPORTED_CLAIMS for passage in passages
) + "</body></html>"


def answer_with_page(page=PAGE, *, offsite=False):
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if str(request.url) == ARTICLE_URL:
            target = "https://example.com/" if offsite else ARTICLE_URL + "/"
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200, text=page)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=QUESTION))

    return asyncio.run(run()), calls


def test_complete_residential_page_answers_without_paid_search():
    result, calls = answer_with_page()
    assert result.status == "answer_with_sources"
    assert result.evidence_status == "passage_checked"
    assert result.answer.count("[1]") == 3
    assert "niet door de Waalse wetgeving geregeld" in result.answer
    assert "erkende technicus" in result.answer
    assert [str(source.url) for source in result.sources] == [ARTICLE_URL + "/"]
    assert result.sources[0].excerpt.startswith("Bien que l'entretien")
    assert all("/api/search" not in url and "/api/providers" not in url for url in calls)


def test_missing_passage_abstains_and_does_not_call_search():
    result, calls = answer_with_page(PAGE.replace(SUPPORTED_CLAIMS[1][1][2], ""))
    assert result.status == "insufficient_evidence"
    assert result.evidence_status == "unverified"
    assert "erkende technicus" not in result.answer
    assert len(result.sources) == 1
    assert all("/api/search" not in url for url in calls)


def test_offsite_redirect_and_hidden_passages_cannot_verify():
    assert answer_with_page(offsite=True)[0].status == "insufficient_evidence"
    assert checked_answer_from_html("<script>" + PAGE + "</script>") is None


@pytest.mark.parametrize("question", [
    "Wat is het verschil tussen onderhoud en controle van een gasketel in Brussel?",
    "Niet in Wallonië: wat is het verschil tussen onderhoud en controle van een gasketel?",
    "Wat is het verschil tussen onderhoud en controle van een gasketel in Wallonië en Brussel?",
    "Wat is het verschil tussen onderhoud en controle van een industriële gasketel in Wallonië?",
    "Hoe vaak is het verschil tussen onderhoud en controle van een gasketel in Wallonië?",
    "Wat is het verschil tussen onderhoud en controle van een mazoutketel in Wallonië?",
])
def test_direct_route_requires_matching_residential_gas_scope(question):
    assert not is_residential_comparison(question)
