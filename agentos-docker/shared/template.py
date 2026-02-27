"""
Report Template Models
======================

Defines the output structure for a discovery report.
Each TemplateSlot is a named section with a description and evidence hints.

The template drives slot-filling: instead of asking Claude to discover
sections from content, the controller fills pre-defined slots one by one,
each with targeted evidence.

Creating a template
-------------------
Option 1 — from CustomerConfig (uses must_include as slot names):
    template = ReportTemplate.from_customer_config(config)

Option 2 — from config_loader (preserves slot descriptions + keywords
           parsed from the Notion config page):
    template = config_loader result already populates slot_definitions
    then: template = ReportTemplate.from_customer_config(config)
    (slot descriptions live on TemplateSlot objects inside config.slot_definitions)

Notion config page extended format
-----------------------------------
    ## Template Slots

    ### Executive Summary
    High-level overview of the customer situation, why this engagement,
    and the key numbers at a glance.
    Keywords: company, revenue, employees, engagement, overview

    ### Key Findings
    The 3-5 most important discoveries from all sources.
    Keywords: finding, insight, key, critical, discovery
"""

import re
from typing import List, Optional
from pydantic import BaseModel, Field


class TemplateSlot(BaseModel):
    """One named section of the output report."""
    name: str
    description: str = ""
    evidence_keywords: List[str] = Field(default_factory=list)
    slide_count_target: int = 2
    required: bool = True

    @classmethod
    def from_section_name(cls, name: str) -> "TemplateSlot":
        """
        Auto-build a minimal slot from just a section name.
        Derives keywords from the words in the name.
        """
        keywords = [w.lower() for w in re.split(r'\W+', name) if len(w) > 3]
        return cls(name=name, evidence_keywords=keywords)


class ReportTemplate(BaseModel):
    """Ordered list of slots that define the output structure."""
    customer_name: str = ""
    slots: List[TemplateSlot] = Field(default_factory=list)

    @classmethod
    def from_customer_config(cls, config) -> "ReportTemplate":
        """
        Build a ReportTemplate from a CustomerConfig.

        Uses config.slot_definitions (set by config_loader when a Notion
        config page provides descriptions + keywords) when available,
        otherwise auto-derives keywords from must_include names.
        """
        slot_defs: dict = getattr(config, "slot_definitions", {})
        slots = []
        for section_name in config.must_include:
            if section_name in slot_defs:
                d = slot_defs[section_name]
                slots.append(TemplateSlot(
                    name=section_name,
                    description=d.get("description", ""),
                    evidence_keywords=d.get("evidence_keywords", []),
                    slide_count_target=d.get("slide_count_target", 2),
                ))
            else:
                slots.append(TemplateSlot.from_section_name(section_name))
        return cls(customer_name=config.name, slots=slots)
