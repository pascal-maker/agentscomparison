"""
Evidence Models
===============

Formal structures for evidence-grounded report generation.
Every factual claim must reference one or more EvidenceItem IDs.
"""

import hashlib
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """
    A single piece of evidence extracted from source content.

    Every factual statement in the report must reference at least one EvidenceItem.
    """
    id: str = ""  # Auto-generated hash: EVID-{short_hash}
    page_title: str = ""
    page_id: str = ""
    page_url: str = ""
    block_path: List[str] = Field(default_factory=list)  # Heading hierarchy
    quote: str = ""  # Verbatim text from source
    text: str = ""  # Cleaned/normalized text
    block_type: str = "paragraph"  # paragraph, bullet, heading, table_cell, code, etc.
    extracted_at: datetime = Field(default_factory=datetime.now)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id and self.quote:
            # Generate deterministic ID from content
            content_hash = hashlib.md5(
                f"{self.page_id}:{self.quote[:100]}".encode()
            ).hexdigest()[:8]
            self.id = f"EVID-{content_hash}"

    def format_reference(self) -> str:
        """Format as inline reference for markdown."""
        return f"[{self.id}]"

    def format_citation(self) -> str:
        """Format as full citation for evidence footer."""
        source = self.page_title or self.page_id or "Source"
        path = " > ".join(self.block_path) if self.block_path else ""
        return f"[{self.id}] {source}" + (f" > {path}" if path else "") + f": \"{self.quote[:100]}{'...' if len(self.quote) > 100 else ''}\""


