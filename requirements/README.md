# Demo dependency matrix

The root repository is a comparison workspace, not one Python application.
Install dependencies per demo so one framework's package constraints do not
break another framework.

| Demo | Install | Run |
| --- | --- | --- |
| OpenAI Agents SDK | `pip install -r requirements/openai-agents.txt` | `python openai/demo.py --demo 8` |
| AutoGen | `pip install -r requirements/autogen.txt` | `python medicautogenapp.py` |
| Gemini | `pip install -r requirements/gemini.txt` | `python geminiagents.py` |
| DeepSeek | `pip install -r requirements/text-models.txt` | `python deepseekenergyagent.py` |
| PydanticAI | `pip install -r requirements/pydantic-ai.txt` | `python pydanticenegryassistant.py` |
| Mem0 | `pip install -r requirements/mem0.txt` | `python mem0Energyassistant.py` |
| Agno | `pip install -r requirements/agno.txt` | `python agnoagents.py` |
| smolagents | `pip install -r requirements/smolagents.txt` | `python agentsfromhuggingface.py` |
| Swarm | `pip install -r requirements/swarm.txt` | `python luminusswarmagent.py` |
| Agent Laboratory energy demo | `pip install -r requirements/agent-lab-energy.txt` | `python agentlaboratory_energy.py` |
| Qwen / medical vision demos | `pip install -r requirements/vision-medical.txt && pip install -e sam2` | `python qwensam2agent.py` |
| Trackio example | `pip install -r requirements/trackio.txt` | `python trackio_example.py` |

Recommended workflow:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/openai-agents.txt
```

For the Qwen + SAM2 demo, install the local SAM2 checkout after the vision
requirements:

```bash
pip install -r requirements/vision-medical.txt
pip install -e sam2
python qwensam2agent.py
```

The `my-agent/` eve demo is a Node project and uses its own `package.json`:

```bash
cd my-agent
pnpm install
pnpm run dev
```
