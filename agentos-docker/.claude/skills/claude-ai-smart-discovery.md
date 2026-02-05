---
name: smart-discovery
description: Generate evidence-grounded discovery report PowerPoint from Notion page
args: <notion_url> [customer_name]
---

# Smart Discovery

Fetches a Notion page and generates an evidence-grounded discovery report with Executive Summary, Key Findings, and Recommendations.

## Usage

```
/smart-discovery https://www.notion.so/page-name-abc123
/smart-discovery https://www.notion.so/page-name-abc123 "Acme Corp"
```

## What it does

1. Fetches the Notion page content via API
2. Extracts evidence items with unique IDs [EVID-xxx]
3. Structures content into discovery report sections
4. Every bullet references source evidence
5. Adds Open Questions for missing information
6. Returns downloadable .pptx file

## Instructions

When the user provides a Notion URL, run this Python code in the Analysis tool:

```python
import requests
import re
import hashlib
from pptx import Presentation
from pptx.util import Inches, Pt
from datetime import datetime

# ============ NOTION API CONFIG ============
NOTION_API_KEY = "YOUR_NOTION_API_KEY_HERE"  # User must replace this
NOTION_VERSION = "2022-06-28"

# ============ CONFIG ============
CUSTOMER_NAME = "Client"  # Replace with customer name if provided
NOTION_URL = "PASTE_NOTION_URL_HERE"  # Replace with actual URL

# ============ EXTRACT PAGE ID ============
def extract_page_id(url):
    patterns = [
        r'([a-f0-9]{32})',
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1).replace('-', '')
    return None

# ============ EVIDENCE ITEM ============
class EvidenceItem:
    def __init__(self, text, section=""):
        self.text = text
        self.section = section
        content_hash = hashlib.md5(f"{section}:{text[:50]}".encode()).hexdigest()[:8]
        self.id = f"EVID-{content_hash}"

    def format_citation(self):
        return f"[{self.id}] {self.section}: \"{self.text[:80]}{'...' if len(self.text) > 80 else ''}\""

# ============ FETCH NOTION PAGE ============
def fetch_notion_page(page_id):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    # Get page title
    page_url = f"https://api.notion.com/v1/pages/{page_id}"
    page_resp = requests.get(page_url, headers=headers)
    page_data = page_resp.json()

    title = "Discovery Report"
    if "properties" in page_data:
        for prop in page_data["properties"].values():
            if prop.get("type") == "title" and prop.get("title"):
                title = "".join([t.get("plain_text", "") for t in prop["title"]])
                break

    # Get blocks
    blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks_resp = requests.get(blocks_url, headers=headers)
    blocks_data = blocks_resp.json()

    return title, blocks_data.get("results", [])

# ============ EXTRACT EVIDENCE ============
def extract_evidence(blocks):
    """Extract all content as evidence items."""
    evidence = []
    current_section = "General"

    for block in blocks:
        block_type = block.get("type", "")

        if block_type in ["heading_1", "heading_2", "heading_3"]:
            text_content = block.get(block_type, {}).get("rich_text", [])
            current_section = "".join([t.get("plain_text", "") for t in text_content])

        elif block_type in ["bulleted_list_item", "numbered_list_item", "paragraph"]:
            text_content = block.get(block_type, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_content])

            if text.strip() and len(text) > 5:
                evidence.append(EvidenceItem(text.strip(), current_section))

    return evidence

# ============ BUILD DISCOVERY SECTIONS ============
def build_discovery_sections(evidence, page_title):
    """Organize evidence into discovery report structure."""

    # Group evidence by original section
    section_groups = {}
    for ev in evidence:
        if ev.section not in section_groups:
            section_groups[ev.section] = []
        section_groups[ev.section].append(ev)

    # Build structured sections
    sections = []

    # 1. Executive Summary (synthesized from all evidence)
    exec_summary = {
        "name": "Executive Summary",
        "bullets": [],
        "open_questions": []
    }
    # Take first item from each section as summary points
    for section_name, items in list(section_groups.items())[:4]:
        if items:
            ev = items[0]
            exec_summary["bullets"].append({
                "text": f"{section_name}: {ev.text[:100]}{'...' if len(ev.text) > 100 else ''}",
                "evidence_ids": [ev.id]
            })
    if not exec_summary["bullets"]:
        exec_summary["open_questions"].append("No content available for executive summary")
    sections.append(exec_summary)

    # 2. Key Findings (from original sections)
    for section_name, items in section_groups.items():
        if section_name == "General" and len(section_groups) > 1:
            continue  # Skip generic section if we have named ones

        finding_section = {
            "name": section_name if section_name != "General" else "Key Findings",
            "bullets": [],
            "open_questions": []
        }

        for ev in items[:6]:  # Max 6 bullets per section
            finding_section["bullets"].append({
                "text": ev.text,
                "evidence_ids": [ev.id]
            })

        if not finding_section["bullets"]:
            finding_section["open_questions"].append(f"No evidence found for {section_name}")

        sections.append(finding_section)

    # 3. Recommendations (always added with open questions)
    recommendations = {
        "name": "Recommendations",
        "bullets": [],
        "open_questions": [
            "What are the priority actions based on findings?",
            "What resources are needed for implementation?",
            "What is the recommended timeline?"
        ]
    }
    sections.append(recommendations)

    return sections

# ============ CREATE POWERPOINT ============
def create_discovery_pptx(title, sections, evidence, customer_name):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(12), Inches(3))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = f"Discovery Report: {title}"
    p.font.size = Pt(40)
    p.font.bold = True

    p2 = tf.add_paragraph()
    p2.text = customer_name
    p2.font.size = Pt(28)

    p3 = tf.add_paragraph()
    p3.text = datetime.now().strftime("%B %Y")
    p3.font.size = Pt(18)

    # Add evidence count to speaker notes
    notes = slide.notes_slide
    notes.notes_text_frame.text = f"Evidence items: {len(evidence)}\nGenerated: {datetime.now().isoformat()}"

    # Agenda slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(12), Inches(1))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = "Agenda"
    p.font.size = Pt(36)
    p.font.bold = True

    txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12), Inches(5))
    tf2 = txBox2.text_frame
    for i, section in enumerate(sections):
        if i == 0:
            p = tf2.paragraphs[0]
        else:
            p = tf2.add_paragraph()
        p.text = f"{i+1}. {section['name']}"
        p.font.size = Pt(18)

    # Content slides
    for section in sections:
        # Section divider
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12), Inches(1.5))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        p.text = section["name"]
        p.font.size = Pt(40)
        p.font.bold = True

        # Content with evidence
        all_items = []
        for bullet in section["bullets"]:
            refs = " ".join(f"[{eid}]" for eid in bullet["evidence_ids"])
            all_items.append((bullet["text"], bullet["evidence_ids"]))

        for q in section["open_questions"]:
            all_items.append((f"[OPEN QUESTION] {q}", []))

        if not all_items:
            continue

        # Split into chunks of 5 (less per slide for readability)
        chunks = [all_items[i:i+5] for i in range(0, len(all_items), 5)]

        for chunk_idx, chunk in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[6])

            # Title
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            slide_title = section["name"] if chunk_idx == 0 else f"{section['name']} (cont.)"
            p.text = slide_title
            p.font.size = Pt(28)
            p.font.bold = True

            # Content
            txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12), Inches(5.5))
            tf2 = txBox2.text_frame

            for i, (text, eids) in enumerate(chunk):
                if i == 0:
                    p = tf2.paragraphs[0]
                else:
                    p = tf2.add_paragraph()

                # Truncate long text
                display_text = text[:150] + "..." if len(text) > 150 else text
                p.text = f"• {display_text}"
                p.font.size = Pt(16)

            # Speaker notes with evidence citations
            evidence_lookup = {ev.id: ev for ev in evidence}
            notes_lines = [f"Section: {section['name']}", "", "Evidence Sources:"]
            for text, eids in chunk:
                for eid in eids:
                    if eid in evidence_lookup:
                        notes_lines.append(evidence_lookup[eid].format_citation())

            notes = slide.notes_slide
            notes.notes_text_frame.text = "\n".join(notes_lines)

    return prs

# ============ MAIN ============
page_id = extract_page_id(NOTION_URL)
print(f"Page ID: {page_id}")

title, blocks = fetch_notion_page(page_id)
print(f"Title: {title}")
print(f"Blocks: {len(blocks)}")

evidence = extract_evidence(blocks)
print(f"Evidence items: {len(evidence)}")

sections = build_discovery_sections(evidence, title)
print(f"Sections: {len(sections)}")
for s in sections:
    print(f"  - {s['name']}: {len(s['bullets'])} bullets, {len(s['open_questions'])} questions")

prs = create_discovery_pptx(title, sections, evidence, CUSTOMER_NAME)

output_file = f"Discovery_Report_{CUSTOMER_NAME.replace(' ', '_')}.pptx"
prs.save(output_file)
print(f"\nCreated: {output_file}")
print(f"Total evidence items: {len(evidence)}")
```

Replace:
- `PASTE_NOTION_URL_HERE` with the user's Notion URL
- `CUSTOMER_NAME = "Client"` with the customer name if provided

The PowerPoint file will be generated with:
- Title slide with customer name
- Agenda
- Executive Summary
- Key Findings sections (from original content)
- Recommendations with Open Questions
- Evidence citations in speaker notes
