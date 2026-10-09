"""One passage-checked answer for residential gas-boiler care in Wallonia."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx

from .invoice_answer import visible_text_from_html
from .source_policy import extract_scope


ARTICLE_PATH = (
    "/home/performance-energetique-des-batiments/batiments-residentiels/"
    "renovation-walloreno/conseils-pratiques/se-chauffer-1/"
    "controle-periodique-et-diagnostic-approfondi-des-chaudieres.html"
)
ARTICLE_URL = "https://energie.wallonie.be" + ARTICLE_PATH
ARTICLE_TITLE = "Wallonië: periodieke controle en onderhoud van ketels"

# The Dutch text is fixed. Each claim is shown only while every supporting
# French phrase is still present in the official page's visible text.
SUPPORTED_CLAIMS = (
    (
        "Voor een ketel in een Waalse woning raadt de overheid regelmatig onderhoud "
        "aan; volgens haar is dat onderhoud niet door de Waalse wetgeving geregeld.",
        (
            "Bien que l'entretien de la chaudière ne soit pas réglementé par la législation wallonne",
            "il est recommandé de le faire régulièrement",
        ),
    ),
    (
        "De periodieke controle moet door een erkende technicus gebeuren. Die kijkt "
        "naar de werking van de ketel en naar de ruimte, ventilatie en schoorsteen.",
        (
            "Le contrôle doit être effectué",
            "par un technicien agréé en combustibles gazeux ou liquides",
            "Le contrôle de la chaudière permet de vérifier qu'elle respecte bien certains critères de fonctionnement",
            "le local où elle est située (y compris la ventilation et la cheminée) est conforme",
        ),
    ),
    (
        "Onderhoud en periodieke controle zijn dus verschillende handelingen die "
        "in de praktijk vaak samen gebeuren.",
        ("En pratique, contrôle et entretien sont généralement liés",),
    ),
)


def is_residential_comparison(question: str) -> bool:
    scope = extract_scope(question)
    text = question.casefold()
    return (
        scope.region == "wallonia"
        and not scope.region_ambiguous
        and scope.topic == "boiler"
        and scope.energy == "gas"
        and scope.maintenance
        and scope.control
        and bool(re.search(r"\bverschil\b|\bonderscheid\b", text))
        and not re.search(r"industri\w*|bedrijf|onderneming|niet.residenti|hoe vaak|frequentie", text)
    )


def is_official_article(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.hostname == "energie.wallonie.be"
            and parsed.path.rstrip("/") == ARTICLE_PATH)


def checked_answer_from_html(html: str) -> tuple[str, str] | None:
    page = re.sub(r"\s+", " ", visible_text_from_html(html)).casefold()
    if not all(passage.casefold() in page
               for _, passages in SUPPORTED_CLAIMS for passage in passages):
        return None
    answer = " ".join(f"{claim} [1]" for claim, _ in SUPPORTED_CLAIMS)
    excerpt = SUPPORTED_CLAIMS[0][1][0] + " … " + SUPPORTED_CLAIMS[1][1][0]
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
