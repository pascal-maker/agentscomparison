# Agents Comparison

Compare AI agent frameworks on the same customer-support task.

This repo uses a fictional **Luminus energy customer support assistant** as the shared benchmark. Every serious demo should answer the same kinds of questions: why a bill changed, how a customer can reduce usage, and when a technician appointment should be proposed.

The current direction of the repo is: one shared scenario harness, many framework adapters.

## Quick Start

Run the deterministic comparison first. It does not require API keys or paid model calls.

```bash
git clone https://github.com/pascal-maker/agentscomparison.git
cd agentscomparison

python compare.py --scenario high_bill
```

Run another scenario:

```bash
python compare.py --scenario appliance_savings
python compare.py --scenario meter_visit
```

Limit the comparison to one adapter:

```bash
python compare.py --scenario high_bill --adapter harness
python compare.py --scenario high_bill --adapter tinyagi
```

## What Works Today

The deterministic comparison runner currently compares:

| Adapter | Backing implementation | Requires API key | Notes |
| --- | --- | --- | --- |
| `harness` | `luminus_harness/` Python module | No | Canonical source of truth |
| `tinyagi` | `tinyagi_energy/.../energy.sh` | No | Shell adapter that delegates to the harness CLI |

The live framework demos are still useful, but they are demos, not yet all wired into `compare.py`.

## Shared Harness

The canonical data and behavior live in `luminus_harness/`:

- customer fixtures: `LUM-1001`, `LUM-1002`, `LUM-1003`
- shared support instructions
- billing explanations
- energy-saving advice
- appointment proposal behavior
- comparison scenarios

Use the harness directly:

```bash
python -m luminus_harness billing LUM-1001
python -m luminus_harness advice LUM-1002 appliances
python -m luminus_harness appointment LUM-1003 inspection 2026-08-12
python -m luminus_harness --json scenarios
```

## Scenarios

| Scenario | Customer | Purpose |
| --- | --- | --- |
| `high_bill` | `LUM-1001` | Explain an unexpectedly high bill and give general savings advice |
| `appliance_savings` | `LUM-1002` | Advise on shifting appliance usage to reduce cost |
| `meter_visit` | `LUM-1003` | Propose a smart meter inspection appointment with approval language |

## Framework Demos

Install dependencies per demo. Do not use one global Python environment for every framework unless you expect dependency conflicts.

| Framework | Path | Install | Run | API key |
| --- | --- | --- | --- | --- |
| OpenAI Agents SDK | `openai/demo.py` | `pip install -r requirements/openai-agents.txt` | `python openai/demo.py --demo 8` | `OPENAI_API_KEY` |
| Microsoft AutoGen | `medicautogenapp.py` | `pip install -r requirements/autogen.txt` | `python medicautogenapp.py` | `OPENAI_API_KEY` |
| smolagents | `agentsfromhuggingface.py` | `pip install -r requirements/smolagents.txt` | `python agentsfromhuggingface.py` | Hugging Face or configured model access |
| Swarm | `luminusswarmagent.py` | `pip install -r requirements/swarm.txt` | `python luminusswarmagent.py` | Usually `OPENAI_API_KEY` |
| PydanticAI | `pydanticenegryassistant.py` | `pip install -r requirements/pydantic-ai.txt` | `python pydanticenegryassistant.py` | Provider-dependent |
| Agno | `agnoagents.py` | `pip install -r requirements/agno.txt` | `python agnoagents.py` | `OPENAI_API_KEY` |
| Mem0 | `mem0Energyassistant.py` | `pip install -r requirements/mem0.txt` | `python mem0Energyassistant.py` | `OPENAI_API_KEY` |
| Gemini | `geminiagents.py` | `pip install -r requirements/gemini.txt` | `python geminiagents.py` | `GOOGLE_API_KEY` |
| DeepSeek / local text model | `deepseekenergyagent.py` | `pip install -r requirements/text-models.txt` | `python deepseekenergyagent.py` | Depends on model setup |
| Qwen + SAM2 | `qwensam2agent.py` | `pip install -r requirements/vision-medical.txt && pip install -e sam2` | `python qwensam2agent.py` | Hugging Face token if required |
| eve / Vercel | `my-agent/` | `cd my-agent && pnpm install` | `pnpm run dev` | Provider config for eve |
| Agent Laboratory | `agentlaboratory_energy.py` | `pip install -r requirements/agent-lab-energy.txt` | `python agentlaboratory_energy.py` | `OPENAI_API_KEY` |
| TinyAGI | `tinyagi_energy/` | See `tinyagi_energy/README.md` | `tinyagi_energy/skills/luminus-energy/scripts/energy.sh billing LUM-1001` | No for tool-layer smoke test |

For the full dependency matrix, see:

```bash
cat requirements/README.md
```

## OpenAI Agents SDK Demo

The OpenAI demo is the most complete single-framework demo. It covers:

- basic agent
- function tools
- handoffs
- streaming
- multi-turn conversation
- SQLite session memory
- LLM-as-a-judge
- agents as tools
- guardrails
- human-in-the-loop
- interactive chat
- voice

Examples:

```bash
pip install -r requirements/openai-agents.txt

python openai/demo.py --demo 8
python openai/demo.py --chat
python openai/demo.py --demo 12
```

## TinyAGI Tool Adapter

The TinyAGI energy skill now delegates to the shared harness CLI, so it uses the same source of truth as the deterministic comparison runner.

```bash
tinyagi_energy/skills/luminus-energy/scripts/energy.sh billing LUM-1001
tinyagi_energy/skills/luminus-energy/scripts/energy.sh advice LUM-1002 heating
tinyagi_energy/skills/luminus-energy/scripts/energy.sh appointment LUM-1003 inspection 2026-08-12
```

## Development

Run the focused test suite:

```bash
python -m pytest tests/test_luminus_harness.py tests/test_compare.py
```

Run compile checks for the local comparison code:

```bash
python -m py_compile compare.py luminus_harness/__init__.py luminus_harness/__main__.py luminus_harness/core.py
```

## Security

Never commit API keys, local `.env` files, generated certificates, model checkpoints, or runtime caches. Use environment variables for provider credentials:

```bash
export OPENAI_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
```

## Project Status

This repo is now in a good shape for local deterministic comparison. The next useful improvement is not more README work; it is adding optional live adapters to `compare.py` one framework at a time.
