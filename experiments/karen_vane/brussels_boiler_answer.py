"""Passage-checked Brussels answer for natural-gas boilers in a home."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from .invoice_answer import visible_text_from_html
from .source_policy import extract_scope


ARTICLE_URL = "https://leefmilieu.brussels/verwarmingsketel"
ARTICLE_TITLE = "Leefmilieu Brussel: EPB-periodieke controle van verwarmingsketels"
REQUIRED_PASSAGES = (
    "verplicht de Brusselse regelgeving tot EPB-periodieke controles door erkende technici",
    "Voor een verwarmingsketel of boiler op aardgas moet om de 2 jaar een EPB-periodieke controle worden uitgevoerd",
)


def is_residential_frequency_question(question: str) -> bool:
    scope = extract_scope(question)
    text = question.casefold()
    return (
        scope.region == "brussels"
        and not scope.region_ambiguous
        and scope.topic == "boiler"
        and scope.energy == "gas"
        and scope.control
        and bool(re.search(r"hoe vaak|om de hoeveel|frequentie|welke termijn", text))
        and not re.search(r"propaan|butaan|lpg|industri\w*|bedrijf|onderneming|niet.residenti", text)
    )


def is_official_article(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.hostname == "leefmilieu.brussels"
            and parsed.path.rstrip("/") == "/verwarmingsketel")


def checked_answer_from_html(html: str) -> tuple[str, str] | None:
    page = re.sub(r"\s+", " ", visible_text_from_html(html)).casefold()
    if not all(passage.casefold() in page for passage in REQUIRED_PASSAGES):
        return None
    answer = (
        "Voor een verwarmingsketel op aardgas in een Brusselse woning moet om de "
        "twee jaar een EPB-periodieke controle gebeuren. [1] De Brusselse regelgeving "
        "laat die controle door een erkende technicus uitvoeren. [1] Gebruik je "
        "een ander gas, vermeld dat dan: deze bevestigde termijn geldt hier voor aardgas."
    )
    excerpt = REQUIRED_PASSAGES[1]
    return answer, excerpt


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
