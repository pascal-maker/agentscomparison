"""Official navigation answers require the expected visible page, without Vane."""

import asyncio

import httpx
import pytest

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.public_navigation_answer import PAGES, page_for_question


QUESTIONS = {
    "brussels_supplier_switch": "Welke Brusselse instantie legt uit hoe ik van elektriciteitsleverancier kan veranderen?",
    "wallonia_gas_meter": "Waar geeft Wallonië officiële uitleg over het doorgeven van mijn meterstand voor aardgas?",
    "belgian_contract_exit": "Waar staat de officiële uitleg over een eventuele opzegvergoeding bij een particulier elektriciteitscontract in België?",
}


@pytest.mark.parametrize("topic", list(QUESTIONS))
def test_checked_navigation_uses_only_exact_official_page(topic):
    page = PAGES[topic]
    calls = []

    def respond(request):
        calls.append(str(request.url))
        assert str(request.url) == page.url
        return httpx.Response(200, text="<html><body>" + " ".join(page.required_passages) + "</body></html>")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=QUESTIONS[topic]))

    result = asyncio.run(call())
    assert calls == [page.url]
    assert result.status == "answer_with_sources"
    assert result.evidence_status == "passage_checked"
    assert [str(source.url) for source in result.sources] == [page.url]
    assert "[1]" in result.answer
    assert "één maand" not in result.answer
    assert "drie weken" not in result.answer


@pytest.mark.parametrize("topic", list(QUESTIONS))
def test_missing_passage_fails_closed_without_vane_or_web_search(topic):
    page = PAGES[topic]

    def respond(request):
        assert str(request.url) == page.url
        return httpx.Response(200, text="<html><body>Unrelated content</body></html>")

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=QUESTIONS[topic]))

    result = asyncio.run(call())
    assert result.status == "insufficient_evidence"
    assert result.sources == []


def test_redirect_to_unrelated_page_is_rejected():
    page = PAGES["brussels_supplier_switch"]

    def respond(request):
        if str(request.url) == page.url:
            return httpx.Response(302, headers={"location": "https://example.com/other"})
        return httpx.Response(200, text=" ".join(page.required_passages))

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(
                question=QUESTIONS["brussels_supplier_switch"]
            ))

    assert asyncio.run(call()).status == "insufficient_evidence"


def test_ambiguous_or_non_navigation_question_does_not_select_page():
    assert page_for_question("Waar staat officiële uitleg voor Brussel én Wallonië over meterstanden?") is None
    assert page_for_question("Vergelijk drie elektriciteitsleveranciers voor Brussel") is None
