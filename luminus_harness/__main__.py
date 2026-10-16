from __future__ import annotations#import classes as they are defined in the same file

import argparse# used to parse arguments
import json# used to work with json
import sys# used to work with the system
from typing import Callable# used for type hints

from .core import (
    CustomerNotFoundError,# used to report an unknown customer cleanly
    billing_explanation,# used to get the billing explanation
    customer_context,# used to get the customer context
    energy_advice,# used to get the energy advice
    energy_insights,# used to get the energy insights
    get_scenario,# used to get the scenario
    list_scenarios,# used to list the scenarios
    propose_appointment,# used to propose an appointment
)


def build_parser() -> argparse.ArgumentParser:# builds the parser
    parser = argparse.ArgumentParser(description="Canonical Luminus comparison harness.")# creates the parser
    parser.add_argument("--json", action="store_true", help="Print a structured JSON payload.")# adds the json argument
    subparsers = parser.add_subparsers(dest="command", required=True)# adds the subparsers

    subparsers.add_parser("scenarios", help="List canonical comparison scenarios.")# adds the scenarios subparser

    context = subparsers.add_parser("context", help="Print canonical customer context.")# adds the context subparser
    context.add_argument("customer_id")# adds the customer id argument

    billing = subparsers.add_parser("billing", help="Print the billing explanation.")# adds the billing subparser
    billing.add_argument("customer_id")# adds the customer id argument

    insights = subparsers.add_parser("insights", help="Print energy usage insights.")# adds the insights subparser
    insights.add_argument("customer_id")# adds the customer id argument

    advice = subparsers.add_parser("advice", help="Print energy-saving advice.")# adds the advice subparser
    advice.add_argument("customer_id")# adds the customer id argument
    advice.add_argument("focus", nargs="?", choices=["heating", "appliances", "general"], default="general")# adds the focus argument

    appointment = subparsers.add_parser("appointment", help="Print an appointment proposal.")# adds the appointment subparser
    appointment.add_argument("customer_id")# adds the customer id argument
    appointment.add_argument("reason")# adds the reason argument
    appointment.add_argument("date")# adds the date argument

    return parser


def render(args: argparse.Namespace) -> str:# renders the parser
    handlers: dict[str, Callable[[argparse.Namespace], str]] = {
        "scenarios": lambda parsed: "\n".join(list_scenarios()),# renders the scenarios
        "context": lambda parsed: customer_context(parsed.customer_id),# renders the context
        "billing": lambda parsed: billing_explanation(parsed.customer_id),# renders the billing
        "insights": lambda parsed: energy_insights(parsed.customer_id),# renders the insights
        "advice": lambda parsed: energy_advice(parsed.customer_id, parsed.focus),# renders the advice
        "appointment": lambda parsed: propose_appointment(parsed.customer_id, parsed.reason, parsed.date),# renders the appointment
    }
    return handlers[args.command](args)# returns the handler for the command


def main(argv: list[str] | None = None) -> int:# the main function
    args = build_parser().parse_args(argv)# parses the arguments
    try:
        text = render(args)# renders the parser
        ok = True
    except CustomerNotFoundError as error:
        text = str(error)
        ok = False

    if args.json:# checks if the json argument is true
        payload = {
            "ok": ok,# indicates success or failure
            "command": args.command,# the command that was executed
            "text": text,# the text that was generated
        }
        if args.command == "scenarios":# checks if the command is scenarios
            payload["scenarios"] = [
                {
                    "id": scenario_id,# the scenario id
                    "title": get_scenario(scenario_id).title,# the scenario title
                    "customer_id": get_scenario(scenario_id).customer_id,# the customer id
                    "query": get_scenario(scenario_id).query,# the scenario query
                }
                for scenario_id in list_scenarios()
            ]
        else:
            payload["customer_id"] = args.customer_id# the customer id
        print(json.dumps(payload, ensure_ascii=False))# prints the payload in json format
    else:
        stream = sys.stdout if ok else sys.stderr# determines the output stream
        print(text, file=stream)# prints the text to the output stream

    return 0 if ok else 1# returns 0 if ok else 1


if __name__ == "__main__":# the main function
    raise SystemExit(main())# raises an error
