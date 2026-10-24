"""Validation and materialization for Karen's curated Flemish expert registry."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import yaml


ALLOWED_DOMAINS = {
    "electricity_prices",
    "energy_contracts",
    "electricity_market",
    "distribution_grids",
    "capacity_tariff",
    "solar_panels",
    "home_batteries",
    "heat_pumps",
    "renovation_energy_efficiency",
    "nuclear_energy",
    "renewable_energy",
    "flexibility_demand_response",
    "electric_vehicles_charging",
    "flemish_energy_policy",
    "energy_regulation",
    "consumer_energy_advice",
}

ALLOWED_EXPERT_TYPES = {
    "academic",
    "research_institute",
    "institutional",
    "journalist",
    "commercial_consumer",
}

ALLOWED_SOURCE_TYPES = {
    "official_profile",
    "institutional_page",
    "paper",
    "report",
    "presentation",
    "interview",
    "podcast",
    "youtube",
    "news_article",
    "government_publication",
}

MIN_EXPERTS = 15
MAX_EXPERTS = 20
MAX_SOURCES_PER_EXPERT = 5
MIN_QUALITY_SCORE = 0.65


class RegistryError(ValueError):
    """Raised when curated metadata violates the review contract."""


def _require_fields(record: dict[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if record.get(field) in (None, "", [])]
    if missing:
        raise RegistryError(f"{label} mist verplichte velden: {', '.join(missing)}")


def _require_keys(record: dict[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise RegistryError(f"{label} mist verplichte sleutels: {', '.join(missing)}")


def _string_list(value: Any, field: str, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RegistryError(f"{label}.{field} moet een niet-lege lijst met strings zijn")
    return value


def _score(value: Any, field: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegistryError(f"{label}.{field} moet een getal tussen 0 en 1 zijn")
    score = float(value)
    if not 0 <= score <= 1:
        raise RegistryError(f"{label}.{field} moet tussen 0 en 1 liggen")
    return score


def canonical_url(value: str) -> str:
    """Return a stable URL identity without fragments or a trailing slash."""
    parts = urlsplit(value.strip())
    if parts.scheme != "https" or not parts.hostname:
        raise RegistryError(f"Alle bron-URL's moeten publieke HTTPS-URL's zijn: {value}")
    host = parts.hostname.casefold()
    if parts.port:
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, parts.query, ""))


def load_registry(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise RegistryError("experts.yaml moet een object op het hoogste niveau bevatten")
    return payload


def validate_registry(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    experts = payload.get("experts")
    sources = payload.get("sources")
    if not isinstance(experts, list) or not isinstance(sources, list):
        raise RegistryError("experts.yaml moet lijsten 'experts' en 'sources' bevatten")
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise RegistryError("experts.yaml moet een scope-object bevatten")
    if scope.get("region") != "Vlaanderen":
        raise RegistryError("scope.region moet Vlaanderen zijn")
    if scope.get("ingestion_approved") is not False:
        raise RegistryError("ingestion_approved moet false blijven tijdens de discoveryfase")
    min_experts = scope.get("min_experts")
    max_experts = scope.get("max_experts")
    max_sources = scope.get("max_sources_per_expert")
    min_quality = scope.get("min_quality_score")
    if isinstance(min_experts, bool) or not isinstance(min_experts, int) or min_experts < MIN_EXPERTS:
        raise RegistryError(f"scope.min_experts mag niet lager zijn dan {MIN_EXPERTS}")
    if (
        isinstance(max_experts, bool)
        or not isinstance(max_experts, int)
        or max_experts > MAX_EXPERTS
        or max_experts < min_experts
    ):
        raise RegistryError(f"scope.max_experts moet tussen {min_experts} en {MAX_EXPERTS} liggen")
    if (
        isinstance(max_sources, bool)
        or not isinstance(max_sources, int)
        or not 1 <= max_sources <= MAX_SOURCES_PER_EXPERT
    ):
        raise RegistryError(f"scope.max_sources_per_expert mag maximaal {MAX_SOURCES_PER_EXPERT} zijn")
    min_quality = _score(min_quality, "min_quality_score", "scope")
    if min_quality < MIN_QUALITY_SCORE:
        raise RegistryError(f"scope.min_quality_score mag niet lager zijn dan {MIN_QUALITY_SCORE}")
    if not min_experts <= len(experts) <= max_experts:
        raise RegistryError(f"Het register moet {min_experts} tot {max_experts} experts bevatten")

    rubric = payload.get("scoring_rubric")
    if not isinstance(rubric, dict) or rubric.get("version") != 1:
        raise RegistryError("scoring_rubric versie 1 is verplicht")
    weights = rubric.get("authority_weights")
    expected_factors = {
        "demonstrated_expertise",
        "institutional_position",
        "experience",
        "publications",
        "flanders_relevance",
    }
    if not isinstance(weights, dict) or set(weights) != expected_factors:
        raise RegistryError("scoring_rubric.authority_weights mist factoren")
    normalized_weights = [_score(value, key, "authority_weights") for key, value in weights.items()]
    if abs(sum(normalized_weights) - 1.0) > 1e-9:
        raise RegistryError("scoring_rubric.authority_weights moet optellen tot 1")

    expert_ids: set[str] = set()
    expert_urls: dict[str, set[str]] = {}
    expert_domains: dict[str, set[str]] = {}
    normalized_experts: list[dict[str, Any]] = []
    for index, expert in enumerate(experts, start=1):
        label = f"expert #{index}"
        if not isinstance(expert, dict):
            raise RegistryError(f"{label} moet een object zijn")
        _require_fields(
            expert,
            (
                "expert_id",
                "name",
                "organization",
                "role",
                "region",
                "expert_type",
                "domains",
                "expertise_summary",
                "selection_rationale",
                "selection_status",
                "authority_score",
                "public_content_score",
                "active",
                "source_urls",
            ),
            label,
        )
        expert_id = str(expert["expert_id"])
        if expert_id in expert_ids:
            raise RegistryError(f"Dubbele expert_id: {expert_id}")
        expert_ids.add(expert_id)
        if expert["region"] != "Vlaanderen":
            raise RegistryError(f"{expert_id} valt buiten de primaire regio Vlaanderen")
        if expert["expert_type"] not in ALLOWED_EXPERT_TYPES:
            raise RegistryError(f"{expert_id} heeft een onbekend expert_type")
        if expert["selection_status"] != "pending_human_review":
            raise RegistryError(f"{expert_id} moet op menselijke selectiecontrole wachten")
        if not isinstance(expert["active"], bool):
            raise RegistryError(f"{expert_id}.active moet true of false zijn")
        domains = set(_string_list(expert["domains"], "domains", expert_id))
        if not domains or not domains <= ALLOWED_DOMAINS:
            raise RegistryError(f"{expert_id} bevat onbekende of lege energiedomeinen")
        source_urls = _string_list(expert["source_urls"], "source_urls", expert_id)
        urls = {canonical_url(url) for url in source_urls}
        if len(urls) != len(source_urls):
            raise RegistryError(f"{expert_id} bevat dubbele source_urls")
        if not 1 <= len(urls) <= max_sources:
            raise RegistryError(f"{expert_id} moet 1 tot {max_sources} unieke bronnen hebben")
        expert_urls[expert_id] = urls
        expert_domains[expert_id] = domains
        normalized = dict(expert)
        normalized["authority_score"] = _score(expert["authority_score"], "authority_score", expert_id)
        normalized["public_content_score"] = _score(
            expert["public_content_score"], "public_content_score", expert_id
        )
        normalized["active"] = expert["active"]
        normalized["domains"] = sorted(domains)
        normalized["source_urls"] = sorted(urls)
        normalized_experts.append(normalized)

    seen_urls: set[str] = set()
    source_count: Counter[str] = Counter()
    normalized_sources: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        label = f"bron #{index}"
        if not isinstance(source, dict):
            raise RegistryError(f"{label} moet een object zijn")
        _require_fields(
            source,
            (
                "expert_id",
                "source_url",
                "source_type",
                "title",
                "publisher",
                "language",
                "domains",
                "quality_score",
                "approval_status",
                "access_status",
            ),
            label,
        )
        _require_keys(source, ("published_at",), label)
        expert_id = str(source["expert_id"])
        if expert_id not in expert_ids:
            raise RegistryError(f"{label} verwijst naar onbekende expert_id {expert_id}")
        url = canonical_url(str(source["source_url"]))
        if url in seen_urls:
            raise RegistryError(f"Dezelfde bron mag maar eenmaal voorkomen: {url}")
        seen_urls.add(url)
        if url not in expert_urls[expert_id]:
            raise RegistryError(f"{url} ontbreekt in source_urls van {expert_id}")
        if source["source_type"] not in ALLOWED_SOURCE_TYPES:
            raise RegistryError(f"{url} heeft een onbekend source_type")
        domains = set(_string_list(source["domains"], "domains", url))
        if not domains or not domains <= ALLOWED_DOMAINS:
            raise RegistryError(f"{url} bevat onbekende of lege energiedomeinen")
        if not domains <= expert_domains[expert_id]:
            raise RegistryError(f"{url} bevat domeinen buiten het profiel van {expert_id}")
        published_at = source["published_at"]
        if published_at is not None and not isinstance(published_at, str):
            raise RegistryError(f"{url}.published_at moet null of een string zijn")
        quality = _score(source["quality_score"], "quality_score", url)
        if quality < min_quality:
            raise RegistryError(f"{url} blijft onder de minimumkwaliteit {min_quality}")
        if source["approval_status"] != "pending_human_review":
            raise RegistryError(f"{url} moet op menselijke controle wachten")
        if source["access_status"] not in {"pending_human_review", "verified_public", "public_browser_only"}:
            raise RegistryError(f"{url} heeft een onbekende access_status")
        source_count[expert_id] += 1
        normalized = dict(source)
        normalized["source_url"] = url
        normalized["quality_score"] = quality
        normalized["domains"] = sorted(domains)
        normalized_sources.append(normalized)

    for expert_id in expert_ids:
        if source_count[expert_id] != len(expert_urls[expert_id]):
            raise RegistryError(f"Bronlijst en bronmetadata verschillen voor {expert_id}")

    return (
        sorted(normalized_experts, key=lambda item: item["expert_id"]),
        sorted(normalized_sources, key=lambda item: (item["expert_id"], item["source_url"])),
    )


def jsonl_text(records: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)


def write_if_changed(path: Path, text: str, *, force: bool = False) -> str:
    """Write atomically, refusing to replace changed curated data silently."""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == text:
            return "unchanged"
        if not force:
            raise FileExistsError(f"{path} bestaat en verschilt; controleer de diff en gebruik dan --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    return "written"


def coverage_report(experts: list[dict[str, Any]], sources: list[dict[str, Any]]) -> str:
    sources_by_expert = Counter(source["expert_id"] for source in sources)
    experts_by_domain: dict[str, list[str]] = {domain: [] for domain in sorted(ALLOWED_DOMAINS)}
    for expert in experts:
        for domain in expert["domains"]:
            experts_by_domain[domain].append(expert["name"])

    lines = [
        "# Vlaamse energie-experts — dekkingsrapport",
        "",
        "> Discoverymetadata voor menselijke controle. Er is nog geen broninhoud gedownload.",
        "",
        f"- Experts: **{len(experts)}**",
        f"- Kandidaat-bron-URL's: **{len(sources)}**",
        "- Regio: **Vlaanderen**",
        "- Minimum quality score: **0.65**",
        "",
        "## Experts",
        "",
        "| Expert | Type | Organisatie | Domeinen | Bronnen |",
        "|---|---|---|---|---:|",
    ]
    for expert in experts:
        domains = ", ".join(expert["domains"])
        lines.append(
            f"| {expert['name']} | {expert['expert_type']} | {expert['organization']} | "
            f"{domains} | {sources_by_expert[expert['expert_id']]} |"
        )
    lines.extend(["", "## Dekking per energiedomein", ""])
    for domain, names in experts_by_domain.items():
        rendered = ", ".join(sorted(names)) if names else "**Nog niet afgedekt**"
        lines.append(f"- **{domain}:** {rendered}")
    lines.extend(
        [
            "",
            "## Controlepunt",
            "",
            "Pas na menselijke goedkeuring van `config/experts.yaml` mogen de fetch-, "
            "normalisatie- en chunkfasen worden geactiveerd.",
            "",
        ]
    )
    return "\n".join(lines)
