import streamlit as st
import asyncio
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from dotenv import load_dotenv
import os

load_dotenv()  # This loads the environment variables from .env
openai_api_key = os.getenv("OPENAI_API_KEY")

# Define the asynchronous function to run your medical agent.
async def get_medical_response(task: str) -> str:
    model_client = OpenAIChatCompletionClient(model="gpt-4o")
    # Create an instance of your MedicalAgent with a custom disclaimer.
    medical_agent = AssistantAgent("medical_agent", model_client=model_client)
    medical_agent.system_prompt = (
        "You are a medical information assistant. "
        "Disclaimer: I am not a licensed medical professional. "
        "The information provided is for informational purposes only and should not be taken as medical advice. "
        "Always advise the user to consult with a healthcare provider for any serious concerns. "
        "Answer the patient's questions about symptoms, diseases, and treatments with caution."
    )
    
    # Run the agent with the given task.
    response = await medical_agent.run(task=task)
    
    # Instead of using response.chat_message, access the final message from the list.
    return response.messages[-1].content

# Streamlit UI
st.title("Medical Information Assistant")
st.markdown(
    "### Disclaimer: This assistant provides informational responses only and is not a substitute for professional medical advice."
)

user_question = st.text_area("Enter your medical question here:")

if st.button("Get Response"):
    if user_question.strip():
        with st.spinner("Consulting the medical assistant..."):
            # Run the async function in a synchronous context.
            response_text = asyncio.run(get_medical_response(user_question))
        st.subheader("Response:")
        st.write(response_text)
    else:
        st.error("Please enter a question.")
