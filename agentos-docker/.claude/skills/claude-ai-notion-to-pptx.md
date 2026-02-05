---
name: notion-to-pptx
description: Convert any Notion page directly to PowerPoint slides (simple mode, preserves structure)
args: <notion_url>
---

# Notion to PowerPoint (Simple Mode)

Fetches a Notion page and converts it directly to PowerPoint slides, preserving the original structure.

## Usage

```
/notion-to-pptx https://www.notion.so/page-name-abc123
```

## What it does

1. Fetches the Notion page content via API
2. Parses headings, bullets, and paragraphs
3. Creates PowerPoint preserving original structure
4. Returns downloadable .pptx file

## Instructions

When the user provides a Notion URL, run this Python code in the Analysis tool:

```python
import requests
import re
from pptx import Presentation
from pptx.util import Inches, Pt
from datetime import datetime

# ============ NOTION API CONFIG ============
NOTION_API_KEY = "YOUR_NOTION_API_KEY_HERE"  # User must replace this
NOTION_VERSION = "2022-06-28"

# ============ EXTRACT PAGE ID ============
def extract_page_id(url):
    """Extract page ID from Notion URL."""
    patterns = [
        r'([a-f0-9]{32})',
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1).replace('-', '')
    return None

# ============ FETCH NOTION PAGE ============
def fetch_notion_page(page_id):
    """Fetch page content from Notion API."""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    # Get page title
    page_url = f"https://api.notion.com/v1/pages/{page_id}"
    page_resp = requests.get(page_url, headers=headers)
    page_data = page_resp.json()

    title = "Presentation"
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

# ============ PARSE BLOCKS TO SECTIONS ============
def parse_blocks(blocks):
    """Parse Notion blocks into sections."""
    sections = []
    current_section = None

    for block in blocks:
        block_type = block.get("type", "")

        if block_type in ["heading_1", "heading_2", "heading_3"]:
            if current_section:
                sections.append(current_section)

            text_content = block.get(block_type, {}).get("rich_text", [])
            title = "".join([t.get("plain_text", "") for t in text_content])

            current_section = {
                "title": title,
                "level": int(block_type[-1]),
                "items": []
            }

        elif block_type == "bulleted_list_item":
            text_content = block.get(block_type, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_content])

            if current_section is None:
                current_section = {"title": "Content", "level": 1, "items": []}
            current_section["items"].append(text)

        elif block_type == "numbered_list_item":
            text_content = block.get(block_type, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_content])

            if current_section is None:
                current_section = {"title": "Content", "level": 1, "items": []}
            current_section["items"].append(text)

        elif block_type == "paragraph":
            text_content = block.get(block_type, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in text_content])

            if text.strip():
                if current_section is None:
                    current_section = {"title": "Content", "level": 1, "items": []}
                current_section["items"].append(text)

    if current_section:
        sections.append(current_section)

    return sections

# ============ CREATE POWERPOINT ============
def create_pptx(title, sections):
    """Create PowerPoint from sections."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Title slide
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(12), Inches(2))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True

    p2 = tf.add_paragraph()
    p2.text = datetime.now().strftime("%B %Y")
    p2.font.size = Pt(20)

    # Agenda slide if multiple sections
    if len(sections) > 1:
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
            p.text = f"{i+1}. {section['title']}"
            p.font.size = Pt(18)

    # Content slides
    for section in sections:
        items = section["items"]
        if not items:
            # Just a divider slide
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12), Inches(1.5))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = section["title"]
            p.font.size = Pt(40)
            p.font.bold = True
            continue

        # Split into chunks of 6
        chunks = [items[i:i+6] for i in range(0, len(items), 6)]

        for chunk_idx, chunk in enumerate(chunks):
            slide = prs.slides.add_slide(prs.slide_layouts[6])

            # Title
            txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(1))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            slide_title = section["title"] if chunk_idx == 0 else f"{section['title']} (cont.)"
            p.text = slide_title
            p.font.size = Pt(28)
            p.font.bold = True

            # Content
            txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12), Inches(5.5))
            tf2 = txBox2.text_frame
            for i, item in enumerate(chunk):
                if i == 0:
                    p = tf2.paragraphs[0]
                else:
                    p = tf2.add_paragraph()
                p.text = f"• {item}"
                p.font.size = Pt(18)

    return prs

# ============ MAIN ============
notion_url = "PASTE_NOTION_URL_HERE"  # Replace with actual URL

page_id = extract_page_id(notion_url)
print(f"Page ID: {page_id}")

title, blocks = fetch_notion_page(page_id)
print(f"Title: {title}")
print(f"Blocks: {len(blocks)}")

sections = parse_blocks(blocks)
print(f"Sections: {len(sections)}")
for s in sections:
    print(f"  - {s['title']}: {len(s['items'])} items")

prs = create_pptx(title, sections)

output_file = f"{title.replace(' ', '_')}.pptx"
prs.save(output_file)
print(f"\nCreated: {output_file}")
```

Replace `PASTE_NOTION_URL_HERE` with the user's Notion URL, then run the code.

The PowerPoint file will be generated and available for download.
