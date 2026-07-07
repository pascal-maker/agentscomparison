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
  8. Agents as tools             — manager orchestrates specialist sub-agents
  9. Guardrails                  — input guardrail blocks competitor questions
 10. Human in the loop           — approval gate for sensitive energy actions

Run a specific demo by commenting/uncommenting the call at the bottom, or
pass `--demo <number>` from the command line.
"""

from __future__ import annotations

import asyncio
import argparse
from dataclasses import dataclass
from typing import Literal

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    ItemHelpers,
    ModelSettings,
    Runner,
    RunContextWrapper,
    SQLiteSession,
    TResponseInputItem,
    function_tool,
    input_guardrail,
    set_tracing_disabled,
    trace,
)
from luminus_harness import (
    APPOINTMENT_INSTRUCTIONS,
    LUMINUS_INSTRUCTIONS,
    billing_explanation,
    luminus_fact,
    propose_appointment,
)

set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# Shared function tools
# ---------------------------------------------------------------------------

@function_tool
def luminus_billing_fun_fact() -> str:
    """Return an interesting Luminus billing or energy-saving fact."""
    return luminus_fact()


@function_tool
def get_average_bill(customer_name: str) -> str:
    """Return the average monthly bill for a Luminus customer (simulated)."""
    return billing_explanation(customer_name)


@function_tool
def book_appointment(customer_name: str, date: str, time_slot: str) -> str:
    """Book a technician appointment for a Luminus customer."""
    return propose_appointment(customer_name, f"technician visit at {time_slot}", date)


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
# 8. Agents as Tools
# ===========================================================================

async def demo_agents_as_tools() -> None:
    """
    A manager agent keeps control of the conversation and calls specialist
    energy agents as tools for bounded subtasks — unlike handoffs, the manager
    always owns the final response.
    """
    print("\n" + "=" * 60)
    print("DEMO 8 — Agents as Tools")
    print("=" * 60)

    billing_analyst = Agent(
        name="Billing Analyst",
        instructions=(
            "You are an expert Luminus billing analyst. "
            "Given a customer question, analyse their billing data and provide "
            "a detailed breakdown of charges, tariff components, and any anomalies."
        ),
        tools=[get_average_bill],
    )

    energy_advisor = Agent(
        name="Energy Efficiency Advisor",
        instructions=(
            "You are a Luminus energy efficiency specialist. "
            "Provide personalised tips to reduce energy consumption based on "
            "the customer's situation. Include estimated savings in euros."
        ),
        tools=[luminus_billing_fun_fact],
    )

    manager_agent = Agent(
        name="Luminus Energy Manager",
        instructions=(
            "You are the main Luminus customer support manager. "
            "You coordinate specialist agents to give customers the best answer. "
            "Use the billing analyst for billing questions and the energy advisor "
            "for efficiency tips. Synthesise their answers into one clear response."
        ),
        tools=[
            billing_analyst.as_tool(
                tool_name="billing_analyst",
                tool_description="Analyses billing data, tariff breakdowns, and charge anomalies.",
            ),
            energy_advisor.as_tool(
                tool_name="energy_advisor",
                tool_description="Provides energy-saving tips with estimated euro savings.",
            ),
        ],
    )

    result = await Runner.run(
        manager_agent,
        "Hi, I'm Sophie. My bill went up last month and I'd like to understand "
        "why AND get tips to bring it down.",
    )
    print(result.final_output)


# ===========================================================================
# 9. Guardrails
# ===========================================================================

COMPETITOR_NAMES = {"engie", "totalenergies", "eneco", "essent", "vattenfall", "mega", "octa+", "bolt", "elegant"}

ENERGY_TOPIC_KEYWORDS = {
    "luminus",
    "bill",
    "billing",
    "invoice",
    "charge",
    "cost",
    "meter",
    "electricity",
    "gas",
    "energy",
    "usage",
    "consumption",
    "tariff",
    "plan",
    "solar",
    "heating",
    "appliance",
    "appointment",
    "technician",
    "smart meter",
}

VOICE_TOPIC_REFUSAL = (
    "Sorry, I can only help with Luminus energy, billing, meter, plan, "
    "saving-tip, or appointment questions."
)


def extract_input_text(input: str | list[TResponseInputItem]) -> str:
    if isinstance(input, str):
        return input.lower()
    return " ".join(
        item.get("content", "").lower()
        for item in input
        if isinstance(item, dict) and isinstance(item.get("content"), str)
    )


@input_guardrail
async def block_competitor_questions(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """Block questions that explicitly mention competitor energy providers by name."""
    text = extract_input_text(input)
    found = any(name in text for name in COMPETITOR_NAMES)
    return GuardrailFunctionOutput(
        output_info={"competitor_detected": found},
        tripwire_triggered=found,
    )


@input_guardrail
async def block_non_energy_questions(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """Block questions outside Luminus energy support topics."""
    text = extract_input_text(input)
    is_energy_related = any(keyword in text for keyword in ENERGY_TOPIC_KEYWORDS)
    return GuardrailFunctionOutput(
        output_info={"energy_related": is_energy_related},
        tripwire_triggered=not is_energy_related,
    )


async def demo_guardrails() -> None:
    """
    Input guardrail that blocks questions about competitor energy providers.
    The agent only answers Luminus-related queries.
    """
    print("\n" + "=" * 60)
    print("DEMO 9 — Guardrails")
    print("=" * 60)

    guarded_agent = Agent(
        name="Luminus Support (Guarded)",
        instructions=(
            LUMINUS_INSTRUCTIONS
            + " You only answer questions related to Luminus services."
        ),
        tools=[luminus_billing_fun_fact, get_average_bill],
        input_guardrails=[block_competitor_questions],
    )

    # Safe question — should pass
    print("\n--- Safe question ---")
    result = await Runner.run(
        guarded_agent,
        "Hi, I'm Tom. What solar panel options does Luminus offer?",
    )
    print(result.final_output)

    # Competitor question — should be blocked
    print("\n--- Competitor question ---")
    try:
        await Runner.run(
            guarded_agent,
            "Can you compare Luminus prices with Engie and TotalEnergies?",
        )
    except InputGuardrailTripwireTriggered:
        print("⚠ Guardrail triggered: competitor question blocked.")


# ===========================================================================
# 10. Human in the Loop
# ===========================================================================

@function_tool(needs_approval=True)
def switch_energy_plan(customer_name: str, new_plan: str) -> str:
    """Switch a customer to a different Luminus energy plan. Requires approval."""
    return (
        f"Plan switch confirmed: {customer_name} has been moved to the "
        f"'{new_plan}' plan. Changes take effect on the next billing cycle."
    )


@function_tool(needs_approval=True)
def schedule_meter_replacement(customer_name: str, meter_type: str) -> str:
    """Schedule a smart meter replacement. Requires approval."""
    return (
        f"Smart meter replacement scheduled for {customer_name}. "
        f"A {meter_type} meter will be installed within 10 business days."
    )


async def demo_human_in_the_loop() -> None:
    """
    Sensitive actions (plan switch, meter replacement) require human approval
    before execution. The run pauses and we simulate approving or rejecting.
    """
    print("\n" + "=" * 60)
    print("DEMO 10 — Human in the Loop")
    print("=" * 60)

    agent = Agent(
        name="Luminus Account Manager",
        instructions=(
            "You are a Luminus account manager who can switch energy plans and "
            "schedule smart meter replacements. When a customer requests an action, "
            "use the appropriate tool immediately — do not ask for extra confirmation."
        ),
        tools=[switch_energy_plan, schedule_meter_replacement],
    )

    # First run — agent will try to call the tool, which pauses for approval
    result = await Runner.run(
        agent,
        "Hi, I'm Clara. Please switch me to the Luminus Green Energy plan right now.",
    )

    if result.interruptions:
        print(f"\n⏸  Execution paused — {len(result.interruptions)} action(s) need approval:")
        state = result.to_state()

        for interruption in result.interruptions:
            print(f"   Tool: {interruption.name}")
            print(f"   Args: {interruption.arguments}")

            # Simulate human approval
            print("   → Approving...")
            state.approve(interruption)

        # Resume execution after approval
        result = await Runner.run(agent, state)
        print(f"\n✓ Final response:\n{result.final_output}")
    else:
        print(result.final_output)


# ===========================================================================
# 11. Interactive chat — full-featured conversational agent
# ===========================================================================

async def demo_interactive_chat() -> None:
    """
    Interactive conversation loop combining all patterns:
    - Function tools (billing, energy tips)
    - Agents as tools (billing analyst, energy advisor)
    - Handoffs (appointment booking)
    - Guardrails (blocks competitor questions)
    - Human in the loop (approval for plan switches & meter replacements)
    - Multi-turn memory via session
    """
    print("\n" + "=" * 60)
    print("  Luminus Energy Assistant — Interactive Chat")
    print("=" * 60)
    print("Type your questions below. Type 'quit' or 'exit' to stop.\n")

    # --- Specialist agents (used as tools) ---
    billing_analyst = Agent(
        name="Billing Analyst",
        instructions=(
            "You are an expert Luminus billing analyst. "
            "Analyse billing data and provide a detailed breakdown of "
            "charges, tariff components, and any anomalies."
        ),
        tools=[get_average_bill],
    )

    energy_advisor = Agent(
        name="Energy Efficiency Advisor",
        instructions=(
            "You are a Luminus energy efficiency specialist. "
            "Provide personalised tips to reduce energy consumption. "
            "Include estimated savings in euros."
        ),
        tools=[luminus_billing_fun_fact],
    )

    # --- Appointment agent (handoff target) ---
    appointment_agent = Agent(
        name="appointment_agent",
        handoff_description="Specialist for booking technician visits at customer premises.",
        instructions=APPOINTMENT_INSTRUCTIONS,
        tools=[book_appointment],
    )

    # --- Main conversational agent ---
    agent = Agent(
        name="Luminus Energy Assistant",
        instructions=(
            "You are the Luminus Energy Assistant — the main customer support agent. "
            "You help customers with billing questions, energy-saving advice, "
            "appointment booking, plan switches, and meter replacements.\n\n"
            "Rules:\n"
            "- Use the billing_analyst tool for detailed billing analysis.\n"
            "- Use the energy_advisor tool for energy-saving tips.\n"
            "- Hand off to the Appointment Agent for technician bookings.\n"
            "- Use switch_energy_plan or schedule_meter_replacement when requested "
            "  (these require human approval).\n"
            "- Be friendly, concise, and always address the customer by name.\n"
            "- You only answer questions related to Luminus services."
        ),
        tools=[
            luminus_billing_fun_fact,
            get_average_bill,
            switch_energy_plan,
            schedule_meter_replacement,
            billing_analyst.as_tool(
                tool_name="billing_analyst",
                tool_description="Deep billing analysis with tariff breakdowns and anomaly detection.",
            ),
            energy_advisor.as_tool(
                tool_name="energy_advisor",
                tool_description="Personalised energy-saving tips with estimated euro savings.",
            ),
        ],
        handoffs=[appointment_agent],
        input_guardrails=[block_non_energy_questions, block_competitor_questions],
    )

    # Use to_input_list() for history — no session to avoid duplicate IDs
    input_items: list[TResponseInputItem] = []

    while True:
        try:
            user_input = input("\n🟢 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("👋 Thanks for chatting with Luminus! Goodbye.")
            break

        input_items.append({"role": "user", "content": user_input})

        try:
            result = await Runner.run(agent, input_items)

            # Handle human-in-the-loop approvals
            if result.interruptions:
                state = result.to_state()
                for interruption in result.interruptions:
                    print(f"\n⏸  Approval needed — {interruption.name}")
                    print(f"   Details: {interruption.arguments}")
                    answer = input("   Approve? (y/n): ").strip().lower()
                    if answer in ("y", "yes"):
                        state.approve(interruption)
                        print("   ✅ Approved.")
                    else:
                        state.reject(interruption, rejection_message="Customer declined this action.")
                        print("   ❌ Rejected.")

                result = await Runner.run(agent, state)

            input_items = result.to_input_list()
            print(f"\n🔵 Luminus: {result.final_output}")

        except InputGuardrailTripwireTriggered:
            print("\n🔴 Luminus: Sorry, I can only help with Luminus-related questions. "
                  "I'm not able to discuss competitor services.")
            # Remove the blocked message from history so conversation continues
            input_items.pop()


# ===========================================================================
# 12. Voice / Realtime agent
# ===========================================================================

async def demo_voice_agent() -> None:
    """
    Voice-powered Luminus energy assistant. Speak into your microphone and
    hear the agent respond through your speakers.

    Uses VoicePipeline: microphone → speech-to-text → agent → text-to-speech → speaker.
    Press Ctrl+C to stop.
    """
    try:
        import numpy as np
        import sounddevice as sd
        from agents.voice import AudioInput, SingleAgentVoiceWorkflow, VoicePipeline
    except ImportError:
        print("Voice dependencies missing. Install with:")
        print("  pip install 'openai-agents[voice]' sounddevice")
        return

    print("\n" + "=" * 60)
    print("  Luminus Energy Assistant — Voice Agent")
    print("=" * 60)

    agent = Agent(
        name="Luminus Voice Assistant",
        instructions=(
            "You are a Luminus voice assistant for energy customers. "
            "Only answer questions about Luminus, billing, energy usage, saving tips, "
            "meters, appointments, plans, and related customer support. "
            "If the user asks about anything else, politely say you can only help "
            "with Luminus energy support. "
            "Keep your answers short and conversational — you are speaking out loud, "
            "not writing. Use simple sentences. Avoid lists and bullet points."
        ),
        tools=[luminus_billing_fun_fact, get_average_bill, book_appointment],
        input_guardrails=[block_non_energy_questions, block_competitor_questions],
    )

    pipeline = VoicePipeline(workflow=SingleAgentVoiceWorkflow(agent))

    # --- Recording settings ---
    SAMPLE_RATE = 24000
    CHANNELS = 1
    DTYPE = np.int16

    print("\n🎙  Listening... Speak into your microphone.")
    print("   Press ENTER when you're done speaking. Ctrl+C to quit.\n")

    while True:
        try:
            # Record audio until user presses Enter
            frames: list[np.ndarray] = []
            recording = True

            def callback(indata, frame_count, time_info, status):
                if recording:
                    frames.append(indata.copy())

            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=callback,
            )
            stream.start()

            input("   🔴 Recording... Press ENTER to send → ")
            recording = False
            stream.stop()
            stream.close()

            if not frames:
                print("   No audio captured, try again.")
                continue

            audio_buffer = np.concatenate(frames, axis=0).flatten()
            print("   🔄 Processing...")

            # Run through the voice pipeline
            audio_input = AudioInput(buffer=audio_buffer)
            try:
                result = await pipeline.run(audio_input)
            except InputGuardrailTripwireTriggered:
                print(f"   🔵 Luminus: {VOICE_TOPIC_REFUSAL}")
                continue

            # Play the response through speakers
            player = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
            )
            player.start()
            print("   🔊 Speaking...")

            async for event in result.stream():
                if event.type == "voice_stream_event_audio":
                    player.write(event.data)

            player.stop()
            player.close()
            print()

        except KeyboardInterrupt:
            print("\n👋 Voice session ended. Goodbye!")
            break


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
    8: ("Agents as Tools", demo_agents_as_tools),
    9: ("Guardrails", demo_guardrails),
    10: ("Human in the Loop", demo_human_in_the_loop),
    11: ("Interactive Chat", demo_interactive_chat),
    12: ("Voice Agent", demo_voice_agent),
}


async def run_all() -> None:
    for num, (name, fn) in DEMOS.items():
        if num in (11, 12):
            continue  # Skip interactive/voice modes in run-all
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
        help="Demo number to run (1–12). Omit to run all demos sequentially.",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Launch the interactive Luminus Energy Assistant chat.",
    )
    args = parser.parse_args()

    if args.chat:
        asyncio.run(run_demo(11))
    elif args.demo is not None:
        asyncio.run(run_demo(args.demo))
    else:
        asyncio.run(run_all())
