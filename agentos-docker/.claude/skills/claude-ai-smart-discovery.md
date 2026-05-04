---
name: "smart-discovery"
description: "Generate evidence-grounded discovery report PowerPoint from Notion page using Sweetspot template"
---

# Smart Discovery

Fetches a Notion page and generates an evidence-grounded discovery report with Executive Summary, Key Findings, and Recommendations using the Sweetspot template.

## Usage

```
/smart-discovery https://www.notion.so/page-name-abc123
/smart-discovery https://www.notion.so/page-name-abc123 "Acme Corp"
```

## What it does

1. Downloads Sweetspot template from GitHub
2. Fetches the Notion page content via API
3. Extracts evidence items with unique IDs [EVID-xxx]
4. Structures content into discovery report sections
5. Every bullet references source evidence
6. Adds Open Questions for missing information
7. Returns downloadable .pptx file with Sweetspot styling

## Instructions

When the user provides a Notion URL, run this Python code in the Analysis tool:

```python
import os
import requests
import re
import io
import hashlib
from pptx import Presentation
from pptx.util import Inches, Pt
from datetime import datetime

# ============ CONFIG ============
NOTION_API_KEY = os.environ.get("NOTION_TOKEN", "")  # Set NOTION_TOKEN in .env
NOTION_VERSION = "2022-06-28"
TEMPLATE_URL = "https://raw.githubusercontent.com/pascal-maker/agentscomparison/master/agentos-docker/templates/sweetspot_template.pptx"

CUSTOMER_NAME = "Client"  # Replace with customer name if provided
NOTION_URL = "PASTE_NOTION_URL_HERE"  # Replace with actual URL

# ============ DOWNLOAD TEMPLATE ============
def download_template():
    """Download Sweetspot template from GitHub."""
    print("Downloading Sweetspot template...")
    response = requests.get(TEMPLATE_URL)
    if response.status_code == 200:
        print("Template downloaded successfully")
        return io.BytesIO(response.content)
    else:
        print(f"Failed to download template: {response.status_code}, using blank")
        return None

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

    page_url = f"https://api.notion.com/v1/pages/{page_id}"
    page_resp = requests.get(page_url, headers=headers)
    page_data = page_resp.json()

    title = "Discovery Report"
    if "properties" in page_data:
        for prop in page_data["properties"].values():
            if prop.get("type") == "title" and prop.get("title"):
                title = "".join([t.get("plain_text", "") for t in prop["title"]])
                break

    blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    blocks_resp = requests.get(blocks_url, headers=headers)
    blocks_data = blocks_resp.json()

    return title, blocks_data.get("results", [])

# ============ EXTRACT EVIDENCE ============
def extract_evidence(blocks):
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
    section_groups = {}
    for ev in evidence:
        if ev.section not in section_groups:
            section_groups[ev.section] = []
        section_groups[ev.section].append(ev)

    sections = []

    # Executive Summary
    exec_summary = {"name": "Executive Summary", "bullets": [], "open_questions": []}
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

    # Key Findings
    for section_name, items in section_groups.items():
        if section_name == "General" and len(section_groups) > 1:
            continue

        finding_section = {
            "name": section_name if section_name != "General" else "Key Findings",
            "bullets": [],
            "open_questions": []
        }

        for ev in items[:6]:
            finding_section["bullets"].append({"text": ev.text, "evidence_ids": [ev.id]})

        if not finding_section["bullets"]:
            finding_section["open_questions"].append(f"No evidence found for {section_name}")

        sections.append(finding_section)

    # Recommendations
    sections.append({
        "name": "Recommendations",
        "bullets": [],
        "open_questions": [
            "What are the priority actions based on findings?",
            "What resources are needed for implementation?",
            "What is the recommended timeline?"
        ]
    })

    return sections

# ============ CREATE POWERPOINT ============
def create_discovery_pptx(title, sections, evidence, customer_name, template_data):
    # Load template or create blank
    if template_data:
        prs = Presentation(template_data)
        while len(prs.slides) > 0:
            rId = prs.slides._sldIdLst[0].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[0]
    else:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    LAYOUT_BLANK = min(0, len(prs.slide_layouts) - 1)
    LAYOUT_CONTENT = min(1, len(prs.slide_layouts) - 1)
    LAYOUT_CHAPTER = min(2, len(prs.slide_layouts) - 1)

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[LAYOUT_BLANK])
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

    notes = slide.notes_slide
    notes.notes_text_frame.text = f"Evidence items: {len(evidence)}\nGenerated: {datetime.now().isoformat()}"

    # Agenda slide
    slide = prs.slides.add_slide(prs.slide_layouts[LAYOUT_CONTENT])
    if slide.shapes.title:
        slide.shapes.title.text = "Agenda"

    content_shape = None
    for shape in slide.shapes:
        if shape.has_text_frame and shape != slide.shapes.title:
            content_shape = shape
            break

    if content_shape:
        tf = content_shape.text_frame
        tf.clear()
        for i, section in enumerate(sections):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"{i+1}. {section['name']}"
            p.font.size = Pt(18)
    else:
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12), Inches(5))
        tf = txBox.text_frame
        for i, section in enumerate(sections):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"{i+1}. {section['name']}"
            p.font.size = Pt(18)

    # Content slides
    for section in sections:
        # Section divider
        slide = prs.slides.add_slide(prs.slide_layouts[LAYOUT_CHAPTER])
        if slide.shapes.title:
            slide.shapes.title.text = section["name"]
        else:
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12), Inches(1.5))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = section["name"]
            p.font.size = Pt(40)
            p.font.bold = True

        all_items = []
        for bullet in section["bullets"]:
            all_items.append((bullet["text"], bullet["evidence_ids"]))
        for q in section["open_questions"]:
            all_items.append((f"[OPEN QUESTION] {q}", []))

        if not all_items:
            continue

        chunks = [all_items[i:i+5] for i in range(0, len(all_items), 5)]

        for chunk_idx, chunk in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[LAYOUT_CONTENT])

            slide_title = section["name"] if chunk_idx == 0 else f"{section['name']} (cont.)"
            if slide.shapes.title:
                slide.shapes.title.text = slide_title

            content_shape = None
            for shape in slide.shapes:
                if shape.has_text_frame and shape != slide.shapes.title:
                    content_shape = shape
                    break

            if content_shape:
                tf = content_shape.text_frame
                tf.clear()
                for i, (text, eids) in enumerate(chunk):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    display_text = text[:150] + "..." if len(text) > 150 else text
                    p.text = f"• {display_text}"
                    p.font.size = Pt(16)
            else:
                txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12), Inches(5.5))
                tf = txBox.text_frame
                for i, (text, eids) in enumerate(chunk):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    display_text = text[:150] + "..." if len(text) > 150 else text
                    p.text = f"• {display_text}"
                    p.font.size = Pt(16)

            # Speaker notes with evidence
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
template_data = download_template()

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

prs = create_discovery_pptx(title, sections, evidence, CUSTOMER_NAME, template_data)

output_file = f"Discovery_Report_{CUSTOMER_NAME.replace(' ', '_')}.pptx"
prs.save(output_file)
print(f"\nCreated: {output_file}")
print(f"Total evidence items: {len(evidence)}")
```

Replace:
- `PASTE_NOTION_URL_HERE` with the user's Notion URL
- `CUSTOMER_NAME = "Client"` with the customer name if provided

The PowerPoint will use the Sweetspot template and include:
- Title slide with customer name
- Agenda
- Executive Summary
- Key Findings sections (from original content)
- Recommendations with Open Questions
- Evidence citations in speaker notes
