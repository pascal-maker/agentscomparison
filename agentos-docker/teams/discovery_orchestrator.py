"""
Discovery Solution Orchestrator (5-Agent Architecture)
======================================================

Coordinates the generation of Discovery Solution reports using 5 specialized agents:

1. Orchestrator (this) - Workflow control, state management, user interaction
2. NotionReader - Reads input pages via MCP
3. SectionDrafter - Generates initial section drafts
4. Reviewer - Quality checks and improves drafts
5. PowerPointWriter - Converts final markdown to PowerPoint

Workflow:
    Input (Notion) → Reader → [Drafter → Reviewer]* → PowerPointWriter → Output
"""

import json
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.team import Team

from agents.notion_reader import notion_reader_agent, read_notion_page, extract_page_id, is_page_allowed
from agents.section_drafter import section_drafter_agent, draft_section
from agents.revisor import revisor_agent, revise_section, generate_feedback_questions
from agents.powerpoint_writer import (
    powerpoint_writer_agent,
    generate_powerpoint_from_markdown,
    suggest_slide_structure,
)
from db import get_postgres_db
from shared.state import ReportState, SectionState, ChangelogEntry, FALLBACK_INTAKE_TEXT

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiscoveryOrchestrator")

# ============================================================================
# Setup
# ============================================================================
team_db = get_postgres_db(contents_table="discovery_team_contents")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
MARKDOWN_OUTPUT = OUTPUT_DIR / "discover_solution.md"
PPTX_OUTPUT = OUTPUT_DIR / "discover_solution.pptx"


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Customer Configuration
# ============================================================================
class CustomerConfig:
    """Customer-specific configuration for report generation."""

    def __init__(
        self,
        name: str,
        mandatory_sections: List[str] = None,
        optional_sections: List[str] = None,
        custom_terminology: Dict[str, str] = None,
        input_pages: List[str] = None,
    ):
        self.name = name
        self.mandatory_sections = mandatory_sections or []
        self.optional_sections = optional_sections or []
        self.custom_terminology = custom_terminology or {}
        self.input_pages = input_pages or []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomerConfig":
        return cls(
            name=data.get("name", "Client"),
            mandatory_sections=data.get("mandatory_sections", []),
            optional_sections=data.get("optional_sections", []),
            custom_terminology=data.get("custom_terminology", {}),
            input_pages=data.get("input_pages", []),
        )


# Default template sections
DEFAULT_TEMPLATE_SECTIONS = [
    "Executive Summary",
    "Business Context",
    "Technical Architecture Overview",
    "Technology Stack",
    "Infrastructure & Hosting",
    "Security & Identity",
    "Development Practices",
    "Team & Organization",
    "Support & Operations",
    "Recommendations",
]


# ============================================================================
# Section Extraction
# ============================================================================
def extract_h3_sections(content: str) -> List[str]:
    """Extract all H3 headings from markdown content."""
    pattern = r"^###\s+(.+)$"
    matches = re.findall(pattern, content, re.MULTILINE)
    return [m.strip() for m in matches]


def extract_section_structure(content: str, section_title: str) -> str:
    """
    Extract the template structure for a specific section.
    Returns content from the H3 heading until the next H3 or end.
    """
    pattern = rf"^###\s+{re.escape(section_title)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""

    start = match.start()
    next_h3 = re.search(r"^###\s+", content[match.end():], re.MULTILINE)
    if next_h3:
        end = match.end() + next_h3.start()
    else:
        end = len(content)

    return content[start:end].strip()


