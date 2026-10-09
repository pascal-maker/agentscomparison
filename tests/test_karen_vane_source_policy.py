"""The relation gate is tested with the actual failure patterns from the trial."""

import asyncio

import httpx
import pytest

from experiments.karen_vane.adapter import PublicQuestion, Settings, VaneAdapter
from experiments.karen_vane.source_policy import extract_scope, source_reason


PROVIDER = {"id": "local", "name": "Karen local Ollama",
            "chatModels": [{"key": "llama3.2:latest"}],
            "embeddingModels": [{"key": "nomic-embed-text:latest"}]}


def answer(question, sources, message="Foutieve modeluitspraak [2]."):
    def handle(request):
        if request.url.path == "/api/providers":
            return httpx.Response(200, json={"providers": [PROVIDER]})
        return httpx.Response(200, json={"message": message, "sources": sources})

    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await VaneAdapter(client, Settings()).answer(PublicQuestion(question=question))

    return asyncio.run(call())


def source(url, content, title="Bron"):
    return {"metadata": {"title": title, "url": url}, "content": content}


def test_wallonia_does_not_use_brussels_rule_or_unconfirmed_commercial_source():
    result = answer("Zoek de regels voor een gasketel in Wallonië", [
        source("https://leefmilieu.brussels/verwarmingsketel", "Gasverwarming in Brussel om de twee jaar"),
        source("https://fireforum.be/waals-gewest", "Gasketel in Wallonië om de drie jaar"),
    ])
    assert result.status == "insufficient_evidence"
    assert result.sources == []
    assert "twee jaar" not in result.answer


def test_wallonia_accepts_known_official_authority_and_only_exposes_excerpt():
    result = answer("Wat zijn de regels voor een gasketel in Wallonië?", [
        source("https://energie.wallonie.be/fr/controle.html", "Contrôle chaudière gaz en Wallonie"),
        source("https://vlaanderen.be/onderhoud", "Onderhoud gasketel in Vlaanderen"),
    ])
    assert result.status == "sources_for_review"
    assert len(result.sources) == 1
    assert "energie.wallonie.be" in str(result.sources[0].url)
    assert "Foutieve modeluitspraak" not in result.answer
    assert result.evidence_status == "unverified"


def test_wallonia_boiler_comparison_excludes_off_topic_official_pages():
    result = answer("Onderhoud en periodieke controle gasketel in Wallonië", [
        source("https://logement.wallonie.be/storage/reparations.pdf",
               "Entretien et contrôle des brûleurs gaz chaudière Wallonie"),
        source("https://www.wallonie.be/fr/demarches/gerer-sa-citerne-mazout",
               "Entretien et contrôle de citerne mazout et chaudière gaz Wallonie"),
        source("https://energie.wallonie.be/home/controle-chaudiere.html",
               "Entretien et contrôle périodique chaudière gaz Wallonie"),
    ])
    assert [str(s.url) for s in result.sources] == ["https://energie.wallonie.be/home/controle-chaudiere.html"]


def test_wallonia_keeps_primary_boiler_page_when_short_excerpt_omits_gas():
    result = answer("Onderhoud en periodieke controle gasketel in Wallonië", [
        source("https://energie.wallonie.be/home/vous-avez-dit-entretien-des-chaudieres.html",
               "L'entretien des chaudières n'est pas obligatoire. Le contrôle périodique l'est.",
               "Vous avez dit entretien des chaudières et des brûleurs?"),
        source("https://energie.wallonie.be/home/les-cheminees.html",
               "Pour les appareils au gaz, l'entretien de la chaudière est utile. Le contrôle périodique est prévu.",
               "Les cheminées : un élément déterminant"),
    ])
    assert [str(s.url) for s in result.sources] == [
        "https://energie.wallonie.be/home/vous-avez-dit-entretien-des-chaudieres.html"]


def test_wallonia_comparison_needs_both_maintenance_and_control_passages():
    scope = extract_scope("Onderhoud en periodieke controle gasketel in Wallonië")
    assert source_reason(scope, "https://energie.wallonie.be/chaudiere-gasnet", "Chaudière gaz",
                         "Chaudière gaz en Wallonie") == "missing_compared_concept"
    assert source_reason(scope, "https://energie.wallonie.be/controle-chaudiere", "Contrôle chaudière",
                         "Contrôle périodique chaudière gaz en Wallonie") == "missing_compared_concept"
    assert source_reason(scope, "https://energie.wallonie.be/beide", "Chaudière",
                         "Entretien et contrôle périodique chaudière gaz en Wallonie") is None


def test_eneco_disambiguates_singapore_company_and_unverified_citations():
    result = answer("What is Eneco? Search the web and cite your sources.", [
        source("https://enecoenergy.com/", "Eneco Energy Limited Singapore logistics"),
        source("https://www.eneco.nl/en/about-us", "Eneco is an international energy company"),
    ], "Eneco is listed in Singapore [8].")
    assert result.status == "sources_for_review"
    assert [str(s.url) for s in result.sources] == ["https://www.eneco.nl/en/about-us"]
    assert "Singapore" not in result.answer
    assert "[8]" not in result.answer


def test_invoice_keeps_supplier_source_and_drops_broker():
    result = answer("Zoek bij Eneco voorschotfactuur versus jaarafrekening", [
        source("https://callmepower.be/nl/energie/eneco", "Eneco voorschotfactuur"),
        source("https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie",
               "Gedurende het jaar betaal je voorschotfacturen; deze worden van de afrekening afgetrokken"),
    ])
    assert result.status == "sources_for_review"
    assert len(result.sources) == 1
    assert "eneco.be" in str(result.sources[0].url)


@pytest.mark.parametrize("question", [
    "Vergelijk de gasketelregels van Wallonië en Brussel",
    "Niet in Wallonië maar in Brussel: gasketelcontrole?",
])
def test_multi_or_negated_regions_are_not_silently_assigned(question):
    scope = extract_scope(question)
    assert scope.region_ambiguous
    assert source_reason(scope, "https://energie.wallonie.be/nl/ketel", "Ketel", "gasketel")


def test_suffix_attack_does_not_count_as_official_domain():
    scope = extract_scope("Wat zegt Eneco over voorschotfacturen?")
    assert source_reason(scope, "https://eneco.be.evil.test/invoice", "Eneco", "voorschotfactuur")


def test_official_host_does_not_override_explicitly_wrong_region_or_energy():
    scope = extract_scope("Gasketelregels in Wallonië?")
    assert source_reason(scope, "https://energie.wallonie.be/vergelijking", "Verwarming",
                         "Voor Brussel geldt een controle van gasketels") == "wrong_region_in_passage"
    assert source_reason(scope, "https://energie.wallonie.be/stroom", "Elektriciteit",
                         "Elektriciteitsprijzen in Wallonië") in {"wrong_topic", "wrong_energy_type"}
