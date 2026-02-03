"""
Report State Models
===================

Pydantic models for managing the Discovery Solution report generation state.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SectionState(BaseModel):
    """State for a single report section."""

    title: str
    template_structure: str = ""  # Original template structure for this section
    draft: str = ""  # Current draft content
    evidence: List[Dict[str, str]] = Field(default_factory=list)  # Sources used
    feedback_history: List[str] = Field(default_factory=list)  # User feedback
    status: str = "pending"  # pending, drafting, reviewing, approved
    revision_count: int = 0


class ChangelogEntry(BaseModel):
    """Entry in the report changelog."""

    timestamp: datetime = Field(default_factory=datetime.now)
    section_title: str
    action: str  # created, updated, approved


class ReportState(BaseModel):
    """
    Full state for the Discovery Solution report generation.
    Persisted across session turns.
    """

    # Template info
    template_url: str = ""
    template_content: str = ""
    template_sections: List[str] = Field(default_factory=list)  # H3 headings

    # Intake info
    intake_url: str = ""
    intake_content: str = ""

    # Additional sources
    additional_sources: Dict[str, str] = Field(default_factory=dict)  # url -> content

    # Customer info
    customer_name: str = "Countroll"
    mandatory_elements: List[str] = Field(default_factory=list)

    # Section progress
    current_section_index: int = 0
    sections: Dict[str, SectionState] = Field(default_factory=dict)  # title -> state

    # Questions for user
    pending_questions: List[str] = Field(default_factory=list)

    # Output
    compiled_md_path: str = "./countroll_report/discover_solution_countroll.md"
    changelog: List[ChangelogEntry] = Field(default_factory=list)

    # Status
    status: str = "initialized"  # initialized, reading_template, reading_intake, processing, completed
    error_message: Optional[str] = None

    def get_current_section(self) -> Optional[SectionState]:
        """Get the current section being worked on."""
        if self.current_section_index >= len(self.template_sections):
            return None
        title = self.template_sections[self.current_section_index]
        return self.sections.get(title)

    def get_current_section_title(self) -> Optional[str]:
        """Get the title of the current section."""
        if self.current_section_index >= len(self.template_sections):
            return None
        return self.template_sections[self.current_section_index]

    def advance_section(self) -> bool:
        """Move to the next section. Returns False if no more sections."""
        self.current_section_index += 1
        return self.current_section_index < len(self.template_sections)

    def is_complete(self) -> bool:
        """Check if all sections are approved."""
        return all(
            s.status == "approved"
            for s in self.sections.values()
        )

    def get_approved_sections_markdown(self) -> str:
        """Compile all approved sections into markdown."""
        lines = [f"# Discover Solution: {self.customer_name}\n"]

        for title in self.template_sections:
            section = self.sections.get(title)
            if section and section.status == "approved":
                lines.append(section.draft)
                lines.append("")

        # Add changelog
        lines.append("\n---\n")
        lines.append("## Changelog\n")
        for entry in self.changelog:
            lines.append(f"- {entry.timestamp.isoformat()} | {entry.section_title} | {entry.action}")

        return "\n".join(lines)


# Fallback intake text for testing without MCP
FALLBACK_INTAKE_TEXT = """
# Technical solution intake (18/12)

# Questions
- Algemene architectuur van de CountRoll oplossing
- Overzicht belangrijkste componenten (Web app, Mobile app(s), Backend services, ...)
- Technical stack (front/backend/mobile)
- Technical tooling (IDE, Bitbucket/Github, ...)
- Development process (Agile/Scrum/...), Process tooling (JIRA, ...)
- Team structure
- Documentation (UML diagrams, wiki, ...)
- Deployment model, CI/CD pipeline, (automated) testing, ...
- Infra/hosting, dimensions, cost structure / driver
- Support, Incident mgmt
- Non functionals : availability, redundancy, security, recoverability, ...
- Gebruik van AI en AI tools op vandaag

# Participants
### Countroll/Axians
Alexander
### Sweetspot
Ronny Dewaele

# Intake notes - Ronny
Interview with Alexander
Notes taken
(countroll.pdf attachment exists in Notion; treat as additional source if MCP can fetch it)

Key extracted facts (use as evidence):
- Cloud-based roll asset management platform: track/monitor industrial rollers lifecycle
- Web portal: Vue.js
- Mobile: Android, Kotlin Multiplatform, MVI pattern
- Backend: Kotlin + Spring Boot, Clean Architecture, Core API + Event Analyzer for sensor data
- Hosting: Microsoft Azure; Application Gateway; VMs; load balancing
- IAM: Keycloak
- Data: Cosmos DB (NoSQL) for domain; raw IoT events in Azure event DB; Keycloak uses MySQL; Redis mentioned as cache
- Tooling: Shortcut for PM; Confluence for docs; CI/CD mix Azure DevOps + GitHub/GitLab; Support via Jira Service Desk; QA with Qase; target 50-70% coverage; happy-path smoke tests
- High availability: dual VM setup + hot upgrade
- Adoption issues (from broader project knowledge included in intake text): low external adoption; internal operational enablement strongest value
"""
