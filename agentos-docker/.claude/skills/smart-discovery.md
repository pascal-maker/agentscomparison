---
name: smart-discovery
description: Generate evidence-grounded PowerPoint from Notion with LLM analysis
args: <notion_url> [customer_name]
---

# Smart Discovery

Generate an evidence-grounded PowerPoint presentation from a Notion page with LLM analysis.

## Usage

```
/smart-discovery <notion_url> [customer_name]
```

## Examples

```
/smart-discovery https://www.notion.so/mypage-abc123
/smart-discovery https://www.notion.so/mypage-abc123 "Acme Corp"
```

## What it does

1. Reads the Notion page
2. Extracts evidence items with unique IDs
3. LLM analyzes content and discovers logical sections
4. Maps every bullet to source evidence `[EVID-xxx]`
5. Revisor pass removes ungrounded content
6. Generates Markdown report + PowerPoint

## Output

- `output/smart_discovery_{customer}.md` - Report with evidence references
- `output/smart_discovery_{customer}.pptx` - PowerPoint presentation

## Instructions

When the user invokes this skill:

1. Extract the Notion URL from the command
2. Extract optional customer name (default: page title)
3. Run the following Python code:

```python
import os
os.environ["NOTION_TOKEN"] = "YOUR_NOTION_TOKEN"  # User must set this
os.environ["NOTION_SAFE_MODE"] = "false"

from teams.smart_discovery import smart_discover
from shared.evidence import CustomerConfig

result = smart_discover(
    notion_url="<NOTION_URL>",
    customer_name="<CUSTOMER_NAME>",
    config=CustomerConfig(
        name="<CUSTOMER_NAME>",
        must_include=["Executive Summary", "Key Findings", "Recommendations"]
    )
)

if result["success"]:
    print(f"Created: {result['powerpoint_path']}")
    print(f"Evidence items: {result['evidence_count']}")
    print(f"Sections: {result['sections']}")
else:
    print(f"Error: {result['error']}")
```

4. Report the results to the user

## Requirements

- `NOTION_TOKEN` environment variable must be set
- `ANTHROPIC_API_KEY` for LLM analysis
