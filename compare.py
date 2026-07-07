#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from luminus_harness import (
    LUMINUS_INSTRUCTIONS,
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


async def openai_live_results(scenario_id: str) -> list[AdapterResult]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --live openai.")

    try:
        from agents import Agent, Runner, function_tool, set_tracing_disabled
    except ImportError as error:
        raise RuntimeError("Install OpenAI Agents dependencies: pip install -r requirements/openai-agents.txt") from error

    scenario = get_scenario(scenario_id)
    set_tracing_disabled(True)

    @function_tool
    def explain_bill() -> str:
        """Return the canonical billing explanation for the scenario customer."""
        return billing_explanation(scenario.customer_id)

    @function_tool
    def suggest_savings() -> str:
        """Return canonical energy-saving advice for the scenario customer."""
        return energy_advice(scenario.customer_id, scenario.focus)

    @function_tool
    def propose_visit() -> str:
        """Return the canonical appointment proposal for the scenario customer."""
        return propose_appointment(scenario.customer_id, scenario.appointment_reason, scenario.appointment_date)

    agent = Agent(
        name="Luminus Live Comparison Agent",
        instructions=(
            LUMINUS_INSTRUCTIONS
            + " Use the available tools for billing, saving advice, and appointment proposals. "
            + "Answer the customer's scenario query in one concise support response."
        ),
        tools=[explain_bill, suggest_savings, propose_visit],
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
    result = await Runner.run(agent, scenario.query)
    return [AdapterResult("openai", "live_response", str(result.final_output))]


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
    parser = argparse.ArgumentParser(description="Compare Luminus adapters on one scenario.")
    parser.add_argument("--scenario", default="high_bill", choices=list_scenarios())
    parser.add_argument(
        "--adapter",
        action="append",
        choices=["harness", "tinyagi"],
        help="Adapter to run. Repeat for multiple. Defaults to harness and tinyagi.",
    )
    parser.add_argument(
        "--live",
        action="append",
        choices=["openai"],
        help="Optional live framework adapter. Repeat for multiple. Requires provider credentials.",
    )
    return parser


async def collect_rows(scenario_id: str, adapters: list[str], live_adapters: list[str]) -> list[AdapterResult]:
    rows: list[AdapterResult] = []
    if "harness" in adapters:
        rows.extend(harness_results(scenario_id))
    if "tinyagi" in adapters:
        rows.extend(tinyagi_results(scenario_id))
    if "openai" in live_adapters:
        rows.extend(await openai_live_results(scenario_id))
    return rows


async def async_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scenario = get_scenario(args.scenario)
    adapters = args.adapter or ["harness", "tinyagi"]
    live_adapters = args.live or []

    try:
        rows = await collect_rows(args.scenario, adapters, live_adapters)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"Scenario: {scenario.title} ({scenario.scenario_id})")
    print(f"Customer: {scenario.customer_id}")
    print(f"Query: {scenario.query}")
    print()
    print(render_table(rows))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
