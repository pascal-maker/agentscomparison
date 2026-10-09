import asyncio

import httpx
import pytest
from pydantic import ValidationError

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter


PROVIDER = {"id": "local-test", "name": "Karen local Ollama",
            "chatModels": [{"key": "llama3.2:latest"}],
            "embeddingModels": [{"key": "nomic-embed-text:latest"}]}
SOURCE = {"content": "Een openbare passage", "metadata": {"title": "CREG", "url": "https://www.creg.be/"}}


def run(payload=None, *, status=200, providers=None, timeout=False):
    requests = []
    def handle(request):
        requests.append(request)
        if request.url.path == "/api/providers":
            return httpx.Response(200, json={"providers": [PROVIDER] if providers is None else providers})
        if timeout:
            raise httpx.ReadTimeout("synthetic", request=request)
        return httpx.Response(status, json=payload)
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question="Wat is een voorschot?"))
    return asyncio.run(call()), requests


def test_direct_answer_keeps_source_order_without_claiming_verified_prices():
    result, calls = run({"message": "Uitleg [1]", "sources": [
        {"content": "Een voorschot is een tussentijdse factuur", "metadata": SOURCE["metadata"]},
        {"content": "Een voorschot is een tussentijdse factuur", "metadata": SOURCE["metadata"]},
    ]})
    assert "Uitleg [1]" not in result.answer
    assert [s.id for s in result.sources] == [1, 2]
    assert result.evidence_status == "unverified"
    assert result.status == "sources_for_review"
    assert [r.url.path for r in calls] == ["/api/providers", "/api/search"]


def test_unsubstantiated_model_answer_is_not_shown():
    result, _ = run({"message": "Gas costs 0.01 EUR/kWh", "sources": []})
    assert result.status == "insufficient_evidence"
    assert "0.01" not in result.answer


@pytest.mark.parametrize("payload", [
    {"message": "", "sources": [SOURCE]},
    {"message": "answer", "sources": [{"metadata": {"title": "bad", "url": "javascript:alert(1)"}, "content": "x"}]},
    {"message": "answer"},
])
def test_malformed_upstream_is_visible(payload):
    result, _ = run(payload)
    assert result.error_code == "invalid_response"


def test_distinct_service_errors():
    assert run(status=429)[0].error_code == "upstream_http_429"
    assert run(timeout=True)[0].error_code == "timeout"
    result, calls = run(providers=[])
    assert result.error_code == "provider_missing"
    assert len(calls) == 1


@pytest.mark.parametrize("extra", [{"session_id": "pdf-token"}, {"pdf_text": "private invoice"}, {"comparison_session_id": "token"}])
def test_trial_rejects_pdf_and_comparison_payloads(extra):
    with pytest.raises(ValidationError):
        PublicQuestion(question="public question", **extra)
