"""
Content Analyzer Agent (Production Grade)
=========================================

Analyzes input content and discovers sections with evidence mapping.
Every discovered section is linked to specific evidence IDs.
"""

import os
import json
import re
import logging
from typing import List, Dict, Any, Tuple

from agno.agent import Agent
from agno.models.anthropic import Claude

from shared.evidence import (
    EvidenceItem,
    EvidenceCollection,
    GroundedSection,
    GroundedBullet,
    CustomerConfig,
    extract_evidence_from_content
)

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContentAnalyzer")

# ============================================================================
# Setup
# ============================================================================
# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a Content Analyzer that discovers structure from input documents with STRICT evidence grounding.

## CRITICAL RULES

1. ONLY output facts that exist in the input - NEVER hallucinate
2. Every bullet point MUST reference specific evidence from the input
3. If information is missing, add it to open_questions - do NOT make it up

## Your Task

Given raw input content and a list of evidence items (with IDs), you must:

1. Identify 3-8 logical sections based on the content
2. For each section, list key points that are DIRECTLY supported by evidence
3. Map each key point to specific evidence IDs
4. Identify gaps where information is missing

## Output Format

Return a JSON object:

```json
{
  "title": "Report title based on content",
  "sections": [
    {
      "name": "Section Name",
      "description": "What this section covers",
      "key_points": [
        {
          "text": "The key point text",
          "evidence_ids": ["EVID-abc123", "EVID-def456"]
        }
      ],
      "open_questions": ["Question about missing info"]
    }
  ],
  "summary": "Executive summary paragraph"
}
```

## Guidelines

- Section names should reflect actual content topics
- Each key_point MUST have at least one evidence_id
- If you cannot find evidence for something, put it in open_questions instead
- Keep 3-8 sections total
- Maximum 6 key points per section
"""

# ============================================================================
# Create Agent
# ============================================================================
content_analyzer_agent = Agent(
    id="content-analyzer",
    name="Content Analyzer",
    model=Claude(id="claude-sonnet-4-20250514"),
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


def analyze_with_evidence(
    evidence_collection: EvidenceCollection,
    customer_config: CustomerConfig = None,
) -> Tuple[List[GroundedSection], str, str]:
    """
    Analyze evidence and discover grounded sections.

    Args:
        evidence_collection: Collection of evidence items with IDs
        customer_config: Optional customer configuration

    Returns:
        Tuple of (grounded_sections, title, summary)
    """
    customer_name = customer_config.name if customer_config else "Client"

    # Format evidence for the prompt
    evidence_text = "\n".join([
        f"[{item.id}] ({item.block_type}) {item.quote}"
        for item in evidence_collection.items.values()
    ])

    prompt = f"""
Analyze this evidence and discover logical sections for a discovery report.

## Customer: {customer_name}

## Evidence Items (use these IDs in your response):
{evidence_text}

## Instructions:
1. Read ALL evidence items carefully
2. Group related evidence into 3-8 logical sections
3. For each section, extract key points that are DIRECTLY supported by evidence
4. Each key point MUST reference at least one evidence ID
5. If information is missing for important topics, add to open_questions
6. Write a brief executive summary

## Required Sections:
These concepts should be covered if evidence exists:
{', '.join(customer_config.must_include) if customer_config else 'Executive Summary, Key Findings, Recommendations'}

