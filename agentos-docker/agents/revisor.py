"""
Revisor Agent
=============

Reviews and improves drafted sections to ensure quality standards.
"""

from agno.agent import Agent
from agno.models.anthropic import Claude

from db import get_postgres_db

# ============================================================================
# Setup
# ============================================================================
agent_db = get_postgres_db(contents_table="revisor_contents")

# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a quality reviewer for consulting deliverables.

## Your Task

Review a drafted section and improve it according to strict quality rules.

## Quality Rules to Enforce

### 1. Remove Vague Language
Replace hand-wavy phrases with concrete facts from evidence:
- BAD: "robust and scalable solution"
- GOOD: "horizontally scalable architecture using Azure VMs with load balancing"

### 2. Consistent Terminology
- Use the exact customer name provided (e.g., "Countroll" not "CountRoll" or "the client")
- Use consistent technical terms throughout

### 3. Mandatory Fields
- Check all required fields exist
- If missing, add "**Open Questions:**" bullets listing what's needed

### 4. Evidence Footer
- Every section must have an "Evidence Sources" footer
- Format: [Source Title] → heading/anchor + brief quote
- Remove claims without evidence support

### 5. Writing Style
- Crisp, professional consulting tone
- Active voice preferred
- Specific numbers and facts over generalities
- No marketing language or superlatives

## Input You Receive

- **Drafted Section**: The section to review
- **Customer Name**: For terminology consistency
- **Evidence List**: Available facts to cross-check
- **Mandatory Elements**: Required fields to verify

## Output Format

Return the improved section with:
1. All quality issues fixed
2. Original structure preserved
3. Updated Evidence Sources footer
4. If significant changes were made, add a brief "Revision Notes" comment at the end

## What NOT to Do

- Don't add new information not in evidence
- Don't change the section structure
- Don't remove valid content
- Don't make the text longer than necessary
"""

# ============================================================================
# Create Agent
# ============================================================================
revisor_agent = Agent(
    id="revisor",
    name="Revisor",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=agent_db,
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


def revise_section(
    drafted_section: str,
    customer_name: str = "Countroll",
    evidence_list: list[dict] = None,
    mandatory_elements: list[str] = None,
) -> dict:
    """
    Revise a drafted section to meet quality standards.

    Args:
        drafted_section: The section markdown to review
        customer_name: Client name for consistency checking
        evidence_list: Available evidence to cross-check
        mandatory_elements: Required fields to verify

    Returns:
        dict with 'revised_section', 'changes_made', 'open_questions'
    """
    evidence_text = ""
    if evidence_list:
        evidence_text = "Available evidence:\n" + "\n".join([
            f"- [{e.get('source', 'Unknown')}]: {e.get('content', '')}"
            for e in evidence_list
        ])

    mandatory_text = ""
    if mandatory_elements:
        mandatory_text = "Mandatory elements to verify:\n" + "\n".join([
            f"- {elem}" for elem in mandatory_elements
        ])

    prompt = f"""
Review and improve this section following the quality rules.

**Customer Name**: {customer_name}

**Drafted Section**:
```markdown
{drafted_section}
```

{evidence_text}

{mandatory_text}

Provide:
1. The improved section (complete markdown)
2. A brief list of changes made
3. Any open questions identified
"""

    response = revisor_agent.run(prompt)
    content = response.content if hasattr(response, 'content') else str(response)

    # Parse the response to extract structured data
    # For simplicity, return the whole response and let the orchestrator handle it
    return {
        "revised_section": content,
        "changes_made": [],
        "open_questions": [],
    }


def generate_feedback_questions(
    section_title: str,
    section_content: str,
    open_questions: list[str] = None,
) -> list[str]:
    """
    Generate 3-6 targeted feedback questions for the user.

    Args:
        section_title: The section being reviewed
        section_content: The drafted content
        open_questions: Any identified gaps

    Returns:
        List of 3-6 questions
    """
    prompt = f"""
Generate 3-6 targeted feedback questions for this section.

**Section**: {section_title}

**Content**:
```markdown
{section_content}
```

**Identified Gaps**: {open_questions or 'None'}

Requirements for questions:
1. Be specific to the content
2. Focus on accuracy and completeness
3. Ask about missing technical details if any
4. Include at least one question about tone/style
5. Keep questions concise

Return ONLY the numbered questions, nothing else.
"""

    response = revisor_agent.run(prompt)
    content = response.content if hasattr(response, 'content') else str(response)

    # Parse questions from response
    questions = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            # Remove numbering/bullets
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                questions.append(clean)

    # Ensure 3-6 questions
    if len(questions) < 3:
        questions.extend([
            "Is the technical accuracy acceptable?",
            "Does the tone match your expectations?",
            "Are there any missing details you'd like to add?",
        ])
    return questions[:6]


if __name__ == "__main__":
    # Test the agent
    test_section = """
### Technical Architecture Overview

Countroll uses a robust cloud-based solution for managing rollers.

The system has:
- A web portal
- A mobile app
- Backend services

**Evidence Sources:**
- [Intake Notes] → "Cloud-based platform"
"""

    result = revise_section(
        drafted_section=test_section,
        customer_name="Countroll",
        evidence_list=[
            {"source": "Intake Notes", "content": "Cloud-based roll asset management platform"},
            {"source": "Technical Stack", "content": "Web portal: Vue.js, Backend: Kotlin + Spring Boot"},
        ],
    )
    print(result["revised_section"])
