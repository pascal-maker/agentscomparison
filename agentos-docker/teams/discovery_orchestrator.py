"""
Discovery Solution Orchestrator Team
====================================

A multi-agent team that generates a "Discover Solution" report
by reading Notion pages, drafting sections interactively,
and compiling the final document.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.team import Team

from agents.notion_reader import notion_reader_agent, read_notion_page, extract_page_id
from agents.section_drafter import section_drafter_agent, draft_section
from agents.revisor import revisor_agent, revise_section, generate_feedback_questions
from db import get_postgres_db
from shared.state import ReportState, SectionState, ChangelogEntry, FALLBACK_INTAKE_TEXT

# ============================================================================
# Setup
# ============================================================================
team_db = get_postgres_db(contents_table="discovery_team_contents")
OUTPUT_DIR = Path("./countroll_report")
OUTPUT_FILE = OUTPUT_DIR / "discover_solution_countroll.md"


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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
    # Find the section start
    pattern = rf"^###\s+{re.escape(section_title)}\s*$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""

    start = match.start()

    # Find the next H3 or end of content
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
    """
    Extract relevant evidence snippets for a section from intake content.
    Uses keyword matching to find relevant passages.
    """
    evidence = []

    # Keywords to look for based on common section topics
    section_keywords = {
        "architecture": ["architecture", "component", "system", "platform", "infrastructure"],
        "stack": ["stack", "framework", "language", "technology", "vue", "kotlin", "spring"],
        "hosting": ["hosting", "azure", "cloud", "deployment", "infrastructure", "vm"],
        "security": ["security", "authentication", "keycloak", "iam", "authorization"],
        "data": ["database", "data", "cosmos", "mysql", "redis", "storage"],
        "team": ["team", "developer", "structure", "organization"],
        "process": ["process", "agile", "scrum", "ci/cd", "pipeline", "testing"],
        "support": ["support", "incident", "monitoring", "availability"],
    }

    # Find relevant keywords for this section
    section_lower = section_title.lower()
    relevant_keywords = []
    for topic, keywords in section_keywords.items():
        if any(kw in section_lower for kw in keywords):
            relevant_keywords.extend(keywords)

    # If no specific keywords, use generic ones
    if not relevant_keywords:
        relevant_keywords = section_title.lower().split()

    # Search intake content for relevant lines
    for line in intake_content.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in relevant_keywords):
            if line.strip() and len(line.strip()) > 10:
                evidence.append({
                    "source": "Intake Notes",
                    "content": line.strip()[:200],
                })

    # Add from additional sources
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

    return evidence[:10]  # Limit to 10 most relevant


# ============================================================================
# Orchestrator Agent
# ============================================================================
orchestrator_instructions = """\
You are the Discovery Solution Orchestrator, coordinating the generation of a comprehensive technical report.

## Your Role

You manage the interactive report generation process:
1. Load template and intake documents from Notion
2. Process each section one at a time
3. Coordinate with specialist agents (Drafter, Revisor)
4. Interact with the user for feedback
5. Compile the final report

## Workflow

For each user message, determine the appropriate action:

### First Message (Start)
If user provides Notion URLs or asks to start:
- Parse the template URL and intake URL
- Load content (via Notion MCP or fallback)
- Extract H3 sections from template
- Start with section 1

### Section Processing
For the current section:
1. Delegate to Section Drafter to create initial draft
2. Delegate to Revisor to improve quality
3. Present the section to user with feedback questions
4. Wait for user response

### User Feedback
Parse user response:
- "approve", "ok", "next", "lgtm" → Approve section, advance to next
- Any other text → Treat as corrections, revise section

### Completion
When all sections are approved:
- Compile final markdown
- Save to output file
- Show summary to user

## State Management

You maintain state across turns including:
- Current section index
- Approved sections
- Open questions
- Compilation progress

## Output Format

