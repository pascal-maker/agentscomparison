from agents.llms import LlamaCppChatCompletion
from agents.tool_executor import need_tool_use

# --- Define Custom Energy Tools ---

def get_billing_details(input_text: str):
    """
    Simulate retrieving billing details.
    In a real-world scenario, this could query a database or an API.
    """
    return {
        "role": "assistant",
        "content": (
            "Billing Details: Your recent bill was high because there was an unexpected surge in peak hour usage "
            "combined with a seasonal tariff adjustment."
        )
    }

def get_energy_insights(input_text: str):
    """
    Simulate retrieving energy usage insights.
    """
    return {
        "role": "assistant",
        "content": (
            "Energy Insights: Your energy usage peaks in the evenings and during the summer months, indicating higher usage "
            "during these periods."
        )
    }

def get_energy_advice(input_text: str):
    """
    Simulate retrieving practical advice on reducing energy consumption.
    """
    return {
        "role": "assistant",
        "content": (
            "Energy Advice: Consider upgrading to energy-efficient appliances and using smart thermostats to optimize your energy usage."
        )
    }

# Assign a 'name' attribute to each tool function.
get_billing_details.name = "get_billing_details"
get_energy_insights.name = "get_energy_insights"
get_energy_advice.name = "get_energy_advice"

# --- Instantiate the LLM ---
llm = LlamaCppChatCompletion.from_default_llm(n_ctx=0)
# Bind our custom energy tools to the LLM.
llm.bind_tools([get_billing_details, get_energy_insights, get_energy_advice])

# --- Define the Conversation ---
messages = [
    {
        "role": "user",
        "content": (
            "Hi John, my last bill was unexpectedly high and I don't understand why. "
            "Can you explain the billing details and provide advice on how I might reduce my energy consumption?"
        )
    }
]

# --- Run the Agent ---
# Get the initial response from the LLM.
output = llm.chat_completion(messages)

# Check if the LLM indicates a need to call tools.
if need_tool_use(output):
    print("Tools are needed—invoking energy tools...")
    # Run the tools based on the LLM's response.
    tool_results = llm.run_tools(output)
    
    # Ensure each tool result has the proper "assistant" role.
    for result in tool_results:
        result["role"] = "assistant"
    
    # Append tool results to the conversation context.
    updated_messages = messages + tool_results
    # Add a follow-up prompt asking the LLM to reason step by step based on the tool outputs.
    updated_messages.append({
        "role": "user",
        "content": "Now, based on the tool results, please provide a final, detailed answer addressing both my billing concerns and energy advice."
    })
    
    # Get the final answer.
    output = llm.chat_completion(updated_messages)

# Print the final answer from the assistant.
print("Final Agent Response:")
print(output.choices[0].message.content)
