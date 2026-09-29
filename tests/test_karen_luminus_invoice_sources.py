import pytest

from luminus_harness import gemma_answer
from luminus_harness.knowledge import KnowledgeChunk


@pytest.mark.asyncio
async def test_advance_question_uses_luminus_page_four_and_only_checked_luminus_web_source(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    page_four = KnowledgeChunk(
        page=4,
        text="Luminus werkt met voorschotfacturen en afrekeningen; het ideale voorschot kan op basis van digitale meterdata worden herberekend.",
        urls=(),
    )
    eneco_page = KnowledgeChunk(
        page=7,
        text="Eneco gebruikt voorschotfacturen; op de jaarafrekening worden betaalde voorschotten verrekend.",
        urls=("https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie/",),
    )
    async def fetch_page(_source_key: str):
        return {
            "title": "Je energiefactuur uitgelegd — Luminus",
            "url": "https://www.luminus.be/nl/prive/energie/energiefactuur-uitgelegd/",
            "content": "De jaarafrekening verrekent de werkelijke kosten met de voorschotten.",
        }

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch_page)
    monkeypatch.setattr(gemma_answer, "_generate", lambda _prompt: "De afrekening verrekent je voorschotten met je werkelijke kosten.")

    result = await gemma_answer.answer_energy_question(
        "Waarom verschilt mijn voorschot van mijn jaarafrekening?",
        [page_four, eneco_page],
    )

    assert result["live_source_status"] == "checked"
    assert any(source.get("url", "").startswith("https://www.luminus.be/") for source in result["sources"])
    assert not any(source.get("url", "").startswith("https://eneco.be/") for source in result["sources"])
    assert any(source["detail"] == "PDF · pagina 4" for source in result["sources"])


@pytest.mark.asyncio
async def test_failed_luminus_fetch_is_not_shown_as_used_source(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    page_four = KnowledgeChunk(
        page=4,
        text="Luminus werkt met voorschotfacturen en afrekeningen.",
        urls=(),
    )

    async def fetch_page(_source_key: str):
        return None

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch_page)
    prompts: list[str] = []
    monkeypatch.setattr(gemma_answer, "_generate", lambda prompt: prompts.append(prompt) or "De bron is beperkt.")

    result = await gemma_answer.answer_energy_question("Waarom verschilt mijn voorschot?", [page_four])

    assert result["live_source_status"] == "failed"
    luminus_source = next(source for source in result["sources"] if "luminus.be" in source.get("url", ""))
    assert luminus_source["detail"] == "Gecurateerde officiële uitleg · pagina niet live opgehaald"
    assert "werkelijke kosten verrekend met de voorschotten" in prompts[0]
    assert any(source["detail"] == "PDF · pagina 4" for source in result["sources"])