Always respond with structured output:
```
**Section [N] of [Total]: [Section Title]**

[Section Content]

---
**Evidence Sources:**
[List of sources]

---
**Feedback Questions:**
1. [Question 1]
2. [Question 2]
...

Reply "approve" to accept, or provide corrections.
```
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
# Process Functions
# ============================================================================
def process_start_command(
    template_url: str,
    intake_url: str,
    customer_name: str = "Countroll",
    state: Optional[ReportState] = None,
) -> tuple[str, ReportState]:
    """
    Initialize the report generation process.

    Args:
        template_url: Notion URL for the template
        intake_url: Notion URL for the intake document
        customer_name: Client name
        state: Existing state or None to create new

    Returns:
        Tuple of (response message, updated state)
    """
    ensure_output_dir()

    if state is None:
        state = ReportState(customer_name=customer_name)

    state.template_url = template_url
    state.intake_url = intake_url
    state.status = "reading_template"

    # Try to read template from Notion
    template_result = read_notion_page(template_url)
    if template_result["success"]:
        state.template_content = template_result["content"]
    else:
        # Use a default template structure
        state.template_content = """
### Executive Summary
Brief overview of the solution discovery findings.

### Business Context
- Business objectives
- Key stakeholders
- Success criteria

### Technical Architecture Overview
- High-level architecture
- Key components
- Integration points

### Technology Stack
- Frontend technologies
- Backend technologies
- Mobile technologies
- Data storage

### Infrastructure & Hosting
- Cloud platform
- Deployment model
- Scalability approach

### Security & Identity
- Authentication mechanism
- Authorization model
- Security measures

### Development Practices
- Development methodology
- CI/CD pipeline
- Testing approach
- Documentation

### Team & Organization
- Team structure
- Roles and responsibilities
- Communication channels

### Support & Operations
- Support model
- Incident management
- Monitoring approach

### Recommendations
- Key findings
- Improvement opportunities
- Next steps
"""

    # Extract sections
    state.template_sections = extract_h3_sections(state.template_content)

    # Initialize section states
    for title in state.template_sections:
        state.sections[title] = SectionState(
            title=title,
            template_structure=extract_section_structure(state.template_content, title),
        )

    state.status = "reading_intake"

    # Try to read intake from Notion
    intake_result = read_notion_page(intake_url)
    if intake_result["success"]:
        state.intake_content = intake_result["content"]
    else:
        # Use fallback
        state.intake_content = FALLBACK_INTAKE_TEXT

    state.status = "processing"
    state.current_section_index = 0

    # Build response
    section_list = "\n".join([f"{i+1}. {s}" for i, s in enumerate(state.template_sections)])
    response = f"""
# Discovery Solution Report - {customer_name}

**Template loaded**: {len(state.template_sections)} sections found
**Intake loaded**: {len(state.intake_content)} characters

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

    Returns:
        Tuple of (response message, updated state)
    """
    section_title = state.get_current_section_title()
    if not section_title:
        return "All sections completed!", state

    section = state.sections[section_title]
    section.status = "drafting"

    # Get evidence for this section
    evidence = extract_evidence_for_section(
        section_title,
        state.intake_content,
        state.additional_sources,
    )
    section.evidence = evidence

    # Draft the section
    drafted = draft_section(
        section_title=section_title,
        template_structure=section.template_structure,
        evidence_snippets=evidence,
        customer_name=state.customer_name,
        mandatory_elements=state.mandatory_elements,
    )

    section.status = "reviewing"

    # Revise the section
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
    """
    Process user feedback on the current section.

    Returns:
        Tuple of (response message, updated state)
    """
    message_lower = user_message.lower().strip()

    # Check if user approves
    approve_keywords = ["approve", "approved", "ok", "okay", "next", "lgtm", "looks good", "accept", "yes"]
    if any(kw in message_lower for kw in approve_keywords):
        return approve_current_section(state)
    else:
        return revise_with_feedback(user_message, state)


def approve_current_section(state: ReportState) -> tuple[str, ReportState]:
    """
    Approve the current section and advance to the next.

    Returns:
        Tuple of (response message, updated state)
    """
    section_title = state.get_current_section_title()
    if not section_title:
        return "No section to approve.", state

    section = state.sections[section_title]
    section.status = "approved"

    # Add to changelog
    state.changelog.append(ChangelogEntry(
        section_title=section_title,
        action="approved",
    ))

    # Save progress
    save_progress(state)

    # Advance to next section
    if state.advance_section():
        response = f"✅ **{section_title}** approved!\n\n"
        section_response, state = process_current_section(state)
        response += section_response
    else:
        # All sections complete
        state.status = "completed"
        response = finalize_report(state)

    return response, state


def revise_with_feedback(feedback: str, state: ReportState) -> tuple[str, ReportState]:
    """
    Revise the current section based on user feedback.

    Returns:
        Tuple of (response message, updated state)
    """
    section_title = state.get_current_section_title()
    if not section_title:
        return "No section to revise.", state

    section = state.sections[section_title]
    section.feedback_history.append(feedback)

    # Re-draft with feedback incorporated
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

    # Generate new questions
    questions = generate_feedback_questions(
        section_title=section_title,
        section_content=section.draft,
    )
    state.pending_questions = questions

    # Build response
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


def save_progress(state: ReportState):
    """Save current progress to the output file."""
    ensure_output_dir()
    content = state.get_approved_sections_markdown()
    OUTPUT_FILE.write_text(content)


def finalize_report(state: ReportState) -> str:
    """
    Finalize the report and save to file.

    Returns:
        Completion message
    """
    ensure_output_dir()
    content = state.get_approved_sections_markdown()
    OUTPUT_FILE.write_text(content)

    return f"""
# ✅ Report Complete!

All {len(state.template_sections)} sections have been approved.

**Output saved to:** `{OUTPUT_FILE}`

## Summary:
- Customer: {state.customer_name}
- Sections: {len(state.template_sections)}
- Total revisions: {sum(s.revision_count for s in state.sections.values())}

## Changelog:
""" + "\n".join([
        f"- {e.timestamp.strftime('%H:%M:%S')} | {e.section_title} | {e.action}"
        for e in state.changelog
    ])


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
    ],
    model=Claude(id="claude-sonnet-4-20250514"),
    db=team_db,
    description="""
A team that generates Discover Solution reports by:
1. Reading templates and intake documents from Notion
2. Processing each section interactively
3. Incorporating user feedback
4. Compiling the final report
""",
    instructions="""
You are the Discovery Solution Team coordinator.

When a user provides Notion URLs, start the report generation process.
Process sections one at a time, getting user approval before moving on.

Key commands:
- START: Initialize with template and intake URLs
- APPROVE: Accept current section
- Any other input: Treat as feedback for revision
""",
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    markdown=True,
    enable_agentic_memory=True,
)


# ============================================================================
# Main Entry Point
# ============================================================================
if __name__ == "__main__":
    print("Discovery Solution Orchestrator Team")
    print("=" * 50)

    # Test with fallback content
    state = ReportState()

    response, state = process_start_command(
        template_url="https://www.notion.so/sweetspot-experts/4-Discover-Solution-2efd31a3b6e48165ad61db743dcc6e85",
        intake_url="https://www.notion.so/sweetspot-experts/Technical-solution-intake-18-12-2cdd31a3b6e480048f55d981080",
        customer_name="Countroll",
        state=state,
    )

    print(response)
