import json
from unittest.mock import Mock

import pytest

from luminus_harness import provider_comparison as provider


BASE = dict(region="flanders", postcode="9000", energy_type="electricity", annual_consumption_kwh=3500)


@pytest.mark.asyncio
async def test_optional_inputs_reach_browser_use_payload_with_existing_cost_cap(monkeypatch):
    requests = []
    def request(method, url, key, payload=None):
        requests.append((method, payload))
        if method == "POST":
            return {"id": "mock-session"}
        return {"status": "stopped", "isTaskSuccessful": True, "output": {
            "status": "needs_input", "offers": [], "notes": [],
            "required_information": ["metertechnologie"], "required_fields": ["meter_technology"],
        }}
    monkeypatch.setattr(provider, "_request_json", request)
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-only-placeholder")
    monkeypatch.delenv("BROWSER_USE_MAX_COST_USD", raising=False)
    reply = await provider.compare_energy_offers(**BASE, meter_type="dual_rate", meter_technology="digital",
                                               annual_day_consumption_kwh=3500, annual_night_consumption_kwh=0,
                                               is_prosumer=False)
    assert json.loads(reply)["status"] == "needs_input"
    payload = requests[0][1]
    assert payload["maxCostUsd"] == 1.0
    assert '"is_prosumer": false' in payload["task"]
    assert '"annual_night_consumption_kwh": 0' in payload["task"]
    assert '"meter_type": "dual_rate"' in payload["task"]
    assert '"meter_technology": "digital"' in payload["task"]
    assert provider.COMPARATORS["flanders"].url in payload["task"]
    assert payload["outputSchema"]["properties"]["required_fields"]["items"]["enum"] == list(provider.EXTRA_FIELDS)
    assert [method for method, _ in requests] == ["POST", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [
    {"annual_day_consumption_kwh": 4000}, {"annual_night_consumption_kwh": 4000},
    {"annual_day_consumption_kwh": -1}, {"annual_night_consumption_kwh": float("nan")},
    {"annual_day_consumption_kwh": True}, {"is_prosumer": "no"}, {"meter_type": "unknown"},
    {"meter_technology": "unknown"}, {"annual_day_consumption_kwh": 1000, "annual_night_consumption_kwh": 1000},
])
async def test_invalid_optional_inputs_do_not_contact_browser_use(monkeypatch, extra):
    lookup = Mock(side_effect=AssertionError("No network allowed"))
    monkeypatch.setattr(provider, "_run_browser_use_lookup", lookup)
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-only-placeholder")
    reply = await provider.compare_energy_offers(**BASE, **extra)
    assert reply
    lookup.assert_not_called()
