"""
Customer Config Loader
======================
Loads CustomerConfig from a structured Notion page.

Expected Notion page format
---------------------------

    # Hannecard

    ## Required Sections
    - Executive Summary
    - Key Findings
    - Recommendations
    - Company Overview
    - Current Technology Landscape

    ## Terminology
    - Customer → Client
    - CRM → Customer Data Platform

    ## Slide Budget
    - Min slides: 8
    - Max slides: 25
    - Max per section: 4

Rules
-----
- Only headings (##) and bullet points are required — Notion tables are not needed.
- The H1 heading (or the page title) becomes the customer name.
  Strip leading "Customer Config:", "Config:", or "Customer:" prefixes.
- "## Required Sections" (or "## Must Include") → must_include list.
- "## Terminology" → terminology_map; each bullet must contain " → " or " -> ".
- "## Slide Budget" → slide_budget dict; looks for min/max/per-section numbers.
- Any section is optional; defaults are used if absent.
"""

import logging
import re
from typing import Optional

from shared.evidence import CustomerConfig

logger = logging.getLogger("ConfigLoader")


# ============================================================================
# Public API
# ============================================================================

def load_customer_config_from_notion(
    url_or_id: str,
    fallback_name: str = "Client",
) -> tuple[CustomerConfig, list[str]]:
    """
    Load CustomerConfig from a structured Notion page.

    Args:
        url_or_id:     Notion page URL or page ID.
        fallback_name: Customer name to use if the page has no H1.

    Returns:
        (CustomerConfig, warnings)  — warnings is a list of human-readable
        strings about missing/defaulted fields. Empty list means all good.
    """
    # Import here to avoid circular imports
    from agents.notion_reader import read_notion_page

    logger.info(f"Loading customer config from Notion: {url_or_id}")

    result = read_notion_page(url_or_id, bypass_safety=True)
    if not result["success"]:
        msg = f"Could not read config page: {result.get('error', 'unknown error')}"
        logger.warning(msg)
        return CustomerConfig(name=fallback_name), [msg]

    content = result["content"]
    page_title = result.get("title", "")

    config, warnings = _parse_config_content(content, page_title, fallback_name)
    logger.info(
        f"Config loaded — name={config.name!r}, "
        f"sections={config.must_include}, "
        f"terminology={len(config.terminology_map)} term(s), "
        f"budget={config.slide_budget}"
    )
    return config, warnings


def parse_config_from_text(
    text: str,
    fallback_name: str = "Client",
) -> tuple[CustomerConfig, list[str]]:
    """
    Parse CustomerConfig directly from a markdown string.
    Useful for testing without a live Notion connection.
    """
    return _parse_config_content(text, "", fallback_name)


# ============================================================================
# Internal parser
# ============================================================================

_SECTION_NAMES = {
    "required_sections": {
        "required section", "must include", "sections", "required",
    },
    "terminology": {
        "terminolog", "glossar", "term mapping", "rename",
    },
    "slide_budget": {
        "slide budget", "budget", "slides",
    },
    "template_slots": {
        "template slot", "slot", "output structure", "report structure",
    },
}


def _detect_section(heading_text: str) -> Optional[str]:
    """Map a heading string to one of our known config sections."""
    lower = heading_text.lower()
    for key, keywords in _SECTION_NAMES.items():
        if any(kw in lower for kw in keywords):
            return key
    return None


def _strip_name_prefix(text: str) -> str:
    """Remove 'Customer Config:', 'Config:', 'Customer:' prefixes."""
    for prefix in (
        "customer config:",
        "config:",
        "customer:",
        "customer config",
        "config",
    ):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


