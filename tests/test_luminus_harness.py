from luminus_harness import (
    billing_explanation,
    customer_context,
    energy_advice,
    propose_appointment,
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
