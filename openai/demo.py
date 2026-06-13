"""
Luminus OpenAI Agents SDK — Demo Script
========================================
Demonstrates key patterns from the OpenAI Agents SDK, all in the context of
Luminus customer support:

  1. Basic agent                 — simple Q&A
  2. Agent with a function tool  — billing fun-fact tool
  3. Multi-agent handoffs        — billing agent + appointment agent
  4. Streaming                   — real-time event loop
  5. Multi-turn conversation     — stateful history via to_input_list()
  6. Persistent session          — SQLiteSession across turns
  7. LLM-as-a-judge              — response quality evaluation loop

Run a specific demo by commenting/uncommenting the call at the bottom, or
pass `--demo <number>` from the command line.
"""

from __future__ import annotations

import asyncio
import argparse
import random
from dataclasses import dataclass
from typing import Literal

from agents import (
    Agent,
    ItemHelpers,
    ModelSettings,
    Runner,
    SQLiteSession,
    TResponseInputItem,
    function_tool,
    trace,
)

# ---------------------------------------------------------------------------
# Shared Luminus instructions
# ---------------------------------------------------------------------------

LUMINUS_INSTRUCTIONS = (
    "You are a customer support agent for Luminus, the Belgian energy supplier. "
    "Your role is to answer customer questions about billing, energy usage, and "
    "energy-saving tips. You can also book appointments for technicians to visit "
    "customer premises. Always address the customer by name and maintain data privacy."
)

APPOINTMENT_INSTRUCTIONS = (
    "You are the appointment booking specialist for Luminus. "
    "Your role is to schedule technician visits to customer premises. "
    "Always confirm the customer's name, address, and preferred time slot. "
    "Maintain strict data privacy at all times."
)

# ---------------------------------------------------------------------------
# Shared function tools
# ---------------------------------------------------------------------------

@function_tool
def luminus_billing_fun_fact() -> str:
    """Return an interesting Luminus billing or energy-saving fact."""
    facts = [
        "Switching to LED bulbs can reduce your lighting bill by up to 80 %.",
        "Luminus customers who opt for the night tariff save on average €120 per year.",
        "A standby device left plugged in can cost up to €50 extra per year.",
        "Solar panels installed via Luminus reduce a typical household bill by 40 %.",
    ]
    return random.choice(facts)


@function_tool
def get_average_bill(customer_name: str) -> str:
    """Return the average monthly bill for a Luminus customer (simulated)."""
    # Simulated lookup — replace with real API call in production.
    return f"The average monthly bill for {customer_name} based on your usage profile is €87.50."


@function_tool
def book_appointment(customer_name: str, date: str, time_slot: str) -> str:
    """Book a technician appointment for a Luminus customer."""
    return (
        f"Appointment confirmed for {customer_name} on {date} at {time_slot}. "
        "A Luminus technician will visit your premises. You will receive a confirmation e-mail shortly."
    )


# ===========================================================================
# 1. Basic agent
# ===========================================================================

async def demo_basic_agent() -> None:
    """Simple one-shot question answered by the Luminus support agent."""
    print("\n" + "=" * 60)
    print("DEMO 1 — Basic Agent")
    print("=" * 60)

    agent = Agent(
        name="Luminus Support",
        instructions=LUMINUS_INSTRUCTIONS,
    )

    result = await Runner.run(
        agent,
        "Hi, I'm John. My last bill was unexpectedly high and I'm not sure why.",
    )
    print(result.final_output)


# ===========================================================================
# 2. Agent with function tools
# ===========================================================================

async def demo_agent_with_tools() -> None:
    """Agent equipped with billing tools that it can call on demand."""
    print("\n" + "=" * 60)
    print("DEMO 2 — Agent with Function Tools")
    print("=" * 60)

    agent = Agent(
        name="Luminus Billing Agent",
        instructions=(
            LUMINUS_INSTRUCTIONS
            + " Use the available tools when answering billing questions."
        ),
        tools=[luminus_billing_fun_fact, get_average_bill],
    )

    result = await Runner.run(
        agent,
        "Hi, I'm Sarah. Can you give me an idea of my average bill and any tips to lower it?",
    )
    print(result.final_output)