Return ONLY valid JSON:
{{
  "title": "Report title",
  "sections": [
    {{
      "name": "Section Name",
      "description": "Brief description",
      "key_points": [
        {{"text": "Key point", "evidence_ids": ["EVID-xxx"]}}
      ],
      "open_questions": ["Question if info missing"]
    }}
  ],
  "summary": "Executive summary"
}}
"""

    try:
        response = content_analyzer_agent.run(prompt)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            logger.error("No JSON found in analyzer response")
            return _create_fallback_sections(evidence_collection), "Analysis Report", ""

        result = json.loads(json_match.group())

        # Convert to GroundedSection objects
        grounded_sections = []
        for section_data in result.get("sections", []):
            section = GroundedSection(
                name=section_data.get("name", "Section"),
                description=section_data.get("description", "")
            )

            # Add key points with evidence
            for kp in section_data.get("key_points", []):
                text = kp.get("text", "")
                evidence_ids = kp.get("evidence_ids", [])

                # Validate evidence IDs exist
                valid_ids = [eid for eid in evidence_ids if evidence_collection.get(eid)]
                if valid_ids:
                    section.add_bullet(text, valid_ids)
                else:
                    # No valid evidence - add as open question instead
                    section.add_open_question(f"Needs evidence: {text}")

            # Add open questions
            for q in section_data.get("open_questions", []):
                section.add_open_question(q)

            grounded_sections.append(section)

        # Apply customer config constraints
        if customer_config:
            grounded_sections = _apply_customer_constraints(
                grounded_sections,
                customer_config,
                evidence_collection
            )

        title = result.get("title", f"Discovery Report: {customer_name}")
        summary = result.get("summary", "")

        logger.info(f"Discovered {len(grounded_sections)} grounded sections")
        return grounded_sections, title, summary

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return _create_fallback_sections(evidence_collection), "Analysis Report", ""
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return _create_fallback_sections(evidence_collection), "Analysis Report", ""


def _apply_customer_constraints(
    sections: List[GroundedSection],
    config: CustomerConfig,
    evidence: EvidenceCollection
) -> List[GroundedSection]:
    """Apply customer config constraints to sections."""

    # Check for missing must_include concepts
    section_names = [s.name.lower() for s in sections]
    missing = config.validate_sections([s.name for s in sections])

    # Add placeholder sections for missing required concepts
    for concept in missing:
        placeholder = GroundedSection(
            name=concept,
            description=f"Section for {concept}",
            has_sufficient_evidence=False
        )
        placeholder.add_open_question(f"No evidence found for {concept}")
        sections.append(placeholder)

    # Apply terminology mapping
    for section in sections:
        section.name = config.apply_terminology(section.name)
        section.description = config.apply_terminology(section.description)
        for bullet in section.bullets:
            bullet.text = config.apply_terminology(bullet.text)

    return sections


def _create_fallback_sections(evidence: EvidenceCollection) -> List[GroundedSection]:
    """Create minimal fallback sections when analysis fails."""
    sections = []

    # Create a single findings section with all evidence
    findings = GroundedSection(
        name="Key Findings",
        description="Extracted findings from source content"
    )

    for item in list(evidence.items.values())[:10]:  # Limit to first 10
        findings.add_bullet(item.text[:100], [item.id])

    if findings.bullets:
        sections.append(findings)

    # Add recommendations placeholder
    recommendations = GroundedSection(
        name="Recommendations",
        description="Recommendations based on findings"
    )
    recommendations.add_open_question("Recommendations to be developed based on findings")
    sections.append(recommendations)

    return sections


# ============================================================================
# Legacy function (backward compatibility)
# ============================================================================
def analyze_content(content: str, context: str = "") -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.

    Use analyze_with_evidence() for production use.
    """
    # Extract evidence from content
    evidence = extract_evidence_from_content(content)

    # Create minimal config
    config = CustomerConfig(name="Client")

    # Run analysis
    sections, title, summary = analyze_with_evidence(evidence, config)

    # Convert to legacy format
    return {
        "title": title,
        "sections": [
            {
                "name": s.name,
                "description": s.description,
                "key_points": [b.text for b in s.bullets],
                "evidence": [eid for eid in s.evidence_ids]
            }
            for s in sections
        ],
        "open_questions": [
            q for s in sections for q in s.open_questions
        ],
        "summary": summary
    }


def analyze_and_generate_sections(content: str, customer_name: str = "Client") -> List[str]:
    """Legacy function - returns section names only."""
    result = analyze_content(content, context=f"Discovery for {customer_name}")
    return [s["name"] for s in result.get("sections", [])]


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    test_content = """
    # Product Interview - TaskFlow

    ## Vision
    TaskFlow aims to be simple task management for teams of 2-10 people.

    ## Users
    - Freelancers managing clients
    - Small agency teams
    - Remote workers

    ## Pain Points
    - "Existing tools are too complex"
    - "Trello boards get messy"

    ## Features
    1. One-click task creation
    2. Team assignment
    3. Due dates

    ## Pricing
    Free tier, $5/user/month for teams.
    """

    print("Testing Content Analyzer with Evidence...")
    print("=" * 60)

    # Extract evidence
    evidence = extract_evidence_from_content(
        test_content,
        page_title="TaskFlow Interview",
        page_id="test-123"
    )
    print(f"Extracted {len(evidence)} evidence items")

    # Analyze
    config = CustomerConfig(name="TaskFlow")
    sections, title, summary = analyze_with_evidence(evidence, config)

    print(f"\nTitle: {title}")
    print(f"\nSections: {len(sections)}")
    for s in sections:
        print(f"  - {s.name}: {len(s.bullets)} bullets, {len(s.open_questions)} questions")
