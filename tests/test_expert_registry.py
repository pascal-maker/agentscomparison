from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from expert_benchmark import validate_benchmark  # noqa: E402
from expert_registry import (  # noqa: E402
    CONTENT_SOURCE_TYPES,
    RegistryError,
    benchmark_holdout,
    canonical_url,
    coverage_report,
    jsonl_text,
    load_registry,
    validate_registry,
    write_if_changed,
)


def test_curated_registry_meets_review_contract() -> None:
    experts, sources = validate_registry(load_registry(ROOT / "config" / "experts.yaml"))

    assert 15 <= len(experts) <= 20
    assert all(expert["region"] == "Vlaanderen" for expert in experts)
    assert all(1 <= len(expert["source_urls"]) <= 5 for expert in experts)
    assert len({source["source_url"] for source in sources}) == len(sources)
    assert all(source["quality_score"] >= 0.65 for source in sources)
    assert all(source["approval_status"] == "pending_human_review" for source in sources)
    assert all(source["access_status"] == "pending_human_review" for source in sources)


def test_materialized_outputs_match_reviewed_yaml() -> None:
    experts, sources = validate_registry(load_registry(ROOT / "config" / "experts.yaml"))

    assert (ROOT / "data" / "experts" / "experts.jsonl").read_text(encoding="utf-8") == jsonl_text(experts)
    assert (ROOT / "data" / "sources" / "sources.jsonl").read_text(encoding="utf-8") == jsonl_text(sources)
    assert (ROOT / "docs" / "flanders-energy-expert-coverage.md").read_text(
        encoding="utf-8"
    ) == coverage_report(experts, sources)


def test_duplicate_source_url_is_rejected() -> None:
    payload = load_registry(ROOT / "config" / "experts.yaml")
    payload["sources"].append(dict(payload["sources"][0]))

    with pytest.raises(RegistryError, match="Dezelfde bron"):
        validate_registry(payload)


def test_expert_without_two_content_sources_is_rejected() -> None:
    payload = load_registry(ROOT / "config" / "experts.yaml")
    expert = payload["experts"][0]
    content = [
        source
        for source in payload["sources"]
        if source["expert_id"] == expert["expert_id"] and source["source_type"] not in {"official_profile", "institutional_page"}
    ]
    for source in content[1:]:
        source["source_type"] = "institutional_page"
        source["quality_score"] = 0.70

    with pytest.raises(RegistryError, match="inhoudelijke bronnen"):
        validate_registry(payload)


def test_profile_page_quality_is_capped() -> None:
    payload = load_registry(ROOT / "config" / "experts.yaml")
    profile = next(source for source in payload["sources"] if source["source_type"] == "official_profile")
    profile["quality_score"] = 0.95

    with pytest.raises(RegistryError, match="profiel- of instellingspagina"):
        validate_registry(payload)


def test_authority_score_must_follow_rubric() -> None:
    payload = load_registry(ROOT / "config" / "experts.yaml")
    payload["experts"][0]["authority_score"] = 0.99

    with pytest.raises(RegistryError, match="scoring_rubric"):
        validate_registry(payload)


def test_url_identity_ignores_fragment_and_trailing_slash() -> None:
    assert canonical_url("https://Example.org/profile/#bio") == "https://example.org/profile"


def test_existing_changed_output_is_not_silently_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "experts.jsonl"
    output.write_text("reviewed\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--force"):
        write_if_changed(output, "replacement\n")

    assert output.read_text(encoding="utf-8") == "reviewed\n"


def test_report_exposes_uncovered_domains() -> None:
    experts, sources = validate_registry(load_registry(ROOT / "config" / "experts.yaml"))
    report = coverage_report(experts, sources)

    assert "# Vlaamse energie-experts" in report
    assert "Nog niet afgedekt" not in report
    assert "Er is nog geen broninhoud gedownload" in report


def test_benchmark_split_keeps_holdout_away_from_karen() -> None:
    _, sources = validate_registry(load_registry(ROOT / "config" / "experts.yaml"))
    benchmark = [source for source in sources if source["use"] == "benchmark"]

    assert 0.25 <= len(benchmark) / len(sources) <= 0.35
    for expert_id in {source["expert_id"] for source in sources}:
        own = [source for source in sources if source["expert_id"] == expert_id]
        assert any(source["use"] == "benchmark" for source in own)
        assert any(source["use"] == "karen" and source["source_type"] in CONTENT_SOURCE_TYPES for source in own)
    assert all(source["source_type"] in CONTENT_SOURCE_TYPES for source in benchmark)
    holdout = benchmark_holdout(sources)
    assert set(holdout["benchmark_only_urls"]) == {source["source_url"] for source in benchmark}


def _benchmark_item(source: dict) -> dict:
    return {
        "id": "q1",
        "expert_id": source["expert_id"],
        "question": "Wat is het capaciteitstarief?",
        "expert_answer": "Een nettarief op basis van je piekverbruik.",
        "quote": "kort citaat",
        "source_url": source["source_url"],
        "published_at": source["published_at"],
    }


def test_benchmark_rejects_karen_and_unapproved_sources() -> None:
    _, sources = validate_registry(load_registry(ROOT / "config" / "experts.yaml"))
    holdout = next(source for source in sources if source["use"] == "benchmark")
    knowledge = next(source for source in sources if source["use"] == "karen")
    approved = {holdout["source_url"], knowledge["source_url"]}

    assert validate_benchmark([_benchmark_item(holdout)], sources, approved)
    with pytest.raises(RegistryError, match="kennisbron van Karen"):
        validate_benchmark([_benchmark_item(knowledge)], sources, approved)
    with pytest.raises(RegistryError, match="niet menselijk is goedgekeurd"):
        validate_benchmark([_benchmark_item(holdout)], sources, set())
