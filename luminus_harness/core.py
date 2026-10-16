from __future__ import annotations

import random# used to select random scenarios
from dataclasses import dataclass# used to create dataclasses
from typing import Literal# used for type hints

Focus = Literal["heating", "appliances", "general"]# used for type hints

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


class CustomerNotFoundError(LookupError):
    """Raised by any tool below that needs a real customer and cannot find one.

    Every function here that depends on an actual account goes through
    require_customer() and raises this the same way, instead of some
    functions returning an explanatory string, others returning None, and
    others silently treating the raw identifier as if it were a valid name.
    """


@dataclass(frozen=True)# used to create dataclasses
class Customer:
    customer_id: str    # used for type hints
    name: str           # used for type hints
    plan: str           # used for type hints
    last_bill_eur: float    # used for type hints


@dataclass(frozen=True)# used to create dataclasses 
class Scenario:
    scenario_id: str    # used for type hints
    title: str  # used for type hints
    customer_id: str    # used for type hints
    query: str  # used for type hints
    focus: Focus = "general"  # used for type hints
    appointment_reason: str = "inspection"  # used for type hints
    appointment_date: str = "2026-08-12"  # used for type hints


CUSTOMERS: dict[str, Customer] = {
    "LUM-1001": Customer("LUM-1001", "Sofie", "Comfy Fixed", 142.50),# customer 1
    "LUM-1002": Customer("LUM-1002", "Marc", "Dynamic", 208.90),# customer 2
    "LUM-1003": Customer("LUM-1003", "Amira", "Solar Buyback", 76.20),# customer 3
}

SCENARIOS: dict[str, Scenario] = {# scenarios for the comparison
    "high_bill": Scenario(
        scenario_id="high_bill",  # scenario 1
        title="Unexpected high bill",  # scenario 1
        customer_id="LUM-1001",  # scenario 1
        query="My last bill was unexpectedly high. Why did it change and how can I lower it?",  # scenario 1
        focus="general",  # scenario 1
    ),
    "appliance_savings": Scenario(
        scenario_id="appliance_savings",  # scenario 2
        title="Appliance off-peak savings",  # scenario 2
        customer_id="LUM-1002",  # scenario 2
        query="Can I lower my bill by changing when I run appliances?",  # scenario 2
        focus="appliances",  # scenario 2
    ),
    "meter_visit": Scenario(
        scenario_id="meter_visit",  # scenario 3
        title="Smart meter appointment",  # scenario 3
        customer_id="LUM-1003",  # scenario 3
        query="I need a smart meter inspection appointment.",  # scenario 3
        focus="general",  # scenario 3
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

# Fixed demo narrative text below: identical for every customer in this POC
# fixture and not derived from any real usage or billing data. The functions
# that use it only ever interpolate genuine Customer fields (id, name, plan,
# last_bill_eur) around it; treat the narrative itself as flavor text, never
# as account-specific analysis.
DEMO_USAGE_NARRATIVE = (
    "Usage peaks on weekday evenings 18:00-22:00 and rises in winter for heating."
)
DEMO_BILLING_EXPLANATION = (
    "The increase versus your average is driven by higher evening peak-hour "
    "usage and a seasonal rate adjustment applied this quarter."
)
DEMO_INSIGHTS_NARRATIVE = (
    "usage peaks on weekday evenings between 18:00 and 22:00 and rises in "
    "winter for heating. Standby load from always-on devices accounts for "
    "roughly 8% of consumption."
)


def get_customer(customer_id: str) -> Customer | None:# gets the customer
    return CUSTOMERS.get(customer_id.strip().upper())# gets the customer


def find_customer(identifier: str) -> Customer | None:# finds the customer
    normalized = identifier.strip().lower()# normalizes the identifier
    direct = get_customer(identifier)# gets the customer
    if direct:# checks if the customer is found
        return direct
    return next((customer for customer in CUSTOMERS.values() if customer.name.lower() == normalized), None)# returns the customer


def require_customer(identifier: str) -> Customer:
    """Resolve a customer by ID or name, or fail the same way every time.

    This is the one place every tool function below that needs a real
    account goes through, so "customer not found" is a single, typed
    failure instead of each caller handling it differently.
    """
    customer = find_customer(identifier)
    if customer is None:
        raise CustomerNotFoundError(f"No Luminus account found for {identifier}.")
    return customer


def customer_context(customer_id: str) -> str:# gets the customer context
    customer = require_customer(customer_id)
    return (
        f"Account {customer.customer_id}: name={customer.name}, plan={customer.plan}, "# gets the account, name, plan
        f"last bill=EUR {customer.last_bill_eur:.2f}. {DEMO_USAGE_NARRATIVE}"
    )


def billing_explanation(identifier: str) -> str:# gets the billing explanation
    customer = require_customer(identifier)
    return (
        f"Account {customer.customer_id} ({customer.name}, {customer.plan} plan): "# gets the account, name, plan
        f"last bill EUR {customer.last_bill_eur:.2f}. {DEMO_BILLING_EXPLANATION}"
    )


def energy_insights(identifier: str) -> str:# gets the energy insights
    customer = require_customer(identifier)
    return f"{customer.name}'s {DEMO_INSIGHTS_NARRATIVE}"


def energy_advice(identifier: str, focus: Focus = "general") -> str:# gets the energy advice
    customer = require_customer(identifier)
    tips = SAVING_TIPS.get(focus, SAVING_TIPS["general"])
    rendered_tips = " ".join(f"- {tip}" for tip in tips)# renders the tips
    return (
        f"Tailored energy-saving advice for {customer.name} ({customer.plan} plan), "
        f"focus={focus}: {rendered_tips}"
    )# returns the energy advice


def propose_appointment(customer_id: str, reason: str, preferred_date: str) -> str:# proposes an appointment
    customer = require_customer(customer_id)
    reference = f"APPT-{customer.customer_id}-{preferred_date.replace('-', '')}"# creates a reference for the appointment
    return (
        f"Proposed appointment for {customer.name} on {preferred_date} ({reason}). "
        f"Reference {reference}. Awaiting human approval before booking."
    )


def luminus_fact() -> str:# returns a random fact
    return random.choice(FACTS)


def list_scenarios() -> list[str]:# lists the scenarios
    return sorted(SCENARIOS)


def get_scenario(scenario_id: str) -> Scenario:# gets the scenario
    try:
        return SCENARIOS[scenario_id]# gets the scenario
    except KeyError as error:# handles the error if the scenario is not found
        known = ", ".join(list_scenarios())# gets the scenarios
        raise ValueError(f"Unknown scenario {scenario_id!r}. Known scenarios: {known}") from error
