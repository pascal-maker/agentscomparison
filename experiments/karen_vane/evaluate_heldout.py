"""Diagnostic checks for public-search observations; never certifies factual claims."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .adapter import KarenAnswer


class HeldoutCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    question: str = Field(min_length=2)
    expected_status: list[str] = Field(min_length=1)
    authority_hosts: list[str]
    concept_groups: list[list[str]]
    review_note: str


def _on_host(url: str, domains: list[str]) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    return parsed.scheme == "https" and any(
        host == domain or host.endswith("." + domain) for domain in domains
    )


def evaluate(case: HeldoutCase, answer: KarenAnswer) -> dict:
    sources = answer.sources
    source_text = " ".join(f"{source.title} {source.excerpt}" for source in sources).casefold()
    source_signals = []
    for source in sources:
        text = f"{source.title} {source.excerpt}".casefold()
        source_signals.append({
            "url": str(source.url),
            "authority_host_match": _on_host(str(source.url), case.authority_hosts),
            "concept_groups_matched": sum(
                any(term.casefold() in text for term in group) for group in case.concept_groups
            ),
        })
    matched_hosts = [signal["url"] for signal in source_signals
                     if signal["authority_host_match"]]
    missing_concepts = [group for group in case.concept_groups
                        if not any(term.casefold() in source_text for term in group)]
    official_source_present = bool(matched_hosts) if case.authority_hosts else None
    # These are retrieval signals. Even a matching host and term can carry a
    # stale, inapplicable or misleading passage; claims need separate review.
    return {
        "id": case.id,
        "status": answer.status,
        "status_allowed": answer.status in case.expected_status,
        "source_count": len(sources),
        "official_source_present": official_source_present,
        "matched_authority_urls": matched_hosts,
        "source_signals": source_signals,
        "lexically_matching_authority_count": sum(
            signal["authority_host_match"]
            and signal["concept_groups_matched"] == len(case.concept_groups)
            for signal in source_signals
        ) if case.concept_groups else None,
        "missing_concept_groups": missing_concepts,
        "claim_verdict": "not_evaluated" if answer.status != "answer_with_sources"
                         else "manual_review_required",
        "evidence_status": answer.evidence_status,
        "review_note": case.review_note,
    }


def evaluate_file(cases_path: Path, observations_path: Path) -> list[dict]:
    cases = {case.id: case for case in (
        HeldoutCase.model_validate(raw) for raw in json.loads(cases_path.read_text())
    )}
    results = []
    for line in observations_path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        case = cases[record["id"]]
        if record["question"] != case.question:
            raise ValueError(f"Question changed for {case.id}")
        result = evaluate(case, KarenAnswer.model_validate(record["response"]))
        result["checked_at"] = record["checked_at"]
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("heldout_questions.json"))
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    for result in evaluate_file(args.cases, args.observations):
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
