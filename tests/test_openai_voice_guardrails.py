import importlib.util
import sys
from pathlib import Path

import pytest


def load_demo_module():
    demo_path = Path(__file__).resolve().parents[1] / "openai" / "demo.py"
    spec = importlib.util.spec_from_file_location("openai_demo", demo_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["openai_demo"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_non_energy_guardrail_allows_billing_questions() -> None:
    demo = load_demo_module()

    result = await demo.block_non_energy_questions.guardrail_function(
        None,
        None,
        "Why is my Luminus electricity bill higher this month?",
    )

    assert result.tripwire_triggered is False
    assert result.output_info == {"energy_related": True}


@pytest.mark.asyncio
async def test_non_energy_guardrail_blocks_general_questions() -> None:
    demo = load_demo_module()

    result = await demo.block_non_energy_questions.guardrail_function(None, None, "Who is Kanye West?")

    assert result.tripwire_triggered is True
    assert result.output_info == {"energy_related": False}


@pytest.mark.asyncio
async def test_competitor_guardrail_still_blocks_competitor_questions() -> None:
    demo = load_demo_module()

    result = await demo.block_competitor_questions.guardrail_function(None, None, "Compare Luminus with Engie.")

    assert result.tripwire_triggered is True
    assert result.output_info == {"competitor_detected": True}


@pytest.mark.asyncio
async def test_voice_workflow_refuses_unrelated_current_turn_despite_energy_history(monkeypatch):
    from unittest.mock import AsyncMock
    demo = load_demo_module()
    agent = demo.create_energy_voice_agent()
    workflow = demo.ConsoleVoiceWorkflow(agent)
    workflow._input_history = [{"role": "user", "content": "Explain my electricity bill"}]
    runner = AsyncMock(side_effect=AssertionError("Unrelated input must not reach Runner"))
    monkeypatch.setattr(demo.Runner, "run", runner)
    answers = [answer async for answer in workflow.run("Who is Kanye West?")]
    assert answers == [demo.ENERGY_TOPIC_REFUSAL]
    assert len(workflow._input_history) == 1
    runner.assert_not_awaited()
    assert "Leveranciers vergelijken is toegestaan" in agent.instructions


@pytest.mark.asyncio
async def test_voice_workflow_allows_supplier_comparison_and_speaks_only_final_output(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    demo = load_demo_module()
    agent = demo.create_energy_voice_agent()
    workflow = demo.ConsoleVoiceWorkflow(agent)
    result = SimpleNamespace(final_output="Geef je postcode.", last_agent=agent, to_input_list=lambda: [])
    runner = AsyncMock(return_value=result)
    monkeypatch.setattr(demo.Runner, "run", runner)
    assert [answer async for answer in workflow.run("Vergelijk Luminus en Engie energiecontracten")] == ["Geef je postcode."]
    assert runner.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("question,pending,allowed", [
    ("9000", "postcode", True), ("Vlaanderen", "region", True),
    ("3500", "annual_consumption_kwh", True), ("nee", "is_prosumer", True),
    ("digitale meter", "meter_technology", True),
    ("Who is Kanye West? 9000", "postcode", False),
    ("Vlaanderen, who is Kanye West?", "region", False),
])
async def test_voice_short_answers_only_bypass_boundary_for_pending_comparison(monkeypatch, question, pending, allowed):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from luminus_harness.comparison_session import FIELDS, EXTRA_FIELDS
    demo = load_demo_module()
    workflow = demo.ConsoleVoiceWorkflow(demo.create_energy_voice_agent())
    store = workflow.comparison_context.comparisons
    token = (await store.submit({}, None))["comparison_session_id"]
    workflow.comparison_context.session_id = token
    state = store.sessions[token]
    complete = dict(region="flanders", postcode="9000", energy_type="electricity", annual_consumption_kwh=3500)
    state.inputs = {key: value for key, value in complete.items() if key != pending}
    if pending in EXTRA_FIELDS:
        state.required_fields = (pending,)
    # Restrict the test to the actual requested primary field.
    if pending in FIELDS:
        state.inputs = {name: complete[name] for name in FIELDS[:FIELDS.index(pending)]}
    runner = AsyncMock(return_value=SimpleNamespace(final_output="Vervolgantwoord", last_agent=workflow._current_agent, to_input_list=lambda: []))
    monkeypatch.setattr(demo.Runner, "run", runner)
    answers = [answer async for answer in workflow.run(question)]
    assert answers == (["Vervolgantwoord"] if allowed else [demo.ENERGY_TOPIC_REFUSAL])
    assert runner.await_count == int(allowed)
    store.discard(token)


@pytest.mark.asyncio
async def test_comparison_tool_schema_forwards_followups_and_prevents_same_turn_retry(monkeypatch):
    import json
    from luminus_harness import comparison_session as comparison
    from unittest.mock import AsyncMock
    from agents import RunContextWrapper
    demo = load_demo_module()
    state = demo.VoiceComparisonContext()
    ctx = RunContextWrapper(state)
    required = json.dumps({"status": "needs_input", "offers": [], "notes": [],
                           "required_information": ["prosumentstatus"], "required_fields": ["is_prosumer"]})
    success = json.dumps({"status": "success", "offers": [{"supplier": "Test", "product": "Variabel",
                            "estimated_annual_cost_eur": 1200, "source_url": "https://www.compacwape.be/results"}],
                          "checked_at_utc": "2026-09-28T12:00:00+00:00", "notes": []})
    lookup = AsyncMock(side_effect=[required, success])
    monkeypatch.setattr(comparison, "compare_energy_offers", lookup)
    tool = demo.compare_energy_providers
    for field in comparison.EXTRA_FIELDS:
        assert field in tool.params_json_schema["properties"]
    async def invoke(**supplied):
        # Exercise the SDK's actual JSON schema and wrapper, including false/zero.
        params = {name: None for name in tool.params_json_schema["properties"]}
        params.update(supplied)
        tool_ctx = ctx
        try:
            from agents.tool_context import ToolContext
            tool_ctx = ToolContext.from_agent_context(ctx, tool_call_id="mock-call", tool_name=tool.name,
                                                     tool_arguments=json.dumps(params))
        except ImportError:  # The deployed SDK 0.2 uses RunContextWrapper directly.
            pass
        return await tool.on_invoke_tool(tool_ctx, json.dumps(params))
    reply = json.loads(await invoke(region="flanders", postcode="9000", energy_type="electricity", annual_consumption_kwh=3500))
    assert reply["comparison_status"] == "collecting"
    await invoke(is_prosumer=False)
    assert lookup.await_count == 1
    state.calls_this_turn = 0
    reply = json.loads(await invoke(is_prosumer=False, meter_type="dual_rate", meter_technology="digital",
                                    annual_day_consumption_kwh=3500, annual_night_consumption_kwh=0))
    assert reply["comparison_status"] == "success"
    assert lookup.await_args.kwargs["is_prosumer"] is False
    assert lookup.await_args.kwargs["annual_night_consumption_kwh"] == 0
    assert lookup.await_args.kwargs["meter_type"] == "dual_rate"
    state.calls_this_turn = 0
    assert json.loads(await invoke(is_prosumer=False))["comparison_status"] == "expired"
    assert lookup.await_count == 2


def test_openai_demo_help_imports_without_credentials():
    import os
    import subprocess
    root = Path(__file__).resolve().parents[1]
    env = {key: value for key, value in os.environ.items() if key not in {"OPENAI_API_KEY", "BROWSER_USE_API_KEY", "BROWSERBASE_API_KEY"}}
    env["PYTHON_DOTENV_DISABLED"] = "1"
    result = subprocess.run([sys.executable, str(root / "openai" / "demo.py"), "--help"],
                            cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--demo" in result.stdout