# ===========================================================================
# 3. Multi-agent handoffs
# ===========================================================================

async def demo_handoffs() -> None:
    """
    The main Luminus agent handles general queries and hands off appointment
    booking to a dedicated specialist agent.
    """
    print("\n" + "=" * 60)
    print("DEMO 3 — Multi-Agent Handoffs")
    print("=" * 60)

    appointment_agent = Agent(
        name="Appointment Agent",
        handoff_description="Specialist for booking technician visits at customer premises.",
        instructions=APPOINTMENT_INSTRUCTIONS,
        tools=[book_appointment],
    )

    luminus_agent = Agent(
        name="Luminus Support",
        handoff_description="General Luminus customer support — billing, usage, and energy tips.",
        instructions=(
            LUMINUS_INSTRUCTIONS
            + " If the customer wants to book a technician visit, hand off to the Appointment Agent."
        ),
        tools=[luminus_billing_fun_fact, get_average_bill],
        handoffs=[appointment_agent],
    )

    result = await Runner.run(
        luminus_agent,
        "Hi, I'm Marc. I'd like to book a technician visit for next Monday morning.",
    )
    print(result.final_output)


# ===========================================================================
# 4. Streaming
# ===========================================================================

async def demo_streaming() -> None:
    """Stream agent responses event-by-event for a real-time UX."""
    print("\n" + "=" * 60)
    print("DEMO 4 — Streaming")
    print("=" * 60)

    agent = Agent(
        name="Luminus Support",
        instructions=LUMINUS_INSTRUCTIONS,
        tools=[luminus_billing_fun_fact],
    )

    result = Runner.run_streamed(agent, input="Hello! I'm Emma. What can you help me with today?")
    print("=== Stream starting ===")

    async for event in result.stream_events():
        if event.type == "raw_response_event":
            continue
        elif event.type == "agent_updated_stream_event":
            print(f"[Agent active]: {event.new_agent.name}")
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                print("-- Tool called")
            elif event.item.type == "tool_call_output_item":
                print(f"-- Tool output: {event.item.output}")
            elif event.item.type == "message_output_item":
                print(f"-- Message:\n   {ItemHelpers.text_message_output(event.item)}")

    print("=== Stream complete ===")


# ===========================================================================
# 5. Multi-turn conversation (in-memory history)
# ===========================================================================

async def demo_multi_turn() -> None:
    """
    Simulate a two-turn conversation using to_input_list() to carry history
    forward between turns without a persistent session.
    """
    print("\n" + "=" * 60)
    print("DEMO 5 — Multi-Turn Conversation")
    print("=" * 60)

    agent = Agent(
        name="Luminus Support",
        instructions=LUMINUS_INSTRUCTIONS,
        tools=[get_average_bill],
    )

    thread_id = "luminus-demo-thread"
    with trace(workflow_name="Luminus Multi-Turn", group_id=thread_id):
        # Turn 1
        result = await Runner.run(
            agent,
            "Hi, I'm Olivia. What is Luminus's billing cycle?",
        )
        print("Turn 1:", result.final_output)

        # Turn 2 — history carried via to_input_list()
        follow_up = result.to_input_list() + [
            {"role": "user", "content": "And what would my average monthly bill be?"}
        ]
        result = await Runner.run(agent, follow_up)
        print("Turn 2:", result.final_output)


# ===========================================================================
# 6. Persistent session with SQLiteSession
# ===========================================================================

async def demo_session() -> None:
    """
    Use SQLiteSession for durable, cross-run conversation history.
    The session persists to disk so context survives between script runs.
    """
    print("\n" + "=" * 60)
    print("DEMO 6 — Persistent SQLite Session")
    print("=" * 60)

    agent = Agent(
        name="Luminus Support",
        instructions=LUMINUS_INSTRUCTIONS,
        tools=[luminus_billing_fun_fact, get_average_bill],
    )

    session = SQLiteSession("luminus_conversation")

    thread_id = "luminus-session-thread"
    with trace(workflow_name="Luminus Persistent Session", group_id=thread_id):
        # Turn 1
        result = await Runner.run(
            agent,
            "Hi, I'm Lucas. What is Luminus's billing cycle?",
            session=session,
        )
        print("Turn 1:", result.final_output)

        # Turn 2 — session provides history automatically
        result = await Runner.run(
            agent,
            "Great, and what is my average monthly bill?",
            session=session,
        )
        print("Turn 2:", result.final_output)