def _parse_config_content(
    content: str,
    page_title: str,
    fallback_name: str,
) -> tuple[CustomerConfig, list[str]]:
    warnings: list[str] = []
    lines = content.split("\n")

    # -------------------------------------------------------------------------
    # Extract customer name from first H1 (or page title)
    # -------------------------------------------------------------------------
    name = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            name = _strip_name_prefix(heading)
            break

    if not name and page_title:
        name = _strip_name_prefix(page_title)

    if not name:
        name = fallback_name
        warnings.append(
            "No customer name found in config page — "
            f"using fallback name '{fallback_name}'."
        )

    # -------------------------------------------------------------------------
    # Walk lines collecting section bullets
    # -------------------------------------------------------------------------
    must_include: list[str] = []
    terminology_map: dict[str, str] = {}
    slide_budget: dict[str, int] = {"min": 8, "max": 30, "per_section_max": 4}
    # slot_definitions: slot_name → {description, evidence_keywords, slide_count_target}
    slot_definitions: dict[str, dict] = {}

    current_section: Optional[str] = None
    current_slot_name: Optional[str] = None   # active H3 slot inside template_slots
    current_slot_desc_lines: list[str] = []   # paragraph lines for the current slot

    def _flush_slot():
        """Save accumulated slot description buffer."""
        nonlocal current_slot_name, current_slot_desc_lines
        if not current_slot_name:
            return
        desc = " ".join(current_slot_desc_lines).strip()
        # Extract keywords line: "Keywords: a, b, c"
        keywords: list[str] = []
        m = re.search(r'keywords?\s*[:=]\s*(.+)', desc, re.IGNORECASE)
        if m:
            keywords = [k.strip().lower() for k in re.split(r'[,;]', m.group(1)) if k.strip()]
            # Remove the keywords line from description
            desc = re.sub(r'keywords?\s*[:=]\s*.+', '', desc, flags=re.IGNORECASE).strip()
        slot_definitions[current_slot_name] = {
            "description": desc,
            "evidence_keywords": keywords,
            "slide_count_target": slide_budget.get("per_section_max", 2),
        }
        current_slot_name = None
        current_slot_desc_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect heading → switch section context
        heading_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if level == 1:
                current_section = None
                _flush_slot()
            elif level == 2:
                _flush_slot()
                current_section = _detect_section(heading_text)
                current_slot_name = None
            elif level == 3 and current_section == "template_slots":
                # Each H3 under Template Slots is a slot definition
                _flush_slot()
                current_slot_name = heading_text
                current_slot_desc_lines = []
            else:
                _flush_slot()
                current_section = None
            continue

        # Inside a template slot — collect description lines
        if current_section == "template_slots" and current_slot_name:
            # Could be a paragraph or a "Keywords: ..." line
            current_slot_desc_lines.append(stripped)
            continue

        # Parse bullets
        bullet_match = re.match(r'^[-*]\s+(.*)', stripped)
        if not bullet_match:
            # Numbered list item in required sections
            num_match = re.match(r'^\d+[.)]\s+(.*)', stripped)
            if num_match and current_section == "required_sections":
                item = num_match.group(1).strip()
                if item:
                    must_include.append(item)
            continue

        item = bullet_match.group(1).strip()
        if not item:
            continue

        if current_section == "required_sections":
            must_include.append(item)

        elif current_section == "terminology":
            # Accept "→", "->", " : " as separators
            # E.g.: "Customer → Client"
            for sep in (" → ", " -> ", " → ", "→", "->"):
                if sep in item:
                    parts = item.split(sep, 1)
                    old_term = parts[0].strip()
                    new_term = parts[1].strip()
                    if old_term and new_term:
                        terminology_map[old_term] = new_term
                    break

        elif current_section == "slide_budget":
            item_lower = item.lower()

            m = re.search(r'per\s*[_-]?section\s*(?:max|maximum)?\s*[:=]\s*(\d+)', item_lower)
            if m:
                slide_budget["per_section_max"] = int(m.group(1))
                continue

            m = re.search(r'max(?:imum)?\s*(?:slides?)?\s*[:=]\s*(\d+)', item_lower)
            if m:
                slide_budget["max"] = int(m.group(1))
                continue

            m = re.search(r'min(?:imum)?\s*(?:slides?)?\s*[:=]\s*(\d+)', item_lower)
            if m:
                slide_budget["min"] = int(m.group(1))
                continue

    # Flush any trailing slot
    _flush_slot()

    # -------------------------------------------------------------------------
    # Defaults + warnings
    # -------------------------------------------------------------------------
    if not must_include:
        must_include = ["Executive Summary", "Key Findings", "Recommendations"]
        warnings.append(
            "No '## Required Sections' found in config page — "
            "using defaults: Executive Summary, Key Findings, Recommendations."
        )

    # Backfill slot_definitions from must_include for any slots not explicitly defined
    for section_name in must_include:
        if section_name not in slot_definitions:
            keywords = [w.lower() for w in re.split(r'\W+', section_name) if len(w) > 3]
            slot_definitions[section_name] = {
                "description": "",
                "evidence_keywords": keywords,
                "slide_count_target": slide_budget.get("per_section_max", 2),
            }

    config = CustomerConfig(
        name=name,
        must_include=must_include,
        terminology_map=terminology_map,
        slide_budget=slide_budget,
        slot_definitions=slot_definitions,
    )

    if slot_definitions:
        explicit = sum(1 for v in slot_definitions.values() if v.get("description"))
        logger.info(
            f"Slot definitions: {len(slot_definitions)} total, "
            f"{explicit} with explicit descriptions"
        )

    return config, warnings
