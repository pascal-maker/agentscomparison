"""
Slot Filler Agent
=================

Fills a single TemplateSlot with evidence-grounded content.

One focused Claude call per slot, with pre-filtered evidence.
This replaces the single "dump everything" content_analyzer call with
targeted per-section generation — better quality, clearer gaps.
"""

import json
import logging
import re
from typing import Optional

import anthropic

from shared.template import TemplateSlot
from shared.evidence import EvidenceCollection, GroundedSection

logger = logging.getLogger("SlotFiller")

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ============================================================================
# Public API
# ============================================================================

def fill_slot(
    slot: TemplateSlot,
    evidence: EvidenceCollection,
    customer_name: str = "Client",
) -> GroundedSection:
    """
    Fill a single template slot using evidence-grounded Claude call.

    Args:
        slot:          The template slot defining name, description, keywords.
        evidence:      Pre-filtered evidence collection for this slot.
        customer_name: Customer name for context.

    Returns:
        GroundedSection with bullets (each referencing evidence IDs)
        and open_questions for gaps.
    """
    section = GroundedSection(name=slot.name, description=slot.description)

    if len(evidence) == 0:
        section.add_open_question(f"No evidence available for {slot.name}")
        return section

    evidence_lines = "\n".join(
        f"[{item.id}] {item.quote}"
        for item in evidence.items.values()
    )

    bullet_target = min(slot.slide_count_target * 3, 8)
    purpose = slot.description or f"Fill the '{slot.name}' section of the discovery report."

    prompt = f"""You are filling ONE specific section of a discovery report.

## Customer: {customer_name}
## Section: {slot.name}
## Purpose: {purpose}

## Available Evidence ({len(evidence)} items):
{evidence_lines}

## Your task:
- Write up to {bullet_target} key points for this section
- ONLY use facts that appear in the evidence above — never invent anything
- Each key_point MUST reference at least one evidence ID from the list
- If evidence is insufficient for something, add it to open_questions instead
- Keep each key point concise (one sentence, max 20 words)

Return ONLY valid JSON — no prose before or after:
{{
  "key_points": [
    {{"text": "Concise fact.", "evidence_ids": ["EVID-xxxxxxxx"]}}
  ],
  "open_questions": ["Question about missing information"]
}}"""

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = response.content[0].text

        data = _parse_json(response_text)
        if data is None:
            logger.error(f"Slot '{slot.name}': no JSON in response")
            section.add_open_question(f"Could not generate content — check logs")
            return section

        for kp in data.get("key_points", []):
            text = kp.get("text", "").strip()
            if not text:
                continue
            valid_ids = [eid for eid in kp.get("evidence_ids", []) if evidence.get(eid)]
            if valid_ids:
                section.add_bullet(text, valid_ids)
            else:
                # Referenced IDs don't exist in evidence — treat as ungrounded
                section.add_open_question(f"Needs evidence: {text}")

        for q in data.get("open_questions", []):
            if q.strip():
                section.add_open_question(q.strip())

        logger.info(
            f"Slot '{slot.name}': {len(section.bullets)} bullets, "
            f"{len(section.open_questions)} open questions"
        )

    except Exception as exc:
        logger.error(f"Slot '{slot.name}' failed: {exc}")
        section.add_open_question(f"Error generating section: {exc}")

    return section


# ============================================================================
# Helpers
# ============================================================================

def _parse_json(text: str) -> Optional[dict]:
    """Extract and parse the first JSON object from a string."""
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
