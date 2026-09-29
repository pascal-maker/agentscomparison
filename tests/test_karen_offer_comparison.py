import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from luminus_harness import comparison_session as comparison
from luminus_harness.rate_limit import SlidingWindowRateLimiter


def result(status="success"):
    return json.dumps({
        "status": status,
        "checked_at_utc": "2026-09-28T12:00:00+00:00",
        "offers": [{"supplier": f"Leverancier {i}", "product": "Variabel",
                    "estimated_annual_cost_eur": 1200.50 + i,
                    "source_url": "https://www.compacwape.be/results"} for i in range(4)],
        "notes": ["De vergelijker is tijdelijk niet beschikbaar."] if status == "unavailable" else [],
        "required_information": ["metertype", "dag/nacht-verbruik"],
    })


@pytest.fixture
def api(monkeypatch):
    import energy_voice_app as app

    monkeypatch.setattr(app, "_comparison_sessions", comparison.ComparisonSessions())
    monkeypatch.setattr(app, "_api_rate_limiter", SlidingWindowRateLimiter(requests=100, window_seconds=60, max_clients=100))
    monkeypatch.setattr(app, "_upload_sessions", {})
    lookup = AsyncMock(return_value=result())
    monkeypatch.setattr(comparison, "compare_energy_offers", lookup)
    hosted = AsyncMock(side_effect=AssertionError("Comparison/PDF must not reach Gemma or CREG"))
    monkeypatch.setattr(app, "answer_energy_question", hosted)
    with TestClient(app.api_app) as client:
        yield client, app, lookup, hosted
    for key in list(app._comparison_sessions.sessions):
        app._comparison_sessions.discard(key)


