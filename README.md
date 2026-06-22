# Agents Comparison

A hands-on comparison of AI agent frameworks, all built around the same use case: a **Luminus energy customer support assistant**. Each framework tackles billing queries, energy-saving advice, appointment booking, and multi-agent orchestration in its own way.

## Frameworks

### OpenAI Agents SDK (`openai/demo.py`)

The most comprehensive demo with 12 patterns covering the full SDK surface:

| # | Pattern | Description |
|---|---------|-------------|
| 1 | Basic Agent | Simple one-shot Q&A |
| 2 | Function Tools | Agent calls billing and energy-saving tools |
| 3 | Multi-Agent Handoffs | Routes to appointment booking specialist |
| 4 | Streaming | Real-time event-by-event response streaming |
| 5 | Multi-Turn Conversation | Stateful history via `to_input_list()` |
| 6 | Persistent Session | SQLiteSession for durable cross-run memory |
| 7 | LLM-as-a-Judge | Evaluator loop that critiques and improves responses |
| 8 | Agents as Tools | Manager orchestrates billing analyst + energy advisor as sub-agents |
| 9 | Guardrails | Input guardrail blocks competitor energy provider questions |
| 10 | Human in the Loop | Approval gate for plan switches and meter replacements |
| 11 | Interactive Chat | Full-featured conversational loop combining all patterns |
| 12 | Voice Agent | Microphone input, speech-to-text, agent, text-to-speech, speaker output |

```bash
pip install openai-agents 'openai-agents[voice]' sounddevice

# Run a specific demo
python openai/demo.py --demo 8

# Interactive chat (type your own questions)
python openai/demo.py --chat

# Voice agent (speak into your mic)
python openai/demo.py --demo 12

# Run all scripted demos
python openai/demo.py
```

---

### Microsoft AutoGen (`medicautogenapp.py`, `luminusagents.py`)

Multi-agent system using `AssistantAgent` subclasses for billing, energy insights, and energy advice. Orchestrated with `RoundRobinGroupChat` to simulate a team conversation answering multi-part customer queries.

```bash
pip install autogen-agentchat autogen-ext
python medicautogenapp.py
```

---

### HuggingFace smolagents (`agentsfromhuggingface.py`)

Lightweight `CodeAgent` with custom system prompts for billing, insights, and advice. Each agent processes the query individually, then an aggregator agent combines outputs. Minimal, fast, and LLM-agnostic.

```bash
pip install smolagents
python agentsfromhuggingface.py
```

---

### Swarm (`luminusswarmagent.py`)

Experimental framework for ergonomic multi-agent handoffs and routines. Agents transfer conversation control based on the task at hand. Educational, not production-ready.

```bash
python luminusswarmagent.py
```

---

### PydanticAI (`pydanticenegryassistant.py`)

Type-safe support agent with dependency injection and Pydantic models for structured, validated responses. Ensures responses adhere to a predefined schema.

```bash
pip install pydantic-ai
python pydanticenegryassistant.py
```

---

### Agno (`agnoagents.py`)

Agent framework demo for energy assistant use case.

```bash
pip install agno
python agnoagents.py
```

---

### Mem0 (`mem0agents.py`, `mem0Energyassistant.py`)

Agents with persistent memory for energy assistant interactions.

```bash
pip install mem0ai
python mem0Energyassistant.py
```

---

### Google Gemini (`geminiagents.py`, `gemini_mcp_agent.py`)

Command-line energy advisor powered by Gemini AI. Also includes an MCP-enabled Gemini agent.

```bash
pip install google-generativeai
python geminiagents.py
```

---

### DeepSeek (`deepseekenergyagent.py`)

Energy assistant using the DeepSeek model.

```bash
python deepseekenergyagent.py
```

---

### Qwen (`qwenagent.py`, `qwensam2agent.py`)

Qwen-VLM for medical Q&A combined with SAM-2 for image segmentation. Includes a Gradio web interface.

```bash
python qwensam2agent.py
```

---

## Setup

1. Clone the repo:
```bash
git clone https://github.com/pascal-maker/agentscomparison.git
cd agentscomparison
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your API keys:
```bash
export OPENAI_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
```

## Key Takeaways

Each framework brings unique strengths:

- **OpenAI Agents SDK** — most complete: tools, handoffs, guardrails, human-in-the-loop, voice, sessions, all in one SDK
- **AutoGen** — best for structured multi-agent team conversations with robust orchestration
- **smolagents** — simplest and fastest to get started, pure Python
- **Swarm** — great for learning handoff patterns
- **PydanticAI** — best for type safety and structured/validated outputs
- **Gemini** — strong multimodal capabilities
- **Mem0** — unique persistent memory across conversations

## Security

Never commit API keys to version control. Always use environment variables.
