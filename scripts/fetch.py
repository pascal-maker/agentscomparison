#!/usr/bin/env python3
"""Reserved for approved ingestion phase; intentionally performs no network calls."""

def main() -> int:
    raise SystemExit(
        "Fetch is geblokkeerd: keur eerst config/experts.yaml en data/sources/sources.jsonl handmatig goed."
    )


if __name__ == "__main__":
    raise SystemExit(main())
