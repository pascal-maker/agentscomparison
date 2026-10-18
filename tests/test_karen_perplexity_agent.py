"""The optional Agent API route keeps private and comparison flows separate."""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from luminus_harness import perplexity_agent as agent


@pytest.fixture(autouse=True)
def fake_perplexity_sdk_if_unavailable(monkeypatch) -> None:
    """Mock the paid SDK even in a checkout without optional dependencies."""
    try:
        import perplexity  # noqa: F401
    except ImportError:
        module = ModuleType("perplexity")
        module.APIConnectionError = type("APIConnectionError", (Exception,), {})
        module.APIStatusError = type("APIStatusError", (Exception,), {})
        module.Perplexity = None
        monkeypatch.setitem(sys.modules, "perplexity", module)


def test_agent_extracts_search_sources_and_keeps_unverified_label(monkeypatch) -> None:
    calls = []
    response = SimpleNamespace(
        status="completed",
        output_text="Het capaciteitstarief hangt af van de maandpiek [web:1].",
        output=[SimpleNamespace(type="search_results", results=[
            SimpleNamespace(id=1, url="https://www.vlaamsenutsregulator.be/capaciteitstarief", title="Capaciteitstarief", date=None),
            SimpleNamespace(id=2, url="https://example.com/uncited", title="Uncited", date=None),
        ])],
    )

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return response

    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(responses=FakeResponses()))
    result = agent.answer_public_web_question("Wat is het capaciteitstarief in Vlaanderen?")

    assert result["evidence_status"] == "AGENT_CITED_UNVERIFIED"
    assert result["sources"] == [{
        "title": "Capaciteitstarief",
        "url": "https://www.vlaamsenutsregulator.be/capaciteitstarief",
        "date": "",
    }]
    assert calls[0]["tools"][0]["type"] == "web_search"
    assert calls[0]["tools"][0]["user_location"] == {"country": "BE"}
    assert calls[0]["model"] == "openai/gpt-6-luna"


def test_agent_does_not_present_unsourced_text_as_grounded(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(status="completed", output_text="Een onbewezen claim", output=[]))
    ))
    result = agent.answer_public_web_question("Wat is het sociaal tarief?")
    assert result["evidence_status"] == "NOT_FOUND"
    assert result["sources"] == []
    assert "onbewezen" not in result["answer"]


def test_uncited_search_results_are_labelled_as_candidates(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="completed",
            output_text="Het capaciteitstarief hangt af van de maandpiek.",
            output=[SimpleNamespace(type="search_results", results=[
                SimpleNamespace(id=1, url="https://www.vlaamsenutsregulator.be/capaciteitstarief", title="Capaciteitstarief", date=None),
            ])],
        ))
    ))
    result = agent.answer_public_web_question("Wat is het capaciteitstarief?")
    assert result["evidence_status"] == "SEARCH_CANDIDATES_UNVERIFIED"
    assert len(result["sources"]) == 1


def test_answer_links_take_priority_over_uncited_search_candidates(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="completed",
            output_text="Zie [de regulator](https://www.creg.be/nl/sociaal-tarief).",
            output=[SimpleNamespace(type="search_results", results=[
                SimpleNamespace(id=1, url="https://example.com/other", title="Other", date=None),
            ])],
        ))
    ))
    result = agent.answer_public_web_question("Wat is het sociaal tarief?")
    assert result["evidence_status"] == "ANSWER_LINKS_UNVERIFIED"
    assert result["sources"][0]["url"] == "https://www.creg.be/nl/sociaal-tarief"


def test_answer_links_take_priority_over_machine_citations(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="completed",
            output_text="Zie [de officiële uitleg](https://www.creg.be/nl/sociaal-tarief) [web:1].",
            output=[SimpleNamespace(type="search_results", results=[
                SimpleNamespace(id=1, url="https://example.com/commercial", title="Blog", date=None),
            ])],
        ))
    ))
    result = agent.answer_public_web_question("Wat is het sociaal tarief?")
    assert result["evidence_status"] == "ANSWER_LINKS_UNVERIFIED"
    assert result["sources"][0]["url"] == "https://www.creg.be/nl/sociaal-tarief"


