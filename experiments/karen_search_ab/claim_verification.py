"""Strict, offline passage checks for manually structured public-energy claims.

This verifies evidence shape, origin, amount, and explicit validity. It cannot
prove semantic entailment, so a passage match only advances after an
independent semantic review, and the highest model-only verdict still needs a
human sign-off. Coverage requires every content word of an answer to belong to
a structured claim or an explicitly exempted hedge, citation or framing.
No Agent or search API is called; ``--fetch`` is the only paid, opt-in path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .benchmark import (
    HERE,
    is_bot_challenge,
    load_domains,
    official_organization,
    retrieve_official_page,
)
from .claim_audit import _DATE, _MONTHS, past_deadlines
from .providers import SearchError

Region = Literal["flanders", "brussels", "wallonia", "federal"]
Kind = Literal["general", "subsidy", "tariff"]
Unit = Literal["EUR", "CENT_PER_KWH", "KW"]
Verdict = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "CONTRADICTED"]
PILOT_EXTRACTOR = "pilot-2026-10-13"
# Connectives may stay unattributed; every other answer word needs a claim or exemption.
CONNECTIVES = frozenset({"en", "of", "maar", "dus"})


class ClaimEvidence(BaseModel):
    case_id: str = Field(min_length=2)
    claim_key: str = Field(min_length=2)
    region: Region
    kind: Kind
    answer_excerpt: str = Field(min_length=12, max_length=500)
    source_url: str | None = Field(default=None, min_length=12, max_length=2048)
    quote: str | None = Field(default=None, min_length=30, max_length=1000)
    # Why no official passage exists; required exactly when source_url is absent.
    evidence_note: str | None = Field(default=None, min_length=20, max_length=500)
    amount: str | None = None
    unit: Unit | None = None
    extracted_by: str = Field(default=PILOT_EXTRACTOR, min_length=2)

    @model_validator(mode="after")
    def evidence_shape(self) -> ClaimEvidence:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be supplied together")
        if self.amount is not None and not _contains_amount(self.answer_excerpt, self.amount, self.unit):
            raise ValueError("the amount and unit must occur in the answer excerpt")
        if (self.source_url is None) != (self.quote is None):
            raise ValueError("source_url and quote must be supplied together")
        if (self.source_url is None) == (self.evidence_note is None):
            raise ValueError("a claim needs either an official passage or an evidence_note, not both")
        return self


class NonClaim(BaseModel):
    """Answer text that asserts nothing checkable: a hedge, a citation label or framing."""

    case_id: str = Field(min_length=2)
    excerpt: str = Field(min_length=2, max_length=300)
    reason: Literal["hedge", "citation", "framing"]
    note: str = Field(default="", max_length=300)


class SemanticReview(BaseModel):
    claim_key: str = Field(min_length=2)
    reviewer: str = Field(min_length=2)
    reviewer_type: Literal["human", "model"]
    verdict: Verdict
    rationale: str = Field(min_length=20, max_length=1000)
    reviewed_on: date


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^\w]+", " ", text).strip()


def _contains_amount(text: str, amount: str, unit: Unit) -> bool:
    amount_match = re.search(r"(?<!\d)" + re.escape(amount) + r"(?!\d)", text)
    if not amount_match:
        return False
    if unit == "EUR":
        return bool(re.search(r"€\s*" + re.escape(amount) + r"\b|\b" + re.escape(amount) + r"\s*€", text))
    if unit == "KW":
        return bool(re.search(r"(?<!\d)" + re.escape(amount) + r"\s*kW\b", text, re.IGNORECASE))
    nearby = text[max(0, amount_match.start() - 40):amount_match.end() + 40]
    return bool(re.search(r"(?:c€|cent|€cent)\s*(?:/|per)\s*kwh", nearby, re.IGNORECASE))


def _periods(content: str) -> list[tuple[date, date]]:
    dates = list(_DATE.finditer(content))
    periods = []
    for first, second in zip(dates, dates[1:]):
        between = content[first.end():second.start()]
        if len(between) > 20 or not re.search(r"[-–]", between):
            continue
        try:
            start = date(int(first.group(3)), _MONTHS[first.group(2).casefold()], int(first.group(1)))
            end = date(int(second.group(3)), _MONTHS[second.group(2).casefold()], int(second.group(1)))
        except ValueError:
            continue
        if start <= end:
            periods.append((start, end))
    return periods


def verify_claim(
    claim: ClaimEvidence, answer: str, pages: list[dict], *, on_date: date
) -> dict:
    """Return a conservative status and a visible original-source passage."""
    result = {"case_id": claim.case_id, "claim_key": claim.claim_key, "source_url": claim.source_url}
    if _normalized(claim.answer_excerpt) not in _normalized(_answer_text(answer)):
        return {**result, "status": "CLAIM_NOT_IN_ANSWER"}
    if claim.source_url is None:
        return {**result, "status": "NO_OFFICIAL_PASSAGE", "evidence_note": claim.evidence_note}
    registry = load_domains()
    organization = official_organization(claim.source_url, claim.region, registry)
    if not organization:
        return {**result, "status": "WRONG_REGION_OR_SOURCE"}
    # A CAPTCHA served with HTTP 200 is not the original page (seen on FOD Economie).
    candidates = [page for page in pages if page.get("url") == claim.source_url
                  and page.get("content") and not is_bot_challenge(page["content"])]
    # The pilot kept an older 10k-character navigation slice as well as a
    # later full-page Fetch for Wallonia. Inspect the fullest saved original.
    page = max(candidates, key=lambda item: len(item["content"]), default=None)
    if page is None:
        return {**result, "status": "SOURCE_MISSING", "organization": organization}
    content = page["content"]
    if _normalized(claim.quote) not in _normalized(content):
        return {**result, "status": "QUOTE_NOT_FOUND", "organization": organization}
    if claim.amount is not None and not _contains_amount(claim.quote, claim.amount, claim.unit):
        return {**result, "status": "AMOUNT_OR_UNIT_NOT_IN_QUOTE", "organization": organization}
    if claim.kind == "subsidy":
        expired = past_deadlines(content, on_date)
        if expired:
            return {**result, "status": "EXPIRED_DEADLINE", "organization": organization,
                    "quote": claim.quote, "expired_deadlines": expired}
        # No explicit deadline is not evidence that applications are open.
        return {**result, "status": "VALIDITY_UNKNOWN", "organization": organization, "quote": claim.quote}
    if claim.kind == "tariff":
        periods = _periods(content)
        if not periods:
            return {**result, "status": "VALIDITY_UNKNOWN", "organization": organization, "quote": claim.quote}
        if len(set(periods)) > 1:
            return {**result, "status": "AMBIGUOUS_SOURCE_PERIOD", "organization": organization, "quote": claim.quote}
        if not any(start <= on_date <= end for start, end in periods):
            return {**result, "status": "OUTSIDE_SOURCE_PERIOD", "organization": organization,
                    "quote": claim.quote, "periods": [[start.isoformat(), end.isoformat()] for start, end in periods]}
    if claim.kind in ("subsidy", "tariff"):
        stamp = str(page.get("retrieved_at", ""))[:10]
        try:
            retrieved_on = date.fromisoformat(stamp)
        except ValueError:
            return {**result, "status": "RETRIEVAL_TIME_UNKNOWN", "organization": organization, "quote": claim.quote}
        if not 0 <= (on_date - retrieved_on).days <= 7:
            return {**result, "status": "SOURCE_STALE", "organization": organization, "quote": claim.quote,
                    "retrieved_at": page["retrieved_at"]}
    return {**result, "status": "PASSAGE_MATCH_NEEDS_REVIEW", "organization": organization,
            "quote": claim.quote, "retrieved_at": page.get("retrieved_at", "")}


def verify_claims(claims: list[ClaimEvidence], answer: str, pages: list[dict], *, on_date: date) -> list[dict]:
    results = [verify_claim(claim, answer, pages, on_date=on_date) for claim in claims]
    # A subject key must include the relevant meter/period/eligibility context.
    # If two current official passages still disagree, require explicit review.
    for key in {claim.claim_key for claim in claims}:
        matched = [(claim, result) for claim, result in zip(claims, results)
                   if claim.claim_key == key and result["status"] == "PASSAGE_MATCH_NEEDS_REVIEW"
                   and claim.amount is not None]
        if len({claim.amount for claim, _ in matched}) > 1:
            for _, result in matched:
                result["status"] = "CONFLICTING_OFFICIAL_AMOUNTS"
    return results


def _answer_text(answer: str) -> str:
    # Keep link text (it can carry a claim, e.g. a named commercial source); drop URLs.
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", answer)


def _answer_lines(answer: str) -> list[str]:
    return [line for line in map(_normalized, _answer_text(answer).splitlines()) if line]


def uncovered_text(answer: str, excerpts: list[str]) -> list[str]:
    """Runs of answer words not attributed to any claim or exemption excerpt."""
    patterns = [excerpt.split() for excerpt in map(_normalized, excerpts) if excerpt]
    uncovered = []
    for line in _answer_lines(answer):
        words = line.split()
        covered = [word in CONNECTIVES for word in words]
        for pattern in patterns:
            for start in range(len(words) - len(pattern) + 1):
                if words[start:start + len(pattern)] == pattern:
                    covered[start:start + len(pattern)] = [True] * len(pattern)
        run: list[str] = []
        for word, is_covered in zip(words + [""], covered + [True]):
            if not is_covered:
                run.append(word)
            elif run:
                uncovered.append(" ".join(run))
                run = []
    return uncovered


def coverage(answer: str, claims: list[ClaimEvidence], non_claims: list[NonClaim]) -> dict:
    text = _normalized(_answer_text(answer))
    missing = [item.excerpt for item in non_claims if _normalized(item.excerpt) not in text]
    uncovered = uncovered_text(answer, [claim.answer_excerpt for claim in claims]
                               + [item.excerpt for item in non_claims])
    return {"complete": not uncovered and not missing, "uncovered": uncovered,
            "exemptions_not_in_answer": missing, "exemptions": len(non_claims)}


def apply_reviews(claims: list[ClaimEvidence], results: list[dict], reviews: list[SemanticReview]) -> list[dict]:
    """Negative findings from anyone block; positive ones count only if independent."""
    by_key: dict[str, list[SemanticReview]] = {}
    for review in reviews:
        by_key.setdefault(review.claim_key, []).append(review)
    reviewed = []
    for claim, result in zip(claims, results):
        result = dict(result)
        found = by_key.get(claim.claim_key, [])
        result["reviews"] = [review.model_dump(mode="json") for review in found]
        negative = [review for review in found if review.verdict != "SUPPORTED"]
        independent = [review for review in found if review.verdict == "SUPPORTED"
                       and review.reviewer != claim.extracted_by]
        if result["status"] == "PASSAGE_MATCH_NEEDS_REVIEW":
            if negative:
                result["status"] = "REVIEW_" + negative[0].verdict
            elif any(review.reviewer_type == "human" for review in independent):
                result["status"] = "HUMAN_REVIEW_SUPPORTED"
            elif independent:
                result["status"] = "MODEL_REVIEW_SUPPORTED"
            else:
                result["status"] = "NEEDS_INDEPENDENT_REVIEW"
        reviewed.append(result)
    return reviewed


_PENDING = {"NEEDS_INDEPENDENT_REVIEW", "PASSAGE_MATCH_NEEDS_REVIEW"}
_SUPPORTED = {"MODEL_REVIEW_SUPPORTED", "HUMAN_REVIEW_SUPPORTED"}


def case_verdict(results: list[dict], case_coverage: dict | None = None) -> str:
    """Never an automatic approval: the best outcome still names who must sign off."""
    if not results:
        return "UNASSESSED"
    statuses = {result["status"] for result in results}
    if statuses - _PENDING - _SUPPORTED:
        return "BLOCKED"
    if case_coverage is None or not case_coverage["complete"]:
        return "INCOMPLETE_COVERAGE"
    if statuses & _PENDING:
        return "NEEDS_SEMANTIC_REVIEW"
    if statuses == {"HUMAN_REVIEW_SUPPORTED"}:
        return "HUMAN_REVIEWED_SUPPORTED"
    return "NEEDS_HUMAN_SIGNOFF"


SOURCES = HERE / "results" / "sources"


def snapshot_path(url: str) -> Path:
    return SOURCES / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".json")


def load_snapshots(urls) -> list[dict]:
    """Full-length original pages fetched separately; Git-ignored like all results."""
    pages = []
    for url in sorted(set(urls)):
        path = snapshot_path(url)
        if path.exists():
            page = json.loads(path.read_text(encoding="utf-8"))
            if page.get("url") == url:
                pages.append(page)
    return pages


def fetch_snapshots(urls, *, api_key: str, fetcher=retrieve_official_page) -> list[str]:
    """One Browserbase Fetch per official URL without a snapshot; returns failures."""
    registry = load_domains()
    failures = []
    SOURCES.mkdir(parents=True, exist_ok=True)
    for url in sorted(set(urls)):
        if snapshot_path(url).exists():
            continue
        try:
            page = fetcher(url, api_key=api_key, registry=registry, max_chars=200000)
        except SearchError as error:
            failures.append(f"{url}: {error}")
            continue
        snapshot_path(url).write_text(json.dumps({"url": url, **page}, ensure_ascii=False), encoding="utf-8")
    return failures


def pilot_pages(row: dict, urls=()) -> list[dict]:
    pages = list(row["official_pages"]) + load_snapshots(urls)
    if row["case_id"] == "wa-05":
        path = HERE / "results" / "wa-05-original-full.json"
        if path.exists():
            pages.append(json.loads(path.read_text(encoding="utf-8")))
    if row["case_id"] == "be-08":
        for energy, prefix in (("electricity", "E"), ("gas", "G")):
            path = HERE / "results" / f"creg-q4-2026-{energy}.txt"
            if path.exists():
                pages.append({
                    "url": f"https://www.creg.be/sites/default/files/assets/Tarifs/Social/{prefix}-TSS-NL-2026-Q4.pdf",
                    "content": path.read_text(encoding="utf-8"),
                    "retrieved_at": "2026-10-13",
                })
    if row["case_id"] == "be-01":
        path = HERE / "results" / "be-01-vlaanderen-full.json"
        if path.exists():
            pages.append(json.loads(path.read_text(encoding="utf-8")))
    return pages


def _load(name: str, model):
    return [model.model_validate(item) for item in json.loads((HERE / name).read_text(encoding="utf-8"))]


def evaluate_case(row: dict, claims: list[ClaimEvidence], non_claims: list[NonClaim],
                  reviews: list[SemanticReview], *, on_date: date) -> dict:
    selected = [claim for claim in claims if claim.case_id == row["case_id"]]
    exempt = [item for item in non_claims if item.case_id == row["case_id"]]
    pages = pilot_pages(row, [claim.source_url for claim in selected if claim.source_url])
    results = apply_reviews(selected, verify_claims(selected, row["answer"], pages, on_date=on_date), reviews)
    case_coverage = coverage(row["answer"], selected, exempt)
    return {"case_id": row["case_id"], "case_verdict": case_verdict(results, case_coverage),
            "coverage": case_coverage, "claims": results}


def review_packet(row: dict, evaluated: dict, claims: list[ClaimEvidence], non_claims: list[NonClaim]) -> str:
    """Markdown for an independent reviewer: answer, every claim with its passage, every exemption."""
    by_key = {claim.claim_key: claim for claim in claims if claim.case_id == row["case_id"]}
    lines = [f"## {row['case_id']}: {row['question']}", "", "> " + row["answer"].replace("\n", "\n> "), ""]
    for result in evaluated["claims"]:
        claim = by_key[result["claim_key"]]
        lines += [f"- [ ] `{claim.claim_key}` ({claim.region}, {claim.kind}) — status `{result['status']}`",
                  f"  - Answer: “{claim.answer_excerpt}”",
                  f"  - Source: {claim.source_url or '—'}",
                  f"  - Passage: “{claim.quote or claim.evidence_note}”",
                  "  - Verdict: SUPPORTED / PARTIALLY_SUPPORTED / NOT_SUPPORTED / CONTRADICTED — rationale:"]
    for item in non_claims:
        if item.case_id == row["case_id"]:
            lines.append(f"- [ ] Exempt as {item.reason}: “{item.excerpt}” {item.note}".rstrip())
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="append", default=[], metavar="URL",
                        help="Paid Browserbase Fetch of an official URL into results/sources/ (repeatable)")
    parser.add_argument("--review-packet", type=Path, help="Write a Markdown packet for an independent reviewer")
    args = parser.parse_args()
    if args.fetch:
        from dotenv import load_dotenv

        load_dotenv(HERE.parents[1] / ".env", override=False)
        api_key = os.getenv("BROWSERBASE_API_KEY")
        if not api_key:
            parser.error("BROWSERBASE_API_KEY is missing")
        for failure in fetch_snapshots(args.fetch, api_key=api_key):
            print(json.dumps({"fetch_failed": failure}, ensure_ascii=False))
        return
    pilot = json.loads((HERE / "results" / "agent-pilot-2026-10-13.json").read_text(encoding="utf-8"))
    claims = _load("pilot_claims.json", ClaimEvidence)
    non_claims = _load("pilot_non_claims.json", NonClaim)
    reviews = _load("semantic_reviews.json", SemanticReview)
    on_date = date.fromisoformat(pilot["run_at"][:10])
    packet = []
    for row in pilot["rows"]:
        evaluated = evaluate_case(row, claims, non_claims, reviews, on_date=on_date)
        packet.append(review_packet(row, evaluated, claims, non_claims))
        print(json.dumps(evaluated, ensure_ascii=False))
    if args.review_packet:
        args.review_packet.write_text("# Karen claim review packet\n\n" + "\n".join(packet), encoding="utf-8")


if __name__ == "__main__":
    main()
