from fastapi.testclient import TestClient
import pytest
from io import BytesIO
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from luminus_harness.knowledge import KnowledgeChunk


def _synthetic_bill_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    }))
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 40 750 Td "
        b"(Leverancier: Luminus. Totaal voorschotten reeds aangerekend: 900,00 EUR.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_uploaded_pdf_and_follow_up_stay_local(monkeypatch) -> None:
    import energy_voice_app

    monkeypatch.setenv("GEMINI_API_KEY", "test-key-present")

    def forbidden_hosted_answer(*args, **kwargs):
        raise AssertionError("PDF follow-up must not call the hosted Gemma route")

    monkeypatch.setattr(energy_voice_app, "answer_energy_question", forbidden_hosted_answer)
    client = TestClient(energy_voice_app.api_app)

    upload = client.post(
        "/api/upload",
        files={"file": ("synthetic-bill.pdf", _synthetic_bill_pdf(), "application/pdf")},
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["processing"] == "local-only"
    assert "€ 900,00" in payload["answer"]
    assert payload["sources"][0]["detail"] == "PDF · pagina 1"

    follow_up = client.post(
        "/api/answer",
        json={"question": "Hoeveel voorschotten zijn aangerekend?", "session_id": payload["session_id"]},
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["processing"] == "local-only"
    assert "900,00" in follow_up.json()["answer"]
    assert "900,00" in follow_up.json()["sources"][0]["excerpt"]

    deleted = client.delete(f"/api/session/{payload['session_id']}")
    assert deleted.status_code == 200
    expired = client.post(
        "/api/answer",
        json={"question": "Wat staat er over voorschotten?", "session_id": payload["session_id"]},
    )
    assert expired.status_code == 404


@pytest.mark.asyncio
async def test_gradio_text_follow_up_keeps_uploaded_pdf_out_of_gemma(monkeypatch) -> None:
    import energy_voice_app

    state = energy_voice_app._fresh_state(None)
    state["knowledge_name"] = "synthetic-bill.pdf"
    state["knowledge_chunks"] = [{
        "page": 2,
        "source": "synthetic-bill.pdf",
        "urls": (),
        "text": "Totaal voorschotten reeds aangerekend: € 900,00 voor elektriciteit.",
    }]

    def forbidden_hosted_answer(*args, **kwargs):
        raise AssertionError("An uploaded PDF question must not call hosted Gemma")

    monkeypatch.setattr(energy_voice_app, "answer_energy_question", forbidden_hosted_answer)
    messages, status, sources, updated_state = await energy_voice_app.answer_text_turn(
        "Hoeveel voorschotten zijn aangerekend?",
        state,
    )

    assert "backend" in status.lower()
    assert "€ 900,00" in messages[-1]["content"]
    assert "PDF · pagina 2" in sources
    assert updated_state["knowledge_name"] == "synthetic-bill.pdf"


@pytest.mark.asyncio
async def test_gradio_voice_follow_up_is_blocked_for_uploaded_pdf(monkeypatch) -> None:
    import energy_voice_app
    import numpy as np

    state = energy_voice_app._fresh_state(None)
    state["knowledge_name"] = "synthetic-bill.pdf"
    monkeypatch.setattr(
        energy_voice_app,
        "VoicePipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("External voice stack must not run")),
    )

    response = energy_voice_app.answer_voice_turn((24_000, np.zeros(32, dtype=np.int16)), state)
    outputs = await anext(response)

    assert "Spraak uit voor factuurprivacy" in outputs[2]
