#!/usr/bin/env python3
"""
Energy Advice & Billing Assistant powered by OpenAI + Mem0 memory.
──────────────────────────────────────────────────────────────────
Features
  ▸ Personalised Q&A on energy bills, usage, and saving tips.
  ▸ Long-term memory of each user's context (tariff, house size, past queries…).
  ▸ Simple extensible data-layer stubs for live meter data or CSV uploads.

Dependencies
  pip install openai mem0ai python-dateutil
"""

import os
import json
from datetime import datetime, timedelta
from dateutil import parser as dateparse
from openai import OpenAI
from mem0 import Memory

# ────────────────────────────────────────────────────────────────
# 1. Config & global objects
# ────────────────────────────────────────────────────────────────
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_KEY")

openai_client = OpenAI()
memory = Memory()                     # default: in-memory Qdrant

# ────────────────────────────────────────────────────────────────
# 2. Data-layer helpers (replace with real integrations)
# ────────────────────────────────────────────────────────────────
def fetch_latest_meter_reading(user_id: str):
    """
    Stub: fetch the most recent kWh reading for this user.
    Replace with smart-meter API / database query.
    """
    return {"timestamp": datetime.utcnow().isoformat(), "kwh": 4356.7}

def estimate_cost(kwh: float, tariff_eur_per_kwh: float = 0.32) -> float:
    """
    Rough cost estimation. Plug in time-of-use pricing if available.
    """
    return round(kwh * tariff_eur_per_kwh, 2)

# ────────────────────────────────────────────────────────────────
# 3. Utility: store & index memories in a consistent JSON format
# ────────────────────────────────────────────────────────────────
def add_memory(user_id: str, kind: str, payload: dict):
    """
    Store a JSON blob so we can search later. `kind` helps retrieval filters.
    """
    blob = {"kind": kind, "data": payload, "ts": datetime.utcnow().isoformat()}
    memory.add(json.dumps(blob), user_id=user_id)

# ────────────────────────────────────────────────────────────────
# 4. Core chat function with retrieval-augmented prompt
# ────────────────────────────────────────────────────────────────
def chat_with_energy_agent(message: str, user_id: str = "default_user") -> str:
    # 4-a. Retrieve top-K relevant memories
    relevant = memory.search(query=message, user_id=user_id, limit=4)
    memories_str = "\n".join(f"- {memory}" for memory in relevant)

    # 4-b. Build system prompt
    system_prompt = f"""
You are **Wattrix**, a friendly energy-advisor AI.
Always answer clearly, cite approximate numbers (kWh, €) when useful,
and suggest actionable tips that suit the user's context.

If the user asks for cost or usage over a period:
  • Look for past 'meter_reading' memories.
  • If data is missing, guide the user to supply it.

Remember new facts (tariff, appliance list, habits) by returning
JSON with `{{"remember": <string>}}` when appropriate.

User Memories:
{memories_str}
""".strip()

    # 4-c. Call OpenAI
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )
    assistant_msg = resp.choices[0].message.content

    # 4-d. Persist the exchange
    memory.add(message, user_id=user_id, metadata={"kind": "user_msg"})
    memory.add(assistant_msg, user_id=user_id, metadata={"kind": "assistant_msg"})

    # 4-e. Parse and store auto-memories (if assistant returns JSON)
    try:
        parsed = json.loads(assistant_msg)
        if isinstance(parsed, dict) and "remember" in parsed:
            add_memory(user_id, "fact", {"note": parsed["remember"]})
    except Exception:
        pass  # response was normal text

    return assistant_msg

# ────────────────────────────────────────────────────────────────
# 5. CLI demo
# ────────────────────────────────────────────────────────────────
def main():
    user_id = input("Choose a customer ID (default_user): ").strip() or "default_user"

    # First-time: store a fresh meter reading so the agent has data
    add_memory(user_id, "meter_reading", fetch_latest_meter_reading(user_id))

    print("\n💬 Start chatting with Wattrix (type 'exit' to quit)\n")
    while True:
        user_in = input("You: ").strip()
        if user_in.lower() == "exit":
            print("👋 Goodbye!")
            break
        response = chat_with_energy_agent(user_in, user_id=user_id)
        print(f"AI: {response}\n")

if __name__ == "__main__":
    main()
