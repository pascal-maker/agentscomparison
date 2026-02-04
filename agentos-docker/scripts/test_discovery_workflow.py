#!/usr/bin/env python3
"""
Discovery Solution Workflow Test
================================

Tests the 5-agent discovery solution workflow.

Usage:
    # Test with fallback content (no Notion MCP needed)
    python -m scripts.test_discovery_workflow

    # Test with actual Notion pages (requires NOTION_TOKEN)
    python -m scripts.test_discovery_workflow --intake-url "https://notion.so/..."

    # Interactive mode - process sections one by one
    python -m scripts.test_discovery_workflow --interactive
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def test_agents_available():
    """Test that all 5 agents can be imported."""
    print("=" * 60)
    print("Testing Agent Imports")
    print("=" * 60)

    agents = []

    try:
        from agents.notion_reader import notion_reader_agent, SAFE_MODE
        agents.append(("NotionReader", notion_reader_agent, f"SAFE_MODE={SAFE_MODE}"))
        print(f"  [x] NotionReader (SAFE_MODE={SAFE_MODE})")
    except Exception as e:
        print(f"  [ ] NotionReader - FAILED: {e}")

    try:
        from agents.section_drafter import section_drafter_agent
        agents.append(("SectionDrafter", section_drafter_agent, ""))
        print(f"  [x] SectionDrafter")
    except Exception as e:
        print(f"  [ ] SectionDrafter - FAILED: {e}")

    try:
        from agents.revisor import revisor_agent
        agents.append(("Reviewer", revisor_agent, ""))
        print(f"  [x] Reviewer")
    except Exception as e:
        print(f"  [ ] Reviewer - FAILED: {e}")

    try:
        from agents.powerpoint_writer import powerpoint_writer_agent, TEMPLATE_PATH
        exists = Path(TEMPLATE_PATH).exists() if TEMPLATE_PATH else False
        agents.append(("PowerPointWriter", powerpoint_writer_agent, f"template={'found' if exists else 'missing'}"))
        print(f"  [x] PowerPointWriter (template={'found' if exists else 'missing'})")
    except Exception as e:
        print(f"  [ ] PowerPointWriter - FAILED: {e}")

    try:
        from teams.discovery_orchestrator import orchestrator_agent, discovery_team
        agents.append(("Orchestrator", orchestrator_agent, f"team_size={len(discovery_team.members)}"))
        print(f"  [x] Orchestrator (team_size={len(discovery_team.members)})")
    except Exception as e:
        print(f"  [ ] Orchestrator - FAILED: {e}")

    print(f"\nResult: {len(agents)}/5 agents loaded successfully")
    return len(agents) == 5


def test_workflow_with_fallback():
    """Test the workflow using fallback content (no MCP needed)."""
    print("\n" + "=" * 60)
    print("Testing Workflow with Fallback Content")
    print("=" * 60)

    try:
        from teams.discovery_orchestrator import start_report, process_user_feedback

        print("\nStarting report generation...")
        response, state = start_report(
            customer_name="Test Customer",
            intake_urls=[],  # Empty = use fallback
            mandatory_sections=[
                "Executive Summary",
                "Technical Architecture Overview",
                "Recommendations",
            ],
        )

        print("\n--- Initial Response ---")
        print(response[:2000])
        if len(response) > 2000:
            print(f"\n... (truncated, {len(response)} total chars)")

        print(f"\nState: {state.status}")
        print(f"Current section: {state.get_current_section_title()}")
        print(f"Sections to process: {len(state.template_sections)}")

        return True

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_powerpoint_generation():
    """Test PowerPoint generation directly."""
    print("\n" + "=" * 60)
    print("Testing PowerPoint Generation")
    print("=" * 60)

    try:
        from agents.powerpoint_writer import generate_powerpoint_from_markdown

        test_markdown = """
### Executive Summary

- Cloud-based platform for managing industrial assets
- Serves enterprise customers in manufacturing sector
- Modern cloud-native architecture on Azure

**Evidence Sources:**
- [Intake Notes] → Overview

### Technical Architecture

- Web portal: Vue.js with TypeScript
- Mobile: Kotlin Multiplatform
- Backend: Kotlin + Spring Boot
- Database: Azure Cosmos DB

**Evidence Sources:**
- [Technical Stack] → Architecture

### Recommendations

- Implement CI/CD pipeline improvements
- Add comprehensive API documentation
- Consider containerization strategy

**Evidence Sources:**
- [Analysis] → Next steps
"""

        print("Generating PowerPoint from test markdown...")
        result = generate_powerpoint_from_markdown(
            markdown_content=test_markdown,
            customer_name="Test Customer",
        )

        if result["success"]:
            print(f"\n  [x] PowerPoint generated successfully")
            print(f"      Slides: {result['slide_count']}")
            print(f"      Output: {result['output_path']}")
            return True
        else:
            print(f"\n  [ ] PowerPoint generation failed: {result['error']}")
            return False

    except ImportError as e:
        print(f"\n  [ ] Missing dependency: {e}")
        print("      Install with: pip install python-pptx")
        return False
    except Exception as e:
        print(f"\n  [ ] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def interactive_workflow(intake_urls=None):
    """Run the workflow interactively."""
    print("\n" + "=" * 60)
    print("Interactive Discovery Workflow")
    print("=" * 60)

    try:
        from teams.discovery_orchestrator import start_report, process_user_feedback

        print("\nStarting report generation...")
        response, state = start_report(
            customer_name="Interactive Test",
            intake_urls=intake_urls or [],
            mandatory_sections=[
                "Executive Summary",
                "Technical Architecture Overview",
                "Technology Stack",
                "Recommendations",
            ],
        )

        print(response)

        while state.status != "completed":
            print("\n" + "-" * 40)
            user_input = input("Your response (approve/skip/status/export/quit): ").strip()

            if user_input.lower() == "quit":
                print("Exiting...")
                break

            response, state = process_user_feedback(user_input, state)
            print(response)

        print("\n" + "=" * 60)
        print("Workflow completed!")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Test the 5-agent Discovery Solution workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--intake-url",
        action="append",
        help="Notion URL for intake content (can be repeated)",
    )
    parser.add_argument(
        "--skip-pptx",
        action="store_true",
        help="Skip PowerPoint generation test",
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_workflow(args.intake_url)
        return

    # Run all tests
    results = []

    results.append(("Agent imports", test_agents_available()))
    results.append(("Workflow with fallback", test_workflow_with_fallback()))

    if not args.skip_pptx:
        results.append(("PowerPoint generation", test_powerpoint_generation()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = 0
    for name, result in results:
        status = "[x] PASS" if result else "[ ] FAIL"
        print(f"  {status} - {name}")
        if result:
            passed += 1

    print(f"\nResult: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("\nAll tests passed! The 5-agent workflow is ready.")
    else:
        print("\nSome tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