def extract_evidence_for_section(
    section_title: str,
    intake_content: str,
    additional_sources: Dict[str, str] = None,
) -> List[Dict[str, str]]:
    """Extract relevant evidence snippets for a section from intake content."""
    evidence = []

    section_keywords = {
        "executive": ["overview", "summary", "platform", "solution", "key"],
        "business": ["business", "objective", "stakeholder", "success", "goal"],
        "architecture": ["architecture", "component", "system", "platform", "infrastructure"],
        "stack": ["stack", "framework", "language", "technology", "vue", "kotlin", "spring"],
        "hosting": ["hosting", "azure", "cloud", "deployment", "infrastructure", "vm"],
        "security": ["security", "authentication", "keycloak", "iam", "authorization"],
        "data": ["database", "data", "cosmos", "mysql", "redis", "storage"],
        "team": ["team", "developer", "structure", "organization"],
        "development": ["development", "agile", "scrum", "ci/cd", "pipeline", "testing"],
        "support": ["support", "incident", "monitoring", "availability"],
        "recommendation": ["recommendation", "improvement", "opportunity", "next"],
    }

    section_lower = section_title.lower()
    relevant_keywords = []
    for topic, keywords in section_keywords.items():
        if any(kw in section_lower for kw in [topic] + keywords[:2]):
            relevant_keywords.extend(keywords)

    if not relevant_keywords:
        relevant_keywords = section_title.lower().split()

    for line in intake_content.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in relevant_keywords):
            if line.strip() and len(line.strip()) > 10:
                evidence.append({
                    "source": "Intake Notes",
                    "content": line.strip()[:200],
                })

    if additional_sources:
        for source_name, source_content in additional_sources.items():
            for line in source_content.split("\n"):
                line_lower = line.lower()
                if any(kw in line_lower for kw in relevant_keywords):
                    if line.strip() and len(line.strip()) > 10:
                        evidence.append({
                            "source": source_name,
                            "content": line.strip()[:200],
                        })

    return evidence[:10]


# ============================================================================
# Orchestrator Agent
# ============================================================================
orchestrator_instructions = """\
You are the Discovery Solution Orchestrator, the lead coordinator for report generation.

## Your Role

You manage a team of 4 specialized agents:
1. **NotionReader** - Reads input from Notion pages
2. **SectionDrafter** - Creates initial drafts of sections
3. **Reviewer** - Improves quality and accuracy
4. **PowerPointWriter** - Formats final output

## Workflow

### Phase 1: Input Collection
- Validate input page URLs (must be in allowlist)
- Read all input sources (interviews, workshops, desk research)
- Combine into unified intake content

### Phase 2: Section Processing
For each section in the template:
1. Extract relevant evidence from intake
2. Delegate to SectionDrafter
3. Delegate to Reviewer for quality check
4. Present to user for approval
5. Iterate if user provides feedback

### Phase 3: Final Output
- Compile all approved sections
- Delegate to PowerPointWriter
- Return links to markdown and PowerPoint files

## User Interaction

When presenting sections:
```
**Section [N] of [Total]: [Title]**

[Content]

---
**Feedback Questions:**
1. [Question]
2. [Question]
...

Reply "approve" to accept, or provide corrections.
```

## Commands

- "start [template_url] [intake_url]" - Begin report generation
- "approve" - Accept current section
- "skip" - Skip to next section
- "status" - Show progress
- "export" - Generate final PowerPoint
"""

orchestrator_agent = Agent(
    id="discovery-orchestrator-coordinator",
    name="Discovery Orchestrator",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=team_db,
    instructions=orchestrator_instructions,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=10,
    markdown=True,
)


# ============================================================================
# Workflow Functions
# ============================================================================
def read_input_pages(
    page_urls: List[str],
    use_fallback: bool = True,
) -> Dict[str, str]:
    """
    Read multiple input pages from Notion.

    Args:
        page_urls: List of Notion page URLs
        use_fallback: Whether to use fallback content if MCP fails

    Returns:
        Dict mapping source name to content
    """
    sources = {}

    for i, url in enumerate(page_urls):
        # Check if allowed first
        is_allowed, reason = is_page_allowed(url)
        if not is_allowed:
            logger.warning(f"Skipping blocked page: {url} - {reason}")
            sources[f"Blocked Source {i+1}"] = f"[ACCESS BLOCKED: {reason}]"
            continue

        result = read_notion_page(url, use_fallback=use_fallback)

        if result["success"]:
            page_id = result["metadata"]["page_id"]
            sources[f"Input Page {i+1}"] = result["content"]
            logger.info(f"Successfully read page: {page_id}")
        elif result["blocked"]:
            sources[f"Blocked Source {i+1}"] = f"[ACCESS BLOCKED: {result['error']}]"
        else:
            logger.warning(f"Failed to read page {url}: {result['error']}")
            if use_fallback:
                sources[f"Fallback {i+1}"] = "[Content unavailable - using fallback]"

    return sources


