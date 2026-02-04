"""
Content Analyzer Agent
======================

Analyzes input content and discovers the most important sections/themes.
No predefined templates - AI determines structure based on content.
"""

import os
import logging
from typing import List, Dict, Any

from agno.agent import Agent
from agno.models.anthropic import Claude

from db import get_postgres_db

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContentAnalyzer")

# ============================================================================
# Setup
# ============================================================================
agent_db = get_postgres_db(contents_table="content_analyzer_contents")

# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a Content Analyzer that discovers the structure and key themes from input documents.

## Your Task

Given raw input content (interviews, research notes, workshop outputs, etc.), you must:

1. **Identify Key Themes**: What are the main topics discussed?
2. **Extract Important Facts**: What concrete information is present?
3. **Determine Logical Sections**: How should this be organized for a report?
4. **Find Evidence**: What quotes/data support each section?

## Output Format

Return a JSON structure with discovered sections:

```json
{
  "title": "Discovered report title based on content",
  "sections": [
    {
      "name": "Section Name",
      "description": "What this section covers",
      "key_points": ["point 1", "point 2"],
      "evidence": ["quote or fact from input"]
    }
  ],
  "open_questions": ["Questions that need answers"],
  "summary": "Brief executive summary"
}
```

## Guidelines

- Only create sections for topics that have actual content
- Don't force content into predefined categories
- Section names should reflect what's actually discussed
- Keep 3-8 sections (not too few, not too many)
- Every key point must have supporting evidence
- Identify gaps where information is missing
"""

# ============================================================================
# Create Agent
# ============================================================================
content_analyzer_agent = Agent(
    id="content-analyzer",
    name="Content Analyzer",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=agent_db,
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


def analyze_content(content: str, context: str = "") -> Dict[str, Any]:
    """
    Analyze content and discover its structure.

    Args:
        content: Raw input content (interviews, notes, research)
        context: Optional context about the content

    Returns:
        Dict with discovered structure:
        {
            "title": str,
            "sections": [{"name", "description", "key_points", "evidence"}],
            "open_questions": [str],
            "summary": str
        }
    """
    prompt = f"""
Analyze this content and discover its structure. Return a JSON object with the discovered sections.

{f"Context: {context}" if context else ""}

## Input Content:
```
{content}
```

## Instructions:
1. Read the entire content carefully
2. Identify the main themes and topics discussed
3. Create logical sections based on what's actually present
4. Extract key points and supporting evidence for each section
5. Note any open questions or gaps in information
6. Write a brief executive summary

Return ONLY a valid JSON object with this structure:
{{
  "title": "Report title based on content",
  "sections": [
    {{
      "name": "Section Name",
      "description": "What this section covers",
      "key_points": ["point 1", "point 2"],
      "evidence": ["direct quote or fact"]
    }}
  ],
  "open_questions": ["question 1", "question 2"],
  "summary": "Executive summary paragraph"
}}
"""

    try:
        response = content_analyzer_agent.run(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from response
        import json
        import re

        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            logger.info(f"Discovered {len(result.get('sections', []))} sections")
            return result
        else:
            logger.error("No JSON found in response")
            return {
                "title": "Analysis Results",
                "sections": [],
                "open_questions": ["Unable to parse content structure"],
                "summary": response_text[:500]
            }

    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        return {
            "title": "Analysis Error",
            "sections": [],
            "open_questions": [str(e)],
            "summary": "Failed to analyze content"
        }


def analyze_and_generate_sections(content: str, customer_name: str = "Client") -> List[str]:
    """
    Analyze content and return list of discovered section names.

    This replaces the hardcoded template sections with dynamic discovery.

    Args:
        content: Input content to analyze
        customer_name: Customer name for context

    Returns:
        List of section names discovered from content
    """
    result = analyze_content(content, context=f"Discovery report for {customer_name}")

    sections = []
    for section in result.get("sections", []):
        sections.append(section.get("name", "Unnamed Section"))

    # Always ensure we have at least summary and recommendations
    if not sections:
        sections = ["Executive Summary", "Key Findings", "Recommendations"]
    elif "Executive Summary" not in sections:
        sections.insert(0, "Executive Summary")
    if "Recommendations" not in sections:
        sections.append("Recommendations")

    return sections


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    # Test with sample content
    test_content = """
    # Product Interview - TaskFlow App

    Interviewed Sarah, Product Owner, on Jan 15.

    ## Vision
    TaskFlow wants to be the simplest task app for small teams (2-10 people).
    Main competitors are Todoist, Trello, and Notion - all too complex.

    ## Target Users
    - Freelancers with multiple clients
    - Small agency teams
    - Remote workers

    ## Key Features Needed
    1. One-click task creation
    2. Simple team assignment
    3. Due date tracking
    4. Mobile app (iOS and Android)

    ## Business Model
    Freemium - free for individuals, $5/user/month for teams.
    Launch planned on Product Hunt Q2.

    ## Success Metrics
    - 60% activation rate target
    - 40% weekly retention
    - NPS > 50
    """

    print("Testing Content Analyzer...")
    print("=" * 60)

    result = analyze_content(test_content, "TaskFlow product discovery")

    print(f"\nTitle: {result.get('title')}")
    print(f"\nSummary: {result.get('summary')}")
    print(f"\nDiscovered Sections:")
    for i, section in enumerate(result.get('sections', []), 1):
        print(f"  {i}. {section.get('name')}")
        print(f"     Key points: {len(section.get('key_points', []))}")
    print(f"\nOpen Questions: {len(result.get('open_questions', []))}")
