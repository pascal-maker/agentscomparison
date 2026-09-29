import pytest

from luminus_harness import gemma_answer
from luminus_harness.browserbase_sources import ENERGY_SOURCES
from luminus_harness.knowledge import KnowledgeChunk


CREG_TEXT = (
    "Voor consumenten, zelfstandigen en kleine bedrijven is de verbrekingsvergoeding afgeschaft.\n"
    "Zij kunnen hun contract op gelijk welk moment stopzetten."
)
LUMINUS_TEXT = "Je kunt dit heel eenvoudig online doen via je My Luminus-klantenzone."


def page(key, content):
    title, url = ENERGY_SOURCES[key]
    return {"title": title, "url": url, "content": content}


def forbid_generation(_prompt):
    raise AssertionError("Cancellation rules must come from verified official passages")


@pytest.mark.asyncio
async def test_reported_question_uses_creg_without_assuming_a_supplier(monkeypatch):
    calls = []

    async def fetch(key):
        calls.append(key)
        return page(key, CREG_TEXT)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    monkeypatch.setattr(gemma_answer, "_generate", forbid_generation)
    result = await gemma_answer.answer_energy_question(
        "Wanneer kan ik mijn contract stopzetten bij mijn energie?", []
    )
    assert calls == ["creg_cancellation"]
    assert "op elk moment" in result["answer"]
    assert "zonder verbrekingsvergoeding" in result["answer"]
    assert "Bij welke leverancier" in result["answer"]
    assert "Luminus" not in result["answer"]
    assert result["sources"][0]["excerpt"] == " ".join(CREG_TEXT.split())
    assert result["suggested_sources"] == []
    assert result["live_source_status"] == "checked"


@pytest.mark.asyncio
async def test_luminus_procedure_is_added_only_with_its_supporting_passage(monkeypatch):
    async def fetch(key):
        return page(key, CREG_TEXT if key == "creg_cancellation" else LUMINUS_TEXT)

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    result = await gemma_answer.answer_energy_question("Wanneer kan ik mijn Luminus-contract opzeggen?", [])
    assert "My Luminus" in result["answer"]
    assert len(result["sources"]) == 2
    assert result["sources"][1]["excerpt"] == LUMINUS_TEXT
    assert result["live_source_status"] == "checked"


@pytest.mark.asyncio
async def test_source_markdown_does_not_hide_verified_passages(monkeypatch):
    async def fetch(key):
        content = (
            CREG_TEXT.replace("verbrekingsvergoeding", "**verbrekingsvergoeding**")
            if key == "creg_cancellation" else
            LUMINUS_TEXT.replace("My Luminus-klantenzone", "[My Luminus-klantenzone](https://my.luminus.be/)")
        )
        return page(key, content)

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    result = await gemma_answer.answer_energy_question("Mijn Luminus energiecontract opzeggen", [])
    assert result["live_source_status"] == "checked"
    assert len(result["sources"]) == 2
    assert result["sources"][1]["excerpt"] == LUMINUS_TEXT


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "Cookies en navigatie", "Er kan een verbrekingsvergoeding gelden."])
async def test_failed_or_unsubstantiated_fetch_never_asserts_the_rule(monkeypatch, content):
    async def fetch(key):
        return page(key, content) if content else None

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    monkeypatch.setattr(gemma_answer, "_generate", forbid_generation)
    result = await gemma_answer.answer_energy_question("Kan ik mijn energiecontract stopzetten?", [])
    assert "niet verifiëren" in result["answer"]
    assert "zonder verbrekingsvergoeding" not in result["answer"]
    assert result["sources"] == []
    assert len(result["suggested_sources"]) == 1
    assert result["live_source_status"] == "failed"


@pytest.mark.asyncio
async def test_partial_fetch_does_not_turn_failed_supplier_link_into_evidence(monkeypatch):
    async def fetch(key):
        return page(key, CREG_TEXT) if key == "creg_cancellation" else None

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    result = await gemma_answer.answer_energy_question("Mijn Luminus energiecontract opzeggen", [])
    assert "zonder verbrekingsvergoeding" in result["answer"]
    assert "My Luminus" not in result["answer"]
    assert len(result["sources"]) == 1
    assert result["suggested_sources"][0]["url"] == ENERGY_SOURCES["luminus_cancellation"][1]
    assert result["live_source_status"] == "failed"


@pytest.mark.parametrize("question", [
    "Mijn domiciliëring voor energie stopzetten",
    "Luminus ketelonderhoud contract opzeggen",
    "Wanneer ontvang ik mijn jaarafrekening?",
    "Ik wil mijn energiecontract herroepen binnen 14 dagen",
])
def test_other_service_and_withdrawal_questions_do_not_use_supply_cancellation_rule(question):
    assert not gemma_answer._is_cancellation_question(question)


def test_unfetched_pdf_urls_are_not_presented_as_used_web_sources():
    chunk = KnowledgeChunk(5, "Contract stopzetten: raadpleeg de leverancier.",
                           (ENERGY_SOURCES["luminus_cancellation"][1],))
    sources = gemma_answer._pdf_sources([chunk], "contract stopzetten")
    assert sources
    assert all("url" not in source for source in sources)


@pytest.mark.parametrize("question", [
    "Wanneer kan ik mijn contract stopzetten bij mijn energie?",
    "Wat kost het om mijn energiecontract op te zeggen?",
    "Kan ik mijn contract stop zetten?",
    "Moet ik een verbrekingsvergoeding betalen?",
])
def test_cancellation_and_fee_variants_use_official_rules(question):
    assert gemma_answer._is_cancellation_question(question)


def test_answer_api_preserves_verified_processing_and_suggested_sources(monkeypatch):
    from fastapi.testclient import TestClient
    import energy_voice_app

    async def fetch(key):
        return None

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    monkeypatch.setattr(gemma_answer, "_generate", forbid_generation)
    response = TestClient(energy_voice_app.api_app).post(
        "/api/answer", json={"question": "Kan ik mijn energiecontract stopzetten?"}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["processing"] == "verified-public-sources"
    assert result["live_source_status"] == "failed"
    assert result["sources"] == []
    assert result["suggested_sources"][0]["url"] == ENERGY_SOURCES["creg_cancellation"][1]


def test_suggested_links_render_separately_and_escape_source_text():
    import energy_voice_app

    rendered = energy_voice_app._render_evidence_sources([], [
        {"title": "CREG <script>", "url": ENERGY_SOURCES["creg_cancellation"][1]},
        {"title": "Unsafe", "url": "javascript:alert(1)"},
    ])
    assert "Geen bronfragment gevonden" in rendered
    assert "Zelf raadplegen · niet als bewijs gebruikt" in rendered
    assert "CREG &lt;script&gt;" in rendered
    assert "javascript:" not in rendered
