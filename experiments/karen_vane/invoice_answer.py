"""One bounded, passage-checked answer for Eneco's invoice comparison."""

from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

import httpx


ARTICLE_PATH = "/nl/contact/alles-over-je-afrekening-van-energie"
SUPPORTED_CLAIMS = (
    (
        "Bij Eneco betaal je gedurende het jaar voorschotfacturen om je "
        "energiekosten te spreiden.",
        ("Gedurende het jaar betaal je voorschotfacturen",
         "Zo spreid je de kosten van je verbruik"),
    ),
    (
        "De afrekening toont je verbruik en totale kosten over een periode; "
        "Eneco trekt de betaalde voorschotten daarvan af.",
        ("De afrekening van gas en elektriciteit geeft je een volledig overzicht van je energiekosten",
         "Je ziet daarop hoeveel je in een bepaalde periode hebt verbruikt en wat dat in totaal heeft gekost",
         "Deze voorschotten vind je duidelijk terug op je afrekening en trekken we af van je totale energiekosten"),
    ),
    (
        "Waren de voorschotten lager, dan betaal je het verschil bij.",
        ("Het bedrag dat je hebt betaald aan voorschotten is lager dan de totale kosten",
         "Dan dien je het verschil bij te betalen"),
    ),
    (
        "Waren ze hoger, dan krijg je het verschil terug.",
        ("Het bedrag dat je hebt betaald aan voorschotten is hoger dan de totale kosten",
         "Dan storten we het verschil terug op je rekening"),
    ),
)
REQUIRED_PASSAGES = tuple(passage for _, passages in SUPPORTED_CLAIMS for passage in passages)


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text_from_html(html: str) -> str:
    parser = _PageText()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def is_invoice_comparison(question: str) -> bool:
    text = question.casefold()
    return (bool(re.search(r"\beneco\b", text))
            and bool(re.search(r"voorschot|advance", text))
            and bool(re.search(r"afrekening|settlement", text)))


def is_official_article(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname in {"eneco.be", "www.eneco.be"}
            and parsed.path.rstrip("/") == ARTICLE_PATH)


def checked_answer_from_html(html: str) -> tuple[str, str] | None:
    page = visible_text_from_html(html).casefold()
    if not all(passage.casefold() in page for passage in REQUIRED_PASSAGES):
        return None
    answer = " ".join(f"{claim} [1]" for claim, _ in SUPPORTED_CLAIMS)
    excerpt = REQUIRED_PASSAGES[4] + "."
    return answer, excerpt


async def fetch_checked_answer(client: httpx.AsyncClient, article_url: str) -> tuple[str, str, str] | None:
    if not is_official_article(article_url):
        return None
    try:
        response = await client.get(article_url, timeout=12, follow_redirects=True)
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError):
        return None
    final_url = str(response.url)
    if not is_official_article(final_url):
        return None
    checked = checked_answer_from_html(response.text)
    return (*checked, final_url) if checked else None
