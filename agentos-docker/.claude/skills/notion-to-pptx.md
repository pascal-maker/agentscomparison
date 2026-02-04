# Notion to PowerPoint (Simple Mode)

Convert any Notion page directly to PowerPoint slides - no LLM analysis, just preserves the original structure.

## Usage

```
/notion-to-pptx <notion_url> [title]
```

## Examples

```
/notion-to-pptx https://www.notion.so/mypage-abc123
/notion-to-pptx https://www.notion.so/mypage-abc123 "My Presentation"
```

## What it does

1. Reads the Notion page
2. Parses headings, bullets, and paragraphs
3. Creates slides preserving the original structure
4. No LLM calls - fast and deterministic

## Output

- `output/notion_pptx_{page_name}.pptx` - PowerPoint presentation

## Slide Structure

- **Title slide**: Page title + date
- **Agenda slide**: List of all sections (if multiple)
- **Content slides**: 6 items per slide, continues with "(cont.)" if needed

## Instructions

When the user invokes this skill:

1. Extract the Notion URL from the command
2. Extract optional title (default: uses Notion page title)
3. Run the following Python code:

```python
import os
os.environ["NOTION_TOKEN"] = "YOUR_NOTION_TOKEN"  # User must set this
os.environ["NOTION_SAFE_MODE"] = "false"

from teams.notion_to_pptx import notion_to_pptx

result = notion_to_pptx(
    notion_url="<NOTION_URL>",
    title="<TITLE>"  # optional
)

if result["success"]:
    print(f"Created: {result['powerpoint_path']}")
    print(f"Slides: {result['slide_count']}")
    print(f"Sections: {result['sections']}")
else:
    print(f"Error: {result['error']}")
```

4. Report the results to the user

## Requirements

- `NOTION_TOKEN` environment variable must be set

## When to use this vs Smart Discovery

| Use Simple Mode | Use Smart Discovery |
|-----------------|---------------------|
| Quick conversion | Need evidence grounding |
| Any content type | Discovery/analysis reports |
| Preserve exact structure | Auto-categorize content |
| No LLM needed | Generate insights |
