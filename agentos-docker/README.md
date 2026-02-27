# Smart Discovery — Notion → PowerPoint Pipeline

Converts Notion pages (interviews, workshops, desk research) into evidence-grounded Sweetspot PowerPoint reports.

---

## How it works

```
Notion pages → Evidence extraction → Template slots → Slot filler agents → .pptx + .md
```

1. **Read** — fetches Notion pages recursively (follows all sub-pages, toggles, callouts)
2. **Extract** — every paragraph, bullet, and heading becomes a tagged evidence item (`EVID-xxxxxxxx`)
3. **Fill slots** — one Claude call per template slot, with keyword-filtered evidence for that section
4. **Output** — Sweetspot-styled `.pptx` + full `.md` report with evidence citations

Every bullet in the output references at least one `[EVID-xxx]` ID. Gaps where evidence is missing become **Open Questions** instead of hallucinated content.

---

## Quick start

### 1. Install dependencies

```bash
uv venv .venv --python 3.12
VIRTUAL_ENV=.venv uv pip install -r requirements.txt streamlit
```

### 2. Set up environment

```bash
cp example.env .env
```

Edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your_key_here
NOTION_TOKEN=ntn_your_integration_token_here
NOTION_SAFE_MODE=false
```

### 3. Run the app

```bash
.venv/bin/streamlit run streamlit_app.py
```

Open **http://localhost:8501**

---

## Setting up Notion access

See [NOTION_SETUP.md](NOTION_SETUP.md) for full instructions. Short version:

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → create integration → copy token → paste into `.env`
2. For every Notion page you want to read: open the page → **···** (top right) → **Connections** → select your integration
3. Sharing a parent page covers all its child pages automatically

Verify it works:
```bash
curl -s "https://api.notion.com/v1/pages/<PAGE_ID>" \
  -H "Authorization: Bearer $NOTION_TOKEN" \
  -H "Notion-Version: 2022-06-28" | python3 -c "
import sys,json; d=json.load(sys.stdin)
print('OK' if d.get('object')=='page' else d.get('message'))
"
```

---

## Using the Streamlit UI

### Step 1 — Choose mode

| Mode | When to use |
|---|---|
| **Smart Discovery** | Full AI pipeline: evidence extraction, template slot filling, evidence grounding |
| **Simple Mode** | Direct Notion → slides conversion, no LLM |

### Step 2 — Customer config URL *(Smart Discovery only, optional)*

Paste the URL of a [Customer Config page](#customer-config-page) to control:
- Which sections appear (and in what order)
- What each section should contain (description + keywords for evidence filtering)
- Terminology substitutions
- Slide budget (min/max slides)

If left blank, defaults to: **Executive Summary, Key Findings, Recommendations**.

### Step 3 — Add sources

Click **+ Add source** for each input. Each source can be:

| Type | Use for |
|---|---|
| **URL** | Notion page — read via API, sub-pages included automatically |
| **Paste** | Interview notes, workshop output, copied text |

Label each source (e.g. `Interview CEO`, `Workshop output`, `Desk research`). Labels appear in evidence citations.

### Step 4 — Generate

Hit **Generate PowerPoint**. Progress logs stream in real time. Download the `.pptx` and `.md` from the results panel.

---

## Customer Config page

Create one Notion page per customer. Share it with your Notion integration. Paste its URL into the **Customer config URL** field.

### Full format

```
# <Customer Name>

## Required Sections
- Executive Summary
- Key Findings
- Recommendations
- <add or remove sections — output follows this order>

## Template Slots

### Executive Summary
Concise overview of the customer situation, why this engagement was
initiated, and the 2-3 most important numbers or facts at a glance.
Keywords: company, revenue, employees, engagement, overview, commissioned

### Key Findings
The 3-5 most critical discoveries from the assessment — structural
problems, root causes, and the most important numbers.
Keywords: finding, critical, structural, failure, conflict, adoption, zero

### Recommendations
Specific actionable next steps with clear ownership and sequencing.
Keywords: recommend, should, next step, action, implement, appoint, resolve

### <Any other section name>
Description of what this section should contain.
Keywords: keyword1, keyword2, keyword3

## Terminology
- OldTerm → NewTerm
- Customer → Client
- CRM → Customer Data Platform

