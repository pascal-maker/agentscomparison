#!/usr/bin/env python3
"""
Energy Advice & Billing Assistant powered by Google Gemini.
Features:
- Energy usage analysis and advice
- Billing explanations and cost estimates
- Energy-saving tips and recommendations

Dependencies:
  pip install google-generativeai
"""

import os
import google.generativeai as genai

# Configure API key from environment variable
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Please set the GOOGLE_API_KEY environment variable")

genai.configure(api_key=GOOGLE_API_KEY)

# List available models
print("Available models:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")

# Initialize the model
model = genai.GenerativeModel('models/gemini-2.5-flash-preview-05-20')  # Using the latest 2.5 flash model

def chat_with_energy_assistant(message):
    try:
        prompt = f"""
        You are an energy advisor AI assistant. Answer this question about energy usage, bills, or saving tips:
        {message}
        
        Be clear, practical, and cite specific numbers when possible.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    print("\n💡 Energy Assistant (type 'exit' to quit)")
    print("Ask me about energy usage, bills, or saving tips!\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() == 'exit':
                print("👋 Goodbye!")
                break
            response = chat_with_energy_assistant(user_input)
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()