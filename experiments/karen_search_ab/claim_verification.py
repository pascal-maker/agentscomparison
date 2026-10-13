"""Strict, offline passage checks for manually structured public-energy claims.

This verifies evidence shape, origin, amount, and explicit validity. It cannot
prove semantic entailment, so even successful checks require human review.
No Agent, search, or Fetch API is called by this module.
"""

from __future__ import annotations

import json
import argparse
import os
import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .benchmark import HERE, load_domains, official_organization, retrieve_official_page
from .claim_audit import _DATE, _MONTHS, past_deadlines

Region = Literal["flanders", "brussels", "wallonia", "federal"]
Kind = Literal["general", "subsidy", "tariff"]
Unit = Literal["EUR", "CENT_PER_KWH"]


class ClaimEvidence(BaseModel):
    case_id: str = Field(min_length=2)
    claim_key: str = Field(min_length=2)
    region: Region
    kind: Kind
    answer_excerpt: str = Field(min_length=12, max_length=500)
    source_url: str = Field(min_length=12, max_length=2048)
    quote: str = Field(min_length=30, max_length=1000)
    amount: str | None = None
    unit: Unit | None = None

    @model_validator(mode="after")
    def amount_and_unit_together(self) -> "ClaimEvidence":
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be supplied together")
        if self.amount is not None and not _contains_amount(self.answer_excerpt, self.amount, self.unit):
            raise ValueError("the amount and unit must occur in the answer excerpt")
        return self


def _normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^\w]+", " ", text).strip()


def _contains_amount(text: str, amount: str, unit: Unit) -> bool:
    amount_match = re.search(r"(?<!\d)" + re.escape(amount) + r"(?!\d)", text)
    if not amount_match:
        return False
    if unit == "EUR":
        return bool(re.search(r"€\s*" + re.escape(amount) + r"\b|\b" + re.escape(amount) + r"\s*€", text))
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
    if _normalized(claim.answer_excerpt) not in _normalized(answer):
        return {**result, "status": "CLAIM_NOT_IN_ANSWER"}
    registry = load_domains()
    organization = official_organization(claim.source_url, claim.region, registry)
    if not organization:
        return {**result, "status": "WRONG_REGION_OR_SOURCE"}
    candidates = [page for page in pages if page.get("url") == claim.source_url and page.get("content")]
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


def case_verdict(results: list[dict]) -> str:
    """Selected claims never imply complete coverage or automatic approval."""
    if not results:
        return "UNASSESSED"
    if any(result["status"] != "PASSAGE_MATCH_NEEDS_REVIEW" for result in results):
        return "BLOCKED"
    return "SELECTED_CLAIMS_NEED_REVIEW"


def pilot_pages(row: dict) -> list[dict]:
    pages = list(row["official_pages"])
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-be01", action="store_true", help="One paid Browserbase Fetch of the official Vlaanderen page")
    args = parser.parse_args()
    pilot = json.loads((HERE / "results" / "agent-pilot-2026-10-13.json").read_text(encoding="utf-8"))
    claims = [ClaimEvidence.model_validate(item) for item in json.loads(
        (HERE / "pilot_claims.json").read_text(encoding="utf-8")
    )]
    on_date = date.fromisoformat(pilot["run_at"][:10])
    if args.refresh_be01:
        from dotenv import load_dotenv

        load_dotenv(HERE.parents[1] / ".env", override=False)
        api_key = os.getenv("BROWSERBASE_API_KEY")
        if not api_key:
            parser.error("BROWSERBASE_API_KEY is missing")
        source_url = next(claim.source_url for claim in claims if claim.case_id == "be-01")
        page = retrieve_official_page(source_url, api_key=api_key, registry=load_domains(), max_chars=100000)
        (HERE / "results" / "be-01-vlaanderen-full.json").write_text(
            json.dumps({"url": source_url, **page}, ensure_ascii=False), encoding="utf-8"
        )
    for row in pilot["rows"]:
        selected = [claim for claim in claims if claim.case_id == row["case_id"]]
        results = verify_claims(selected, row["answer"], pilot_pages(row), on_date=on_date)
        print(json.dumps({"case_id": row["case_id"], "case_verdict": case_verdict(results),
                          "claims": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
