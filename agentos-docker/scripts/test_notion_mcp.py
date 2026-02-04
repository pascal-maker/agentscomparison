#!/usr/bin/env python3
"""
Notion MCP Smoke Test
=====================

A simple CLI to test the Notion MCP integration with safety features.

Usage:
    python -m scripts.test_notion_mcp <page_url_or_id>
    python -m scripts.test_notion_mcp --check-config
    python -m scripts.test_notion_mcp --list-tools

Examples:
    # Check configuration
    python -m scripts.test_notion_mcp --check-config

    # Test reading a page (will respect SAFE_MODE allowlist)
    python -m scripts.test_notion_mcp "https://www.notion.so/my-workspace/Test-Page-abc123"

    # List available MCP tools
    python -m scripts.test_notion_mcp --list-tools
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def check_config():
    """Check and display current configuration."""
    print("=" * 60)
    print("Notion MCP Configuration Check")
    print("=" * 60)

    # Check NOTION_TOKEN
    token = os.getenv("NOTION_TOKEN", "")
    if token:
        masked = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "***"
        print(f"✅ NOTION_TOKEN: {masked}")
    else:
        print("❌ NOTION_TOKEN: NOT SET")

    # Check SAFE_MODE
    safe_mode = os.getenv("NOTION_SAFE_MODE", "true").lower() in ("true", "1", "yes")
    status = "🔒 ENABLED (recommended)" if safe_mode else "⚠️  DISABLED"
    print(f"   NOTION_SAFE_MODE: {status}")

    # Check allowlists
    workspaces = [w.strip() for w in os.getenv("NOTION_ALLOWED_WORKSPACES", "").split(",") if w.strip()]
    pages = [p.strip() for p in os.getenv("NOTION_ALLOWED_PAGES", "").split(",") if p.strip()]

    print(f"   Allowed workspaces: {len(workspaces)}")
    for ws in workspaces:
        print(f"      - {ws}")

    print(f"   Allowed pages: {len(pages)}")
    for pg in pages:
        print(f"      - {pg[:20]}..." if len(pg) > 20 else f"      - {pg}")

    # Recommendations
    print("\n" + "-" * 60)
    print("Recommendations:")

    if not token:
        print("1. Set NOTION_TOKEN in your .env file")
        print("   Get it from: https://www.notion.so/my-integrations")

    if safe_mode and not workspaces and not pages:
        print("2. Add test pages/workspaces to your allowlist:")
        print("   NOTION_ALLOWED_WORKSPACES=my-test-workspace")
        print("   NOTION_ALLOWED_PAGES=abc123def456...")

    if not safe_mode:
        print("⚠️  SAFE_MODE is disabled. Enable it to prevent accidental access.")

    print("=" * 60)


def list_tools():
    """List available MCP tools."""
    print("=" * 60)
    print("Checking available MCP tools...")
    print("=" * 60)

    try:
        from agents.notion_reader import notion_mcp, notion_reader_agent

        if not notion_mcp:
            print("❌ MCP not available. Check NOTION_TOKEN.")
            return

        print("Asking agent about available tools...\n")
        response = notion_reader_agent.run("What tools do you have available? List them briefly.")
        content = response.content if hasattr(response, 'content') else str(response)
        print(content)

    except Exception as e:
        print(f"❌ Error: {e}")


def test_read_page(url_or_id: str, lines: int = 30):
    """Test reading a Notion page."""
    print("=" * 60)
    print(f"Testing Notion page read: {url_or_id[:50]}...")
    print("=" * 60)

    try:
        from agents.notion_reader import (
            read_notion_page,
            is_page_allowed,
            extract_page_id,
            SAFE_MODE,
        )

        page_id = extract_page_id(url_or_id)
        print(f"Extracted page ID: {page_id}")
        print(f"SAFE_MODE: {SAFE_MODE}")

        # Check if allowed first
        is_allowed, reason = is_page_allowed(url_or_id)
        print(f"Access check: {'✅ ALLOWED' if is_allowed else '🚫 BLOCKED'}")
        print(f"Reason: {reason}")

        if not is_allowed:
            print("\n" + "-" * 60)
            print("To allow this page, add to your .env:")
            print(f"   NOTION_ALLOWED_PAGES={page_id}")
            print("-" * 60)
            return

        # Try to read the page
        print("\nReading page...")
        result = read_notion_page(url_or_id)

        if result["blocked"]:
            print(f"🚫 BLOCKED: {result['error']}")
            return

        if result["success"]:
            print(f"✅ SUCCESS!")
            print("-" * 60)
            print(f"First {lines} lines of content:\n")

            content_lines = result["content"].split("\n")[:lines]
            for i, line in enumerate(content_lines, 1):
                print(f"{i:3}| {line}")

            if len(result["content"].split("\n")) > lines:
                print(f"\n... ({len(result['content'].split(chr(10))) - lines} more lines)")
        else:
            print(f"❌ FAILED: {result['error']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Test Notion MCP integration with safety features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "page",
        nargs="?",
        help="Notion page URL or ID to read",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Check current configuration",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List available MCP tools",
    )
    parser.add_argument(
        "--lines", "-n",
        type=int,
        default=30,
        help="Number of lines to print (default: 30)",
    )

    args = parser.parse_args()

    if args.check_config:
        check_config()
    elif args.list_tools:
        list_tools()
    elif args.page:
        test_read_page(args.page, args.lines)
    else:
        check_config()
        print("\nUsage: python -m scripts.test_notion_mcp <page_url_or_id>")


if __name__ == "__main__":
    main()
