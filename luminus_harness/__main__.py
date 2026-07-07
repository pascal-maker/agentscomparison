from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

from .core import (
    billing_explanation,
    customer_context,
    energy_advice,
    energy_insights,
    get_scenario,
    list_scenarios,
    propose_appointment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical Luminus comparison harness.")
    parser.add_argument("--json", action="store_true", help="Print a structured JSON payload.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scenarios", help="List canonical comparison scenarios.")

    context = subparsers.add_parser("context", help="Print canonical customer context.")
    context.add_argument("customer_id")

    billing = subparsers.add_parser("billing", help="Print the billing explanation.")
    billing.add_argument("customer_id")

    insights = subparsers.add_parser("insights", help="Print energy usage insights.")
    insights.add_argument("customer_id")

    advice = subparsers.add_parser("advice", help="Print energy-saving advice.")
    advice.add_argument("customer_id")
    advice.add_argument("focus", nargs="?", choices=["heating", "appliances", "general"], default="general")

    appointment = subparsers.add_parser("appointment", help="Print an appointment proposal.")
    appointment.add_argument("customer_id")
    appointment.add_argument("reason")
    appointment.add_argument("date")

    return parser


def render(args: argparse.Namespace) -> str:
    handlers: dict[str, Callable[[argparse.Namespace], str]] = {
        "scenarios": lambda parsed: "\n".join(list_scenarios()),
        "context": lambda parsed: customer_context(parsed.customer_id),
        "billing": lambda parsed: billing_explanation(parsed.customer_id),
        "insights": lambda parsed: energy_insights(parsed.customer_id),
        "advice": lambda parsed: energy_advice(parsed.customer_id, parsed.focus),
        "appointment": lambda parsed: propose_appointment(parsed.customer_id, parsed.reason, parsed.date),
    }
    return handlers[args.command](args)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = render(args)
    ok = not text.startswith("No Luminus account found")

    if args.json:
        payload = {
            "ok": ok,
            "command": args.command,
            "text": text,
        }
        if args.command == "scenarios":
            payload["scenarios"] = [
                {
                    "id": scenario_id,
                    "title": get_scenario(scenario_id).title,
                    "customer_id": get_scenario(scenario_id).customer_id,
                    "query": get_scenario(scenario_id).query,
                }
                for scenario_id in list_scenarios()
            ]
        else:
            payload["customer_id"] = args.customer_id
        print(json.dumps(payload, ensure_ascii=False))
    else:
        stream = sys.stdout if ok else sys.stderr
        print(text, file=stream)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
