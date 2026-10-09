"""Passage-checked maintenance answer for central gas boilers in Flanders."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from .invoice_answer import visible_text_from_html
from .source_policy import extract_scope


ARTICLE_URL = "https://www.vlaanderen.be/verplicht-onderhoud-van-uw-cv-installatie-centrale-verwarming"
ARTICLE_TITLE = "Vlaanderen.be: verplicht onderhoud van centrale verwarming"
GENERAL_PASSAGES = (
    "De onderhoudsregels hieronder zijn alleen van toepassing op centrale stooktoestellen (centrale verwarming)",
    "Het onderhoud op een gas- of stookolieketel moet uitgevoerd worden door een erkende technicus",
    "Het vermogen in kilowatt (kW) staat op het kenplaatje van uw cv-ketel",
)
GAS_PASSAGES = (
    "Voor centrale stooktoestellen op gas (aardgas, butaan, propaan) met een vermogen vanaf 20 kilowatt (kW)",
    "Verplicht 2-jaarlijks onderhoud",
    "Voor centrale stooktoestellen met een vermogen van minder dan 20 kilowatt (kW) is onderhoud niet verplicht, maar het wordt wel aangeraden",
)


def is_gas_maintenance_question(question: str) -> bool:
    scope = extract_scope(question)
    text = question.casefold()
    return (
        scope.region == "flanders"
        and not scope.region_ambiguous
        and scope.topic == "boiler"
        and scope.energy == "gas"
        and scope.maintenance
        and not re.search(r"geiser|kachel|haard|doorstromer|audit|premie|prijs|kost|nieuwe ketel", text)
    )


def is_official_article(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.hostname in {"vlaanderen.be", "www.vlaanderen.be"}
            and parsed.path.rstrip("/") == urlsplit(ARTICLE_URL).path)


def checked_answer_from_html(html: str) -> tuple[str, str] | None:
    page = re.sub(r"\s+", " ", visible_text_from_html(html)).casefold()
    start = page.find(GAS_PASSAGES[0].casefold())
    end = page.find("vaste brandstof", start) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    gas_section = page[start:end]
    if (not all(passage.casefold() in page for passage in GENERAL_PASSAGES)
            or not all(passage.casefold() in gas_section for passage in GAS_PASSAGES)):
        return None
    answer = (
        "Voor een centrale gasketel in Vlaanderen is vanaf 20 kW onderhoud om de "
        "twee jaar verplicht, door een erkende technicus. [1] Onder 20 kW is "
        "onderhoud niet verplicht, maar wel aanbevolen. [1] Deze regels gelden voor "
        "centrale verwarming; voor afzonderlijke toestellen gelden andere regels. [1] "
        "Het vermogen staat op het kenplaatje van je cv-ketel. [1]"
    )
    return answer, GAS_PASSAGES[0] + " … " + GAS_PASSAGES[1]


async def fetch_checked_answer(client: httpx.AsyncClient) -> tuple[str, str, str] | None:
    try:
        response = await client.get(ARTICLE_URL, timeout=12, follow_redirects=True)
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None
    final_url = str(response.url)
    if not is_official_article(final_url):
        return None
    checked = checked_answer_from_html(response.text)
    return (*checked, final_url) if checked else None