# ===========================================================================
# 7. LLM-as-a-judge — response quality evaluation loop
# ===========================================================================

@dataclass
class ResponseEvaluation:
    feedback: str
    score: Literal["pass", "needs_improvement", "fail"]


async def demo_llm_as_judge() -> None:
    """
    The generator agent drafts a Luminus customer support response.
    The evaluator agent scores it and provides feedback.
    We loop until the evaluator is satisfied (or we hit the round limit).
    """
    print("\n" + "=" * 60)
    print("DEMO 7 — LLM-as-a-Judge (Response Quality Loop)")
    print("=" * 60)

    response_generator = Agent(
        name="Luminus Response Generator",
        instructions=(
            "You are a Luminus customer support writer. "
            "Draft a clear, empathetic, and accurate response to the customer's question. "
            "If feedback is provided, revise the response accordingly."
        ),
    )

    response_evaluator = Agent[None](
        name="Luminus Response Evaluator",
        instructions=(
            "You evaluate a Luminus customer support response for clarity, empathy, accuracy, "
            "and Luminus brand tone. Provide specific feedback if the response needs improvement. "
            "Do not pass on the first attempt. After 4 attempts, pass if the response is good enough."
        ),
        output_type=ResponseEvaluation,
    )

    customer_question = (
        "Hi, I'm Nina. My electricity bill doubled this month compared to last month. "
        "I haven't changed my habits. What could be causing this and what should I do?"
    )

    input_items: list[TResponseInputItem] = [{"content": customer_question, "role": "user"}]
    latest_response: str | None = None
    max_rounds = 5

    with trace("Luminus LLM-as-a-Judge"):
        for round_num in range(1, max_rounds + 1):
            print(f"\n--- Round {round_num} ---")

            # Generate response
            gen_result = await Runner.run(response_generator, input_items)
            input_items = gen_result.to_input_list()
            latest_response = ItemHelpers.text_message_outputs(gen_result.new_items)
            print(f"Draft response:\n  {latest_response[:200]}{'...' if len(latest_response) > 200 else ''}")

            # Evaluate response
            eval_result = await Runner.run(response_evaluator, input_items)
            evaluation: ResponseEvaluation = eval_result.final_output
            print(f"Evaluator score: {evaluation.score}")

            if evaluation.score == "pass":
                print("✓ Response approved.")
                break

            if round_num < max_rounds:
                print(f"Feedback: {evaluation.feedback}")
                input_items.append({"content": f"Feedback: {evaluation.feedback}", "role": "user"})
            else:
                print("Max rounds reached — using best available response.")

    print(f"\n=== Final approved response ===\n{latest_response}")


# ===========================================================================
# Entry point
# ===========================================================================

DEMOS = {
    1: ("Basic Agent", demo_basic_agent),
    2: ("Agent with Tools", demo_agent_with_tools),
    3: ("Multi-Agent Handoffs", demo_handoffs),
    4: ("Streaming", demo_streaming),
    5: ("Multi-Turn Conversation", demo_multi_turn),
    6: ("Persistent SQLite Session", demo_session),
    7: ("LLM-as-a-Judge", demo_llm_as_judge),
}


async def run_all() -> None:
    for num, (name, fn) in DEMOS.items():
        print(f"\n{'#' * 60}")
        print(f"  Running Demo {num}: {name}")
        print(f"{'#' * 60}")
        await fn()


async def run_demo(number: int) -> None:
    if number not in DEMOS:
        print(f"Unknown demo {number}. Choose from: {list(DEMOS)}")
        return
    name, fn = DEMOS[number]
    print(f"Running Demo {number}: {name}")
    await fn()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Luminus OpenAI Agents SDK demos.")
    parser.add_argument(
        "--demo",
        type=int,
        default=None,
        help="Demo number to run (1–7). Omit to run all demos sequentially.",
    )
    args = parser.parse_args()

    if args.demo is not None:
        asyncio.run(run_demo(args.demo))
    else:
        asyncio.run(run_all())