#!/usr/bin/env python3
"""Generate the human-review coverage report for the curated registry."""

from __future__ import annotations

import argparse
from pathlib import Path

from expert_registry import coverage_report, load_registry, validate_registry, write_if_changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/experts.yaml"))
    parser.add_argument("--output", type=Path, default=Path("docs/flanders-energy-expert-coverage.md"))
    parser.add_argument("--force", action="store_true", help="Vervang alleen na handmatige review")
    args = parser.parse_args()

    experts, sources = validate_registry(load_registry(args.config))
    status = write_if_changed(args.output, coverage_report(experts, sources), force=args.force)
    print(f"{status}: rapport -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
