"""
Smart Discovery Workflow
========================

Automatically discovers structure from any input content.
No predefined templates - AI determines what's important.

Workflow:
1. Read Notion page(s)
2. Content Analyzer discovers key themes and sections
3. Section Drafter generates content for each discovered section
4. Reviewer checks quality
5. PowerPoint Writer creates Sweetspot presentation
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from agno.agent import Agent
from agno.models.anthropic import Claude

from agents.notion_reader import read_notion_page
from agents.content_analyzer import analyze_content, content_analyzer_agent
from agents.powerpoint_writer import (
    generate_powerpoint_from_markdown,
    SlideContent,
    create_powerpoint,
    parse_markdown_to_slides,
)

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartDiscovery")

# ============================================================================
# Output Directory
# ============================================================================
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
OUTPUT_DIR.mkdir(exist_ok=True)


def smart_discover(
    notion_url: str = None,
    raw_content: str = None,
    customer_name: str = "Client",
) -> Dict[str, Any]:
    """
    Smart discovery that auto-detects structure from any content.

    Args:
        notion_url: Notion page URL to read (optional)
        raw_content: Raw content string (alternative to notion_url)
        customer_name: Customer name for the report

    Returns:
        Dict with:
        - success: bool
        - markdown_path: path to generated .md file
        - powerpoint_path: path to generated .pptx file
        - sections: list of discovered sections
        - error: error message if failed
    """
    result = {
        "success": False,
        "markdown_path": None,
        "powerpoint_path": None,
        "sections": [],
        "error": None,
    }

    # Step 1: Get content
    logger.info("=" * 60)
    logger.info("SMART DISCOVERY WORKFLOW")
    logger.info("=" * 60)

    if notion_url:
        logger.info(f"Reading Notion page: {notion_url}")
        notion_result = read_notion_page(notion_url)
        if not notion_result["success"]:
            result["error"] = f"Failed to read Notion: {notion_result['error']}"
            return result
        content = notion_result["content"]
        logger.info(f"Read {len(content)} characters from Notion")
    elif raw_content:
        content = raw_content
        logger.info(f"Using provided content: {len(content)} characters")
    else:
        result["error"] = "No content provided (need notion_url or raw_content)"
        return result

    # Step 2: Analyze content and discover structure
    logger.info("\nStep 2: Analyzing content to discover structure...")
    analysis = analyze_content(content, context=f"Discovery for {customer_name}")

    discovered_title = analysis.get("title", f"Discovery Report: {customer_name}")
    discovered_sections = analysis.get("sections", [])
    summary = analysis.get("summary", "")
    open_questions = analysis.get("open_questions", [])

    logger.info(f"Discovered title: {discovered_title}")
    logger.info(f"Discovered {len(discovered_sections)} sections:")
    for i, section in enumerate(discovered_sections, 1):
        logger.info(f"  {i}. {section.get('name')}")

    result["sections"] = [s.get("name") for s in discovered_sections]

    # Step 3: Generate markdown report
    logger.info("\nStep 3: Generating markdown report...")

    md_lines = [
        f"# {discovered_title}",
        "",
        f"**Customer:** {customer_name}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    # Add executive summary
    md_lines.extend([
        "### Executive Summary",
        "",
        summary if summary else "*Summary to be added based on complete analysis.*",
        "",
    ])

    # Add discovered sections
    for section in discovered_sections:
        section_name = section.get("name", "Section")
        description = section.get("description", "")
        key_points = section.get("key_points", [])
        evidence = section.get("evidence", [])

        md_lines.extend([
            f"### {section_name}",
            "",
        ])

        if description:
            md_lines.append(description)
            md_lines.append("")

        if key_points:
            for point in key_points:
                md_lines.append(f"- {point}")
            md_lines.append("")

        if evidence:
            md_lines.append("**Evidence Sources:**")
            for ev in evidence:
                md_lines.append(f"- {ev}")
            md_lines.append("")

        md_lines.append("")

    # Add open questions
    if open_questions:
        md_lines.extend([
            "### Open Questions",
            "",
        ])
        for q in open_questions:
            md_lines.append(f"- {q}")
        md_lines.append("")

    # Add recommendations placeholder
    md_lines.extend([
        "### Recommendations",
        "",
        "*Recommendations to be developed based on findings.*",
        "",
        "---",
        "",
        f"*Report generated by Smart Discovery on {datetime.now().isoformat()}*",
    ])

    markdown_content = "\n".join(md_lines)

    # Save markdown
    safe_name = "".join(c if c.isalnum() else "_" for c in customer_name)
    md_filename = f"smart_discovery_{safe_name}.md"
    md_path = OUTPUT_DIR / md_filename
    md_path.write_text(markdown_content)
    result["markdown_path"] = str(md_path)
    logger.info(f"Saved markdown: {md_path}")

    # Step 4: Generate PowerPoint
    logger.info("\nStep 4: Generating PowerPoint...")

    pptx_result = generate_powerpoint_from_markdown(
        markdown_content=markdown_content,
        customer_name=customer_name,
        output_filename=f"smart_discovery_{safe_name}.pptx",
    )

    if pptx_result["success"]:
        result["powerpoint_path"] = pptx_result["output_path"]
        logger.info(f"Generated PowerPoint: {pptx_result['output_path']} ({pptx_result['slide_count']} slides)")
    else:
        logger.warning(f"PowerPoint generation failed: {pptx_result['error']}")

    result["success"] = True
    logger.info("\n" + "=" * 60)
    logger.info("SMART DISCOVERY COMPLETE")
    logger.info("=" * 60)

    return result


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    import sys

    # Test with sample content
    test_content = """
    # Product Interview - TaskFlow App

    Interviewed Sarah Chen, Product Owner, on January 15, 2025.

    ## Product Vision
    TaskFlow aims to be the simplest task management app for small teams of 2-10 people.
    We want to help teams stay organized without the complexity of enterprise tools like Jira or Asana.

    ## Target Users
    Our primary users are:
    - Freelancers managing multiple clients
    - Small agency teams (design, marketing, dev shops)
    - Startup founders juggling many priorities
    - Remote teams needing simple collaboration

    ## Current Pain Points
    Users told us:
    - "Existing tools are too complex - I spend more time managing the tool than doing work"
    - "Trello boards get messy fast with a team"
    - "Notion requires too much setup for simple task tracking"
    - "We end up using spreadsheets because nothing else is simple enough"

    ## Competitive Landscape
    Main competitors:
    - Todoist: Good for individuals, lacks team features
    - Trello: Board-based doesn't work for everyone
    - Notion: Too much setup required
    - Linear: Too developer-focused

    ## Key Features Requested
    Must-have features from user research:
    1. Simple task creation (one click, no forms)
    2. Team assignment with @mentions
    3. Due date tracking with calendar view
    4. Basic project grouping
    5. Mobile app (iOS priority, then Android)

    Nice-to-have:
    - Slack integration
    - Calendar sync
    - Time tracking

    ## Business Model
    Freemium approach:
    - Free: Individual use, up to 3 projects
    - Team: $5/user/month, unlimited projects
    - Target: 10,000 paying teams in Year 1

    ## Go-to-Market Strategy
    Phase 1 (Q1-Q2):
    - Launch on Product Hunt
    - Content marketing (blog, YouTube tutorials)
    - Target indie hackers and solopreneurs

    Phase 2 (Q3-Q4):
    - Agency partnerships
    - Paid acquisition (Google, LinkedIn)
    - Enterprise pilot program

    ## Success Metrics
    Key KPIs:
    - User activation rate: > 60%
    - Weekly active users retention: > 40%
    - NPS score: > 50
    - Time to first task: < 2 minutes

    ## Technical Notes
    Stack decision pending:
    - Frontend: React or Vue?
    - Backend: Node.js or Python?
    - Database: PostgreSQL
    - Hosting: AWS or Vercel?

    ## Open Items
    - Need to finalize pricing tiers
    - iOS developer hire in progress
    - Design system not started yet
    """

    print("Testing Smart Discovery...")
    result = smart_discover(
        raw_content=test_content,
        customer_name="TaskFlow"
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success: {result['success']}")
    print(f"Sections discovered: {len(result['sections'])}")
    for i, s in enumerate(result['sections'], 1):
        print(f"  {i}. {s}")
    print(f"Markdown: {result['markdown_path']}")
    print(f"PowerPoint: {result['powerpoint_path']}")
    if result['error']:
        print(f"Error: {result['error']}")
