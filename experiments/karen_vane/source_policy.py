"""Small, explicit source relationships for the isolated public-question trial.

These checks identify a suitable *source*, not whether a model's prose is true.
Keep the map narrow: an unknown authority must not be guessed from a page title.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


RELATIONS = json.loads(Path(__file__).with_name("source_relations.json").read_text())
REGION_AUTHORITIES = RELATIONS["regions"]
ENERGY_REGION_AUTHORITIES = RELATIONS["energy_regions"]
TOPIC_AUTHORITIES = RELATIONS["topic_authorities"]
SUPPLIER_AUTHORITIES = RELATIONS["suppliers"]
TOPIC_TERMS = {
    "invoice": ("factuur", "afrekening", "voorschot", "invoice", "bill"),
    "boiler": ("ketel", "chaudi", "boiler"),
    "capacity_peak": ("maandpiek", "capaciteitstarief"),
    "social_tariff_period": ("sociaal tarief", "tarif social"),
}
ENERGY_TERMS = {
    "gas": ("gas", "gaz"),
    "electricity": ("elektric", "stroom", "électric", "electric"),
}
REGION_MENTIONS = {
    "wallonia": r"\b(?:walloni[eë]|waals\w*|walloon|wallonia)\b",
    "brussels": r"\b(?:brussel\w*|bruxelles|brussels)\b",
    "flanders": r"\b(?:vlaander\w*|vlaams\w*|flanders|flemish)\b",
}


@dataclass(frozen=True)
class Scope:
    region: str | None = None
    supplier: str | None = None
    energy: str | None = None
    topic: str | None = None
    region_ambiguous: bool = False
    maintenance: bool = False
    control: bool = False


def extract_scope(question: str) -> Scope:
    text = question.casefold()
    found = [name for name, pattern in REGION_MENTIONS.items() if re.search(pattern, text)]
    # A multi-region comparison cannot be reduced to one region without error.
    negated_region = bool(re.search(
        r"\bniet\s+(?:in\s+)?(?:walloni[eë]|vlaander\w*|brussel\w*|bruxelles)", text))
    region = found[0] if len(found) == 1 and not negated_region else None
    supplier = "eneco" if re.search(r"\beneco\b", text) else None
    topic = ("capacity_peak" if region == "flanders" and re.search(r"maandpiek|capaciteitstarief", text)
             else "social_tariff_period" if re.search(r"sociaal\s+tarief|tarif\s+social", text)
             and re.search(r"geldigheidsperiode|huidig|kwartaal|trimestre|période", text)
             and re.search(r"\bgas\b|aardgas|\bgaz\b", text)
             else "invoice" if re.search(r"factuur|afrekening|voorschot|invoice|\bbill\b", text)
             else "boiler" if re.search(r"ketel|verwarm|chaudi|boiler", text) else None)
    energy = ("gas" if re.search(r"\bgas\b|gasketel|chaudi", text)
              else "electricity" if re.search(r"elektric|stroom|électric", text) else None)
    return Scope(region, supplier, energy, topic, len(found) > 1 or negated_region,
                 bool(re.search(r"onderhoud|entretien", text)),
                 bool(re.search(r"controle|contrôle|inspection", text)))


def _host_in(host: str, domains: list[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def source_reason(scope: Scope, url: str, title: str, content: str) -> str | None:
    """Return a rejection reason; None means only that source checks passed."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
    except ValueError:
        return "invalid_url"
    if parsed.scheme != "https" or not host:
        return "invalid_url"

    if scope.region_ambiguous:
        return "ambiguous_question_region"

    domains = (TOPIC_AUTHORITIES[scope.topic] if scope.topic in TOPIC_AUTHORITIES
               else ENERGY_REGION_AUTHORITIES[scope.region]
               if scope.region in ENERGY_REGION_AUTHORITIES and scope.topic == "boiler"
               else REGION_AUTHORITIES.get(scope.region, []))
    if scope.topic in TOPIC_AUTHORITIES and not _host_in(host, domains):
        return "wrong_topic_authority"
    if scope.region and not _host_in(host, domains):
        return "wrong_region_or_unconfirmed_authority"
    if scope.supplier and not _host_in(host, SUPPLIER_AUTHORITIES[scope.supplier]):
        return "wrong_supplier_or_unconfirmed_authority"

    passage = (title + " " + content).casefold()
    walloon_gas_boiler_comparison = (scope.region == "wallonia" and scope.topic == "boiler"
                                    and scope.energy == "gas" and scope.maintenance
                                    and scope.control)
    boiler_page = bool(re.search(r"ketel|chaudi|boiler", title.casefold() + " " + parsed.path.casefold()))
    if walloon_gas_boiler_comparison and not boiler_page:
        return "wrong_topic"
    if scope.region:
        mentioned = {name for name, pattern in REGION_MENTIONS.items()
                     if re.search(pattern, passage)}
        if mentioned and scope.region not in mentioned:
            return "wrong_region_in_passage"
    if scope.topic and not any(term in passage for term in TOPIC_TERMS[scope.topic]):
        return "wrong_topic"
    if scope.energy and not any(term in passage for term in ENERGY_TERMS[scope.energy]) \
            and not (walloon_gas_boiler_comparison and boiler_page):
        return "wrong_energy_type"
    if scope.maintenance and scope.control and not (
            re.search(r"onderhoud|entretien", passage)
            and re.search(r"controle|contrôle|inspection", passage)):
        return "missing_compared_concept"
    if scope.supplier and scope.supplier not in passage and scope.supplier not in host:
        return "supplier_not_in_passage"
    page_label = title.casefold() + " " + parsed.path.casefold()
    if scope.topic == "capacity_peak" and not (
            re.search(r"maandpiek|capaciteitstarief|piekvermogen|nettarief", page_label)
            and "maandpiek" in passage and "capaciteitstarief" in passage):
        return "wrong_topic"
    if scope.topic == "social_tariff_period" and not (
            not re.search(r"premie|prime", page_label)
            and re.search(r"sociaal.?tarief|sociale.?tarieven|tarif.?social", page_label)
            and re.search(r"sociaal\s+tarief|tarif\s+social", passage)
            and re.search(r"\bgas\b|aardgas|\bgaz\b", passage)
            and re.search(r"geldigh|periode|période|kwartaal|trimestre|\bq[1-4]\s*20\d{2}\b", passage)):
        return "wrong_topic"
    return None