def ask(api, question, session=None, **extra):
    response = api[0].post("/api/answer", json={"question": question, "comparison_session_id": session, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_request_uses_exact_inputs_and_up_to_three_displayed_prices(api):
    reply = ask(api, "Vergelijk aanbiedingen in Wallonië, postcode 5000, gas, jaarlijks 15.000 kWh")
    api[2].assert_awaited_once_with(region="wallonia", postcode="5000", energy_type="gas", annual_consumption_kwh=15000)
    assert reply["comparison_status"] == "success"
    assert reply["comparison_session_id"] is None
    assert "€ 1.200,50 per jaar" in reply["answer"]
    assert "28-09-2026 om 14:00 CEST" in reply["answer"]
    assert len(reply["sources"]) == 3
    assert "Leverancier 3" not in reply["answer"]
    assert reply["live_source_status"] == "checked"
    assert not api[1]._comparison_sessions.sessions
    api[3].assert_not_awaited()


def test_compound_energy_name_and_labelled_prosumer_answer_are_forwarded(api):
    reply = ask(api, "Vergelijk elektriciteitsaanbiedingen in Vlaanderen voor postcode 9000 en "
                     "3500 kWh per jaar. Digitale meter, enkelvoudig tarief, prosument: nee.")
    assert reply["comparison_status"] == "success"
    api[2].assert_awaited_once_with(region="flanders", postcode="9000", energy_type="electricity",
                                    annual_consumption_kwh=3500, meter_type="single_rate",
                                    meter_technology="digital", is_prosumer=False)


def test_missing_details_across_turns_and_state_contains_no_conversation(api):
    reply = ask(api, "Vergelijk energieaanbiedingen")
    token = reply["comparison_session_id"]
    assert "gewest" in reply["answer"]
    for question, missing in (("Vlaanderen", "postcode"), ("9000", "energy_type"), ("elektriciteit", "annual_consumption_kwh")):
        reply = ask(api, question, token)
        assert reply["comparison_session_id"] == token
        assert reply["required_information"][0] == missing
        api[2].assert_not_awaited()
    state = api[1]._comparison_sessions.sessions[token]
    assert state.inputs == {"region": "flanders", "postcode": "9000", "energy_type": "electricity"}
    assert set(vars(state)) == {"inputs", "expires_at", "required_fields", "in_flight"}
    ask(api, "3500", token)
    api[2].assert_awaited_once_with(region="flanders", postcode="9000", energy_type="electricity", annual_consumption_kwh=3500)
    assert not api[1]._comparison_sessions.sessions
    assert ask(api, "3500", token)["comparison_status"] == "expired"
    assert api[2].await_count == 1


@pytest.mark.parametrize("question,missing", [
    ("Vergelijk elektriciteit, postcode 9000, 3500 kWh", "region"),
    ("Vergelijk in Vlaanderen elektriciteit, 3500 kWh", "postcode"),
    ("Vergelijk in Vlaanderen, postcode 9000, 3500 kWh", "energy_type"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen en Brussel, postcode 9000, gas, 3500 kWh", "region"),
    ("Vergelijk niet in Vlaanderen, postcode 9000, gas, 3500 kWh", "region"),
    ("Vergelijk in Vlaanderen, postcode 900, gas, 3500 kWh", "postcode"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas en elektriciteit, 3500 kWh", "energy_type"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, -3500 kWh", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, 0 kWh", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, 300 kWh per maand", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, maandelijks 300 kWh", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, 3500 kWh", "annual_consumption_kwh"),
    ("Vergelijk in Vlaanderen, postcode 9000, gas, 1500 kWh dag en 2000 kWh nacht", "annual_consumption_kwh"),
])
def test_never_infers_missing_or_ambiguous_details(api, question, missing):
    reply = ask(api, question)
    assert reply["comparison_status"] == "collecting"
    assert reply["required_information"][0] == missing
    api[2].assert_not_awaited()
    api[3].assert_not_awaited()


def test_independent_sessions_expiry_and_unknown_id(api):
    first = ask(api, "Vergelijk elektriciteit in Vlaanderen, jaarlijks 3500 kWh")
    second = ask(api, "Vergelijk gas in Brussel, jaarlijks 12000 kWh")
    assert first["comparison_session_id"] != second["comparison_session_id"]
    first_id = first["comparison_session_id"]
    api[1]._comparison_sessions.sessions[first_id].expires_at = 0
    assert ask(api, "9000", first_id)["comparison_status"] == "expired"
    assert first_id not in api[1]._comparison_sessions.sessions
    ask(api, "postcode 1000", second["comparison_session_id"])
    api[2].assert_awaited_once_with(region="brussels", postcode="1000", energy_type="gas", annual_consumption_kwh=12000)
    assert ask(api, "Vlaanderen", "unknown-session-id")["comparison_status"] == "expired"


@pytest.mark.asyncio
async def test_expiry_removes_inputs_without_another_request(monkeypatch):
    monkeypatch.setattr(comparison, "SESSION_TTL_SECONDS", 0.02)
    store = comparison.ComparisonSessions()
    reply = await store.answer("Vergelijk gas in Brussel", None)
    assert reply["comparison_session_id"] in store.sessions
    await asyncio.sleep(0.05)
    assert not store.sessions
    assert not store._expiry_handles


def test_storage_is_bounded_and_does_not_extend_deadline(api, monkeypatch):
    monkeypatch.setattr(comparison, "MAX_SESSIONS", 2)
    first = ask(api, "Vergelijk aanbiedingen")["comparison_session_id"]
    expires = api[1]._comparison_sessions.sessions[first].expires_at
    ask(api, "Vlaanderen", first)
    assert api[1]._comparison_sessions.sessions[first].expires_at == expires
    ask(api, "Vergelijk gas")
    ask(api, "Vergelijk elektriciteit")
    assert len(api[1]._comparison_sessions.sessions) == 2
    assert first not in api[1]._comparison_sessions.sessions


@pytest.mark.parametrize("raw,status", [(result("unavailable"), "unavailable"),
                                          ("Live comparison is not configured. Set BROWSER_USE_API_KEY", "failed"),
                                          ("not JSON", "failed"), ("{}", "failed")])
def test_failure_and_extra_information_never_present_prices(api, raw, status):
    api[2].return_value = raw
    reply = ask(api, "Vergelijk gas in Wallonië, 5000, jaarlijks 15000 kWh")
    assert reply["comparison_status"] == status
    assert reply["comparison_session_id"] is None
    assert "geen jaarprijzen bevestigd" in reply["answer"]
    assert "€" not in reply["answer"]
    assert "BROWSER_USE_API_KEY" not in reply["answer"]
    assert not reply["sources"]
    assert reply["suggested_sources"][0]["url"] == comparison.COMPARATORS["wallonia"].url
    assert not api[1]._comparison_sessions.sessions


def test_raised_comparator_error_is_safe_and_consumes_session(api):
    api[2].side_effect = RuntimeError("private debug response")
    reply = ask(api, "Vergelijk gas in Brussel, postcode 1000, jaarlijks 12000 kWh")
    assert reply["comparison_status"] == "failed"
    assert "private debug" not in reply["answer"]
    assert not api[1]._comparison_sessions.sessions


@pytest.mark.parametrize("change", [
    {"estimated_annual_cost_eur": -1}, {"estimated_annual_cost_eur": True},
    {"estimated_annual_cost_eur": float("nan")}, {"source_url": "http://example.com"},
    {"source_url": "javascript:alert(1)"}, {"supplier": ""},
])
def test_malformed_offers_do_not_become_confirmed_prices(api, change):
    payload = json.loads(result())
    payload["offers"][0].update(change)
    api[2].return_value = json.dumps(payload)
    reply = ask(api, "Vergelijk gas in Brussel, postcode 1000, jaarlijks 12000 kWh")
    assert reply["comparison_status"] == "failed"
    assert "€" not in reply["answer"]
    assert not reply["sources"]


def test_bare_number_is_not_inferred_outside_the_requested_field(api):
    token = ask(api, "Vergelijk aanbiedingen")["comparison_session_id"]
    reply = ask(api, "3500", token)
    assert reply["required_information"] == list(comparison.FIELDS)
    assert api[1]._comparison_sessions.sessions[token].inputs == {}


def test_ordinary_creg_question_clears_expired_token_and_keeps_its_route(api):
    api[3].side_effect = None
    api[3].return_value = {"answer": "Bestaand CREG-antwoord", "sources": []}
    token = ask(api, "Vergelijk gas")["comparison_session_id"]
    api[1]._comparison_sessions.sessions[token].expires_at = 0
    reply = ask(api, "Wat is de elektriciteitsprijs volgens CREG?", token)
    assert reply["answer"] == "Bestaand CREG-antwoord"
    assert reply["comparison_session_id"] is None
    api[2].assert_not_awaited()


@pytest.mark.parametrize("question", ["Wat is de huidige elektriciteitsprijs volgens CREG?", "Waarom verschilt mijn voorschot van mijn jaarafrekening?"])
def test_ordinary_public_questions_keep_existing_route_even_mid_comparison(api, question):
    api[3].side_effect = None
    api[3].return_value = {"answer": "Bestaand publiek antwoord", "sources": []}
    token = ask(api, "Vergelijk gas")["comparison_session_id"]
    reply = ask(api, question, token)
    assert reply["answer"] == "Bestaand publiek antwoord"
    assert reply["comparison_session_id"] == token
    assert api[1]._comparison_sessions.sessions[token].inputs == {"energy_type": "gas"}
    api[2].assert_not_awaited()
    assert api[3].await_args.args[0] == question


def test_pdf_questions_stay_local_and_pdf_comparison_is_blocked(api, monkeypatch):
    pdf_id = "synthetic-pdf-session"
    monkeypatch.setattr(api[1], "_get_upload_session", lambda key: {"chunks": ["PRIVATE PDF TEXT"], "filename": "bill.pdf"})
    calls = []
    def local_answer(question, chunks):
        calls.append((question, chunks))
        return {"answer": "Lokaal PDF-antwoord", "sources": []}
    monkeypatch.setattr(api[1], "answer_uploaded_pdf_question", local_answer)
    token = ask(api, "Vergelijk gas")["comparison_session_id"]
    blocked = ask(api, "Vergelijk gas in Brussel postcode 1000 12000 kWh", token, session_id=pdf_id)
    assert blocked["comparison_status"] == "pdf-blocked"
    assert "Verwijder eerst je PDF" in blocked["answer"]
    assert token not in api[1]._comparison_sessions.sessions
    assert not calls
    blocked = ask(api, "Vergelijk elektriciteit", session_id="expired-pdf-session")
    assert blocked["comparison_status"] == "pdf-blocked"
    reply = ask(api, "Wat staat er over voorschotten?", session_id=pdf_id)
    assert reply["processing"] == "local-only"
    assert calls[0][1] == ["PRIVATE PDF TEXT"]
    api[2].assert_not_awaited()
    api[3].assert_not_awaited()


def test_cancellation_and_delete_clear_only_comparison_inputs(api):
    token = ask(api, "Vergelijk gas")["comparison_session_id"]
    assert ask(api, "annuleer", token)["comparison_status"] == "cancelled"
    token = ask(api, "Vergelijk gas")["comparison_session_id"]
    assert api[0].delete(f"/api/comparison-session/{token}").status_code == 200
    assert not api[1]._comparison_sessions.sessions
    api[2].assert_not_awaited()


COMPLETE = "Vergelijk elektriciteit in Vlaanderen, postcode 9000, jaarlijks 3500 kWh"


def needs(*fields):
    return json.dumps({"status": "needs_input", "offers": [], "notes": [],
                       "required_fields": list(fields), "required_information": list(fields)})


def test_comparator_followups_are_collected_and_forwarded_without_extra_calls(api):
    api[2].side_effect = [needs("meter_type", "meter_technology", "annual_day_consumption_kwh",
                                 "annual_night_consumption_kwh", "is_prosumer"), result()]
    reply = ask(api, COMPLETE)
    token = reply["comparison_session_id"]
    state = api[1]._comparison_sessions.sessions[token]
    expires = state.expires_at
    assert reply["comparison_status"] == "collecting"
    assert "geen jaarprijzen bevestigd" in reply["answer"]
    for answer in ("ik weet het niet", "tweevoudige meter", "digitaal", "1500", "2000"):
        reply = ask(api, answer, token)
        assert reply["comparison_status"] == "collecting"
        assert reply["comparison_session_id"] == token
        assert api[2].await_count == 1
        assert state.expires_at == expires
    assert state.inputs["annual_consumption_kwh"] == 3500
    assert state.required_fields == ("meter_type", "meter_technology", "annual_day_consumption_kwh",
                                     "annual_night_consumption_kwh", "is_prosumer")
    assert set(vars(state)) == {"inputs", "expires_at", "required_fields", "in_flight"}
    reply = ask(api, "nee", token)
    assert reply["comparison_status"] == "success"
    api[2].assert_awaited_with(region="flanders", postcode="9000", energy_type="electricity",
                              annual_consumption_kwh=3500, meter_type="dual_rate", meter_technology="digital",
                              annual_day_consumption_kwh=1500, annual_night_consumption_kwh=2000, is_prosumer=False)
    assert not api[1]._comparison_sessions.sessions
    assert ask(api, "nee", token)["comparison_status"] == "expired"
    assert api[2].await_count == 2


def test_legacy_requested_fields_and_zero_consumption_are_supported(api):
    api[2].side_effect = [result("needs_input"), result()]
    token = ask(api, COMPLETE)["comparison_session_id"]
    ask(api, "tweevoudig", token)
    ask(api, "dag 3500 kWh", token)
    reply = ask(api, "nacht 0 kWh", token)
    assert reply["comparison_status"] == "success"
    assert api[2].await_args.kwargs["annual_night_consumption_kwh"] == 0


def test_inconsistent_and_monthly_splits_do_not_repeat_lookup(api):
    api[2].side_effect = [needs("annual_day_consumption_kwh", "annual_night_consumption_kwh"), result()]
    token = ask(api, COMPLETE)["comparison_session_id"]
    assert ask(api, "dag 100 kWh per maand", token)["comparison_status"] == "collecting"
    ask(api, "dag 1500 kWh", token)
    reply = ask(api, "nacht 1000 kWh", token)
    assert "wijkt af" in reply["answer"]
    assert api[2].await_count == 1
    assert "annual_consumption_kwh" in api[1]._comparison_sessions.sessions[token].inputs
    ask(api, "1500", token)
    assert ask(api, "2000", token)["comparison_status"] == "success"


@pytest.mark.parametrize("fields", [("onbekend veld",), (), ("meter_type", "unknown")])
def test_unsupported_requirements_close_without_retry(api, fields):
    api[2].return_value = needs(*fields)
    reply = ask(api, COMPLETE)
    assert reply["comparison_status"] == "needs_input"
    assert reply["comparison_session_id"] is None
    assert reply["suggested_sources"]
    assert not reply["sources"]
    assert not api[1]._comparison_sessions.sessions
    assert api[2].await_count == 1


def test_repeated_requirement_for_already_supplied_field_closes(api):
    api[2].side_effect = [needs("meter_type"), needs("meter_type")]
    token = ask(api, COMPLETE)["comparison_session_id"]
    reply = ask(api, "enkelvoudig", token)
    assert reply["comparison_status"] == "needs_input"
    assert reply["comparison_session_id"] is None
    assert ask(api, "enkelvoudig", token)["comparison_status"] == "expired"
    assert api[2].await_count == 2


def test_extra_input_sessions_remain_isolated_and_expire(api):
    api[2].return_value = needs("meter_type")
    first = ask(api, COMPLETE)["comparison_session_id"]
    second = ask(api, COMPLETE)["comparison_session_id"]
    api[1]._comparison_sessions.sessions[first].expires_at = 0
    assert ask(api, "enkelvoudig", first)["comparison_status"] == "expired"
    assert api[1]._comparison_sessions.sessions[second].required_fields == ("meter_type",)
    assert "meter_type" not in api[1]._comparison_sessions.sessions[second].inputs
    assert api[2].await_count == 2


@pytest.mark.asyncio
async def test_concurrent_followup_cannot_repeat_lookup_and_cancel_does_not_restore_state(monkeypatch):
    store = comparison.ComparisonSessions()
    lookup = AsyncMock(return_value=needs("meter_type"))
    monkeypatch.setattr(comparison, "compare_energy_offers", lookup)
    token = (await store.answer(COMPLETE, None))["comparison_session_id"]
    started, release = asyncio.Event(), asyncio.Event()
    async def waiting(**inputs):
        started.set()
        await release.wait()
        return needs("is_prosumer")
    lookup.side_effect = waiting
    task = asyncio.create_task(store.answer("enkelvoudig", token))
    await started.wait()
    duplicate = await store.answer("enkelvoudig", token)
    assert duplicate["comparison_status"] == "running"
    assert lookup.await_count == 2
    await store.answer("annuleer", token)
    release.set()
    assert (await task)["comparison_status"] == "expired"
    assert not store.sessions


def test_pdf_blocks_pending_extra_inputs(api, monkeypatch):
    api[2].return_value = needs("is_prosumer")
    token = ask(api, COMPLETE)["comparison_session_id"]
    reply = ask(api, "nee", token, session_id="synthetic-pdf-session")
    assert reply["comparison_status"] == "pdf-blocked"
    assert api[2].await_count == 1
    assert not api[1]._comparison_sessions.sessions



def test_new_explicit_request_does_not_reuse_old_extra_input_session(api):
    api[2].side_effect = [needs("meter_type"), result()]
    token = ask(api, COMPLETE)["comparison_session_id"]
    reply = ask(api, "Vergelijk gas in Brussel, postcode 1000, jaarlijks 12000 kWh", token)
    assert reply["comparison_status"] == "success"
    assert token not in api[1]._comparison_sessions.sessions
    api[2].assert_awaited_with(region="brussels", postcode="1000", energy_type="gas", annual_consumption_kwh=12000)


def test_ambiguous_meter_and_unprompted_split_are_not_inferred(api):
    api[2].return_value = needs("meter_type", "annual_day_consumption_kwh", "annual_night_consumption_kwh")
    token = ask(api, COMPLETE)["comparison_session_id"]
    reply = ask(api, "enkelvoudig of tweevoudig, dag 1500 kWh en nacht 2000 kWh", token)
    state = api[1]._comparison_sessions.sessions[token]
    assert reply["required_information"][0] == "meter_type"
    assert "meter_type" not in state.inputs
    assert "annual_day_consumption_kwh" not in state.inputs
    assert "annual_night_consumption_kwh" not in state.inputs
    assert api[2].await_count == 1