@pytest.mark.parametrize("answer", [
    "De premie is nu €600. [Waalse overheid](https://energie.wallonie.be/premies)",
    "Het tarief is 5,738 cent/kWh. [CREG](https://www.creg.be/nl/sociaal-tarief)",
    "De premie bedraagt 600 €. [Waalse overheid](https://energie.wallonie.be/premies)",
    "Het tarief is 5,738 c€/kWh. [CREG](https://www.creg.be/nl/sociaal-tarief)",
])
def test_current_amounts_are_withheld_without_original_source_verification(monkeypatch, answer) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="completed", output_text=answer, output=[]))
    ))
    result = agent.answer_public_web_question("Welke regeling geldt nu?")
    assert result["evidence_status"] == "CURRENT_AMOUNT_UNVERIFIED"
    assert "600" not in result["answer"] and "5,738" not in result["answer"]
    assert result["sources"] and all("example.com" not in s["url"] for s in result["sources"])


def test_commercial_source_is_not_presented_as_official_for_amount(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="completed", output_text="€600 [blog](https://example.com/premies)", output=[]))
    ))
    result = agent.answer_public_web_question("Welke premie bestaat er?")
    assert result["evidence_status"] == "CURRENT_AMOUNT_UNVERIFIED"
    assert result["sources"] == []


def test_incomplete_agent_response_is_not_shown(monkeypatch) -> None:
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-only")
    monkeypatch.setattr("perplexity.Perplexity", lambda **kwargs: SimpleNamespace(
        responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(
            status="incomplete",
            output_text="Een halve uitleg [web:1]",
            output=[SimpleNamespace(type="search_results", results=[
                SimpleNamespace(id=1, url="https://example.com/source", title="Source", date=None),
            ])],
        ))
    ))
    assert agent.answer_public_web_question("Wat is het sociaal tarief?")["evidence_status"] == "NOT_FOUND"


@pytest.mark.parametrize("question", [
    "Wat staat er op mijn factuur?",
    "Mijn EAN 541234567890123456, wat betekent dit?",
    "Mail mij op pascal@example.com over zonnepanelen",
    "Wat is het capaciteitstarief?\nKlantnummer 123",
])
def test_private_input_is_rejected_before_agent_call(monkeypatch, question) -> None:
    import energy_voice_app as app

    monkeypatch.setattr(app, "answer_public_web_question", lambda *_args: pytest.fail("external call"))
    with TestClient(app.api_app) as client:
        response = client.post("/api/public-web-answer", json={"question": question})
    assert response.status_code == 422


def test_endpoint_rejects_session_and_offer_comparison(monkeypatch) -> None:
    import energy_voice_app as app

    monkeypatch.setattr(app, "answer_public_web_question", lambda *_args: pytest.fail("external call"))
    with TestClient(app.api_app) as client:
        session = client.post("/api/public-web-answer", json={"question": "Wat is het capaciteitstarief?", "session_id": "x" * 20})
        comparison = client.post("/api/public-web-answer", json={"question": "Vergelijk gasaanbiedingen in Brussel"})
    assert session.status_code == 422
    assert comparison.status_code == 422


def test_endpoint_returns_public_answer_and_speech_token(monkeypatch) -> None:
    import energy_voice_app as app

    monkeypatch.setattr(app, "answer_public_web_question", lambda _question: {
        "answer": "Een algemeen antwoord.",
        "sources": [{"title": "Regulator", "url": "https://example.com", "date": ""}],
        "evidence_status": "SEARCH_CANDIDATES_UNVERIFIED",
    })
    with TestClient(app.api_app) as client:
        response = client.post("/api/public-web-answer", json={"question": "Wat is het sociaal tarief?"})
    assert response.status_code == 200
    assert response.json()["processing"] == "perplexity-agent-public-web"
    assert response.json()["evidence_status"] == "SEARCH_CANDIDATES_UNVERIFIED"
    assert response.json()["petra_speech_token"]


def test_endpoint_maps_rate_limit_and_retry_after(monkeypatch) -> None:
    import energy_voice_app as app

    def limited(_question):
        raise agent.PublicWebAgentError("De webdienst is tijdelijk te druk.", 429, "12")

    monkeypatch.setattr(app, "answer_public_web_question", limited)
    with TestClient(app.api_app) as client:
        response = client.post("/api/public-web-answer", json={"question": "Wat is het sociaal tarief?"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "12"