def process_start_command(
    template_url: str,
    intake_urls: List[str],
    customer_config: CustomerConfig,
    state: Optional[ReportState] = None,
) -> tuple[str, ReportState]:
    """
    Initialize the report generation process.

    Args:
        template_url: Notion URL for the template (or None to use default)
        intake_urls: List of Notion URLs for intake documents
        customer_config: Customer-specific configuration
        state: Existing state or None to create new

    Returns:
        Tuple of (response message, updated state)
    """
    ensure_output_dir()

    if state is None:
        state = ReportState(customer_name=customer_config.name)

    state.template_url = template_url or ""
    state.intake_url = ",".join(intake_urls)
    state.status = "reading_inputs"

    logger.info(f"Starting report for {customer_config.name}")
    logger.info(f"Reading {len(intake_urls)} input pages...")

    # Read template (if URL provided)
    if template_url:
        template_result = read_notion_page(template_url)
        if template_result["success"]:
            state.template_content = template_result["content"]
            state.template_sections = extract_h3_sections(state.template_content)
        else:
            logger.warning(f"Could not read template: {template_result['error']}")

    # Use default sections if no template or template read failed
    if not state.template_sections:
        state.template_sections = (
            customer_config.mandatory_sections or DEFAULT_TEMPLATE_SECTIONS
        )
        # Build default template content
        state.template_content = "\n\n".join([
            f"### {section}\n- Key points to cover\n- Evidence-based content"
            for section in state.template_sections
        ])

    # Initialize section states
    for title in state.template_sections:
        state.sections[title] = SectionState(
            title=title,
            template_structure=extract_section_structure(state.template_content, title),
        )

    # Read intake pages
    state.status = "reading_intake"
    intake_sources = read_input_pages(intake_urls, use_fallback=True)

    # Combine all intake content
    combined_intake = []
    for source_name, content in intake_sources.items():
        combined_intake.append(f"## {source_name}\n\n{content}")
        state.additional_sources[source_name] = content

    if combined_intake:
        state.intake_content = "\n\n---\n\n".join(combined_intake)
    else:
        logger.warning("No intake content read, using fallback")
        state.intake_content = FALLBACK_INTAKE_TEXT

    state.status = "processing"
    state.current_section_index = 0

    # Build response
    section_list = "\n".join([
        f"{i+1}. {s}" for i, s in enumerate(state.template_sections)
    ])

    response = f"""
# Discovery Solution Report - {customer_config.name}

**Input sources loaded**: {len(intake_sources)} pages
**Template sections**: {len(state.template_sections)} sections
**Intake content**: {len(state.intake_content)} characters

## Sections to Process:
{section_list}

---

Starting with Section 1...

"""

    # Process first section
    section_response, state = process_current_section(state)
    response += section_response

    return response, state


def process_current_section(state: ReportState) -> tuple[str, ReportState]:
    """
    Process the current section: draft, revise, and present for feedback.
    """
    section_title = state.get_current_section_title()
    if not section_title:
        return "All sections completed!", state

    section = state.sections[section_title]
    section.status = "drafting"

    logger.info(f"Processing section: {section_title}")

    # Extract evidence
    evidence = extract_evidence_for_section(
        section_title,
        state.intake_content,
        state.additional_sources,
    )
    section.evidence = evidence

    # Draft the section (Agent 3: SectionDrafter)
    logger.info(f"Drafting section: {section_title}")
    drafted = draft_section(
        section_title=section_title,
        template_structure=section.template_structure or f"### {section_title}\n- Key points\n- Evidence-based content",
        evidence_snippets=evidence,
        customer_name=state.customer_name,
        mandatory_elements=state.mandatory_elements,
    )

    section.status = "reviewing"

    # Revise the section (Agent 4: Reviewer)
    logger.info(f"Reviewing section: {section_title}")
    revision_result = revise_section(
        drafted_section=drafted,
        customer_name=state.customer_name,
        evidence_list=evidence,
        mandatory_elements=state.mandatory_elements,
    )

    section.draft = revision_result["revised_section"]
    section.revision_count += 1

    # Generate feedback questions
    questions = generate_feedback_questions(
        section_title=section_title,
        section_content=section.draft,
        open_questions=revision_result.get("open_questions", []),
    )
    state.pending_questions = questions

    # Build response
    total = len(state.template_sections)
    current = state.current_section_index + 1

    response = f"""
**Section {current} of {total}: {section_title}**

{section.draft}

---

**Feedback Questions:**
"""
    for i, q in enumerate(questions, 1):
        response += f"{i}. {q}\n"

    response += """
---
Reply **"approve"** to accept this section, or provide corrections/feedback.
"""

    return response, state


