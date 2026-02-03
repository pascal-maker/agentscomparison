"""
Section Drafter Agent
=====================

Drafts report sections following a template structure,
using evidence from intake documents.
"""

from agno.agent import Agent
from agno.models.anthropic import Claude

from db import get_postgres_db

# ============================================================================
# Setup
# ============================================================================
agent_db = get_postgres_db(contents_table="section_drafter_contents")

# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a technical document section drafter for consulting deliverables.

## Your Task

Draft a single section of a "Discover Solution" report following:
1. The exact structure from the template
2. Evidence and facts from the intake documents
3. Professional consulting-style writing

## Input You Receive

- **Section Title**: The H3 heading you're writing
- **Template Structure**: How this section should be organized (subheadings, bullets, etc.)
- **Evidence Snippets**: Relevant facts extracted from intake documents
- **Customer Name**: The client name to use consistently (e.g., "Countroll")
- **Mandatory Elements**: Any required fields for this customer

## Output Requirements

1. **Follow Template Structure Exactly**
   - Match all subheadings from template
   - Include all required bullet points or tables
   - Keep same ordering

2. **Use Evidence, Not Assumptions**
   - Every statement must be backed by evidence
   - If information is missing, add an "Open Questions" bullet
   - Never make up technical details

3. **Professional Tone**
   - Crisp, consulting-style writing
   - Active voice
   - Specific and concrete (no vague language)

4. **Include Evidence Footer**
   - List sources at the end of the section
   - Format: [Source Title] → relevant heading/anchor + brief quote

## Output Format

```markdown
### [Section Title]

[Section content following template structure]

**Evidence Sources:**
- [Intake Notes] → Key extracted facts: "Cloud-based roll asset management platform"
- [Technical Stack] → "Backend: Kotlin + Spring Boot"
```

## What NOT to Do

- Don't add sections not in the template
- Don't use vague phrases like "state-of-the-art" or "robust solution"
- Don't assume technical details not in evidence
- Don't change the customer name or terminology
"""

# ============================================================================
# Create Agent
# ============================================================================
section_drafter_agent = Agent(
    id="section-drafter",
    name="Section Drafter",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=agent_db,
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


def draft_section(
    section_title: str,
    template_structure: str,
    evidence_snippets: list[dict],
    customer_name: str = "Countroll",
    mandatory_elements: list[str] = None,
) -> str:
    """
    Draft a single report section.

    Args:
        section_title: The H3 heading for this section
        template_structure: Template text showing required structure
        evidence_snippets: List of dicts with 'source' and 'content' keys
        customer_name: Client name to use
        mandatory_elements: Required fields for this customer

    Returns:
        Drafted section as markdown string
    """
    # Build evidence text
    evidence_text = "\n".join([
        f"- [{e.get('source', 'Unknown')}]: {e.get('content', '')}"
        for e in evidence_snippets
    ]) if evidence_snippets else "No specific evidence provided."

    # Build mandatory elements text
    mandatory_text = ""
    if mandatory_elements:
        mandatory_text = f"\n\nMandatory elements to include:\n" + "\n".join(
            f"- {elem}" for elem in mandatory_elements
        )

    prompt = f"""
Draft the following section for a Discover Solution report.

**Customer**: {customer_name}

**Section Title**: {section_title}

**Template Structure to Follow**:
```
{template_structure}
```

**Available Evidence**:
{evidence_text}
{mandatory_text}

Write the complete section now, following the template structure exactly.
Include an Evidence Sources footer.
If any required information is missing, add "Open Questions" bullets.
"""

    response = section_drafter_agent.run(prompt)
    return response.content if hasattr(response, 'content') else str(response)


if __name__ == "__main__":
    # Test the agent
    test_evidence = [
        {"source": "Intake Notes", "content": "Cloud-based roll asset management platform"},
        {"source": "Technical Stack", "content": "Backend: Kotlin + Spring Boot, Clean Architecture"},
        {"source": "Hosting", "content": "Microsoft Azure with Application Gateway and VMs"},
    ]

    result = draft_section(
        section_title="Technical Architecture Overview",
        template_structure="""
### Technical Architecture Overview

- High-level architecture diagram description
- Key components and their responsibilities
- Integration points
- Data flow summary
""",
        evidence_snippets=test_evidence,
        customer_name="Countroll",
    )
    print(result)
