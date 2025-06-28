#!/usr/bin/env python3
"""
Gemini Agent with MCP Functionality.
"""

import os
import google.generativeai as genai
import requests 

# Configure API key from environment variable
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set the GEMINI_API_KEY environment variable")

genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the model
model = genai.GenerativeModel('models/gemini-1.5-flash')

def query_mcp_service(query):
    """
    Queries the MCP service with a given query.
    """
    try:
        # Replace with the actual API endpoint and authentication method for gitmcp.io
        response = requests.get(f"https://gitmcp.io/pascal-maker/agentscomparison?q={query}")
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()  # Assuming the service returns JSON
    except requests.exceptions.RequestException as e:
        return f"Error querying MCP service: {e}"

def chat_with_gemini_mcp_agent(message):
    """
    Chat with the Gemini MCP agent.
    """
    try:
        # First, try to get information from the MCP service
        mcp_response = query_mcp_service(message)

        # Create a prompt that includes the context from the MCP service
        prompt = f"""
        You are a helpful assistant. Based on the following information from our internal documentation service, 
        answer the user's question.

        Documentation Service Response:
        {mcp_response}

        User's Question:
        {message}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    """
    Main function to run the agent.
    """
    print("\n🤖 Gemini MCP Agent (type 'exit' to quit)")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() == 'exit':
                print("👋 Goodbye!")
                break
            response = chat_with_gemini_mcp_agent(user_input)
            print(f"\nAgent: {response}\n")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
