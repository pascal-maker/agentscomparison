"""
Luminus energy customer-support assistant built on **Agent Laboratory**.

Agent Laboratory ships a unified LLM interface, `query_model(model_str, prompt,
system_prompt, ...)`, that its specialized research agents are driven by. This demo
reuses that exact interface to build a small team of specialized support agents for
the same Luminus use case as the other frameworks in this repo:

    BillingAnalyst   -> explains the customer's bill and usage
    EnergyAdvisor    -> gives tailored energy-saving advice
    AppointmentAgent -> proposes a technician appointment (human approves)
    SupportManager   -> routes the customer query to the right specialist(s)

Run:
    export OPENAI_API_KEY="your-key"
    python agentlaboratory_energy.py
    python agentlaboratory_energy.py --query "Why was my bill so high?" --customer LUM-1002
"""

import argparse
import os
import sys

# Agent Laboratory lives in a sibling directory with its own modules.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "AgentLaboratory"))
from inference import query_model  # type: ignore[import-not-found]  # noqa: E402 (path injected above)

MODEL = os.getenv("AGENTLAB_MODEL", "gpt-4o-mini")

# --- Simulated Luminus customer database --------------------------------------
CUSTOMERS = {
    "LUM-1001": {"name": "Sofie", "plan": "Comfy Fixed", "last_bill_eur": 142.50},
    "LUM-1002": {"name": "Marc", "plan": "Dynamic", "last_bill_eur": 208.90},
    "LUM-1003": {"name": "Amira", "plan": "Solar Buyback", "last_bill_eur": 76.20},
}


def customer_context(customer_id: str) -> str:
    c = CUSTOMERS.get(customer_id)
    if not c:
        return f"No Luminus account found for {customer_id}."
    return (
        f"Account {customer_id}: name={c['name']}, plan={c['plan']}, "
        f"last bill=€{c['last_bill_eur']:.2f}. Usage peaks on weekday evenings "
        f"(18:00-22:00) and rises in winter for heating."
    )


# --- Specialized agents (the Agent Laboratory pattern) ------------------------
class SupportAgent:
    """A specialized agent driven by Agent Laboratory's query_model interface."""

    def __init__(self, role: str, system_prompt: str):
        self.role = role
        self.system_prompt = system_prompt

    def respond(self, prompt: str) -> str:
        return query_model(
            model_str=MODEL,
            system_prompt=self.system_prompt,
            prompt=prompt,
            temp=0.3,
            print_cost=False,
        )


BILLING_ANALYST = SupportAgent(
    "BillingAnalyst",
    "You are a Luminus billing analyst. Explain the customer's bill clearly using the "
    "provided account context. Be concrete about why the amount changed. Do not invent numbers.",
)

ENERGY_ADVISOR = SupportAgent(
    "EnergyAdvisor",
    "You are a Luminus energy advisor. Give 3-4 specific, actionable tips to lower the "
    "customer's consumption, tailored to their usage pattern. Keep it short and practical.",
)

APPOINTMENT_AGENT = SupportAgent(
    "AppointmentAgent",
    "You are a Luminus scheduling agent. Propose a single technician appointment slot for the "
    "stated reason. End with: 'Awaiting human approval before booking.' Never confirm a booking yourself.",
)

SUPPORT_MANAGER = SupportAgent(
    "SupportManager",
    "You are a Luminus support manager. Given a customer query, reply with a comma-separated list "
    "of which specialists are needed, choosing only from: billing, advice, appointment. "
    "Reply with ONLY the list, e.g. 'billing, advice'.",
)


def route(query: str) -> list[str]:
    raw = SUPPORT_MANAGER.respond(f"Customer query: {query}").lower()
    chosen = [s for s in ("billing", "advice", "appointment") if s in raw]
    return chosen or ["billing", "advice"]


def handle(query: str, customer_id: str) -> None:
    ctx = customer_context(customer_id)
    print(f"\n=== Luminus support (Agent Laboratory) — {customer_id} ===")
    print(f"Customer: {query}\n")
    print(f"[context] {ctx}\n")

    specialists = route(query)
    print(f"[manager] routing to: {', '.join(specialists)}\n")

    if "billing" in specialists:
        print("[BillingAnalyst]")
        print(BILLING_ANALYST.respond(f"Account context: {ctx}\n\nCustomer asks: {query}"), "\n")
    if "advice" in specialists:
        print("[EnergyAdvisor]")
        print(ENERGY_ADVISOR.respond(f"Account context: {ctx}\n\nCustomer asks: {query}"), "\n")
    if "appointment" in specialists:
        print("[AppointmentAgent]")
        print(APPOINTMENT_AGENT.respond(f"Account context: {ctx}\n\nCustomer request: {query}"), "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Luminus support assistant on Agent Laboratory.")
    parser.add_argument("--query", default="My last bill was unexpectedly high. How can I lower it?")
    parser.add_argument("--customer", default="LUM-1001", help="Luminus account id, e.g. LUM-1001")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY before running (Agent Laboratory's query_model needs it).")

    handle(args.query, args.customer)


if __name__ == "__main__":
    main()
