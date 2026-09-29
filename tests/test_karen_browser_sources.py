import pytest

from luminus_harness import browserbase_sources


@pytest.mark.asyncio
async def test_failed_fetch_is_not_returned_as_a_checked_live_source(monkeypatch) -> None:
    monkeypatch.setattr(
        browserbase_sources,
        "_search",
        lambda query, scope: [{"title": "CREG", "url": "https://www.creg.be/example"}],
    )
    monkeypatch.setattr(
        browserbase_sources,
        "_fetch",
        lambda url: "Browserbase is nog niet geconfigureerd.",
    )

    pages = await browserbase_sources.search_energy_pages("actuele stroomprijs", "creg", max_pages=1)

    assert pages == []


@pytest.mark.asyncio
async def test_successful_fetch_returns_checked_source_content(monkeypatch) -> None:
    monkeypatch.setattr(
        browserbase_sources,
        "_search",
        lambda query, scope: [{"title": "CREG", "url": "https://www.creg.be/example"}],
    )
    monkeypatch.setattr(browserbase_sources, "_fetch", lambda url: "Maandgemiddelde gepubliceerd in mei.")

    pages = await browserbase_sources.search_energy_pages("actuele stroomprijs", "creg", max_pages=1)

    assert pages == [{
        "title": "CREG",
        "url": "https://www.creg.be/example",
        "content": "Maandgemiddelde gepubliceerd in mei.",
    }]


@pytest.mark.asyncio
async def test_curated_source_is_not_returned_when_fetch_fails(monkeypatch) -> None:
    monkeypatch.setattr(browserbase_sources, "_fetch", lambda url: "Browserbase is nog niet geconfigureerd.")

    page = await browserbase_sources.fetch_energy_page("luminus_invoice")

    assert page is None


@pytest.mark.asyncio
async def test_curated_source_returns_page_only_after_successful_fetch(monkeypatch) -> None:
    monkeypatch.setattr(browserbase_sources, "_fetch", lambda url: "Een voorschot is een maandelijkse inschatting.")

    page = await browserbase_sources.fetch_energy_page("luminus_invoice")

    assert page == {
        "title": "Je energiefactuur uitgelegd — Luminus",
        "url": "https://www.luminus.be/nl/prive/energie/energiefactuur-uitgelegd/",
        "content": "Een voorschot is een maandelijkse inschatting.",
    }