def process_user_feedback(user_message: str, state: ReportState) -> tuple[str, ReportState]:
    """Process user feedback on the current section."""
    message_lower = user_message.lower().strip()

    approve_keywords = ["approve", "approved", "ok", "okay", "next", "lgtm", "looks good", "accept", "yes"]
    if any(kw in message_lower for kw in approve_keywords):
        return approve_current_section(state)

    if message_lower == "skip":
        return skip_current_section(state)

    if message_lower == "export":
        return export_final_report(state)

    if message_lower == "status":
        return get_status(state)

    return revise_with_feedback(user_message, state)


def approve_current_section(state: ReportState) -> tuple[str, ReportState]:
    """Approve the current section and advance to the next."""
    section_title = state.get_current_section_title()
    if not section_title:
        return "No section to approve.", state

    section = state.sections[section_title]
    section.status = "approved"

    state.changelog.append(ChangelogEntry(
        section_title=section_title,
        action="approved",
    ))

    save_progress(state)
    logger.info(f"Approved section: {section_title}")

    if state.advance_section():
        response = f"**{section_title}** approved!\n\n"
        section_response, state = process_current_section(state)
        response += section_response
    else:
        state.status = "completed"
        response = finalize_report(state)

    return response, state


def skip_current_section(state: ReportState) -> tuple[str, ReportState]:
    """Skip the current section."""
    section_title = state.get_current_section_title()
    if not section_title:
        return "No section to skip.", state

    section = state.sections[section_title]
    section.status = "skipped"

    state.changelog.append(ChangelogEntry(
        section_title=section_title,
        action="skipped",
    ))

    logger.info(f"Skipped section: {section_title}")

    if state.advance_section():
        response = f"Skipped **{section_title}**\n\n"
        section_response, state = process_current_section(state)
        response += section_response
    else:
        state.status = "completed"
        response = finalize_report(state)

    return response, state


def revise_with_feedback(feedback: str, state: ReportState) -> tuple[str, ReportState]:
    """Revise the current section based on user feedback."""
    section_title = state.get_current_section_title()
    if not section_title:
        return "No section to revise.", state

    section = state.sections[section_title]
    section.feedback_history.append(feedback)

    logger.info(f"Revising section with feedback: {section_title}")

    prompt = f"""
Revise this section based on user feedback.

**Current Section:**
{section.draft}

**User Feedback:**
{feedback}

**Original Evidence:**
{json.dumps(section.evidence, indent=2)}

Incorporate the feedback while maintaining:
- The same structure
- Evidence-based content
- Professional tone

Return the complete revised section.
"""

    response = revisor_agent.run(prompt)
    revised = response.content if hasattr(response, 'content') else str(response)

    section.draft = revised
    section.revision_count += 1

    questions = generate_feedback_questions(
        section_title=section_title,
        section_content=section.draft,
    )
    state.pending_questions = questions

    total = len(state.template_sections)
    current = state.current_section_index + 1

    result = f"""
**Revised Section {current} of {total}: {section_title}** (Revision {section.revision_count})

{section.draft}

---

**Updated Questions:**
"""
    for i, q in enumerate(questions, 1):
        result += f"{i}. {q}\n"

    result += """
---
Reply **"approve"** to accept, or provide more corrections.
"""

    return result, state


def get_status(state: ReportState) -> tuple[str, ReportState]:
    """Get current progress status."""
    approved = sum(1 for s in state.sections.values() if s.status == "approved")
    skipped = sum(1 for s in state.sections.values() if s.status == "skipped")
    pending = len(state.template_sections) - approved - skipped

    current_title = state.get_current_section_title() or "None"

    status = f"""
# Report Status: {state.customer_name}

**Progress:** {approved}/{len(state.template_sections)} sections approved
**Skipped:** {skipped}
**Remaining:** {pending}
**Current:** {current_title}

## Section Status:
"""
    for i, title in enumerate(state.template_sections):
        section = state.sections.get(title)
        status_icon = {
            "approved": "[x]",
            "skipped": "[-]",
            "drafting": "[~]",
            "reviewing": "[~]",
        }.get(section.status if section else "pending", "[ ]")

        marker = " <-- current" if i == state.current_section_index else ""
        status += f"{status_icon} {title}{marker}\n"

    return status, state


def save_progress(state: ReportState):
    """Save current progress to markdown file."""
    ensure_output_dir()
    content = state.get_approved_sections_markdown()
    MARKDOWN_OUTPUT.write_text(content)
    logger.info(f"Progress saved to: {MARKDOWN_OUTPUT}")


