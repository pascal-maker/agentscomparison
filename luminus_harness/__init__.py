"""Luminus demo modules with lazy exports for the legacy benchmark fixture."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_CORE_EXPORTS = {
    "APPOINTMENT_INSTRUCTIONS",
    "LUMINUS_INSTRUCTIONS",
    "SAVING_TIPS",
    "Customer",
    "Scenario",
    "billing_explanation",
    "customer_context",
    "energy_advice",
    "energy_insights",
    "find_customer",
    "get_customer",
    "get_scenario",
    "list_scenarios",
    "luminus_fact",
    "propose_appointment",
}

__all__ = sorted(_CORE_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _CORE_EXPORTS:
        return getattr(import_module(".core", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
