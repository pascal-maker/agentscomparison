import json
import subprocess
import sys

import pytest

from luminus_harness import (
    CustomerNotFoundError,
    billing_explanation,
    customer_context,
    energy_advice,
    energy_insights,
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
    with pytest.raises(CustomerNotFoundError, match="LUM-9999"):
        customer_context("LUM-9999")


def test_every_customer_tool_fails_the_same_way_for_an_unknown_customer() -> None:
    for tool in (
        lambda: customer_context("LUM-9999"),
        lambda: billing_explanation("LUM-9999"),
        lambda: energy_insights("LUM-9999"),
        lambda: energy_advice("LUM-9999"),
        lambda: propose_appointment("LUM-9999", "inspection", "2026-08-12"),
    ):
        with pytest.raises(CustomerNotFoundError, match="LUM-9999"):
            tool()


def test_demo_narratives_are_not_mistaken_for_account_specific_data() -> None:
    # The canned narrative sentence is identical for every customer; only the
    # genuine Customer fields around it should differ between accounts.
    import luminus_harness.core as core

    assert core.DEMO_USAGE_NARRATIVE in customer_context("LUM-1001")
    assert core.DEMO_USAGE_NARRATIVE in customer_context("LUM-1002")


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


def test_cli_unknown_customer_reports_error_and_exit_code() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "luminus_harness", "billing", "LUM-9999"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "No Luminus account found for LUM-9999" in result.stderr


def test_cli_unknown_customer_json_output_is_explicit() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "luminus_harness", "--json", "context", "LUM-9999"],
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "No Luminus account found for LUM-9999" in payload["text"]
    assert result.returncode == 1


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


def test_unknown_scenario_is_explicit() -> None:
    with pytest.raises(ValueError, match="Unknown scenario"):
        get_scenario("does_not_exist")


def test_customer_lookup_is_case_insensitive() -> None:
    # Both an ID (get_customer uppercases it) and a bare name (find_customer
    # lowercases both sides) resolve regardless of case.
    assert "Marc" in billing_explanation("lum-1002")
    assert "Marc" in billing_explanation("marc")


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
