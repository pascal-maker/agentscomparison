import streamlit as st
import os
import sys
import torch
import tempfile
import uuid
import base64
import numpy as np
from PIL import Image

# ---------------------------
# Fix Python path to detect local sam2 directory
sys.path.append(os.path.abspath("."))

# ---------------------------
# Qwen VLM Imports
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# ---------------------------
# SAM2 Imports – if installed
try:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False

# ---------------------------
# Ensure torch.classes.__path__ is defined
torch.classes.__path__ = []

# ---------------------------
# Disable Streamlit file-watcher warnings
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# ---------------------------
@st.cache_resource(show_spinner=False)
def load_qwen_model_and_processor(hf_token=None):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    st.write(f"Using device for Qwen: {device}")

    auth_kwargs = {}
    if hf_token and hf_token.strip():
        auth_kwargs["use_auth_token"] = hf_token

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        trust_remote_code=True,
        attn_implementation="eager",
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
        device_map=None,
        **auth_kwargs
    )
    model.to(device)

    processor = AutoProcessor.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        trust_remote_code=True,
        **auth_kwargs
    )

    return model, processor, device

# ---------------------------
class MedicalVLMAgent:
    def __init__(self, model, processor, device):
        self.model = model
        self.processor = processor
        self.device = device
        self.system_prompt = (
            "You are a medical information assistant with vision capabilities. "
            "Disclaimer: I am not a licensed medical professional. "
            "The information provided is for reference only and should not be taken as medical advice. "
            "If you have serious concerns, consult a healthcare provider."
        )

    def run(self, user_text: str, image: Image.Image = None) -> str:
        messages = [{
            "role": "system",
            "content": [{"type": "text", "text": self.system_prompt}]
        }]

        user_content = []
        if image:
            temp_filename = f"/tmp/{uuid.uuid4()}.png"
            image.save(temp_filename)
            user_content.append({"type": "image", "image": temp_filename})
        if not user_text.strip():
            user_text = "Please describe the image or provide some medical context."
        user_content.append({"type": "text", "text": user_text})
        messages.append({"role": "user", "content": user_content})

        text_prompt = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text_prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )
        inputs = inputs.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=128)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_texts = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return output_texts[0] if output_texts else "**No output text was generated.**"

# ---------------------------
@st.cache_resource(show_spinner=False)
def load_sam2_predictor():
    if not SAM2_AVAILABLE:
        return None
    try:
        predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
        return predictor
    except Exception as e:
        st.error(f"Error loading SAM2 predictor: {e}")
        return None

# ---------------------------
def main():
    st.title("Medical Qwen VLM & SAM2 Integration")
    st.markdown("<p style='text-align: center;'>Choose between Medical Q&A and Tumor Segmentation</p>", unsafe_allow_html=True)

    hf_token = st.sidebar.text_input("Enter your HF token (if needed)", type="password")
    task = st.sidebar.radio("Select Task", ["Medical Q&A with Qwen VLM", "Tumor Segmentation with SAM2"])
    uploaded_file = st.sidebar.file_uploader("Upload an image", type=["jpg", "png", "jpeg"])

    if task == "Medical Q&A with Qwen VLM":
        model, processor, device = load_qwen_model_and_processor(hf_token)
        agent = MedicalVLMAgent(model, processor, device)

        user_question = st.text_area("Ask a medical question or describe symptoms:")
        if uploaded_file:
            image = Image.open(uploaded_file).convert("RGB")
            st.image(image, caption="Uploaded Image", width=None)
        else:
            image = None

        if st.button("Submit Q&A"):
            with st.spinner("Generating response..."):
                response = agent.run(user_question, image)
                st.markdown("### Response:")
                st.write(response)

    elif task == "Tumor Segmentation with SAM2":
        if not SAM2_AVAILABLE:
            st.error("SAM2 is not installed or failed to import.")
            return

        predictor = load_sam2_predictor()
        if uploaded_file is None:
            st.warning("Please upload an image for segmentation.")
            return

        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="Uploaded Image", width=None)
        image_np = np.array(image)

        prompt_input = st.text_input("Enter coordinate prompts (format: x,y or x1,y1; x2,y2)", value="")

        if prompt_input.strip():
            try:
                prompt_list = [
                    [int(coord.strip()) for coord in point.split(",")]
                    for point in prompt_input.split(";") if point.strip()
                ]
            except Exception as e:
                st.error(f"Error parsing coordinate prompts: {e}")
                prompt_list = []
        else:
            prompt_list = []

        st.markdown(f"Using coordinate prompts: {prompt_list}" if prompt_list else "No coordinate prompts provided; using automatic segmentation.")

        if st.button("Run SAM2 Segmentation"):
            try:
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    predictor.set_image(image_np)
                    masks, _, _ = predictor.predict(input_prompts=prompt_list)
                    output_image = predictor.plot()
                segmented_image = Image.fromarray(output_image)
                st.image(segmented_image, caption="Segmented Output", width=None)
            except Exception as e:
                st.error(f"SAM2 Prediction Error: {e}")

if __name__ == "__main__":
    main()
