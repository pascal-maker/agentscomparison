#!/usr/bin/env python3
"""Materialize explicitly approved source metadata without downloading content."""

from __future__ import annotations

import argparse
from pathlib import Path

from expert_registry import jsonl_text, load_registry, validate_registry, write_if_changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/experts.yaml"))
    parser.add_argument("--output", type=Path, default=Path("data/sources/sources.jsonl"))
    parser.add_argument("--force", action="store_true", help="Vervang alleen na handmatige review")
    args = parser.parse_args()

    _, sources = validate_registry(load_registry(args.config))
    status = write_if_changed(args.output, jsonl_text(sources), force=args.force)
    print(f"{status}: {len(sources)} bronnen -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
