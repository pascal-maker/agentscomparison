#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from luminus_harness import (
    billing_explanation,
    energy_advice,
    get_scenario,
    list_scenarios,
    propose_appointment,
)

REPO_ROOT = Path(__file__).resolve().parent
TINYAGI_ENERGY = REPO_ROOT / "tinyagi_energy" / "skills" / "luminus-energy" / "scripts" / "energy.sh"


@dataclass(frozen=True)
class AdapterResult:
    adapter: str
    capability: str
    output: str


def harness_results(scenario_id: str) -> list[AdapterResult]:
    scenario = get_scenario(scenario_id)
    return [
        AdapterResult("harness", "billing", billing_explanation(scenario.customer_id)),
        AdapterResult("harness", "advice", energy_advice(scenario.customer_id, scenario.focus)),
        AdapterResult(
            "harness",
            "appointment",
            propose_appointment(scenario.customer_id, scenario.appointment_reason, scenario.appointment_date),
        ),
    ]


def run_tinyagi(command: list[str]) -> str:
    result = subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def tinyagi_results(scenario_id: str) -> list[AdapterResult]:
    scenario = get_scenario(scenario_id)
    base = [str(TINYAGI_ENERGY)]
    return [
        AdapterResult("tinyagi", "billing", run_tinyagi(base + ["billing", scenario.customer_id])),
        AdapterResult("tinyagi", "advice", run_tinyagi(base + ["advice", scenario.customer_id, scenario.focus])),
        AdapterResult(
            "tinyagi",
            "appointment",
            run_tinyagi(base + ["appointment", scenario.customer_id, scenario.appointment_reason, scenario.appointment_date]),
        ),
    ]


def render_table(rows: list[AdapterResult]) -> str:
    adapter_width = max(len("Adapter"), *(len(row.adapter) for row in rows))
    capability_width = max(len("Capability"), *(len(row.capability) for row in rows))
    lines = [
        f"{'Adapter':<{adapter_width}}  {'Capability':<{capability_width}}  Output",
        f"{'-' * adapter_width}  {'-' * capability_width}  {'-' * 80}",
    ]
    for row in rows:
        compact_output = " ".join(row.output.split())
        lines.append(f"{row.adapter:<{adapter_width}}  {row.capability:<{capability_width}}  {compact_output}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare deterministic Luminus adapters on one scenario.")
    parser.add_argument("--scenario", default="high_bill", choices=list_scenarios())
    parser.add_argument(
        "--adapter",
        action="append",
        choices=["harness", "tinyagi"],
        help="Adapter to run. Repeat for multiple. Defaults to harness and tinyagi.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenario = get_scenario(args.scenario)
    adapters = args.adapter or ["harness", "tinyagi"]

    rows: list[AdapterResult] = []
    if "harness" in adapters:
        rows.extend(harness_results(args.scenario))
    if "tinyagi" in adapters:
        rows.extend(tinyagi_results(args.scenario))

    print(f"Scenario: {scenario.title} ({scenario.scenario_id})")
    print(f"Customer: {scenario.customer_id}")
    print(f"Query: {scenario.query}")
    print()
    print(render_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
