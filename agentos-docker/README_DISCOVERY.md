# Discovery Solution Report Generator

A multi-agent team workflow built on Agno AgentOS that generates "Discover Solution" reports for consulting engagements.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Discovery Orchestrator Team                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │NotionReader │  │SectionDrafter│  │      Revisor       │ │
│  │   Agent     │  │    Agent     │  │       Agent        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │                │                    │            │
│         ▼                ▼                    ▼            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Orchestrator Coordinator                 │  │
│  │  - Manages section-by-section workflow               │  │
│  │  - Handles user feedback loop                        │  │
│  │  - Compiles final report                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Environment Variables

Create/update `.env` file:

```bash
# Notion integration (for NotionTools agent - requires database sharing)
NOTION_API_KEY=ntn_xxxxx
NOTION_DATABASE_ID=xxxxx

# Notion MCP token (for reading any page via MCP)
NOTION_TOKEN=ntn_xxxxx

# Other required vars
OPENAI_API_KEY=sk-xxxxx  # Or use Ollama (default)
```

### 2. Start Services

```bash
docker compose down && docker compose up -d
```

### 3. Verify Health

```bash
curl http://localhost:8000/health
```

## Usage

### Start a Report Generation

```bash
curl -X POST "http://localhost:8000/teams/discovery-orchestrator/runs" \
  -F "message=Start report for Countroll. Template: https://www.notion.so/sweetspot-experts/4-Discover-Solution-2efd31a3b6e48165ad61db743dcc6e85 Intake: https://www.notion.so/sweetspot-experts/Technical-solution-intake-18-12-2cdd31a3b6e480048f55d981080" \
  -F "stream=false"
```

### Continue with Session ID

Save the `session_id` from the response, then continue:

```bash
curl -X POST "http://localhost:8000/teams/discovery-orchestrator/runs" \
  -F "message=approve" \
  -F "session_id=YOUR_SESSION_ID" \
  -F "stream=false"
```

### Provide Feedback

```bash
curl -X POST "http://localhost:8000/teams/discovery-orchestrator/runs" \
  -F "message=Please add more details about the Azure hosting setup" \
  -F "session_id=YOUR_SESSION_ID" \
  -F "stream=false"
```

## Workflow

1. **Initialization**: Provide template and intake Notion URLs
2. **Section Processing**: For each H3 section in the template:
   - Draft section using evidence from intake
   - Revise for quality
   - Present to user with feedback questions
3. **User Feedback Loop**:
   - Reply "approve" → Accept section, move to next
   - Reply with corrections → Revise and re-present
4. **Completion**: All sections compiled to `./countroll_report/discover_solution_countroll.md`

## Agents

| Agent | Purpose |
|-------|---------|
| **Notion Reader** | Reads Notion pages via MCP (or fallback) |
| **Section Drafter** | Creates section drafts following template structure |
| **Revisor** | Improves quality, enforces consistency, adds evidence |
| **Orchestrator** | Coordinates workflow, manages state |

## Output

Final report saved to:
```
./countroll_report/discover_solution_countroll.md
```

With changelog footer tracking all approvals and revisions.

## Notion MCP Setup (Optional)

For full Notion integration via MCP:

1. Install Node.js in the container (or run MCP server separately)
2. The Notion MCP server uses `NOTION_TOKEN` environment variable
3. Without MCP, fallback intake text is used for testing

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/teams/discovery-orchestrator/runs` | POST | Run the discovery team |
| `/agents/notion-reader/runs` | POST | Direct Notion reading |
| `/agents/section-drafter/runs` | POST | Direct section drafting |
| `/agents/revisor/runs` | POST | Direct revision |

## Files Created

```
agentos-docker/
├── agents/
│   ├── notion_reader.py      # Notion MCP reader agent
│   ├── section_drafter.py    # Section drafting agent
│   └── revisor.py            # Quality revision agent
├── teams/
│   └── discovery_orchestrator.py  # Main team orchestrator
├── shared/
│   └── state.py              # Report state models
├── countroll_report/
│   └── discover_solution_countroll.md  # Output file
└── README_DISCOVERY.md       # This file
```
