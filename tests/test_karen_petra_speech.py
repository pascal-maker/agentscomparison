"""Public Petra playback must never receive text from a PDF session."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from luminus_harness.knowledge import KnowledgeChunk


def test_public_answer_can_be_spoken_after_text_is_returned(monkeypatch) -> None:
    import energy_voice_app as app

    async def public_answer(*_args):
        return {"answer": "De voorschotten worden op de afrekening verrekend.", "sources": []}

    spoken = []
    monkeypatch.setattr(app, "answer_energy_question", public_answer)
    monkeypatch.setattr(app, "synthesize_petra", lambda text: spoken.append(text) or b"RIFF0000WAVE")
    with TestClient(app.api_app) as client:
        answer = client.post("/api/answer", json={"question": "Wat zijn voorschotten?"})
        assert answer.status_code == 200
        assert spoken == []
        token = answer.json()["petra_speech_token"]

        audio = client.post("/api/petra-speech", json={"token": token})
        assert audio.status_code == 200
        assert audio.headers["content-type"] == "audio/wav"
        assert audio.headers["cache-control"] == "no-store"
        assert spoken == [answer.json()["answer"]]


def test_pdf_answer_never_receives_petra_token(monkeypatch) -> None:
    import energy_voice_app as app

    monkeypatch.setattr(
        app, "answer_uploaded_pdf_question",
        lambda *_args: {"answer": "Je factuur toont een persoonlijk bedrag.", "sources": []},
    )
    session_id = app._store_upload_session(
        [KnowledgeChunk(text="Privéfactuur", page=1, urls=(), source="factuur.pdf")],
        {}, "factuur.pdf",
    )
    with TestClient(app.api_app) as client:
        answer = client.post(
            "/api/answer",
            json={"question": "Wat staat op mijn factuur?", "session_id": session_id},
        )
    assert answer.status_code == 200
    assert answer.json()["processing"] == "local-only"
    assert "petra_speech_token" not in answer.json()
    app._upload_sessions.pop(session_id, None)


def test_petra_service_failure_does_not_expose_internal_error(monkeypatch) -> None:
    import energy_voice_app as app

    def unavailable(_text):
        raise RuntimeError("demo secret diagnostic")

    monkeypatch.setattr(app, "synthesize_petra", unavailable)
    token = app._sign_public_speech("Publiek antwoord")
    with TestClient(app.api_app) as client:
        response = client.post("/api/petra-speech", json={"token": token})
    assert response.status_code == 503
    assert response.json()["detail"] == "Petra is nu niet beschikbaar."


def test_petra_token_rejects_tampering_and_expiry(monkeypatch) -> None:
    import energy_voice_app as app

    monkeypatch.setattr(app.time, "time", lambda: 1000)
    token = app._sign_public_speech("Publiek antwoord")
    assert token is not None
    assert app._public_speech_from_token(token) == "Publiek antwoord"
    with pytest.raises(HTTPException) as invalid:
        app._public_speech_from_token("x" * 40)
    assert invalid.value.status_code == 404

    monkeypatch.setattr(app.time, "time", lambda: 1301)
    with pytest.raises(HTTPException) as expired:
        app._public_speech_from_token(token)
    assert expired.value.status_code == 404
    assert app._sign_public_speech("a" * (app.MAX_SPEECH_CHARS + 1)) is None