def finalize_report(state: ReportState) -> str:
    """Finalize the report and generate outputs."""
    ensure_output_dir()

    # Save markdown
    markdown_content = state.get_approved_sections_markdown()
    MARKDOWN_OUTPUT.write_text(markdown_content)

    # Generate PowerPoint (Agent 5: PowerPointWriter)
    logger.info("Generating PowerPoint output...")
    pptx_result = generate_powerpoint_from_markdown(
        markdown_content=markdown_content,
        customer_name=state.customer_name,
        output_filename=f"discover_solution_{state.customer_name.replace(' ', '_')}.pptx",
    )

    approved_count = sum(1 for s in state.sections.values() if s.status == "approved")
    revision_count = sum(s.revision_count for s in state.sections.values())

    result = f"""
# Report Complete!

All sections have been processed.

## Summary
- **Customer:** {state.customer_name}
- **Sections approved:** {approved_count}/{len(state.template_sections)}
- **Total revisions:** {revision_count}

## Output Files
- **Markdown:** `{MARKDOWN_OUTPUT}`
"""

    if pptx_result["success"]:
        result += f"- **PowerPoint:** `{pptx_result['output_path']}` ({pptx_result['slide_count']} slides)\n"
    else:
        result += f"- **PowerPoint:** Failed - {pptx_result['error']}\n"

    result += """
## Changelog
"""
    for e in state.changelog:
        result += f"- {e.timestamp.strftime('%H:%M:%S')} | {e.section_title} | {e.action}\n"

    return result


def export_final_report(state: ReportState) -> tuple[str, ReportState]:
    """Export the current report even if not all sections are approved."""
    return finalize_report(state), state


# ============================================================================
# Team Definition
# ============================================================================
discovery_team = Team(
    id="discovery-orchestrator",
    name="Discovery Solution Team",
    members=[
        orchestrator_agent,
        notion_reader_agent,
        section_drafter_agent,
        revisor_agent,
        powerpoint_writer_agent,
    ],
    model=Claude(id="claude-sonnet-4-20250514"),
    db=team_db,
    description="""
A 5-agent team that generates Discover Solution reports:

1. **Orchestrator** - Workflow control and user interaction
2. **NotionReader** - Reads input from Notion pages (with safety checks)
3. **SectionDrafter** - Creates initial section drafts
4. **Reviewer** - Quality checks and improvements
5. **PowerPointWriter** - Generates final PowerPoint output

Workflow: Input → Reader → [Drafter → Reviewer]* → PowerPointWriter → Output
""",
    instructions="""
You are the Discovery Solution Team coordinator.

When a user provides Notion URLs, start the report generation process.
Process sections one at a time, getting user approval before moving on.

Key commands:
- START: Initialize with intake URLs
- APPROVE: Accept current section
- SKIP: Skip current section
- STATUS: Show progress
- EXPORT: Generate final output
""",
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    markdown=True,
    enable_agentic_memory=True,
)


# ============================================================================
# Convenience Functions
# ============================================================================
def start_report(
    customer_name: str,
    intake_urls: List[str],
    template_url: str = None,
    mandatory_sections: List[str] = None,
) -> tuple[str, ReportState]:
    """
    Convenience function to start a new report.

    Args:
        customer_name: Name of the customer
        intake_urls: List of Notion URLs with input content
        template_url: Optional Notion URL for template
        mandatory_sections: Optional list of required sections

    Returns:
        Tuple of (response message, state)
    """
    config = CustomerConfig(
        name=customer_name,
        mandatory_sections=mandatory_sections,
        input_pages=intake_urls,
    )

    return process_start_command(
        template_url=template_url,
        intake_urls=intake_urls,
        customer_config=config,
    )


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Discovery Solution Orchestrator - 5 Agent Architecture")
    print("=" * 60)
    print("\nAgents:")
    print("  1. Orchestrator - Workflow control")
    print("  2. NotionReader - Input from Notion")
    print("  3. SectionDrafter - Draft sections")
    print("  4. Reviewer - Quality check")
    print("  5. PowerPointWriter - Generate output")
    print("\n" + "=" * 60)

    # Test with fallback content (no MCP required)
    print("\nTesting with fallback content...")

    response, state = start_report(
        customer_name="Test Customer",
        intake_urls=[],  # Empty = use fallback
        mandatory_sections=[
            "Executive Summary",
            "Technical Architecture Overview",
            "Recommendations",
        ],
    )

    print(response)
