import asyncio
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

# --- Simulated Database for Energy Data ---
# In a real scenario this would connect to your data source.
class EnergyDB:
    async def get_billing_details(self, customer_id: int) -> str:
        # Simulated response; in reality, look up the customer's billing details.
        return "Your bill was high due to increased peak hour usage and a seasonal rate adjustment."

    async def get_energy_insights(self, customer_id: int) -> str:
        # Simulated energy usage insights.
        return "Your energy usage peaks in the evenings, with a notable increase during the summer months."

    async def get_energy_advice(self, customer_id: int) -> str:
        # Simulated advice for reducing energy consumption.
        return "Consider installing energy-efficient appliances and using smart thermostats to optimize usage."

# --- Dependency Injection Data Class ---
@dataclass
class EnergyDependencies:
    customer_id: int
    customer_name: str
    db: EnergyDB

# --- Pydantic Model for the Final Result ---
class EnergyAssistantResult(BaseModel):
    billing_details: str = Field(description="Billing information for the customer.")
    energy_insights: str = Field(description="Insights on the customer's energy usage patterns.")
    energy_advice: str = Field(description="Actionable advice to reduce energy consumption.")

# --- Create the Agent ---
energy_agent = Agent(
    'openai:gpt-4o',           # Replace with your model identifier; note that PydanticAI supports various providers.
    deps_type=EnergyDependencies,
    result_type=EnergyAssistantResult,
    system_prompt=(
        "You are an energy assistant for Luminus. Your task is to provide clear billing details, "
        "energy usage insights, and actionable advice on reducing energy consumption. "
        "Always address the customer by name and ensure data privacy."
    ),
)

# --- Dynamic System Prompt Injection ---
@energy_agent.system_prompt
async def add_customer_info(ctx: RunContext[EnergyDependencies]) -> str:
    # Inject additional context (e.g., customer name) into the system prompt.
    return f"Customer Name: {ctx.deps.customer_name!r}."

# --- Define Tools (functions the agent may call during the conversation) ---
@energy_agent.tool
async def fetch_billing(ctx: RunContext[EnergyDependencies]) -> str:
    """Returns the customer's billing details."""
    return await ctx.deps.db.get_billing_details(ctx.deps.customer_id)

@energy_agent.tool
async def fetch_energy_insights(ctx: RunContext[EnergyDependencies]) -> str:
    """Returns insights on the customer's energy usage."""
    return await ctx.deps.db.get_energy_insights(ctx.deps.customer_id)

@energy_agent.tool
async def fetch_energy_advice(ctx: RunContext[EnergyDependencies]) -> str:
    """Returns practical advice on reducing energy consumption."""
    return await ctx.deps.db.get_energy_advice(ctx.deps.customer_id)

# --- Main Async Function to Run the Agent ---
async def main():
    # Create a simulated database instance.
    db = EnergyDB()
    # Create dependency object with customer details.
    deps = EnergyDependencies(customer_id=123, customer_name="John", db=db)
    
    # Run the agent with a sample customer query.
    # The agent will interact with the LLM and call the registered tools as needed.
    query = (
        "Hi John, my last bill was unexpectedly high and I'm not sure why. "
        "Could you explain the billing details and provide advice on how to lower my energy consumption?"
    )
    result = await energy_agent.run(query, deps=deps)
    
    # Print the validated result.
    print("Final Energy Assistant Response:")
    print(result.data.json(indent=2))

# --- Entry Point ---
if __name__ == "__main__":
    asyncio.run(main())
