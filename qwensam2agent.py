import io
import os
import sys
import uuid
import base64
import tempfile
import torch
import numpy as np
import streamlit as st
import requests
from PIL import Image, ImageDraw
from transformers import  Qwen2_5_VLForConditionalGeneration, AutoProcessor



# ------------------------------------------------------
# Streamlit Demo for Medical Qwen VLM & SAM2 Integration
# ------------------------------------------------------
# Fix Python path to detect local SAM2 directory.
sys.path.append(os.path.abspath("."))

# ---------------------------
# Qwen VLM Imports and utility
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

@st.cache_resource(show_spinner=False)
def load_qwen_model_and_processor(hf_token=None):
    device_qwen = "mps" if torch.backends.mps.is_available() else "cpu"
    st.write(f"Using device for Qwen: {device_qwen}")
    auth_kwargs = {}
    if hf_token and hf_token.strip():
        auth_kwargs["use_auth_token"] = hf_token
    model_qwen = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        trust_remote_code=True,
        attn_implementation="eager",
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
        device_map=None,
        **auth_kwargs
    )
    model_qwen.to(device_qwen)
    processor = AutoProcessor.from_pretrained(
        "Qwen/Qwen2.5-VL-3B-Instruct",
        trust_remote_code=True,
        **auth_kwargs
    )
    return model_qwen, processor, device_qwen

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

def main():
    st.title("Medical Qwen VLM, SAM2 & ")
    st.markdown("<p style='text-align: center;'>Choose between, Medical Q&A, and Tumor Segmentation</p>", unsafe_allow_html=True)

    hf_token = st.sidebar.text_input("Enter your HF token (if needed)", type="password")
    task = st.sidebar.radio("Select Task", [
        "Medical Q&A with Qwen VLM", 
        "Tumor Segmentation with SAM2"
    ])

   
    # ---------------------------
    # Medical Q&A with Qwen VLM Task
    if task == "Medical Q&A with Qwen VLM":
        model_qwen, processor, device_qwen = load_qwen_model_and_processor(hf_token)
        agent = MedicalVLMAgent(model_qwen, processor, device_qwen)
        st.subheader("Medical Q&A with Qwen VLM")
        user_question = st.text_area("Ask a medical question or describe symptoms:")
        uploaded_file = st.file_uploader("Upload an image (optional)", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            image = Image.open(uploaded_file).convert("RGB")
            st.image(image, caption="Uploaded Image")
        else:
            image = None
        if st.button("Submit Q&A"):
            with st.spinner("Generating response..."):
                response = agent.run(user_question, image)
                st.markdown("### Response:")
                st.write(response)

    # ---------------------------
    # Tumor Segmentation with SAM2 Task
    elif task == "Tumor Segmentation with SAM2":
        if not SAM2_AVAILABLE:
            st.error("SAM2 is not installed or failed to import.")
            return
        predictor = load_sam2_predictor()
        uploaded_file = st.file_uploader("Upload an image for segmentation", type=["jpg", "png", "jpeg"])
        if not uploaded_file:
            st.warning("Please upload an image for segmentation.")
            return
        st.subheader("Tumor Segmentation with SAM2")
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="Uploaded Image")
        image_np = np.array(image)
        st.markdown("Draw bounding boxes on the uploaded image using format: `x1,y1,x2,y2` (one per line, ensuring x1 < x2 and y1 < y2).")
        bbox_input = st.text_area("Bounding boxes (one per line):", value="")
        bbox_list = []
        if bbox_input.strip():
            try:
                lines = bbox_input.strip().split("\n")
                for line in lines:
                    coords = [int(p.strip()) for p in line.split(",")]
                    if len(coords) == 4:
                        x1, y1, x2, y2 = coords
                        if x2 < x1:
                            x1, x2 = x2, x1
                        if y2 < y1:
                            y1, y2 = y2, y1
                        bbox_list.append([x1, y1, x2, y2])
            except Exception as e:
                st.error(f"Error parsing bounding boxes: {e}")
        st.markdown(f"Using bounding boxes: {bbox_list}" if bbox_list else "No bounding boxes provided; using automatic segmentation.")
        if st.button("Run SAM2 Segmentation"):
            try:
                with torch.inference_mode(), torch.autocast("mps", dtype=torch.float32):
                    predictor.set_image(image_np)
                    masks, _, _ = predictor.predict(input_prompts=bbox_list)
                    output_image = predictor.plot()
                segmented_image = Image.fromarray(output_image)
                st.image(segmented_image, caption="Segmented Output")
            except Exception as e:
                st.error(f"SAM2 Prediction Error: {e}")

if __name__ == "__main__":
    main()