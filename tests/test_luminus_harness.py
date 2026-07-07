import json
import subprocess
import sys

from luminus_harness import (
    billing_explanation,
    customer_context,
    energy_advice,
    propose_appointment,
    get_scenario,
    list_scenarios,
)


def test_customer_context_uses_canonical_fixture() -> None:
    context = customer_context("LUM-1002")

    assert "Account LUM-1002" in context
    assert "Marc" in context
    assert "Dynamic" in context
    assert "208.90" in context


def test_unknown_customer_context_is_explicit() -> None:
    assert customer_context("LUM-9999") == "No Luminus account found for LUM-9999."


def test_billing_explanation_and_advice_are_stable() -> None:
    assert "last bill EUR 142.50" in billing_explanation("LUM-1001")
    assert "standby" in energy_advice("LUM-1001", focus="appliances").lower()


def test_appointment_proposal_requires_approval_language() -> None:
    proposal = propose_appointment("LUM-1003", "smart meter inspection", "2026-08-12")

    assert "APPT-LUM-1003-20260812" in proposal
    assert "Awaiting human approval" in proposal


def test_appointment_proposal_accepts_customer_name() -> None:
    proposal = propose_appointment("Marc", "meter reading", "2026-08-13")

    assert "APPT-LUM-1002-20260813" in proposal
    assert "Marc" in proposal


def test_cli_billing_text_output() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "luminus_harness", "billing", "LUM-1001"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Account LUM-1001" in result.stdout
    assert "last bill EUR 142.50" in result.stdout


def test_cli_context_json_output() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "luminus_harness", "--json", "context", "LUM-1002"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {
        "ok": True,
        "command": "context",
        "customer_id": "LUM-1002",
        "text": customer_context("LUM-1002"),
    }


def test_scenario_registry_exposes_canonical_inputs() -> None:
    scenarios = list_scenarios()

    assert "high_bill" in scenarios
    assert get_scenario("high_bill").customer_id == "LUM-1001"
    assert "unexpectedly high" in get_scenario("high_bill").query


def test_cli_scenarios_json_output() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "luminus_harness", "--json", "scenarios"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "high_bill" in {scenario["id"] for scenario in payload["scenarios"]}
