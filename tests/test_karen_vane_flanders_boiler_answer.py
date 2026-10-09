import asyncio

import httpx
import pytest

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.flanders_boiler_answer import (
    ARTICLE_URL, GAS_PASSAGES, GENERAL_PASSAGES,
    checked_answer_from_html, is_gas_maintenance_question,
)


QUESTION = "Wat zijn de regels voor onderhoud van een gasketel in Vlaanderen? Zoek de officiële informatie."
PAGE = ("<html><body>" + ". ".join(GENERAL_PASSAGES)
        + " Vloeibare brandstof. Gas " + ". ".join(GAS_PASSAGES)
        + ". Vaste brandstof. Jaarlijks onderhoud.</body></html>")


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


def test_official_page_answers_both_power_brackets_without_search():
    result, calls = answer_with_page()
    assert result.status == "answer_with_sources"
    assert result.evidence_status == "passage_checked"
    assert "vanaf 20 kW" in result.answer
    assert "Onder 20 kW" in result.answer
    assert "om de twee jaar" in result.answer
    assert result.answer.count("[1]") == 4
    assert [str(source.url) for source in result.sources] == [ARTICLE_URL]
    assert calls == [ARTICLE_URL]


def test_below_20_kw_evidence_must_be_in_gas_section():
    moved = ("<html><body>" + ". ".join(GENERAL_PASSAGES)
             + ". Vloeibare brandstof. " + GAS_PASSAGES[2]
             + ". Gas. " + ". ".join(GAS_PASSAGES[:2])
             + ". Vaste brandstof.</body></html>")
    result, calls = answer_with_page(moved)
    assert result.status == "insufficient_evidence"
    assert result.evidence_status == "unverified"
    assert "20 kW" not in result.answer
    assert calls == [ARTICLE_URL]


def test_source_failure_redirect_and_hidden_text_abstain():
    assert answer_with_page(status=503)[0].status == "insufficient_evidence"
    assert answer_with_page(offsite=True)[0].status == "insufficient_evidence"
    assert checked_answer_from_html("<script>" + PAGE + "</script>") is None


@pytest.mark.parametrize("question", [
    "Wat zijn de regels voor onderhoud van een gasketel in Wallonië?",
    "Niet in Vlaanderen: onderhoud van een gasketel?",
    "Onderhoud van een gasketel in Vlaanderen en Brussel?",
    "Wat zijn de regels voor onderhoud van een stookolieketel in Vlaanderen?",
    "Wat zijn de regels voor onderhoud van een gasgeiser in Vlaanderen?",
    "Wat kost onderhoud van een gasketel in Vlaanderen?",
    "Wat zijn de regels voor een verwarmingsaudit van een gasketel in Vlaanderen?",
])
def test_route_rejects_other_scope_or_topic(question):
    assert not is_gas_maintenance_question(question)
