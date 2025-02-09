from smolagents import CodeAgent, HfApiModel

# Initialize the model (smolagents supports many models; here we use HfApiModel as an example)
model = HfApiModel()

# --- Define the Specialized Agents ---

# Billing Agent: handles billing-related queries.
billing_agent = CodeAgent(tools=[], model=model)
billing_agent.system_prompt = (
    "You are a billing expert for Luminus. Handle questions such as 'Why is my bill high?', "
    "payment due dates, and capacity tariff explanations. Always address the customer by name and "
    "ensure data privacy. If the query is not related to billing, respond with 'Not applicable to billing domain.'"
)

# Energy Insights Agent: provides analysis on energy usage.
insights_agent = CodeAgent(tools=[], model=model)
insights_agent.system_prompt = (
    "You are an energy insights specialist for Luminus. Analyze past energy usage, identify peak usage, "
    "and discuss consumption trends. Always address the customer by name and observe data privacy. "
    "If the query does not pertain to energy insights, reply with 'Not applicable to energy insights domain.'"
)

# Energy Advice Agent: offers practical tips to reduce energy consumption.
advice_agent = CodeAgent(tools=[], model=model)
advice_agent.system_prompt = (
    "You are an energy advisor for Luminus. Provide actionable advice on reducing energy consumption "
    "and lowering bills. Always address the customer personally and securely. "
    "If the query is not about energy advice, respond with 'Not applicable to energy advice domain.'"
)

# --- Helper Functions to Coordinate the Team ---

def get_specialized_responses(query: str):
    """
    Ask each specialized agent the same query and return their responses.
    """
    billing_response = billing_agent.run(query)
    insights_response = insights_agent.run(query)
    advice_response = advice_agent.run(query)
    return billing_response, insights_response, advice_response

def aggregate_responses(billing_resp: str, insights_resp: str, advice_resp: str) -> str:
    """
    Combine the responses from the specialized agents into a final, coherent answer.
    """
    aggregator = CodeAgent(tools=[], model=model)
    aggregator.system_prompt = (
        "You are an aggregator for Luminus's energy assistant. Given the responses from the billing, "
        "energy insights, and energy advice experts, combine them into one final answer that addresses the customer's query."
    )
    aggregation_query = (
        "Combine the following responses into one coherent answer:\n\n"
        f"Billing: {billing_resp}\n\n"
        f"Energy Insights: {insights_resp}\n\n"
        f"Energy Advice: {advice_resp}\n\n"
        "Provide a final response that is clear, addresses the customer's concern, and maintains a friendly tone."
    )
    final_response = aggregator.run(aggregation_query)
    return final_response

# --- Main Execution ---

if __name__ == "__main__":
    # A sample customer query (note the personalized greeting and multi-part question)
    customer_query = (
        "Hi John, my last bill was unexpectedly high and I'm not sure why. "
        "Could you help me understand the billing details? Also, I'd appreciate some advice on how to reduce my energy consumption."
    )
    
    # 1. Get responses from each specialized agent.
    billing_resp, insights_resp, advice_resp = get_specialized_responses(customer_query)
    
    # 2. Aggregate the responses into a final answer.
    final_answer = aggregate_responses(billing_resp, insights_resp, advice_resp)
    
    # 3. Print the final aggregated response.
    print("Final Aggregated Response:")
    print(final_answer)
