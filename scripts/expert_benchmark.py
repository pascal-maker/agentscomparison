#!/usr/bin/env python3
"""Validate expert question-answer pairs and export the benchmark/Karen source split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from expert_registry import (
    RegistryError,
    benchmark_holdout,
    canonical_url,
    load_registry,
    validate_registry,
    write_if_changed,
)

ITEM_FIELDS = ("id", "expert_id", "question", "expert_answer", "quote", "source_url", "published_at")
# Een korte letterlijke steun voor het antwoord, geen overgenomen artikel.
MAX_QUOTE_CHARS = 300


def validate_benchmark(items: Any, sources: list[dict[str, Any]], approved_urls: set[str]) -> list[dict[str, Any]]:
    """Each pair must come from an approved benchmark-only source of the same expert."""
    if not isinstance(items, list):
        raise RegistryError("expert_benchmark.json moet een lijst zijn")
    by_url = {source["source_url"]: source for source in sources}
    seen_ids: set[str] = set()
    seen_questions: set[str] = set()
    for index, item in enumerate(items, start=1):
        label = f"benchmarkvraag #{index}"
        if not isinstance(item, dict):
            raise RegistryError(f"{label} moet een object zijn")
        missing = [field for field in ITEM_FIELDS if field != "published_at" and not item.get(field)]
        if missing or "published_at" not in item:
            raise RegistryError(f"{label} mist velden: {', '.join(missing or ['published_at'])}")
        if item["id"] in seen_ids:
            raise RegistryError(f"Dubbele benchmark-id: {item['id']}")
        seen_ids.add(item["id"])
        question = " ".join(str(item["question"]).casefold().split())
        if question in seen_questions:
            raise RegistryError(f"{item['id']} herhaalt een bestaande vraag")
        seen_questions.add(question)
        url = canonical_url(str(item["source_url"]))
        source = by_url.get(url)
        if source is None:
            raise RegistryError(f"{item['id']} verwijst naar een bron buiten het register: {url}")
        if source["use"] != "benchmark":
            raise RegistryError(f"{item['id']} gebruikt een kennisbron van Karen; alleen benchmarkbronnen zijn toegestaan")
        if url not in approved_urls:
            raise RegistryError(f"{item['id']} gebruikt een bron die nog niet menselijk is goedgekeurd")
        if source["expert_id"] != item["expert_id"]:
            raise RegistryError(f"{item['id']} hoort bij {source['expert_id']}, niet bij {item['expert_id']}")
        if len(str(item["quote"])) > MAX_QUOTE_CHARS:
            raise RegistryError(f"{item['id']}.quote mag maximaal {MAX_QUOTE_CHARS} tekens zijn")
    return sorted(items, key=lambda item: item["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/experts.yaml"))
    parser.add_argument("--benchmark", type=Path, default=Path("data/benchmark/expert_benchmark.json"))
    parser.add_argument("--holdout", type=Path, default=Path("data/benchmark/holdout.json"))
    parser.add_argument("--force", action="store_true", help="Vervang alleen na handmatige review")
    args = parser.parse_args()

    payload = load_registry(args.config)
    _, sources = validate_registry(payload)
    holdout = json.dumps(benchmark_holdout(sources), ensure_ascii=False, indent=2) + "\n"
    status = write_if_changed(args.holdout, holdout, force=args.force)
    print(f"{status}: split -> {args.holdout}")

    if args.benchmark.exists():
        approved = {
            canonical_url(source["source_url"])
            for source in payload["sources"]
            if source.get("approval_status") == "approved"
        }
        items = validate_benchmark(json.loads(args.benchmark.read_text(encoding="utf-8")), sources, approved)
        print(f"ok: {len(items)} benchmarkvragen in {args.benchmark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
