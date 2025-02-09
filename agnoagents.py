from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Define the Billing Agent: Handles billing inquiries.
billing_agent = Agent(
    name="Billing Agent",
    role="Handle billing inquiries",
    model=OpenAIChat(id="gpt-4o"),
    instructions=(
        "You are a billing expert for Luminus. You handle questions such as "
        "'Why is my bill high?', 'When is payment due?', and provide explanations for capacity tariffs. "
        "Always address the customer by name and ensure data privacy. "
        "If the query is not related to billing, respond with 'Not applicable to billing domain.'"
    ),
    markdown=True
)

# Define the Energy Insights Agent: Provides energy usage analysis.
insights_agent = Agent(
    name="Energy Insights Agent",
    role="Provide energy usage insights",
    model=OpenAIChat(id="gpt-4o"),
    instructions=(
        "You are an energy insights specialist for Luminus. Your task is to analyze past energy usage, "
        "identify peak usage, and discuss consumption trends. Always address the customer by name and maintain data privacy. "
        "If the query does not pertain to energy insights, reply with 'Not applicable to energy insights domain.'"
    ),
    markdown=True
)

# Define the Energy Advice Agent: Offers practical tips on reducing energy consumption.
advice_agent = Agent(
    name="Energy Advice Agent",
    role="Give energy-saving advice",
    model=OpenAIChat(id="gpt-4o"),
    instructions=(
        "You are an energy advisor for Luminus. Provide practical advice on how to reduce energy consumption "
        "and lower bills. Always address the customer personally and ensure security and privacy. "
        "If the query is not related to energy advice, respond with 'Not applicable to energy advice domain.'"
    ),
    markdown=True
)

# Combine the three agents into a team.
# Agno will coordinate among the team members to provide a comprehensive answer.
team_agent = Agent(
    team=[billing_agent, insights_agent, advice_agent],
    model=OpenAIChat(id="gpt-4o"),
    instructions=[
        "Collaborate and coordinate among the specialized agents to provide a comprehensive response.",
        "Address the customer personally in your responses."
    ],
    markdown=True
)

# Sample query from a customer named John.
sample_query = (
    "Hi John, my last bill was unexpectedly high and I'm not sure why. "
    "Could you help me understand the billing details? Also, I'd appreciate some advice on how to reduce my energy consumption."
)

# Print the response from the team agent (streaming enabled).
team_agent.print_response(sample_query, stream=True)
