---
title: medical-imaging-analysis
emoji: 🏥
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.19.2
app_file: qwensam2agent.py
pinned: false
---

# Medical Imaging Analysis

This application combines multiple AI models for medical image analysis:
- Qwen-VLM for medical Q&A
- SAM-2 for automatic image segmentation
- CheXagent for structured medical reports

## Features
- Medical Q&A with image support
- Automatic image segmentation
- Structured medical report generation
- Visual grounding capabilities

---

**AutoGen**  
We built a robust multi-agent system by subclassing `AssistantAgent` to create specialized agents for billing, energy insights, and energy advice. These agents were orchestrated using a `RoundRobinGroupChat` to simulate a team conversation that answers a multi-part customer query—ensuring the customer is addressed by name and data privacy is maintained.

---

**smolagents**  
Using the lightweight `CodeAgent`, we defined agents with custom system prompts for billing, insights, and advice. Each agent processes the customer query individually, and their outputs are later aggregated by an aggregator agent. This approach demonstrated how a minimal, fast, and LLM-agnostic solution can be implemented in pure Python.

---

**Swarm (Experimental)**  
We explored Swarm to understand ergonomic multi-agent handoffs and routines. In this educational framework, agents are designed to transfer conversation control among themselves based on the task at hand. Although not production-ready, it showcased how to model multi-step interactions and agent collaboration in a lightweight, client-side system.

---

**PydanticAI (Beta)**  
PydanticAI was used to prototype a type-safe support agent that leverages dependency injection and Pydantic models for structured, validated responses. This approach ensures that responses adhere to a predefined schema, adding a layer of data integrity and security to the solution.

---

**ai-gradio**  
We deployed an interactive multi-modal interface using ai-gradio, which is built on Gradio. This framework allowed us to quickly create and launch web interfaces for text (and potentially voice or video) interactions with the AI models, demonstrating a user-friendly way to interact with our agents across different channels.

---

Each framework brought its unique strengths—from AutoGen's robust orchestration to smolagents' simplicity, Swarm's educational handoff patterns, PydanticAI's structured responses, and ai-gradio's interactive deployment—illustrating diverse approaches to building a comprehensive, multimodal energy assistant for Luminus. Personally speaking Microsoft Autogen was the best in this simple case it provided the user with input questions and it asnwered queries perfectly even when mispelling sentences.

# Energy Assistant with Gemini AI

A command-line energy advisor powered by Google's Gemini AI that helps users with:
- Energy usage analysis
- Billing explanations
- Energy-saving tips
- Cost estimates

## Setup

1. Install dependencies:
```bash
pip install google-generativeai
```

2. Set up your Google API key:
```bash
export GOOGLE_API_KEY='your-api-key-here'
```

## Usage

Run the script:
```bash
python geminiagents.py
```

Type your energy-related questions and get AI-powered advice. Type 'exit' to quit.

## Features

- Real-time energy advice
- Personalized recommendations
- Cost calculations
- Usage analysis
- Energy-saving tips

## Security Note

Never commit your API key to version control. Always use environment variables to store sensitive information.
