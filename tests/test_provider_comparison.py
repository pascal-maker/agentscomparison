import json
from types import SimpleNamespace
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
    assert "separate Search input inside the opened dropdown" in payload["task"]
    assert "not JavaScript that mutates form values" in payload["task"]
    assert "never default to variable" in payload["task"]
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


def test_assumed_prosumer_status_never_returns_offers():
    result = provider._validate_result({
        "status": "success", "offers": [{"supplier": "Example", "product": "Tariff",
                                         "estimated_annual_cost_eur": 999, "source_url": "https://www.vtest.be/"}],
        "notes": ["Er is uitgegaan van de veronderstelling dat er geen zonnepanelen zijn."],
        "required_information": [],
    }, "flanders", "electricity", 3500)
    assert result["status"] == "needs_input"
    assert result["offers"] == []
    assert result["required_fields"] == ["is_prosumer"]


def test_flemish_task_targets_live_select2_postcode_search():
    task = provider._build_task(comparator=provider.COMPARATORS["flanders"], **BASE)
    assert provider.COMPARATORS["flanders"].url == "https://www.vtest.be/"
    assert "separate Search input inside the opened dropdown" in task
    assert "verify the collapsed field shows 9000" in task
    assert "there is no Next button here" in task
    assert "click 'Ik ken mijn verbruik'" in task
    assert "If the form defaults a missing meter detail" in task
    assert "# used to" not in task


@pytest.mark.asyncio
async def test_vtest_requires_explicit_meter_answers_before_paid_lookup(monkeypatch):
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")
    monkeypatch.setattr(provider, "_run_browser_use_lookup", lambda **_kwargs: pytest.fail("Paid lookup started"))

    first = json.loads(await provider.compare_energy_offers(**BASE))
    assert first["status"] == "needs_input"
    assert first["required_fields"] == ["meter_technology", "meter_type", "is_prosumer"]

    dual = json.loads(await provider.compare_energy_offers(
        **BASE, meter_technology="digital", meter_type="dual_rate", is_prosumer=False,
    ))
    assert dual["required_fields"] == ["annual_day_consumption_kwh", "annual_night_consumption_kwh"]


def test_success_requires_official_comparator_source():
    with pytest.raises(RuntimeError, match="official comparator source"):
        provider._validate_result({
            "status": "success", "offers": [{"supplier": "Example", "product": "Tariff",
                                             "estimated_annual_cost_eur": 999,
                                             "source_url": "https://example.com/offer"}],
            "notes": [], "required_information": [],
        }, "flanders", "electricity", 3500)


@pytest.mark.parametrize("source_url", [
    "https://brugel.brusim.be/nl/",
    "https://app.brusim.be/nl-BE/customer?theme=light",
])
def test_brussels_official_brusim_hosts_are_accepted(source_url):
    result = provider._validate_result({
        "status": "success", "offers": [{"supplier": "Example", "product": "Gas",
                                         "estimated_annual_cost_eur": 100,
                                         "source_url": source_url}],
        "notes": [], "required_information": [],
    }, "brussels", "gas", 200)
    assert result["offers"][0]["source_url"] == source_url


def test_brusim_lookalike_host_is_rejected():
    with pytest.raises(RuntimeError, match="official comparator source"):
        provider._validate_result({
            "status": "success", "offers": [{"supplier": "Example", "product": "Gas",
                                             "estimated_annual_cost_eur": 100,
                                             "source_url": "https://app.brusim.be.evil.example/offer"}],
            "notes": [], "required_information": [],
        }, "brussels", "gas", 200)


def test_local_timeout_stops_remote_session(monkeypatch):
    requests = []
    def request(method, url, key, payload=None):
        requests.append((method, url, payload))
        if url.endswith("/stop"):
            return {"status": "stopped", "totalCostUsd": "0.40"}
        if method == "POST":
            return {"id": "mock-session"}
        return {"status": "running"}
    monkeypatch.setattr(provider, "_request_json", request)
    monkeypatch.setattr(provider, "time", SimpleNamespace(monotonic=Mock(side_effect=[0, 211]),
                                                           sleep=Mock()))
    with pytest.raises(RuntimeError, match="Local wait limit"):
        provider._run_browser_use_lookup(api_key="test-only-placeholder", max_cost_usd=1.0, **BASE)
    assert [(method, url.rsplit("/", 1)[-1]) for method, url, _ in requests] == [
        ("POST", "sessions"), ("GET", "mock-session"), ("POST", "stop")]
    assert requests[-1][2] == {"strategy": "session"}
