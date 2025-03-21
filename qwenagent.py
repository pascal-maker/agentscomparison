import streamlit as st
import asyncio
import torch
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from PIL import Image
import os

# Try to import dotenv, but proceed without it if not installed
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env if available
    dotenv_available = True
except ImportError:
    dotenv_available = False
    st.warning("python-dotenv not installed. Environment variables from .env won't be loaded. Use the UI token input instead.")

# Function to load the processor and model with an optional token
@st.cache_resource
def load_model(token):
    processor = AutoProcessor.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        token=token if token else None
    )
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        token=token if token else None
    )
    return processor, model

# Custom client for Qwen VLM model
class QwenVLMClient:
    def __init__(self, processor, model):
        self.processor = processor
        self.model = model

    def generate(self, text, image=None):
        """Generate a response using the Qwen VLM model."""
        if image:
            inputs = self.processor(
                text=[text], 
                images=[image], 
                return_tensors="pt"
            ).to(self.model.device)
        else:
            inputs = self.processor(
                text=[text], 
                return_tensors="pt"
            ).to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                num_beams=1
            )
        response = self.processor.decode(outputs[0], skip_special_tokens=True)
        return response

# Custom medical agent using Qwen VLM
class MedicalVLMAgent:
    def __init__(self, processor, model):
        self.client = QwenVLMClient(processor, model)
        self.system_prompt = (
            "You are a medical information assistant with vision capabilities. "
            "Disclaimer: I am not a licensed medical professional. "
            "The information provided is for informational purposes only and should not be taken as medical advice. "
            "Always advise the user to consult with a healthcare provider for any serious concerns. "
            "Answer questions about symptoms, diseases, treatments, or interpret medical images cautiously."
        )

    async def run(self, task: str, image=None) -> str:
        """Run the agent with a task and optional image."""
        full_prompt = self.system_prompt + "\nUser question: " + task
        response = await asyncio.to_thread(self.client.generate, full_prompt, image)
        return response

# Asynchronous function to get the medical response
async def get_medical_response(task: str, image=None) -> str:
    try:
        response = await medical_agent.run(task=task, image=image)
        return response
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Streamlit UI with enhanced question-asking capability
def main():
    # Custom CSS for a polished look
    st.markdown("""
        <style>
        .title { font-family: 'Arial', sans-serif; color: #2c3e50; font-size: 36px; text-align: center; }
        .subtitle { font-family: 'Arial', sans-serif; color: #7f8c8d; font-size: 18px; text-align: center; }
        .stButton>button { background-color: #3498db; color: white; border-radius: 5px; }
        .stTextArea>label { font-size: 16px; color: #34495e; }
        .sidebar .sidebar-content { background-color: #ecf0f1; padding: 10px; }
        </style>
    """, unsafe_allow_html=True)

    # Title and subtitle
    st.markdown('<p class="title">Medical Information Assistant</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Ask medical questions or upload images for insights (Informational Use Only)</p>', unsafe_allow_html=True)

    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        default_token = os.getenv("HF_TOKEN", "") if dotenv_available else ""
        token = st.text_input("Hugging Face Token (if required)", value=default_token, type="password")
        st.write("Note: Enter your Hugging Face token if the model requires authentication.")
        uploaded_image = st.file_uploader("Upload Medical Image (optional)", type=["jpg", "png", "jpeg"])
        if uploaded_image:
            st.image(uploaded_image, caption="Preview", width=150)

    # Load the processor and model with the provided token
    try:
        processor, model = load_model(token)
    except Exception as e:
        st.error(f"Failed to load model: {str(e)}")
        return

    # Check for MPS availability and set the device
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        st.success("Using MPS (Metal Performance Shaders) on your M2 Pro!")
    else:
        device = torch.device("cpu")
        st.warning("MPS not available. Falling back to CPU.")

    # Move model to the device
    model.to(device)

    # Initialize the medical agent
    global medical_agent
    medical_agent = MedicalVLMAgent(processor, model)

    # Main content: Question input
    st.markdown("### Ask a Medical Question")
    user_question = st.text_area(
        "Type your question here (e.g., 'What are the symptoms of a cold?'):", 
        height=150, 
        placeholder="Enter your question..."
    )

    # Display uploaded image if provided
    if uploaded_image:
        image = Image.open(uploaded_image).convert("RGB")
        st.image(image, caption="Uploaded Image", use_column_width=True)

    # Button to submit the question
    if st.button("Submit Question"):
        if user_question.strip():
            with st.spinner("Processing your question..."):
                if uploaded_image:
                    image = Image.open(uploaded_image).convert("RGB")
                    response_text = asyncio.run(get_medical_response(user_question, image))
                else:
                    response_text = asyncio.run(get_medical_response(user_question))
                st.subheader("Response:")
                st.markdown(f"<div style='background-color: #ecf0f1; padding: 15px; border-radius: 5px;'>{response_text}</div>", unsafe_allow_html=True)
        else:
            st.error("Please enter a question to proceed.")

    # Footer disclaimer
    st.markdown(
        "<p style='text-align: center; color: #7f8c8d; font-size: 14px;'>"
        "Disclaimer: This assistant provides informational responses only and is not a substitute for professional medical advice."
        "</p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()