class EvidenceCollection(BaseModel):
    """Collection of evidence items with lookup methods."""
    items: Dict[str, EvidenceItem] = Field(default_factory=dict)
    source_url: str = ""
    source_title: str = ""
    extracted_at: datetime = Field(default_factory=datetime.now)

    def add(self, item: EvidenceItem) -> str:
        """Add evidence item and return its ID."""
        if not item.id:
            # Generate ID if not set
            content_hash = hashlib.md5(
                f"{item.page_id}:{item.quote[:100]}".encode()
            ).hexdigest()[:8]
            item.id = f"EVID-{content_hash}"
        self.items[item.id] = item
        return item.id

    def get(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Get evidence item by ID."""
        return self.items.get(evidence_id)

    def get_by_ids(self, ids: List[str]) -> List[EvidenceItem]:
        """Get multiple evidence items by IDs."""
        return [self.items[id] for id in ids if id in self.items]

    def search(self, keywords: List[str]) -> List[EvidenceItem]:
        """Search evidence items by keywords."""
        results = []
        for item in self.items.values():
            text_lower = (item.text + item.quote).lower()
            if any(kw.lower() in text_lower for kw in keywords):
                results.append(item)
        return results

    def format_citations(self, ids: List[str] = None) -> str:
        """Format evidence citations for report footer."""
        items_to_cite = self.get_by_ids(ids) if ids else list(self.items.values())
        return "\n".join(item.format_citation() for item in items_to_cite)

    def merge(self, other: "EvidenceCollection") -> None:
        """Merge another EvidenceCollection into this one."""
        self.items.update(other.items)

    def __len__(self) -> int:
        return len(self.items)


class GroundedBullet(BaseModel):
    """A bullet point with mandatory evidence grounding."""
    text: str
    evidence_ids: List[str] = Field(default_factory=list)

    def is_grounded(self) -> bool:
        """Check if bullet has at least one evidence reference."""
        return len(self.evidence_ids) > 0

    def format_markdown(self) -> str:
        """Format bullet with evidence references."""
        refs = " ".join(f"[{eid}]" for eid in self.evidence_ids)
        return f"- {self.text} {refs}"


class GroundedSection(BaseModel):
    """A report section with evidence-grounded content."""
    name: str
    description: str = ""
    bullets: List[GroundedBullet] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)  # All evidence used
    open_questions: List[str] = Field(default_factory=list)
    has_sufficient_evidence: bool = True

    def add_bullet(self, text: str, evidence_ids: List[str]) -> None:
        """Add a grounded bullet point."""
        self.bullets.append(GroundedBullet(text=text, evidence_ids=evidence_ids))
        self.evidence_ids.extend(evidence_ids)

    def add_open_question(self, question: str) -> None:
        """Add an open question for missing information."""
        self.open_questions.append(question)
        self.has_sufficient_evidence = False

    def validate_grounding(self) -> List[str]:
        """Validate all bullets are grounded. Returns list of ungrounded bullets."""
        ungrounded = []
        for bullet in self.bullets:
            if not bullet.is_grounded():
                ungrounded.append(bullet.text)
        return ungrounded

    def format_markdown(self, evidence_collection: EvidenceCollection = None) -> str:
        """Format section as markdown with evidence references."""
        lines = [f"### {self.name}", ""]

        if self.description:
            lines.append(self.description)
            lines.append("")

        # Bullets with evidence references
        for bullet in self.bullets:
            lines.append(bullet.format_markdown())

        if self.bullets:
            lines.append("")

        # Open questions if any
        if self.open_questions:
            lines.append("**Open Questions:**")
            for q in self.open_questions:
                lines.append(f"- {q}")
            lines.append("")

        # Evidence footer
        if self.evidence_ids and evidence_collection:
            lines.append("**Evidence Sources:**")
            for eid in set(self.evidence_ids):
                item = evidence_collection.get(eid)
                if item:
                    lines.append(f"- {item.format_citation()}")
            lines.append("")

        return "\n".join(lines)


class CustomerConfig(BaseModel):
    """
    Customer-specific configuration for report generation.

    Controls what must be included, terminology, and output constraints.
    slot_definitions is populated by config_loader when a Notion config
    page provides per-slot descriptions and evidence keywords.
    """
    name: str

    # Required concepts that must appear in report
    must_include: List[str] = Field(default_factory=lambda: [
        "Executive Summary",
        "Key Findings",
        "Recommendations"
    ])

    # Optional slot metadata keyed by section name.
    # Values are dicts with keys: description, evidence_keywords, slide_count_target.
    # Populated by config_loader; ignored when building config manually.
    slot_definitions: Dict[str, Any] = Field(default_factory=dict)

    # Terminology mapping (input term -> output term)
    terminology_map: Dict[str, str] = Field(default_factory=dict)

    # Slide budget constraints
    slide_budget: Dict[str, int] = Field(default_factory=lambda: {
        "min": 8,
        "max": 40,
        "per_section_max": 6
    })

    # Emphasis weights for prioritizing content (higher = more important)
    emphasis_weights: Dict[str, float] = Field(default_factory=lambda: {
        "goals": 1.0,
        "problems": 1.0,
        "risks": 0.8,
        "timeline": 0.7,
        "budget": 0.7
    })

    # Input pages
    input_pages: List[str] = Field(default_factory=list)

    def apply_terminology(self, text: str) -> str:
        """Apply terminology mapping to text."""
        result = text
        for old_term, new_term in self.terminology_map.items():
            result = re.sub(
                rf'\b{re.escape(old_term)}\b',
                new_term,
                result,
                flags=re.IGNORECASE
            )
        return result

    def validate_sections(self, sections: List[str]) -> List[str]:
        """Check which must_include concepts are missing."""
        missing = []
        sections_lower = [s.lower() for s in sections]

        for concept in self.must_include:
            concept_lower = concept.lower()
            # Check if concept exists in any section name
            found = any(concept_lower in s for s in sections_lower)
            if not found:
                missing.append(concept)

        return missing

    def get_max_slides(self) -> int:
        """Get maximum total slides allowed."""
        return self.slide_budget.get("max", 40)

    def get_min_slides(self) -> int:
        """Get minimum total slides required."""
        return self.slide_budget.get("min", 8)

    def get_per_section_max(self) -> int:
        """Get maximum slides per section."""
        return self.slide_budget.get("per_section_max", 6)


def extract_evidence_from_content(
    content: str,
    page_title: str = "",
    page_id: str = "",
    page_url: str = ""
) -> EvidenceCollection:
    """
    Extract evidence items from raw content.

    Parses markdown-like content and creates EvidenceItem for each meaningful block.

    Args:
        content: Raw text content (markdown format)
        page_title: Source page title
        page_id: Source page ID
        page_url: Source page URL

    Returns:
        EvidenceCollection with all extracted evidence
    """
    collection = EvidenceCollection(
        source_url=page_url,
        source_title=page_title
    )

    lines = content.split('\n')
    current_path = []  # Heading hierarchy

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Track heading hierarchy
        if line.startswith('# '):
            current_path = [line[2:].strip()]
            block_type = "heading"
            text = line[2:].strip()
        elif line.startswith('## '):
            current_path = current_path[:1] + [line[3:].strip()]
            block_type = "heading"
            text = line[3:].strip()
        elif line.startswith('### '):
            current_path = current_path[:2] + [line[4:].strip()]
            block_type = "heading"
            text = line[4:].strip()
        elif line.startswith('- ') or line.startswith('* '):
            block_type = "bullet"
            text = line[2:].strip()
        elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
            block_type = "numbered"
            text = line[3:].strip()
        elif line.startswith('```'):
            block_type = "code"
            text = line
        elif line.startswith('>'):
            block_type = "quote"
            text = line[1:].strip()
        else:
            block_type = "paragraph"
            text = line

        # Skip very short content
        if len(text) < 5:
            continue

        # Create evidence item
        item = EvidenceItem(
            page_title=page_title,
            page_id=page_id,
            page_url=page_url,
            block_path=current_path.copy(),
            quote=text,
            text=text,
            block_type=block_type
        )

        collection.add(item)

    return collection


# Validation functions

def validate_grounded_report(sections: List[GroundedSection]) -> Dict[str, Any]:
    """
    Validate that all sections are properly grounded.

    Returns validation results including any failures.
    """
    results = {
        "valid": True,
        "total_sections": len(sections),
        "total_bullets": 0,
        "grounded_bullets": 0,
        "ungrounded_bullets": [],
        "sections_with_questions": 0,
        "errors": []
    }

    for section in sections:
        ungrounded = section.validate_grounding()
        results["total_bullets"] += len(section.bullets)
        results["grounded_bullets"] += len(section.bullets) - len(ungrounded)

        if ungrounded:
            results["valid"] = False
            results["ungrounded_bullets"].extend([
                {"section": section.name, "bullet": b} for b in ungrounded
            ])
            results["errors"].append(
                f"Section '{section.name}' has {len(ungrounded)} ungrounded bullets"
            )

        if section.open_questions:
            results["sections_with_questions"] += 1

    return results
