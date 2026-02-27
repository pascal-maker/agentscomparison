"""
Revisor Agent (Production Grade)
================================

Post-drafting agent that enforces evidence grounding rules.

Responsibilities:
1. Remove any claim without EvidenceItem reference
2. Ensure each section has either evidence or Open Questions
3. Check terminology consistency
4. Validate slide budget constraints
"""

import logging
from typing import List, Dict, Any, Tuple

from agno.agent import Agent
from agno.models.anthropic import Claude

from shared.evidence import (
    EvidenceCollection,
    GroundedSection,
    GroundedBullet,
    CustomerConfig,
    validate_grounded_report
)

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Revisor")

# ============================================================================
# Setup
# ============================================================================
# ============================================================================
# Agent Instructions (for LLM-assisted revision)
# ============================================================================
instructions = """\
You are a quality reviewer for consulting deliverables with STRICT evidence grounding rules.

## CRITICAL RULES

1. EVERY bullet point must have [EVID-xxx] reference
2. Remove ANY claim without evidence reference
3. If information is missing, add to Open Questions - do NOT make it up
4. Never hallucinate or add information not in evidence

## Quality Rules to Enforce

### 1. Evidence Grounding
- Every factual statement must reference an evidence ID
- Format: "Statement text [EVID-abc123]"
- Remove claims without evidence

### 2. Terminology Consistency
- Use exact customer name provided
- Apply terminology mappings consistently

### 3. Open Questions
- If section lacks evidence, add Open Questions subsection
- Questions should identify specific missing information

### 4. Writing Style
- Crisp, professional consulting tone
- Active voice preferred
- Specific facts over generalities
"""

