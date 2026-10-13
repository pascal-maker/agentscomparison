"""Bounded Agent API evaluation on held-out static public questions.

Records the raw Agent answer for claim review *and* the answer Karen's public
route would show after its CURRENT_AMOUNT_UNVERIFIED gate, so accuracy and the
helpfulness cost of failing closed are measured on the same call. Official
non-PDF sources cited by each answer are stored as full-length snapshots for
``claim_verification``. Uses only ``cases.json``; no PDF or personal data.

Requires the optional ``luminus_harness.perplexity_agent`` module.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from time import perf_counter, sleep

from .benchmark import HERE, load_cases, load_domains, official_organization
from .claim_verification import fetch_snapshots

HELD_OUT = ("fl-03", "fl-05", "fl-06", "fl-09", "br-05", "br-08", "wa-02", "wa-04", "be-03", "be-12")
MAX_AGENT_CALLS = 12


def official_sources(sources: list[dict], registry: dict) -> list[str]:
    return [source["url"] for source in sources
            if not source["url"].lower().split("?", 1)[0].endswith(".pdf")
            and any(official_organization(source["url"], scope, registry) for scope in registry)]


def ask(question: str) -> dict:
    """One Agent call; returns the raw answer plus the gated status Karen would show."""
    from luminus_harness import perplexity_agent as agent

    gate = agent._protect_current_amounts
    captured: dict = {}

    def capture(answer, sources):
        captured["gated"] = gate(answer, sources)
        return None

    agent._protect_current_amounts = capture
    try:
        result = agent.answer_public_web_question(question)
    finally:
        agent._protect_current_amounts = gate
    gated = captured.get("gated")
    return {**result, "shown_evidence_status": gated["evidence_status"] if gated else result["evidence_status"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=",".join(HELD_OUT), help="Comma-separated case IDs from cases.json")
    parser.add_argument("--output", default="agent-eval-2026-10-13.json")
    parser.add_argument("--live", action="store_true", help="Permit paid Agent and Browserbase Fetch calls")
    args = parser.parse_args()
    cases = {case["id"]: case for case in load_cases()}
    selected = [cases[case_id] for case_id in args.cases.split(",")]
    if len(selected) > MAX_AGENT_CALLS:
        parser.error(f"at most {MAX_AGENT_CALLS} Agent calls per run")
    if not args.live:
        print(f"Ready: {len(selected)} static public questions; add --live to call APIs.")
        return
    from dotenv import load_dotenv

    load_dotenv(HERE.parents[1] / ".env", override=False)
    from luminus_harness.perplexity_agent import PublicWebAgentError

    registry = load_domains()
    rows = []
    for index, case in enumerate(selected):
        if index:
            sleep(1.2)
        row = {"case_id": case["id"], "question": case["question"], "region": case["region"],
               "topic": case["topic"], "answer": "", "evidence_status": "NOT_FOUND",
               "shown_evidence_status": "NOT_FOUND", "sources": [], "official_pages": [], "agent_error": ""}
        started = perf_counter()
        try:
            row.update(ask(case["question"]))
        except PublicWebAgentError as error:
            row["agent_error"] = error.message
        row["agent_latency_ms"] = round((perf_counter() - started) * 1000)
        urls = official_sources(row["sources"], registry)
        row["fetch_failures"] = fetch_snapshots(urls, api_key=os.environ["BROWSERBASE_API_KEY"])
        rows.append(row)
        print(json.dumps({key: row[key] for key in ("case_id", "evidence_status", "shown_evidence_status",
                                                     "agent_latency_ms", "agent_error")}
                         | {"sources": len(row["sources"]), "official_urls": len(urls),
                            "fetch_failures": len(row["fetch_failures"])}, ensure_ascii=False))
    output = HERE / "results" / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"run_at": datetime.now(UTC).isoformat(), "agent_calls": len(rows), "rows": rows},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved public evaluation evidence to {output}")


if __name__ == "__main__":
    main()
