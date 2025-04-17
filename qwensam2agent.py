import os
import sys
import io
import uuid
import base64
import tempfile
from threading import Thread

import torch
import numpy as np
from PIL import Image, ImageDraw
import gradio as gr

# Add the current directory to sys.path to detect local SAM2 if present
sys.path.append(os.path.abspath("."))

# ---------------------------
# Qwen VLM Imports and utilities
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# ---------------------------
# SAM2 Imports – try local clone first, then fallback to segment_anything
try:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
    print("SAM2 imported successfully from local './sam2' clone.")
except ImportError as e_local:
    # If sam2 folder exists, add to path for segment_anything subpackage
    sam2_dir = os.path.join(os.path.abspath("."), "sam2")
    if os.path.isdir(sam2_dir):
        sys.path.insert(0, sam2_dir)
    try:
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
        import torch as _torch, numpy as _np

        # Wrap segment_anything into SAM2ImagePredictor interface
        class SAM2ImagePredictor:
            """
            Wrapper around segment_anything's AutomaticMaskGenerator to match SAM2ImagePredictor API.
            """
            @classmethod
            def from_pretrained(cls, pretrained_model_name_or_path=None):
                device = _torch.device("cuda" if _torch.cuda.is_available() else "cpu")
                model_type = "vit_h"
                checkpoint = (
                    pretrained_model_name_or_path
                    if pretrained_model_name_or_path and pretrained_model_name_or_path.endswith(".pth")
                    else None
                )
                sam = sam_model_registry[model_type](checkpoint=checkpoint).to(device)
                mask_generator = SamAutomaticMaskGenerator(sam)
                return cls(sam, mask_generator)

            def __init__(self, sam_model, mask_generator):
                self.sam = sam_model
                self.mask_generator = mask_generator
                self.image = None

            def set_image(self, image_np):
                self.image = image_np

            def predict(self, input_prompts=None):  # pylint: disable=unused-argument
                masks = self.mask_generator.generate(self.image)
                return masks, None, None

            def plot(self):
                img = self.image
                if img.ndim == 2:
                    rgb = _np.stack([img] * 3, axis=2)
                elif img.ndim == 3 and img.shape[2] == 3:
                    rgb = img.copy()
                else:
                    rgb = img[..., :3].copy()
                for mask in self.mask_generator.generate(self.image):
                    m = mask.get("segmentation")
                    if m is None:
                        continue
                    color = _np.random.randint(0, 255, 3, dtype=_np.uint8)
                    rgb[m] = (rgb[m] * 0.5 + color * 0.5).astype(_np.uint8)
                return rgb

        SAM2_AVAILABLE = True
        print("SAM2 imported successfully via segment_anything fallback.")
    except ImportError:
        SAM2_AVAILABLE = False
        print(
            f"SAM2 import failed: {e_local}. To enable SAM2 segmentation, "
            "clone the facebookresearch/sam2 repo into './sam2' or install segment-anything from PyPI."
        )

# ---------------------------
# CheXagent Imports
from transformers import AutoTokenizer, AutoModelForCausalLM, TextIteratorStreamer

# ---------------------------
# Helper: Device determination for segmentation and CheXagent
def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    else:
        return torch.device("cpu")

# ---------------------------
# Qwen Model Loading
_qwen_model = None
_qwen_processor = None
_qwen_device = None

def load_qwen_model_and_processor(hf_token=None):
    global _qwen_model, _qwen_processor, _qwen_device
    if _qwen_model is None:
        _qwen_device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"Using device for Qwen: {_qwen_device}")
        auth_kwargs = {}
        if hf_token and hf_token.strip():
            auth_kwargs["use_auth_token"] = hf_token
        _qwen_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2.5-VL-3B-Instruct",
            trust_remote_code=True,
            attn_implementation="eager",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
            device_map=None,
            **auth_kwargs
        )
        _qwen_model.to(_qwen_device)
        _qwen_processor = AutoProcessor.from_pretrained(
            "Qwen/Qwen2.5-VL-3B-Instruct",
            trust_remote_code=True,
            **auth_kwargs
        )
    return _qwen_model, _qwen_processor, _qwen_device

