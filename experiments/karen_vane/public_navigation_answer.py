"""Passage-checked navigation to three known public energy pages.

These answers identify where an explanation lives. They do not extract a
current tariff, offer, legal notice period, or personalized instruction.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

import httpx

from .invoice_answer import visible_text_from_html
from .source_policy import extract_scope


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    required_passages: tuple[str, ...]
    answer: str
    excerpt: str


PAGES = {
    "brussels_supplier_switch": Page(
        url="https://brugel.brussels/themes/consommateurs-7/les-5-etapes-pour-changer-de-fournisseur-9",
        title="BRUGEL: vijf stappen om van leverancier te veranderen",
        required_passages=(
            "5 étapes pour changer de fournisseur",
            "comparez les prix des différents fournisseurs grâce à notre outil en ligne",
            "gaz et en électricité",
        ),
        answer=("BRUGEL legt op deze pagina uit hoe je in Brussel van "
                "elektriciteitsleverancier verandert. [1]"),
        excerpt="5 étapes pour changer de fournisseur … comparez les prix des différents fournisseurs",
    ),
    "wallonia_gas_meter": Page(
        url="https://www.ores.be/particulier/le-releve-index",
        title="ORES: meterstand doorgeven",
        required_passages=(
            "Transmettre mon relevé d'index",
            "J'encode mon index",
            "gaz naturel",
        ),
        answer=("ORES legt hier uit hoe je een meterstand doorgeeft als ORES "
                "je netbeheerder is. [1] Is dat een andere netbeheerder, "
                "noem die dan zodat ik de juiste uitleg kan zoeken."),
        excerpt="Transmettre mon relevé d'index … J'encode mon index … gaz naturel",
    ),
    "belgian_contract_exit": Page(
        url="https://www.creg.be/nl/consumenten/prijzen-en-tarieven/types-contracten-voor-elektriciteit-en-aardgas",
        title="CREG: types contracten voor elektriciteit en aardgas",
        required_passages=(
            "Consumenten kunnen hun leveringscontract voor energie te allen tijde opzeggen",
            "De leverancier mag hem geen opzeggingsvergoeding in rekening brengen",
        ),
        answer=("De CREG bespreekt op deze pagina de opzegging van een "
                "particulier energiecontract en een eventuele opzeggingsvergoeding. [1] "
                "Ik bevestig hier geen opzegtermijn of voorwaarden voor jouw contract."),
        excerpt="De leverancier mag hem geen opzeggingsvergoeding in rekening brengen.",
    ),
}


def page_for_question(question: str) -> Page | None:
    text = question.casefold()
    if (not re.search(r"\b(?:waar|welke)\b", text)
            or not re.search(r"uitleg|instantie|offici[eë]le", text)):
        return None
    scope = extract_scope(question)
    if scope.region_ambiguous:
        return None
    return PAGES.get(scope.topic)


def checked_answer_from_html(html: str, page: Page) -> tuple[str, str] | None:
    visible = visible_text_from_html(html).casefold()
    if not all(passage.casefold() in visible for passage in page.required_passages):
        return None
    return page.answer, page.excerpt


async def fetch_checked_answer(client: httpx.AsyncClient, page: Page) -> tuple[str, str, str] | None:
    try:
        response = await client.get(page.url, timeout=12, follow_redirects=True)
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None
    original, final = urlsplit(page.url), urlsplit(str(response.url))
    if (final.scheme != "https" or final.hostname != original.hostname
            or final.path.rstrip("/") != original.path.rstrip("/")):
        return None
    checked = checked_answer_from_html(response.text, page)
    return (*checked, str(response.url)) if checked else None
