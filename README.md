# Agents Comparison

A hands-on comparison of AI agent frameworks, all built around the same use case: a **Luminus energy customer support assistant**. Each framework tackles billing queries, energy-saving advice, appointment booking, and multi-agent orchestration in its own way.

## Shared Harness

The canonical Luminus fixtures, instructions, billing explanation, advice text, and appointment proposal behavior live in `luminus_harness/`. Framework demos should adapt to that module instead of redefining their own customer data. This keeps the comparison stable: when `LUM-1001` changes, every demo sees the same scenario.

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
pip install -r requirements/openai-agents.txt

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
pip install -r requirements/autogen.txt
python medicautogenapp.py
```

---

### HuggingFace smolagents (`agentsfromhuggingface.py`)

Lightweight `CodeAgent` with custom system prompts for billing, insights, and advice. Each agent processes the query individually, then an aggregator agent combines outputs. Minimal, fast, and LLM-agnostic.

```bash
pip install -r requirements/smolagents.txt
python agentsfromhuggingface.py
```

---

### Swarm (`luminusswarmagent.py`)

Experimental framework for ergonomic multi-agent handoffs and routines. Agents transfer conversation control based on the task at hand. Educational, not production-ready.

```bash
pip install -r requirements/swarm.txt
python luminusswarmagent.py
```

---

### PydanticAI (`pydanticenegryassistant.py`)

Type-safe support agent with dependency injection and Pydantic models for structured, validated responses. Ensures responses adhere to a predefined schema.

```bash
pip install -r requirements/pydantic-ai.txt
python pydanticenegryassistant.py
```

---

### Agno (`agnoagents.py`)

Agent framework demo for energy assistant use case.

```bash
pip install -r requirements/agno.txt
python agnoagents.py
```

---

### Mem0 (`mem0agents.py`, `mem0Energyassistant.py`)

Agents with persistent memory for energy assistant interactions.

```bash
pip install -r requirements/mem0.txt
python mem0Energyassistant.py
```

---

### Google Gemini (`geminiagents.py`, `gemini_mcp_agent.py`)

Command-line energy advisor powered by Gemini AI. Also includes an MCP-enabled Gemini agent.

```bash
pip install -r requirements/gemini.txt
python geminiagents.py
```

---

### DeepSeek (`deepseekenergyagent.py`)

Energy assistant using the DeepSeek model.

```bash
pip install -r requirements/text-models.txt
python deepseekenergyagent.py
```

---

### Qwen (`qwenagent.py`, `qwensam2agent.py`)

Qwen-VLM for medical Q&A combined with SAM-2 for image segmentation. Includes a Gradio web interface.

```bash
pip install -r requirements/vision-medical.txt
pip install -e sam2
python qwensam2agent.py
```

---

### Vercel / eve (`my-agent/`)

A [Vercel-deployable eve agent](https://eve.dev) for the Luminus use case. Each capability is a typed tool auto-discovered from `agent/tools/` (`get_billing`, `energy_saving_tips`, `book_appointment`), backed by a shared `agent/lib/energy_db.ts`. The appointment tool is gated with `approval: always()` to demonstrate durable human-in-the-loop. The persona lives in `agent/instructions.md`.

```bash
cd my-agent
npm install
npm run dev   # opens the eve dev TUI; ask "My account is LUM-1001, why is my bill high?"
```

---

### Agent Laboratory (`agentlaboratory_energy.py`)

Reuses [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory)'s unified `query_model()` interface to drive a small team of specialized support agents — a `SupportManager` routes the query to a `BillingAnalyst`, `EnergyAdvisor`, and/or `AppointmentAgent`. Multi-agent orchestration in Agent Laboratory's own agent style, applied to customer support instead of research.

```bash
export OPENAI_API_KEY="your-key"
pip install -r requirements/agent-lab-energy.txt
python agentlaboratory_energy.py
python agentlaboratory_energy.py --query "Why was my bill so high?" --customer LUM-1002
```

---

### TinyAGI (`tinyagi_energy/`)

A drop-in [TinyAGI](https://github.com/TinyAGI/tinyagi) team configuration (config + skills, not a single script). A `support` front-desk agent fans work out to `billing`, `advisor`, and `scheduler` teammates via `[@agent_id: ...]`, using the `luminus-energy` skill whose `energy.sh` script simulates the billing backend. Runs as a 24/7 multi-channel daemon.

```bash
# Try the tool layer directly — no daemon required:
tinyagi_energy/skills/luminus-energy/scripts/energy.sh billing LUM-1001
tinyagi_energy/skills/luminus-energy/scripts/energy.sh advice LUM-1002 heating
# Full setup: see tinyagi_energy/README.md
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
# Pick the demo you want. For example:
pip install -r requirements/openai-agents.txt

# See the full matrix:
cat requirements/README.md
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
- **Vercel / eve** — typed tools, durable human-in-the-loop approvals, one-command deploy to Vercel
- **Agent Laboratory** — research-grade multi-agent orchestration with a unified multi-provider model interface
- **TinyAGI** — config-driven 24/7 multi-agent teams across Discord/Telegram/WhatsApp

## Security

Never commit API keys to version control. Always use environment variables.