## Slide Budget
- Min slides: 8
- Max slides: 20
- Max per section: 3
```

### Field reference

| Section | Required | What it does |
|---|---|---|
| `# Customer Name` (H1) | Yes | Sets the customer name in the report and output filenames |
| `## Required Sections` | Yes | Which slots appear in the output, in this order |
| `## Template Slots` | Recommended | Per-slot description + keywords improve evidence targeting |
| `## Terminology` | Optional | Find-and-replace applied to all output text (`Old → New`) |
| `## Slide Budget` | Optional | Defaults: min 8, max 30, max 4 per section |

### Why Template Slots matter

Without slot descriptions, keywords are auto-derived from the section name words (e.g. "Key Findings" → `['findings']`). This works but is imprecise — especially for generic section names.

With slot descriptions and keywords, each Claude call knows **what kind of content** to extract, and the evidence filter sends only the most relevant items. This produces sharper bullets and fewer irrelevant Open Questions.

---

## How the pipeline works internally

```
Step 1  Read all sources (Notion URLs + pasted blocks) → merge evidence
Step 2  Build ReportTemplate from CustomerConfig (slots in order)
Step 3  Controller: for each slot
           → filter evidence by slot keywords
           → call SlotFiller (one Claude call) → GroundedSection
Step 4  Enforce slide budget (trim longest sections first)
Step 5  Validate grounding (every bullet must have ≥1 EVID reference)
Step 6  Generate Markdown report with evidence appendix
Step 7  Generate PowerPoint (.pptx) with evidence in speaker notes
```

### Evidence grounding

Every bullet must reference at least one source:

```
- Countroll has 1% external adoption from 4,500 customers [EVID-2bfa321a]
```

The Evidence Appendix maps every `EVID-xxx` to the exact quote and source path:

```
[EVID-2bfa321a] Report > 1.2 Key Findings: "Countroll has achieved approximately
1% external adoption from 4,500 customers — 60–70 active users..."
```

Bullets with no valid evidence become Open Questions automatically — nothing is invented.

---

## Output files

Saved to `./output/`:

| File | Contents |
|---|---|
| `smart_discovery_<Customer>.pptx` | Sweetspot-styled PowerPoint |
| `smart_discovery_<Customer>.md` | Full report with `[EVID-xxx]` citations |

PowerPoint structure:
1. **Title slide** — customer name, report title, date
2. **Agenda slide** — numbered section list
3. **Section divider** + **content slides** per slot
4. Evidence citations in speaker notes (not visible in presentation)

---

## Project structure

```
agentos-docker/
├── streamlit_app.py          # Web UI
├── teams/
│   └── smart_discovery.py    # Main 7-step pipeline
├── agents/
│   ├── notion_reader.py      # Reads Notion pages via API (recursive)
│   ├── controller.py         # Orchestrates slot filling + title/summary
│   ├── slot_filler.py        # One focused Claude call per slot
│   └── revisor.py            # Enforces slide budget
├── shared/
│   ├── evidence.py           # EvidenceItem, EvidenceCollection, CustomerConfig
│   ├── template.py           # TemplateSlot, ReportTemplate
│   └── config_loader.py      # Parses CustomerConfig from Notion page
├── templates/
│   └── sweetspot_template.pptx
├── output/                   # Generated reports (gitignored)
├── NOTION_SETUP.md           # Notion integration setup guide
├── .env                      # Secrets — never commit this
└── requirements.txt
```

---

## Troubleshooting

**"No Notion client available. Set NOTION_TOKEN in .env"**
→ `NOTION_TOKEN` is missing or `.env` wasn't loaded. Restart the app after editing `.env`.

**404 on a Notion page**
→ Page not shared with integration. Open page → **···** → **Connections** → add your integration.

**Slots with many Open Questions / few bullets**
→ The evidence keywords for that slot are too narrow, or the source doesn't contain that content. Add a `## Template Slots` section to the config page with better-targeted keywords.

**Content cut off / slides missing**
→ Hit the slide budget. Increase `Max slides` in the config page or in Advanced options.

**"Key Findings" slot always gets few evidence items**
→ Keywords like `finding`, `key`, `insight` are too common. Use more specific terms from your actual document: `adoption`, `conflict`, `structural`, `root cause`.