# ============================================================================
# Create Agent
# ============================================================================
revisor_agent = Agent(
    id="revisor",
    name="Revisor",
    model=Claude(id="claude-sonnet-4-20250514"),
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


class RevisionResult:
    """Result of revision pass."""

    def __init__(self):
        self.valid: bool = True
        self.sections_revised: int = 0
        self.bullets_removed: int = 0
        self.questions_added: int = 0
        self.terminology_fixes: int = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def summary(self) -> str:
        lines = [
            f"Revision Result: {'VALID' if self.valid else 'INVALID'}",
            f"  Sections revised: {self.sections_revised}",
            f"  Bullets removed: {self.bullets_removed}",
            f"  Questions added: {self.questions_added}",
            f"  Terminology fixes: {self.terminology_fixes}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for e in self.errors[:5]:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
            for w in self.warnings[:5]:
                lines.append(f"    - {w}")
        return "\n".join(lines)


def revise_sections(
    sections: List[GroundedSection],
    evidence: EvidenceCollection,
    config: CustomerConfig = None,
) -> Tuple[List[GroundedSection], RevisionResult]:
    """
    Revise sections to enforce grounding rules.

    Args:
        sections: List of sections to revise
        evidence: Evidence collection for validation
        config: Customer configuration

    Returns:
        Tuple of (revised_sections, revision_result)
    """
    result = RevisionResult()
    revised_sections = []

    for section in sections:
        revised_section, section_result = _revise_section(section, evidence, config)
        revised_sections.append(revised_section)

        result.sections_revised += 1
        result.bullets_removed += section_result.get("bullets_removed", 0)
        result.questions_added += section_result.get("questions_added", 0)
        result.terminology_fixes += section_result.get("terminology_fixes", 0)

        for error in section_result.get("errors", []):
            result.add_error(f"[{section.name}] {error}")
        for warning in section_result.get("warnings", []):
            result.add_warning(f"[{section.name}] {warning}")

    # Validate final result
    validation = validate_grounded_report(revised_sections)
    if not validation["valid"]:
        for error in validation["errors"]:
            result.add_error(error)

    # Check slide budget
    if config:
        budget_result = _check_slide_budget(revised_sections, config)
        if not budget_result["valid"]:
            for error in budget_result["errors"]:
                result.add_warning(error)  # Warning, not error - we'll enforce later

    logger.info(result.summary())
    return revised_sections, result


def _revise_section(
    section: GroundedSection,
    evidence: EvidenceCollection,
    config: CustomerConfig = None,
) -> Tuple[GroundedSection, Dict[str, Any]]:
    """Revise a single section."""
    result = {
        "bullets_removed": 0,
        "questions_added": 0,
        "terminology_fixes": 0,
        "errors": [],
        "warnings": []
    }

    # Filter bullets - keep only those with valid evidence
    valid_bullets = []
    removed_bullets = []

    for bullet in section.bullets:
        # Validate all evidence IDs exist
        valid_ids = [eid for eid in bullet.evidence_ids if evidence.get(eid)]

        if valid_ids:
            # Keep bullet with valid IDs only
            bullet.evidence_ids = valid_ids
            valid_bullets.append(bullet)
        else:
            # No valid evidence - remove bullet
            removed_bullets.append(bullet)
            result["bullets_removed"] += 1
            result["warnings"].append(f"Removed ungrounded bullet: {bullet.text[:50]}...")

    # Update section bullets
    section.bullets = valid_bullets

    # Add removed bullets as open questions
    for bullet in removed_bullets:
        question = f"Needs evidence: {bullet.text}"
        if question not in section.open_questions:
            section.add_open_question(question)
            result["questions_added"] += 1

    # If section has no bullets and no questions, add a question
    if not section.bullets and not section.open_questions:
        section.add_open_question(f"No evidence found for {section.name}")
        result["questions_added"] += 1
        section.has_sufficient_evidence = False

    # Apply terminology fixes if config provided
    if config and config.terminology_map:
        original_name = section.name
        section.name = config.apply_terminology(section.name)
        if section.name != original_name:
            result["terminology_fixes"] += 1

        for bullet in section.bullets:
            original_text = bullet.text
            bullet.text = config.apply_terminology(bullet.text)
            if bullet.text != original_text:
                result["terminology_fixes"] += 1

    return section, result


def _check_slide_budget(
    sections: List[GroundedSection],
    config: CustomerConfig
) -> Dict[str, Any]:
    """Check if sections fit within slide budget."""
    result = {"valid": True, "errors": [], "estimated_slides": 0}

    # Estimate slides:
    # - 1 title slide
    # - 1 agenda slide
    # - Per section: 1 divider + ceil(bullets/6) content slides
    estimated = 2  # Title + Agenda

    per_section_max = config.get_per_section_max()

    for section in sections:
        # Section divider
        estimated += 1

        # Content slides (max 6 bullets per slide)
        bullet_count = len(section.bullets)
        if section.open_questions:
            bullet_count += len(section.open_questions)

        content_slides = max(1, (bullet_count + 5) // 6)

        # Enforce per-section max
        if content_slides > per_section_max:
            content_slides = per_section_max
            result["errors"].append(
                f"Section '{section.name}' exceeds {per_section_max} slides, will be truncated"
            )

        estimated += content_slides

    result["estimated_slides"] = estimated

    # Check total budget
    if estimated < config.get_min_slides():
        result["valid"] = False
        result["errors"].append(
            f"Report has only {estimated} slides, minimum is {config.get_min_slides()}"
        )

    if estimated > config.get_max_slides():
        result["valid"] = False
        result["errors"].append(
            f"Report has {estimated} slides, maximum is {config.get_max_slides()}"
        )

    return result


def enforce_slide_budget(
    sections: List[GroundedSection],
    config: CustomerConfig
) -> List[GroundedSection]:
    """
    Enforce slide budget by trimming sections if needed.

    Rules:
    1. Never remove required sections (must_include)
    2. Trim bullets from longest sections first
    3. Keep at least 1 bullet or 1 open question per section
    """
    budget = _check_slide_budget(sections, config)

    if budget["valid"]:
        return sections  # Already within budget

    max_slides = config.get_max_slides()
    per_section_max = config.get_per_section_max()
    estimated = budget["estimated_slides"]

    # Need to trim
    slides_to_remove = estimated - max_slides

    logger.info(f"Enforcing slide budget: need to remove ~{slides_to_remove} slides")

    # Sort sections by bullet count (descending) - trim longest first
    # But protect must_include sections
    must_include_lower = [m.lower() for m in config.must_include]

    for section in sorted(sections, key=lambda s: len(s.bullets), reverse=True):
        if slides_to_remove <= 0:
            break

        # Calculate max bullets for this section
        max_bullets = per_section_max * 6  # 6 bullets per slide

        if len(section.bullets) > max_bullets:
            removed = len(section.bullets) - max_bullets
            section.bullets = section.bullets[:max_bullets]
            slides_to_remove -= (removed // 6)
            logger.info(f"Trimmed {removed} bullets from '{section.name}'")

    return sections


# ============================================================================
# Legacy functions (backward compatibility)
# ============================================================================
def revise_section(
    drafted_section: str,
    customer_name: str = "Client",
    evidence_list: list = None,
    mandatory_elements: list = None,
) -> dict:
    """Legacy function for backward compatibility."""
    prompt = f"""
Review and improve this section following strict evidence grounding rules.

**Customer Name**: {customer_name}

**Drafted Section**:
```markdown
{drafted_section}
```

Ensure every bullet has an evidence reference [EVID-xxx].
Remove any claims without evidence.
Add Open Questions for missing information.
"""

    response = revisor_agent.run(prompt)
    content = response.content if hasattr(response, 'content') else str(response)

    return {
        "revised_section": content,
        "changes_made": [],
        "open_questions": [],
    }


def generate_feedback_questions(
    section_title: str,
    section_content: str,
    open_questions: list = None,
) -> list:
    """Generate feedback questions for a section."""
    prompt = f"""
Generate 3-6 targeted feedback questions for this section.

**Section**: {section_title}

**Content**:
```markdown
{section_content}
```

**Identified Gaps**: {open_questions or 'None'}

Return ONLY the numbered questions.
"""

    response = revisor_agent.run(prompt)
    content = response.content if hasattr(response, 'content') else str(response)

    questions = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            clean = line.lstrip("0123456789.-) ").strip()
            if clean:
                questions.append(clean)

    if len(questions) < 3:
        questions.extend([
            "Is the technical accuracy acceptable?",
            "Does the tone match your expectations?",
            "Are there any missing details?",
        ])
    return questions[:6]


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    from shared.evidence import extract_evidence_from_content

    test_content = """
    # Test Content

    ## Section A
    - Point 1 about features
    - Point 2 about users

    ## Section B
    - Point 3 about pricing
    """

    print("Testing Revisor...")
    print("=" * 60)

    # Create evidence
    evidence = extract_evidence_from_content(test_content, page_title="Test")
    print(f"Evidence items: {len(evidence)}")

    # Create sections with some ungrounded bullets
    sections = [
        GroundedSection(name="Valid Section"),
        GroundedSection(name="Empty Section"),
    ]

    # Add grounded bullet
    evidence_items = list(evidence.items.values())
    if evidence_items:
        sections[0].add_bullet("Grounded point", [evidence_items[0].id])

    # Add ungrounded bullet
    sections[0].bullets.append(GroundedBullet(text="Ungrounded point", evidence_ids=["FAKE-ID"]))

    # Create config
    config = CustomerConfig(
        name="Test",
        slide_budget={"min": 5, "max": 20, "per_section_max": 4}
    )

    # Revise
    revised, result = revise_sections(sections, evidence, config)

    print(result.summary())
    print(f"\nRevised sections: {len(revised)}")
    for s in revised:
        print(f"  - {s.name}: {len(s.bullets)} bullets, {len(s.open_questions)} questions")
