"""
Discovery Controller
====================

Orchestrates template-driven slot filling.

Flow:
1. Receive a ReportTemplate (ordered list of slots) + merged EvidenceCollection
2. For each slot:
   a. Filter evidence relevant to that slot (by keywords)
   b. Call slot_filler.fill_slot() → GroundedSection
3. Apply CustomerConfig terminology mapping across all sections
4. Generate report title + executive summary from filled sections
5. Return (sections, title, summary)

This replaces the single "dump everything into one prompt" approach with
targeted per-slot calls — each section gets Claude's full attention on
just the relevant evidence.
"""

import json
import logging
import re
from typing import List, Optional, Tuple

import anthropic

from shared.template import ReportTemplate, TemplateSlot
from shared.evidence import EvidenceCollection, GroundedSection, CustomerConfig
from agents.slot_filler import fill_slot

logger = logging.getLogger("Controller")

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ============================================================================
# Public API
# ============================================================================

def fill_template(
    template: ReportTemplate,
    evidence: EvidenceCollection,
    config: CustomerConfig,
) -> Tuple[List[GroundedSection], str, str]:
    """
    Fill all template slots and produce a complete grounded report.

    Args:
        template:  ReportTemplate built from CustomerConfig.
        evidence:  Merged evidence collection from all sources.
        config:    CustomerConfig for terminology + constraints.

    Returns:
        (sections, title, summary)
    """
    logger.info(
        f"Controller: filling {len(template.slots)} slots "
        f"from {len(evidence)} evidence items"
    )

    sections: List[GroundedSection] = []

    for slot in template.slots:
        logger.info(f"  → Slot: {slot.name}")

        # Filter evidence to items relevant to this slot
        relevant = _filter_evidence(slot, evidence)
        logger.info(f"    Evidence: {len(relevant)}/{len(evidence)} items relevant")

        # Fill the slot
        section = fill_slot(slot, relevant, config.name)
        sections.append(section)

    # Apply terminology mapping
    for section in sections:
        section.name = config.apply_terminology(section.name)
        section.description = config.apply_terminology(section.description)
        for bullet in section.bullets:
            bullet.text = config.apply_terminology(bullet.text)

    # Generate title + executive summary
    title, summary = _generate_title_and_summary(sections, config)
    logger.info(f"Controller: complete — {len(sections)} sections, title='{title[:60]}'")

    return sections, title, summary


# ============================================================================
# Evidence filtering
# ============================================================================

_MIN_RELEVANT = 5     # Fall back to all evidence if fewer than this many items match
_MAX_RELEVANT = 120   # Cap to avoid overly long prompts


def _filter_evidence(
    slot: TemplateSlot,
    evidence: EvidenceCollection,
) -> EvidenceCollection:
    """
    Return a filtered EvidenceCollection relevant to this slot.

    Uses keyword search from the slot definition. Falls back to the full
    collection when there aren't enough keyword matches.
    """
    if not slot.evidence_keywords or len(evidence) <= _MIN_RELEVANT:
        return _cap(evidence)

    matches = evidence.search(slot.evidence_keywords)

    if len(matches) < _MIN_RELEVANT:
        # Not enough targeted hits — use everything so the slot can still
        # produce some output rather than failing silently
        return _cap(evidence)

    filtered = EvidenceCollection()
    for item in matches[:_MAX_RELEVANT]:
        filtered.items[item.id] = item
    return filtered


def _cap(evidence: EvidenceCollection) -> EvidenceCollection:
    """Return at most _MAX_RELEVANT items from a collection (first N)."""
    if len(evidence) <= _MAX_RELEVANT:
        return evidence
    capped = EvidenceCollection()
    for item in list(evidence.items.values())[:_MAX_RELEVANT]:
        capped.items[item.id] = item
    return capped


# ============================================================================
# Title + summary generation
# ============================================================================

def _generate_title_and_summary(
    sections: List[GroundedSection],
    config: CustomerConfig,
) -> Tuple[str, str]:
    """Generate a report title and executive summary from filled sections."""
    # Build a compact snapshot of grounded bullets across all sections
    snapshot = "\n\n".join(
        f"## {s.name}\n" + "\n".join(f"- {b.text}" for b in s.bullets[:4])
        for s in sections
        if s.bullets
    )
    if not snapshot.strip():
        return f"Discovery Report: {config.name}", ""

    prompt = f"""Based on these discovery report sections for customer '{config.name}':

{snapshot}

Write:
1. A concise report title (max 12 words, include customer name and topic)
2. An executive summary paragraph (3–5 sentences) covering: who the customer is,
   the core problem/opportunity, and the key finding or recommendation.

Return ONLY valid JSON:
{{"title": "...", "summary": "..."}}"""

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            data = json.loads(match.group())
            return (
                data.get("title", f"Discovery Report: {config.name}"),
                data.get("summary", ""),
            )
    except Exception as exc:
        logger.error(f"Title/summary generation failed: {exc}")

    return f"Discovery Report: {config.name}", ""
