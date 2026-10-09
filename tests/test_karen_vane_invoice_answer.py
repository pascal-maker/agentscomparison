import asyncio

import httpx

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.invoice_answer import REQUIRED_PASSAGES, checked_answer_from_html


QUESTION = "Zoek bij Eneco het verschil tussen een voorschotfactuur en een jaarafrekening."
ARTICLE = "https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie"
PROVIDER = {"id": "local", "name": "Karen local Ollama",
            "chatModels": [{"key": "llama3.2:latest"}],
            "embeddingModels": [{"key": "nomic-embed-text:latest"}]}


def call_adapter(page: str, *, article_present=True):
    def respond(request):
        if request.url.path == "/api/providers":
            return httpx.Response(200, json={"providers": [PROVIDER]})
        if request.url.path == "/api/search":
            sources = [{"content": "Een voorschotfactuur", "metadata": {
                "title": "Eneco afrekening", "url": ARTICLE}}] if article_present else [
                {"content": "My Eneco afrekening", "metadata": {
                    "title": "My Eneco", "url": "https://eneco.be/nl/contact/my-eneco"}}]
            return httpx.Response(200, json={"message": "Voorschot is werkelijk maandverbruik [8]", "sources": sources})
        if request.url.host == "eneco.be":
            return httpx.Response(200, text=page)
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=QUESTION))

    return asyncio.run(run())


def test_complete_official_passages_produce_short_supported_answer():
    page = "<html><body>" + " ".join(f"<p>{p}.</p>" for p in REQUIRED_PASSAGES) + "</body></html>"
    result = call_adapter(page)
    assert result.status == "answer_with_sources"
    assert result.evidence_status == "passage_checked"
    assert "voorschotfacturen" in result.answer
    assert "betaal je het verschil bij" in result.answer
    assert result.answer.count("[1]") == 4
    assert "werkelijk maandverbruik" not in result.answer
    assert [s.id for s in result.sources] == [1]
    assert str(result.sources[0].url).startswith(ARTICLE)


def test_missing_support_does_not_show_model_answer():
    page = "<html><body>" + " ".join(REQUIRED_PASSAGES[:-1]) + "</body></html>"
    result = call_adapter(page)
    assert result.status == "sources_for_review"
    assert result.evidence_status == "unverified"
    assert "werkelijk maandverbruik" not in result.answer


def test_article_must_have_appeared_in_search_sources():
    result = call_adapter("", article_present=False)
    assert result.status == "sources_for_review"


def test_html_with_phrases_only_in_script_is_rejected():
    page = "<script>" + " ".join(REQUIRED_PASSAGES) + "</script>"
    assert checked_answer_from_html(page) is None
