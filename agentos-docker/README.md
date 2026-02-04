# AgentOS Docker Template

Deploy a multi-agent system to production with Docker.

[What is AgentOS?](https://docs.agno.com/agent-os/introduction) · [Agno Docs](https://docs.agno.com) · [Discord](https://agno.com/discord)

---

## What's Included

| Agent | Pattern | Description |
|-------|---------|-------------|
| **Pal** | Learning + Tools | Your AI-powered second brain |
| Knowledge Agent | RAG | Answers questions from a knowledge base |
| MCP Agent | Tool Use | Connects to external services via MCP |

**Pal** (Personal Agent that Learns) is your AI-powered second brain. It researches, captures, organizes, connects, and retrieves your personal knowledge - so nothing useful is ever lost.

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone and configure
```sh
git clone https://github.com/agno-agi/agentos-docker-template.git agentos-docker
cd agentos-docker
cp example.env .env
# Add your OPENAI_API_KEY to .env
```

### 2. Start locally
```sh
docker compose up -d --build
```

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Database**: localhost:5432

### 3. Connect to control plane

1. Open [os.agno.com](https://os.agno.com)
2. Click "Add OS" → "Local"
3. Enter `http://localhost:8000`

---

## The Agents

### Pal (Personal Agent that Learns)

Your AI-powered second brain. Pal researches, captures, organizes, connects, and retrieves your personal knowledge - so nothing useful is ever lost.

**What Pal stores:**

| Type | Examples |
|------|----------|
| **Notes** | Ideas, decisions, snippets, learnings |
| **Bookmarks** | URLs with context - why you saved it |
| **People** | Contacts - who they are, how you know them |
| **Meetings** | Notes, decisions, action items |
| **Projects** | Goals, status, related items |
| **Research** | Findings from web search, saved for later |

**Try it:**
```
Note: decided to use Postgres for the new project - better JSON support
Bookmark https://www.ashpreetbedi.com/articles/lm-technical-design - great intro
Research event sourcing patterns and save the key findings
What notes do I have?
What do I know about event sourcing?
```

**How it works:**
- **DuckDB** stores your actual data (notes, bookmarks, people, etc.)
- **Learning system** remembers schemas and research findings
- **Exa search** powers web research, company lookup, and people search

**Data persistence:** Pal stores structured data in DuckDB at `/data/pal.db`. This persists across container restarts.

### Knowledge Agent

Answers questions using a vector knowledge base (RAG pattern).

**Try it:**
```
What is Agno?
How do I create my first agent?
What documents are in your knowledge base?
```

**Load documents:**
```sh
docker exec -it agentos-api python -m agents.knowledge_agent
```

### MCP Agent

Connects to external tools via the Model Context Protocol.

**Try it:**
```
What tools do you have access to?
Search the docs for how to use LearningMachine
Find examples of agents with memory
```

### Smart Discovery (Multi-Agent Team)

Transforms raw content (Notion pages, interview transcripts, etc.) into evidence-grounded PowerPoint presentations.

**Key Features:**
- **Evidence Grounding**: Every bullet point must reference source evidence `[EVID-abc123]`
- **Auto-Discovery**: Analyzes ANY content to find logical sections (no hardcoded templates)
- **Open Questions**: Missing information becomes questions, never hallucinated content
- **Slide Budget**: Configurable min/max slides with per-section limits

**Try it:**
```python
from teams.smart_discovery import smart_discover
from shared.evidence import CustomerConfig

result = smart_discover(
    raw_content="Your interview transcript or notes here...",
    customer_name="Acme Corp",
    config=CustomerConfig(
        name="Acme Corp",
        must_include=["Executive Summary", "Key Findings", "Recommendations"],
        slide_budget={"min": 8, "max": 40, "per_section_max": 6}
    )
)

print(f"Markdown: {result['markdown_path']}")
print(f"PowerPoint: {result['powerpoint_path']}")
```

---

## Smart Discovery: How It Works

### The 7-Step Pipeline

```
Raw Content → Extract Evidence → Analyze → Revise → Budget → Validate → Markdown → PowerPoint
```

| Step | Agent | What It Does |
|------|-------|--------------|
| 1. Extract | `extract_evidence_from_content()` | Parses content into EvidenceItems with unique IDs |
| 2. Analyze | `ContentAnalyzer` | Discovers logical sections, maps evidence to bullets |
| 3. Revise | `Revisor` | Removes ungrounded bullets, adds Open Questions |
| 4. Budget | `enforce_slide_budget()` | Trims content to fit slide constraints |
| 5. Validate | `validate_grounded_report()` | Ensures 100% evidence grounding |
| 6. Markdown | Template generation | Creates `.md` with `[EVID-xxx]` references |
| 7. PowerPoint | `python-pptx` | Generates `.pptx` with evidence in speaker notes |

### Evidence Grounding

Every factual claim must reference an `EvidenceItem`:

```python
class EvidenceItem:
    id: str           # "EVID-abc123" (auto-generated MD5 hash)
    page_title: str   # Source document title
    page_id: str      # Source document ID
    block_path: list  # Heading hierarchy ["Section", "Subsection"]
    quote: str        # Verbatim text from source
    text: str         # Cleaned/normalized text
    block_type: str   # "bullet", "paragraph", "heading", etc.
```

**In Markdown:**
```markdown
### Key Findings

- Platform uses Azure Cosmos DB for data storage [EVID-a1b2c3d4]
- Mobile app built with Kotlin Multiplatform [EVID-e5f6g7h8] [EVID-i9j0k1l2]

**Open Questions:**
- What is the expected user growth rate?
```

**In PowerPoint:**
- Bullet text appears on slide (without evidence IDs)
- Speaker notes contain full evidence citations:
  ```
  Evidence Sources:
  [EVID-a1b2c3d4] Technical Interview > Architecture: "Uses Azure Cosmos DB for domain data"
  ```

### Slide Budget Enforcement

The `CustomerConfig.slide_budget` controls output size:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min` | 8 | Minimum total slides (warns if below) |
| `max` | 40 | Maximum total slides (trims if exceeded) |
| `per_section_max` | 6 | Max slides per section |

**Budget calculation:**
- Title slide: 1
- Agenda slide: 1
- Per section: 1 divider + ceil(bullets / 6) content slides

**Enforcement rules:**
1. Sections sorted by bullet count (descending)
2. Longest sections trimmed first
3. Each section keeps max `per_section_max × 6` bullets
4. `must_include` sections are never removed (only trimmed)

### CustomerConfig Options

```python
CustomerConfig(
    name="Acme Corp",                    # Customer name for branding

    must_include=[                       # Required sections (added as placeholders if missing)
        "Executive Summary",
        "Key Findings",
        "Recommendations"
    ],

    terminology_map={                    # Find/replace for consistent naming
        "client": "Acme Corp",
        "the customer": "Acme Corp"
    },

    slide_budget={                       # Output constraints
        "min": 8,
        "max": 40,
        "per_section_max": 6
    },

    emphasis_weights={                   # Content prioritization (future use)
        "goals": 1.0,
        "problems": 1.0,
        "risks": 0.8
    }
)
```

### Output Files

Smart Discovery generates:

| File | Location | Contents |
|------|----------|----------|
| Markdown | `outputs/{customer}_{timestamp}.md` | Full report with `[EVID-xxx]` references |
| PowerPoint | `outputs/{customer}_{timestamp}.pptx` | Presentation with evidence in speaker notes |

**PowerPoint Structure:**
1. **Title Slide**: Customer name + "Discovery Report"
2. **Agenda Slide**: List of all sections
3. **Section Slides**: Content with bullet points
4. Evidence stored in speaker notes (not visible in presentation)

---

## Project Structure
```
├── agents/
│   ├── pal.py              # Personal second brain agent
│   ├── knowledge_agent.py  # RAG agent
│   ├── mcp_agent.py        # MCP tools agent
│   ├── content_analyzer.py # Evidence-aware content analysis
│   └── revisor.py          # Evidence grounding enforcement
├── teams/
│   └── smart_discovery.py  # Multi-agent discovery pipeline
├── shared/
│   └── evidence.py         # Evidence models (EvidenceItem, CustomerConfig)
├── tests/
│   └── test_smart_discovery.py  # Production-grade tests
├── outputs/                # Generated reports (.md, .pptx)
├── app/
│   ├── main.py             # AgentOS entry point
│   └── config.yaml         # Quick prompts config
├── db/
│   ├── session.py          # Database session
│   └── url.py              # Connection URL builder
├── scripts/                # Helper scripts
├── compose.yaml            # Docker Compose config
├── Dockerfile
└── pyproject.toml          # Dependencies
```

---

## Common Tasks

### Add your own agent

1. Create `agents/my_agent.py`:
```python
from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from db.session import get_postgres_db

my_agent = Agent(
    id="my-agent",
    name="My Agent",
    model=OpenAIResponses(id="gpt-5.2"),
    db=get_postgres_db(),
    instructions="You are a helpful assistant.",
)
```

2. Register in `app/main.py`:
```python
from agents.my_agent import my_agent

agent_os = AgentOS(
    name="AgentOS",
    agents=[pal, knowledge_agent, mcp_agent, my_agent],
    ...
)
```

3. Restart: `docker compose restart`

### Add tools to an agent

Agno includes 100+ tool integrations. See the [full list](https://docs.agno.com/tools/toolkits).
```python
from agno.tools.slack import SlackTools
from agno.tools.google_calendar import GoogleCalendarTools

my_agent = Agent(
    ...
    tools=[
        SlackTools(),
        GoogleCalendarTools(),
    ],
)
```

### Add dependencies

1. Edit `pyproject.toml`
2. Regenerate requirements: `./scripts/generate_requirements.sh`
3. Rebuild: `docker compose up -d --build`

### Use a different model provider

1. Add your API key to `.env` (e.g., `ANTHROPIC_API_KEY`)
2. Update agents to use the new provider:
```python
from agno.models.anthropic import Claude

model=Claude(id="claude-sonnet-4-5")
```
3. Add dependency: `anthropic` in `pyproject.toml`

---

## Local Development

For development without Docker:
```sh
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup environment
./scripts/venv_setup.sh
source .venv/bin/activate

# Start PostgreSQL (required)
docker compose up -d agentos-db

# Run the app
python -m app.main
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `ANTHROPIC_API_KEY` | For Discovery | - | Anthropic API key (Smart Discovery agents) |
| `NOTION_API_KEY` | For Discovery | - | Notion API key (to read Notion pages) |
| `EXA_API_KEY` | No | - | Exa API key for web research |
| `DB_HOST` | No | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `DB_USER` | No | `ai` | Database user |
| `DB_PASS` | No | `ai` | Database password |
| `DB_DATABASE` | No | `ai` | Database name |
| `DATA_DIR` | No | `/data` | Directory for DuckDB storage |
| `RUNTIME_ENV` | No | `prd` | Set to `dev` for auto-reload |

---

## Extending Pal

Pal is designed to be extended. Connect it to your existing tools:

### Communication
```python
from agno.tools.slack import SlackTools
from agno.tools.gmail import GmailTools

tools=[
    ...
    SlackTools(),    # Capture decisions from Slack
    GmailTools(),    # Track important emails
]
```

### Productivity
```python
from agno.tools.google_calendar import GoogleCalendarTools
from agno.tools.linear import LinearTools

tools=[
    ...
    GoogleCalendarTools(),  # Meeting context
    LinearTools(),          # Project tracking
]
```

### Research
```python
from agno.tools.yfinance import YFinanceTools
from agno.tools.github import GithubTools

tools=[
    ...
    YFinanceTools(),  # Financial data
    GithubTools(),    # Code and repos
]
```

See the [Agno Tools documentation](https://docs.agno.com/tools/toolkits) for the full list of available integrations.

---

## Learn More

- [Agno Documentation](https://docs.agno.com)
- [AgentOS Documentation](https://docs.agno.com/agent-os/introduction)
- [Tools & Integrations](https://docs.agno.com/tools/toolkits)
- [Discord Community](https://agno.com/discord)
