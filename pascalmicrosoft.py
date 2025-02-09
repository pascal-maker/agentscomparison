import asyncio

# Import core agents and team utilities from AutoGen AgentChat.
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Define specialized agents by subclassing AssistantAgent and setting custom system prompts.
class BillingAgent(AssistantAgent):
    def __init__(self, name: str, model_client: OpenAIChatCompletionClient) -> None:
        super().__init__(name, model_client)
        self.system_prompt = (
            "You are a billing expert for Luminus. You handle billing questions such as: "
            "'Why is my bill high?', 'When is payment due?', and explanations of the capacity tariff. "
            "Always address the customer by name and ensure data privacy. "
            "If the query does not relate to billing, respond with 'Not applicable to billing domain'."
        )

class EnergyInsightsAgent(AssistantAgent):
    def __init__(self, name: str, model_client: OpenAIChatCompletionClient) -> None:
        super().__init__(name, model_client)
        self.system_prompt = (
            "You are an energy insights specialist for Luminus. You provide analysis on past usage, "
            "peak usage, and energy consumption trends. Always address the customer by name and adhere to data privacy guidelines. "
            "If the query does not pertain to energy insights, respond with 'Not applicable to energy insights domain'."
        )

class EnergyAdviceAgent(AssistantAgent):
    def __init__(self, name: str, model_client: OpenAIChatCompletionClient) -> None:
        super().__init__(name, model_client)
        self.system_prompt = (
            "You are an energy advisor for Luminus. Your role is to provide practical tips on how to reduce energy consumption "
            "and lower energy bills. Always address the customer personally and ensure security and privacy. "
            "If the query does not require energy advice, respond with 'Not applicable to energy advice domain'."
        )

async def main() -> None:
    # Initialize the model client (ensure you have Python 3.10+ and required extensions installed)
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    
    # Instantiate our domain-specific agents with custom system prompts.
    billing_agent = BillingAgent("billing", model_client)
    insights_agent = EnergyInsightsAgent("insights", model_client)
    advice_agent = EnergyAdviceAgent("advice", model_client)
    
    # Instantiate a UserProxyAgent to simulate seamless user login.
    user_proxy = UserProxyAgent("user_proxy")
    
    # Define a termination condition (type "exit" to end the conversation).
    termination = TextMentionTermination("exit")
    
    # Create a RoundRobinGroupChat team with all agents.
    team = RoundRobinGroupChat(
        [user_proxy, billing_agent, insights_agent, advice_agent],
        termination_condition=termination
    )
    
    # Sample task: A logged-in customer (with a name, e.g., "John") asks a question covering multiple domains.
    task = (
        "Hi John, I'm concerned because my last bill was unexpectedly high. "
        "Can you help me understand the reasons behind this? Additionally, I would appreciate some advice on how "
        "I might reduce my energy consumption in the future."
    )
    
    # Run the conversation in the console UI.
    await Console(team.run_stream(task=task))

if __name__ == "__main__":
    asyncio.run(main())
