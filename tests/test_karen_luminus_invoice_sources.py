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
        "Waarom verschilt mijn Luminus-voorschot van mijn jaarafrekening?",
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

    result = await gemma_answer.answer_energy_question("Waarom verschilt mijn Luminus-voorschot?", [page_four])

    assert result["live_source_status"] == "failed"
    luminus_source = next(source for source in result["sources"] if "luminus.be" in source.get("url", ""))
    assert luminus_source["detail"] == "Gecurateerde officiële uitleg · pagina niet live opgehaald"
    assert "werkelijke kosten verrekend met de voorschotten" in prompts[0]
    assert any(source["detail"] == "PDF · pagina 4" for source in result["sources"])

@pytest.mark.asyncio
async def test_naming_a_different_supplier_never_shows_luminus_content(monkeypatch) -> None:
    """The bug karen-architecture-audit-2026-10-01.md flagged: a question
    naming a different supplier must not be answered with Luminus's page."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    page_four = KnowledgeChunk(
        page=4,
        text="Luminus werkt met voorschotfacturen en afrekeningen; het ideale voorschot kan op basis van digitale meterdata worden herberekend.",
        urls=(),
    )

    async def fetch_page(source_key: str):
        assert source_key == "eneco_settlement"
        return {
            "title": "Eneco afrekening",
            "url": "https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie/",
            "content": "Eneco verrekent de werkelijke kosten met de betaalde voorschotten op de jaarafrekening.",
        }

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch_page)
    monkeypatch.setattr(gemma_answer, "_generate", lambda _prompt: "Eneco verrekent je voorschotten op de jaarafrekening.")

    result = await gemma_answer.answer_energy_question(
        "Leg mijn Eneco jaarafrekening uit", [page_four]
    )

    assert not any(source.get("url", "").startswith("https://www.luminus.be/") for source in result["sources"])
    assert any(source.get("url", "").startswith("https://eneco.be/") for source in result["sources"])
    assert not any(source["detail"] == "PDF · pagina 4" for source in result["sources"])


@pytest.mark.asyncio
async def test_no_named_supplier_does_not_default_to_luminus(monkeypatch) -> None:
    """A generic invoice question with no supplier named must not assume
    Luminus -- it falls through to the general public-source search."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    page_four = KnowledgeChunk(
        page=4,
        text="Luminus werkt met voorschotfacturen en afrekeningen.",
        urls=(),
    )
    searched_scopes: list[str] = []

    async def search_pages(_query: str, scope: str, *, max_pages: int = 2):
        searched_scopes.append(scope)
        return []

    monkeypatch.setattr(gemma_answer, "search_energy_pages", search_pages)
    monkeypatch.setattr(gemma_answer, "_generate", lambda _prompt: "Algemene uitleg.")

    result = await gemma_answer.answer_energy_question("Wat is een jaarafrekening?", [page_four])

    assert not any(source.get("url", "").startswith("https://www.luminus.be/") for source in result["sources"])
    assert searched_scopes  # the generic public-source search ran instead

@pytest.mark.asyncio
async def test_a_newly_added_supplier_is_fetched_not_assumed(monkeypatch) -> None:
    """Mega only has 'help'/'cancellation' sources registered, no 'invoice'
    page -- a cancellation question naming it should fetch that page as an
    unverified suggested source, not show Luminus content or stay silent."""
    async def fetch(key):
        from luminus_harness.browserbase_sources import ENERGY_SOURCES
        title, url = ENERGY_SOURCES[key]
        content = (
            "Voor consumenten, zelfstandigen en kleine bedrijven is de verbrekingsvergoeding afgeschaft.\n"
            "Zij kunnen hun contract op gelijk welk moment stopzetten."
        ) if key == "creg_cancellation" else "Je kunt je Mega-contract opzeggen via het contactformulier."
        return {"title": title, "url": url, "content": content}

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch)
    result = await gemma_answer.answer_energy_question("Ik wil mijn Mega-contract opzeggen", [])

    assert any(source.get("url", "") == "https://www.mega.be/nl/energie/contact" for source in result["suggested_sources"])
    assert "Luminus" not in result["answer"]


def test_named_supplier_ignores_megawattuur() -> None:
    from luminus_harness.browserbase_sources import named_supplier

    assert named_supplier("Hoeveel megawattuur verbruikt mijn huis per jaar?") is None
    assert named_supplier("Ik zit bij Mega en wil opzeggen") == "mega"


def test_new_supplier_aliases_are_explicit_and_collision_safe() -> None:
    from luminus_harness.browserbase_sources import named_supplier

    assert named_supplier("Mijn OCTA+ contract") == "octaplus"
    assert named_supplier("Mijn octaplus contract") == "octaplus"
    assert named_supplier("Ik zit bij Aspiravi") == "aspiravi"
    assert named_supplier("Ik heb een octane-installatie") is None
    assert named_supplier("Mijn aspiratie is minder verbruik") is None
    assert named_supplier("Een frankering op mijn brief") is None


def test_frank_and_bolt_require_the_full_brand_not_a_common_word() -> None:
    """"frank" is a common first name and "bolt" a common hardware word --
    both require the fuller brand phrase, same as "total energies"."""
    from luminus_harness.browserbase_sources import named_supplier

    assert named_supplier("Frank heeft een vraag over zijn energiefactuur") is None
    assert named_supplier("Kan je dit aan Frank doorgeven?") is None
    assert named_supplier("Ik heb mijn deur op slot gedaan met een bolt") is None
    assert named_supplier("Ik zit bij Frank Energie") == "frank"
    assert named_supplier("Ik ben klant bij frankenergie") == "frank"
    assert named_supplier("Mijn Bolt Energie-contract opzeggen") == "bolt"
    assert named_supplier("Ik ben klant bij boltenergie") == "bolt"


@pytest.mark.asyncio
async def test_each_new_supplier_uses_only_its_registered_official_source(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    async def fetch_page(source_key: str):
        from luminus_harness.browserbase_sources import ENERGY_SOURCES

        title, url = ENERGY_SOURCES[source_key]
        return {"title": title, "url": url, "content": f"Official content for {source_key}."}

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch_page)
    monkeypatch.setattr(gemma_answer, "_generate", lambda _prompt: "De officiële bron is gecontroleerd.")

    for supplier, phrase, domain in (
        ("octaplus", "OCTA+", "octaplus.be"),
        ("frank", "Frank Energie", "frankenergie.be"),
    ):
        result = await gemma_answer.answer_energy_question(f"Ik wil mijn {phrase}-contract opzeggen", [])
        assert result["live_source_status"] == "failed"
        assert any(domain in source.get("url", "") for source in result["suggested_sources"])


@pytest.mark.asyncio
async def test_aspiravi_has_no_cancellation_source_and_never_leaks_another_suppliers_content(monkeypatch) -> None:
    """Aspiravi is registered help-only (its official material is
    B2B-oriented) -- an end-to-end check, not just a registry lookup: no
    source is fetched for it, and no other supplier's content appears."""
    calls: list[str] = []

    async def fetch_track(source_key: str):
        calls.append(source_key)
        return None

    monkeypatch.setattr(gemma_answer, "fetch_energy_page", fetch_track)

    result = await gemma_answer.answer_energy_question("Ik wil mijn Aspiravi-contract opzeggen", [])

    assert "aspiravi_help" not in calls
    assert not any("luminus.be" in source.get("url", "") for source in result["sources"] + result["suggested_sources"])
    assert result["sources"] == []
    assert "nog geen officiële bron geregistreerd" in result["answer"]