# ---------------------------
# Medical Q&A Agent definition
class MedicalVLMAgent:
    def __init__(self, model, processor, device):
        self.model = model
        self.processor = processor
        self.device = device
        self.system_prompt = (
            "You are a medical information assistant with vision capabilities and understanding. "
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

# Initialize Qwen and the medical agent (you can pass your HF token if needed)
qwen_model, qwen_processor, qwen_device = load_qwen_model_and_processor(hf_token=None)
medical_agent = MedicalVLMAgent(qwen_model, qwen_processor, qwen_device)

# ---------------------------
# SAM2 Predictor Loading
_sam2_predictor = None
def load_sam2_predictor():
    global _sam2_predictor
    if not SAM2_AVAILABLE:
        return None
    if _sam2_predictor is None:
        try:
            _sam2_predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2-hiera-large")
        except Exception as e:
            print(f"Error loading SAM2 predictor: {e}")
            _sam2_predictor = None
    return _sam2_predictor

sam2_predictor = load_sam2_predictor()

# ---------------------------
# CheXagent Model Loading
chexagent_model_name = "StanfordAIMI/CheXagent-2-3b"
chexagent_tokenizer = AutoTokenizer.from_pretrained(chexagent_model_name, trust_remote_code=True)
chexagent_model = AutoModelForCausalLM.from_pretrained(
    chexagent_model_name,
    device_map="auto",
    trust_remote_code=True
)
if torch.cuda.is_available():
    chexagent_model = chexagent_model.half()
else:
    chexagent_model = chexagent_model.float()
chexagent_model = chexagent_model.eval()

def get_model_device(model):
    for param in model.parameters():
        return param.device
    return torch.device("cpu")

# ---------------------------
# CheXagent Functions
def print_and_write(text):
    print(text)
    with open("log.txt", "at") as f:
        f.write(text)

def clean_text(text):
    return text.replace("</s>", "")

@torch.no_grad()
def response_report_generation(pil_image_1, pil_image_2):
    streamer = TextIteratorStreamer(chexagent_tokenizer, skip_prompt=True, skip_special_tokens=True)
    paths = []
    if pil_image_1 is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
        pil_image_1.save(temp_path)
        paths.append(temp_path)
    if pil_image_2 is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
        pil_image_2.save(temp_path)
        paths.append(temp_path)

    model_device = get_model_device(chexagent_model)
    anatomies = [
        "Airway", "Breathing", "Cardiac",
        "Diaphragm",
        "Everything else (e.g., mediastinal contours, bones, soft tissues, tubes, valves, and pacemakers)"
    ]
    prompts = [f'Please provide a detailed description of "{anatomy}" in the chest X-ray' for anatomy in anatomies]
    anatomies = ["View"] + anatomies
    prompts = ["Determine the view of this CXR"] + prompts

    findings = ""
    partial_message = "## Generating Findings (step-by-step):\n\n"
    for anatomy_idx, (anatomy, prompt) in enumerate(zip(anatomies, prompts)):
        query = chexagent_tokenizer.from_list_format([*[{'image': path} for path in paths], {'text': prompt}])
        conv = [{"from": "system", "value": "You are a helpful assistant."},
                {"from": "human", "value": query}]
        input_ids = chexagent_tokenizer.apply_chat_template(conv, add_generation_prompt=True, return_tensors="pt")
        generate_kwargs = dict(
            input_ids=input_ids.to(model_device),
            do_sample=False,
            num_beams=1,
            temperature=1,
            top_p=1.0,
            use_cache=True,
            max_new_tokens=512,
            streamer=streamer
        )
        t = Thread(target=chexagent_model.generate, kwargs=generate_kwargs)
        t.start()
        partial_message += f'**Step {anatomy_idx}: Analyzing {anatomy}...**\n\n'
        for new_token in streamer:
            if anatomy_idx != 0:
                findings += new_token
            partial_message += new_token
            yield clean_text(partial_message)
        partial_message += "\n\n"
        findings += " "
    findings = findings.strip().replace("</s>", "")

    # Step 2: Impression Generation
    impression = ""
    partial_message += "## Generating Impression\n\n"
    prompt = f'Write the Impression section for the following Findings: {findings}'
    query = chexagent_tokenizer.from_list_format([{'text': prompt}])
    conv = [{"from": "system", "value": "You are a helpful assistant."},
            {"from": "human", "value": query}]
    input_ids = chexagent_tokenizer.apply_chat_template(conv, add_generation_prompt=True, return_tensors="pt")
    generate_kwargs = dict(
        input_ids=input_ids.to(model_device),
        do_sample=False,
        num_beams=1,
        temperature=1,
        top_p=1.0,
        use_cache=True,
        repetition_penalty=1.0,
        max_new_tokens=512,
        streamer=streamer
    )
    t = Thread(target=chexagent_model.generate, kwargs=generate_kwargs)
    t.start()
    for new_token in streamer:
        impression += new_token
        partial_message += new_token
        yield clean_text(partial_message)
    partial_message += "\n\n"
    impression = impression.strip().replace("</s>", "")
    print_and_write(f"Findings: {findings}\n")
    print_and_write(f"Impression: {impression}\n")

@torch.no_grad()
def response_phrase_grounding(pil_image, text):
    streamer = TextIteratorStreamer(chexagent_tokenizer, skip_prompt=True, skip_special_tokens=True)
    if pil_image is not None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
        pil_image.save(temp_path)
        paths = [temp_path]
    else:
        paths = []

    model_device = get_model_device(chexagent_model)
    query = chexagent_tokenizer.from_list_format([*[{'image': path} for path in paths], {'text': text}])
    conv = [{"from": "system", "value": "You are a helpful assistant."},
            {"from": "human", "value": query}]
    input_ids = chexagent_tokenizer.apply_chat_template(conv, add_generation_prompt=True, return_tensors="pt")
    generate_kwargs = dict(
        input_ids=input_ids.to(model_device),
        do_sample=False,
        num_beams=1,
        temperature=1,
        top_p=1.0,
        use_cache=True,
        max_new_tokens=512,
        streamer=streamer
    )
    t = Thread(target=chexagent_model.generate, kwargs=generate_kwargs)
    t.start()
    response = ""
    partial_message = f"## User:\n{text}\n\n## CheXagent:\n"
    for new_token in streamer:
        partial_message += new_token
        response += new_token
        yield partial_message.replace("</s>", ""), None
    partial_message += "\n\n"

    print_and_write(f"Response: {partial_message}\n")
    # Example: parse boxes and draw them (if provided in the output)
    boxes = [entry["box"] for entry in chexagent_tokenizer.to_list_format(response) if "box" in entry]
    boxes = [[int(cord) / 100 for cord in box.replace("(", "").replace(")", "").split(",")] for box in boxes]
    w, h = pil_image.width, pil_image.height
    draw = ImageDraw.Draw(pil_image)
    for box in boxes:
        draw.rectangle((box[0] * w, box[1] * h, box[2] * w, box[3] * h), width=10, outline="#FF6969")
    yield partial_message, pil_image.convert("RGB")

# ---------------------------
# Gradio interface functions for our tasks
def medical_qa_interface(question, image):
    response = medical_agent.run(question, image)
    return response

def tumor_segmentation_interface(image, bbox_text):
    error_msg = ""
    if image is None:
        return None, "Please upload an image for segmentation."
    image_np = np.array(image)
    bbox_list = []
    if bbox_text.strip():
        try:
            for line in bbox_text.splitlines():
                coords = [int(x.strip()) for x in line.split(",")]
                if len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    if x2 < x1:
                        x1, x2 = x2, x1
                    if y2 < y1:
                        y1, y2 = y2, y1
                    bbox_list.append([x1, y1, x2, y2])
        except Exception as e:
            error_msg = f"Error parsing bounding boxes: {e}"
            return None, error_msg
    if sam2_predictor is None:
        error_msg = (
            "SAM2 predictor is not available. To enable segmentation, "
            "clone the facebookresearch/sam2 repo into './sam2' or install the segment-anything package."
        )
        return None, error_msg
    try:
        device_seg = "mps" if torch.backends.mps.is_available() else "cpu"
        with torch.inference_mode(), torch.autocast(device_seg, dtype=torch.float32):
            sam2_predictor.set_image(image_np)
            # If bounding boxes provided, use them; otherwise run automatic mask generation
            if bbox_list:
                masks, _, _ = sam2_predictor.predict(input_prompts=bbox_list)
            else:
                masks, _, _ = sam2_predictor.predict()
            output_image = sam2_predictor.plot()
        segmented_image = Image.fromarray(output_image)
        return segmented_image, ""
    except Exception as e:
        error_msg = f"SAM2 Prediction Error: {e}"
        return None, error_msg

# ---------------------------
# Build the Gradio App
with gr.Blocks() as demo:
    gr.Markdown("# Combined Medical & CheXagent Demo")
    gr.Markdown("This demo integrates Medical Q&A with Qwen VLM, Tumor Segmentation with SAM2, and CheXagent functionalities.")

    with gr.Tab("Medical Q&A with Qwen VLM"):
        with gr.Row():
            question_input = gr.Textbox(label="Medical Question / Description", placeholder="Enter your question or describe symptoms...", lines=3)
            image_input = gr.Image(label="Upload Image (optional)", type="pil")
        qa_button = gr.Button("Submit Q&A")
        qa_output = gr.Textbox(label="Response")
        qa_button.click(fn=medical_qa_interface, inputs=[question_input, image_input], outputs=qa_output)

    if SAM2_AVAILABLE:
        with gr.Tab("Tumor Segmentation with SAM2"):
            with gr.Row():
                seg_image_input = gr.Image(label="Upload Image for Segmentation", type="pil")
            bbox_input = gr.Textbox(label="Bounding Boxes", placeholder="Enter one bounding box per line as x1,y1,x2,y2")
            seg_button = gr.Button("Run SAM2 Segmentation")
            seg_image_output = gr.Image(label="Segmented Output", type="pil")
            seg_error_output = gr.Textbox(label="Status / Error Message")
            seg_button.click(fn=tumor_segmentation_interface, inputs=[seg_image_input, bbox_input],
                             outputs=[seg_image_output, seg_error_output])
    else:
        with gr.Tab("Tumor Segmentation with SAM2"):
            gr.Markdown("SAM2 predictor is not available. Please install SAM2 to enable tumor segmentation functionality.")

    with gr.Tab("Structured Report Generation (CheXagent)"):
        gr.Markdown("Upload one or two images and wait for the report to stream in.")
        with gr.Row():
            chex_image1 = gr.Image(label="Input Image 1", image_mode="L", type="pil")
            chex_image2 = gr.Image(label="Input Image 2", image_mode="L", type="pil")
        chex_report = gr.Markdown(label="Structured Report")
        # Use streaming output because the function yields output over time.
        gr.Interface(fn=response_report_generation, inputs=[chex_image1, chex_image2],
                     outputs=chex_report, live=True).render()

    with gr.Tab("Visual Grounding (CheXagent)"):
        gr.Markdown("Upload an image and provide a text prompt for visual grounding.")
        with gr.Row():
            vg_image = gr.Image(label="Input Image", image_mode="L", type="pil")
            vg_text = gr.Textbox(label="Prompt", value="Please locate the following phrase:")
        vg_markdown = gr.Markdown(label="Response")
        vg_image_out = gr.Image(label="Visual Grounding Output", type="pil")
        gr.Interface(fn=response_phrase_grounding, inputs=[vg_image, vg_text],
                     outputs=[vg_markdown, vg_image_out], live=True).render()

demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
