from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

Focus = Literal["heating", "appliances", "general"]

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


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    plan: str
    last_bill_eur: float


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    customer_id: str
    query: str
    focus: Focus = "general"
    appointment_reason: str = "inspection"
    appointment_date: str = "2026-08-12"


CUSTOMERS: dict[str, Customer] = {
    "LUM-1001": Customer("LUM-1001", "Sofie", "Comfy Fixed", 142.50),
    "LUM-1002": Customer("LUM-1002", "Marc", "Dynamic", 208.90),
    "LUM-1003": Customer("LUM-1003", "Amira", "Solar Buyback", 76.20),
}

SCENARIOS: dict[str, Scenario] = {
    "high_bill": Scenario(
        scenario_id="high_bill",
        title="Unexpected high bill",
        customer_id="LUM-1001",
        query="My last bill was unexpectedly high. Why did it change and how can I lower it?",
        focus="general",
    ),
    "appliance_savings": Scenario(
        scenario_id="appliance_savings",
        title="Appliance off-peak savings",
        customer_id="LUM-1002",
        query="Can I lower my bill by changing when I run appliances?",
        focus="appliances",
    ),
    "meter_visit": Scenario(
        scenario_id="meter_visit",
        title="Smart meter appointment",
        customer_id="LUM-1003",
        query="I need a smart meter inspection appointment.",
        focus="general",
        appointment_reason="smart meter inspection",
        appointment_date="2026-08-12",
    ),
}

SAVING_TIPS = {
    "heating": [
        "Lower the thermostat by 1C to cut heating costs by about 6%.",
        "Use a smart thermostat schedule so heating is off when nobody is home.",
    ],
    "appliances": [
        "Shift dishwasher and laundry to off-peak hours after 22:00.",
        "Switch standby devices off at the wall to remove always-on load.",
    ],
    "general": [
        "Shift heavy appliances to off-peak hours after 22:00.",
        "Lower the thermostat by 1C to cut heating costs by about 6%.",
        "Switch standby devices off at the wall to remove always-on load.",
    ],
}

FACTS = [
    "Switching to LED bulbs can reduce your lighting bill by up to 80%.",
    "Luminus customers who opt for the night tariff save on average EUR 120 per year.",
    "A standby device left plugged in can cost up to EUR 50 extra per year.",
    "Solar panels installed via Luminus reduce a typical household bill by 40%.",
]


def get_customer(customer_id: str) -> Customer | None:
    return CUSTOMERS.get(customer_id.strip().upper())


def find_customer(identifier: str) -> Customer | None:
    normalized = identifier.strip().lower()
    direct = get_customer(identifier)
    if direct:
        return direct
    return next((customer for customer in CUSTOMERS.values() if customer.name.lower() == normalized), None)


def customer_context(customer_id: str) -> str:
    customer = get_customer(customer_id)
    if not customer:
        return f"No Luminus account found for {customer_id}."
    return (
        f"Account {customer.customer_id}: name={customer.name}, plan={customer.plan}, "
        f"last bill=EUR {customer.last_bill_eur:.2f}. Usage peaks on weekday evenings "
        "18:00-22:00 and rises in winter for heating."
    )


def billing_explanation(identifier: str) -> str:
    customer = find_customer(identifier)
    if not customer:
        return f"No Luminus account found for {identifier}."
    return (
        f"Account {customer.customer_id} ({customer.name}, {customer.plan} plan): "
        f"last bill EUR {customer.last_bill_eur:.2f}. The increase versus your average "
        "is driven by higher evening peak-hour usage and a seasonal rate adjustment "
        "applied this quarter."
    )


def energy_insights(identifier: str) -> str:
    customer = find_customer(identifier)
    name = customer.name if customer else identifier
    return (
        f"{name}'s usage peaks on weekday evenings between 18:00 and 22:00 and rises "
        "in winter for heating. Standby load from always-on devices accounts for "
        "roughly 8% of consumption."
    )


def energy_advice(identifier: str, focus: Focus = "general") -> str:
    customer = find_customer(identifier)
    name = customer.name if customer else identifier
    plan = f" ({customer.plan} plan)" if customer else ""
    tips = SAVING_TIPS.get(focus, SAVING_TIPS["general"])
    rendered_tips = " ".join(f"- {tip}" for tip in tips)
    return f"Tailored energy-saving advice for {name}{plan}, focus={focus}: {rendered_tips}"


def propose_appointment(customer_id: str, reason: str, preferred_date: str) -> str:
    customer = find_customer(customer_id)
    if not customer:
        return f"No Luminus account found for {customer_id}."
    reference = f"APPT-{customer.customer_id}-{preferred_date.replace('-', '')}"
    return (
        f"Proposed appointment for {customer.name} on {preferred_date} ({reason}). "
        f"Reference {reference}. Awaiting human approval before booking."
    )


def luminus_fact() -> str:
    return random.choice(FACTS)


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS)


def get_scenario(scenario_id: str) -> Scenario:
    try:
        return SCENARIOS[scenario_id]
    except KeyError as error:
        known = ", ".join(list_scenarios())
        raise ValueError(f"Unknown scenario {scenario_id!r}. Known scenarios: {known}") from error
