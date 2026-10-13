"""Offline, conservative audit of monetary Agent claims against saved original pages.

This is an evaluation aid, not a semantic verifier or a production answer path.
It deliberately never labels a claim VERIFIED: a number appearing somewhere on
an official page need not support the Agent's exact claim.
"""

from __future__ import annotations

import json
import argparse
import os
import re
from datetime import date

from .benchmark import HERE, load_domains, official_organization, retrieve_official_page

_MONTHS = {
    "januari": 1, "janvier": 1, "februari": 2, "février": 2,
    "maart": 3, "mars": 3, "april": 4, "avril": 4,
    "mei": 5, "mai": 5, "juni": 6, "juin": 6,
    "juli": 7, "juillet": 7, "augustus": 8, "août": 8,
    "september": 9, "septembre": 9, "oktober": 10, "octobre": 10,
    "november": 11, "novembre": 11, "december": 12, "décembre": 12,
}
_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(20\d{2})\b", re.IGNORECASE)
_DEADLINE = re.compile(r"(?:au plus tard le|uiterlijk|deadline|avant le)\s+.{0,15}", re.IGNORECASE)
_EUROS = re.compile(r"€\s*(\d+(?:[.,]\d+)?)|\b(\d+(?:[.,]\d+)?)\s*€")
_CENT_RANGE = re.compile(r"\b(\d+[.,]\d+)\s*[–-]\s*(\d+[.,]\d+)\s*(?:cent|c€)")
_CENTS = re.compile(r"\b(\d+[.,]\d+)\s*(?:cent|c€)")


def monetary_numbers(answer: str) -> set[str]:
    numbers = {a or b for a, b in _EUROS.findall(answer)}
    numbers.update(_CENTS.findall(answer))
    for first, last in _CENT_RANGE.findall(answer):
        numbers.update((first, last))
    return numbers


def past_deadlines(content: str, on_date: date) -> list[str]:
    """Find explicit application deadlines; incomplete formats remain unknown."""
    found = []
    for match in _DEADLINE.finditer(content):
        date_match = _DATE.search(content[match.start():match.end() + 30])
        if not date_match:
            continue
        day, month, year = date_match.groups()
        try:
            deadline = date(int(year), _MONTHS[month.casefold()], int(day))
        except ValueError:
            continue
        if deadline < on_date:
            found.append(deadline.isoformat())
    return sorted(set(found))


def audit_amount_claim(answer: str, pages: list[dict], *, on_date: date) -> dict:
    """Compare literal amounts and explicit expiry in official original-page text."""
    amounts = monetary_numbers(answer)
    if not amounts:
        return {"status": "NO_MONETARY_CLAIM", "missing_amounts": [], "expired_deadlines": []}
    registry = load_domains()
    official = [page for page in pages if isinstance(page.get("content"), str) and any(
        official_organization(page.get("url", ""), scope, registry) for scope in registry
    )]
    contents = [page["content"] for page in official]
    missing = sorted(amount for amount in amounts if not any(
        re.search(r"(?<!\d)" + re.escape(amount) + r"(?!\d)", content) for content in contents
    ))
    deadlines = sorted({deadline for content in contents for deadline in past_deadlines(content, on_date)})
    status = "EXPIRED_DEADLINE" if deadlines else ("MISSING_ORIGINAL_PASSAGE" if missing else "TEXT_MATCH_ONLY")
    return {
        "status": status,
        "missing_amounts": missing,
        "expired_deadlines": deadlines,
        "official_pages_read": len(official),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-wallonia", action="store_true", help="One paid Browserbase Fetch of the original official page")
    args = parser.parse_args()
    pilot = json.loads((HERE / "results" / "agent-pilot-2026-10-13.json").read_text(encoding="utf-8"))
    on_date = date.fromisoformat(pilot["run_at"][:10])
    wallonia_cache = HERE / "results" / "wa-05-original-full.json"
    if args.refresh_wallonia:
        from dotenv import load_dotenv

        load_dotenv(HERE.parents[1] / ".env", override=False)
        api_key = os.getenv("BROWSERBASE_API_KEY")
        if not api_key:
            parser.error("BROWSERBASE_API_KEY is missing")
        row = next(row for row in pilot["rows"] if row["case_id"] == "wa-05")
        url = next(source["url"] for source in row["sources"] if source["url"].startswith(
            "https://energie.wallonie.be/home/"
        ))
        page = retrieve_official_page(url, api_key=api_key, registry=load_domains(), max_chars=100000)
        wallonia_cache.write_text(json.dumps({"url": url, **page}, ensure_ascii=False), encoding="utf-8")
    for row in pilot["rows"]:
        pages = list(row["official_pages"])
        if row["case_id"] == "wa-05" and wallonia_cache.exists():
            pages.append(json.loads(wallonia_cache.read_text(encoding="utf-8")))
        if row["case_id"] == "be-08":
            for energy in ("electricity", "gas"):
                path = HERE / "results" / f"creg-q4-2026-{energy}.txt"
                if path.exists():
                    pages.append({
                        "url": f"https://www.creg.be/sites/default/files/assets/Tarifs/Social/{'E' if energy == 'electricity' else 'G'}-TSS-NL-2026-Q4.pdf",
                        "content": path.read_text(encoding="utf-8"),
                    })
        print(json.dumps({"case_id": row["case_id"], **audit_amount_claim(
            row["answer"], pages, on_date=on_date
        )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
