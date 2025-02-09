from swarm import Swarm, Agent

# Instantiate the Swarm client.
client = Swarm()

# --- Define Specialized Agents ---

# Billing Agent: Explains why a customer's bill might be high.
billing_agent = Agent(
    name="Billing Agent",
    instructions=(
        "You are a billing expert for Luminus. Explain concisely why the customer's bill might be unexpectedly high. "
        "Mention factors such as peak usage times, seasonal tariff adjustments, or other billing anomalies. "
        "If the query is not related to billing, reply with 'Not applicable to billing domain.'"
    ),
)

# Energy Insights Agent: Provides insights on energy usage patterns.
insights_agent = Agent(
    name="Energy Insights Agent",
    instructions=(
        "You are an energy usage expert for Luminus. Provide insights on the customer's energy consumption patterns, "
        "highlighting peak times and usage trends. If the query does not relate to energy insights, reply with "
        "'Not applicable to energy insights domain.'"
    ),
)

# Energy Advice Agent: Offers practical tips to reduce energy consumption.
advice_agent = Agent(
    name="Energy Advice Agent",
    instructions=(
        "You are an energy advisor for Luminus. Offer actionable advice for reducing energy consumption and lowering bills. "
        "If the query is not about energy advice, reply with 'Not applicable to energy advice domain.'"
    ),
)

# --- Define Hand-off Functions ---
# When a function returns an Agent, Swarm automatically transfers execution to that Agent.

def transfer_to_billing():
    return billing_agent

def transfer_to_insights():
    return insights_agent

def transfer_to_advice():
    return advice_agent

# --- Define a Front Desk Agent ---
# This agent examines the user's query and initiates a handoff to a specialized agent.
# (For this demonstration, we set its instructions to hand off to the Billing Agent.)
front_desk_agent = Agent(
    name="Front Desk Agent",
    instructions=(
        "You are the front desk energy assistant for Luminus. A customer has asked a question that includes billing concerns. "
        "Your role is to first transfer the conversation to the Billing Agent for a detailed explanation. "
        "Additional handoffs to energy insights or advice may be handled in follow-up interactions."
    ),
    functions=[transfer_to_billing, transfer_to_insights, transfer_to_advice],
)

# --- Run the Swarm ---
# The client.run() call starts the conversation using the front desk agent.
# If the front desk agent calls one of its functions that returns a specialized agent,
# Swarm will hand off execution to that agent.

messages = [
    {
        "role": "user",
        "content": (
            "Hi John, my last bill was unexpectedly high and I'm confused about the charges. "
            "Can you explain why my bill is high and advise me on reducing my energy consumption?"
        )
    }
]

# Run the conversation; Swarm will follow any agent handoffs.
response = client.run(
    agent=front_desk_agent,
    messages=messages,
)

# Print the final response (from the last active agent in the conversation).
print("Final Response:")
print(response.messages[-1]["content"])
