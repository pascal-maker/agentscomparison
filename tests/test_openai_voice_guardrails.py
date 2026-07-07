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
