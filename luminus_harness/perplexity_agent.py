"""Optional, public-only web-grounded answers through the Perplexity Agent API.

This is deliberately separate from Karen's PDF, search benchmark, and offer
comparison routes. Agent citations are discovery evidence, not independently
verified passages from the original pages.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

_PRIVATE_INPUT = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b(?:BE\d{2}[\s-]?)?(?:\d{4}[\s-]?){3,4}\b|"
    r"\b(?:EAN|klantnummer|rekeningnummer|factuurnummer|contractnummer)\b|"
    r"\b(?:mijn|m'n|onze)\s+(?:factuur|contract|adres|voorschotbedrag)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PublicWebAgentError(Exception):
    message: str
    status_code: int = 503
    retry_after: str | None = None

    def __str__(self) -> str:
        return self.message


def validate_public_question(question: str) -> str:
    """Reject obvious private document content before it can leave the server."""
    question = question.strip()
    if not 2 <= len(question) <= 300 or "\n" in question or "\r" in question:
        raise PublicWebAgentError("Stel één korte algemene energievraag.", 422)
    if _PRIVATE_INPUT.search(question):
        raise PublicWebAgentError("Stel een algemene vraag zonder persoonlijke factuur- of contractgegevens.", 422)
    return question


def _field(item: Any, key: str, default: Any = None) -> Any:
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _sources(output: Any, answer: str) -> tuple[list[dict[str, str]], str]:
    sources: list[dict[str, str]] = []
    candidates: list[Any] = []
    seen: set[str] = set()
    cited_ids = set(re.findall(r"\[web:(\d+)\]", answer))
    # The answer can cite a different page from the search-result metadata.
    # Keep the links the user actually sees ahead of uncited candidates.
    for title, url in re.findall(r"\[([^\]]{1,160})\]\((https://[^)\s]+)\)", answer):
        if url in seen or urlparse(url).scheme != "https" or not urlparse(url).hostname:
            continue
        seen.add(url)
        sources.append({"title": title, "url": url, "date": ""})
        if len(sources) == 5:
            return sources, "ANSWER_LINKS_UNVERIFIED"
    if sources:
        return sources, "ANSWER_LINKS_UNVERIFIED"
    for item in output or []:
        if _field(item, "type") == "search_results":
            results = _field(item, "results", []) or []
            candidates.extend(results)
            selected = [result for result in results if str(_field(result, "id")) in cited_ids]
        elif _field(item, "type") == "message":
            selected = []
            for content in _field(item, "content", []) or []:
                selected.extend(_field(content, "annotations", []) or [])
        else:
            continue
        for candidate in selected:
            url = _field(candidate, "url")
            if not url or url in seen or urlparse(url).scheme != "https" or not urlparse(url).hostname:
                continue
            seen.add(url)
            sources.append({
                "title": str(_field(candidate, "title") or urlparse(url).hostname),
                "url": url,
                "date": str(_field(candidate, "date") or ""),
            })
            if len(sources) == 5:
                return sources, "AGENT_CITED_UNVERIFIED"
    if sources:
        return sources, "AGENT_CITED_UNVERIFIED"
    for candidate in candidates:
        url = _field(candidate, "url")
        if not url or url in seen or urlparse(url).scheme != "https" or not urlparse(url).hostname:
            continue
        seen.add(url)
        sources.append({
            "title": str(_field(candidate, "title") or urlparse(url).hostname),
            "url": url,
            "date": str(_field(candidate, "date") or ""),
        })
        if len(sources) == 3:
            break
    return sources, "SEARCH_CANDIDATES_UNVERIFIED"


_UNVERIFIED_MONEY = re.compile(
    r"€\s*\d|\b\d[\d.,]*\s*(?:euro|cent)\b|\b\d[\d.,]*\s*(?:€|c€)(?!\w)|"
    r"\b(?:premie|subsidie)\b.{0,100}\b(?:bedrag|aanvraag|beschikbaar|bestaat)\b",
    re.IGNORECASE | re.DOTALL,
)
_OFFICIAL_HOSTS = (
    "creg.be", "economie.fgov.be", "belgium.be", "vlaamsenutsregulator.be",
    "vlaanderen.be", "fluvius.be", "brugel.brussels", "leefmilieu.brussels",
    "environnement.brussels", "sibelga.be", "cwape.be", "energie.wallonie.be",
    "wallonie.be", "ores.be",
)


def _protect_current_amounts(answer: str, sources: list[dict[str, str]]) -> dict[str, Any] | None:
    """Do not relay Agent-generated monetary or subsidy claims as current facts.

    A URL or search snippet does not establish the applicable period, eligibility,
    or the number in the original source. This gate stays in place until a
    separate original-passage and validity verifier can make that decision.
    """
    if not _UNVERIFIED_MONEY.search(answer):
        return None
    official_sources = [source for source in sources if any(
        (host := (urlparse(source["url"]).hostname or "").lower()) == domain
        or host.endswith("." + domain) for domain in _OFFICIAL_HOSTS
    )]
    guidance = (
        "Controleer de officiële bron voor de voorwaarden en de geldende periode."
        if official_sources else "Ik vond daarbij geen controleerbare officiële bron."
    )
    return {
        "answer": (
            "Ik kan het actuele bedrag of de geldigheid van deze regeling niet "
            f"onafhankelijk bevestigen. {guidance}"
        ),
        "sources": official_sources,
        "evidence_status": "CURRENT_AMOUNT_UNVERIFIED",
    }


def answer_public_web_question(question: str) -> dict[str, Any]:
    """Get a Dutch public-energy answer; never assert independent verification."""
    question = validate_public_question(question)
    if not os.getenv("PERPLEXITY_API_KEY"):
        raise PublicWebAgentError("Publieke webvragen zijn momenteel niet beschikbaar: API-sleutel ontbreekt.")

    from perplexity import APIConnectionError, APIStatusError, Perplexity

    try:
        response = Perplexity(max_retries=0, timeout=30.0).responses.create(
            model="openai/gpt-6-luna",
            input=question,
            instructions=(
                "Je bent Karen, een Nederlandstalige energieassistent voor België. "
                "Gebruik web_search voor actuele publieke informatie. Geef de voorkeur aan "
                "de bevoegde officiële Belgische overheid, regulator of netbeheerder en let op "
                "het juiste gewest. Antwoord beknopt in het Nederlands met bronverwijzingen. "
                "Verzin geen gegevens of persoonlijke jaarprijzen. Als betrouwbare bronnen "
                "ontbreken, zeg dat expliciet."
            ),
            language_preference="nl",
            max_steps=3,
            max_output_tokens=800,
            reasoning={"effort": "none"},
            tools=[{
                "type": "web_search",
                "max_results": 3,
                "max_tokens": 1000,
                "max_tokens_per_page": 300,
                "user_location": {"country": "BE"},
            }],
        )
    except APIStatusError as error:
        retry_after = error.response.headers.get("retry-after") if error.status_code == 429 else None
        if error.status_code == 429:
            raise PublicWebAgentError("De webdienst is tijdelijk te druk. Probeer later opnieuw.", 429, retry_after) from error
        raise PublicWebAgentError("De webdienst kon de vraag niet beantwoorden.") from error
    except APIConnectionError as error:
        raise PublicWebAgentError("De webdienst is tijdelijk niet bereikbaar.") from error

    answer = (response.output_text or "").strip()
    sources, evidence_status = _sources(response.output, answer)
    if response.status != "completed" or not sources or not answer:
        return {"answer": "Ik vond geen controleerbare publieke bron voor deze vraag.", "sources": [], "evidence_status": "NOT_FOUND"}
    protected = _protect_current_amounts(answer, sources)
    if protected is not None:
        return protected
    return {
        "answer": answer,
        "sources": sources,
        "evidence_status": evidence_status,
    }
