"""
Notion Reader Agent
===================

Reads Notion pages using MCP (Model Context Protocol).

Uses the official Notion MCP server to access private pages.
"""

import os
import re
from typing import Optional

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools.mcp import MCPTools

from db import get_postgres_db

# ============================================================================
# Setup
# ============================================================================
agent_db = get_postgres_db(contents_table="notion_reader_contents")

# Notion token for MCP (masked for security)
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
if NOTION_TOKEN:
    masked = f"{NOTION_TOKEN[:6]}...{NOTION_TOKEN[-4:]}"
    print(f"[NotionReader] NOTION_TOKEN loaded: {masked}")
else:
    print("[NotionReader] WARNING: NOTION_TOKEN not set")


def extract_page_id(url_or_id: str) -> str:
    """
    Extract Notion page ID from URL or return as-is if already an ID.

    Examples:
    - https://www.notion.so/workspace/Page-Name-abc123def456 -> abc123def456
    - abc123def456 -> abc123def456
    """
    # If it's a URL, extract the ID from the end
    if "notion.so" in url_or_id:
        # Remove query params
        url_clean = url_or_id.split("?")[0]
        # Get the last segment
        parts = url_clean.rstrip("/").split("/")
        last_part = parts[-1]
        # ID is the last 32 chars (with dashes removed) or after the last dash
        match = re.search(r"([a-f0-9]{32})$", last_part.replace("-", ""))
        if match:
            raw_id = match.group(1)
            # Format as UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
            return f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
    # Return as-is (assume it's already an ID)
    return url_or_id


# ============================================================================
# MCP Configuration for Notion
# ============================================================================
# The Notion MCP server needs to be run with:
# npx @notionhq/notion-mcp-server
#
# We configure MCPTools to connect to it via stdio transport.
# The server will use NOTION_TOKEN from environment.

def create_notion_mcp_tools() -> Optional[MCPTools]:
    """Create MCPTools configured for Notion MCP server."""
    if not NOTION_TOKEN:
        print("[NotionReader] Cannot create MCP tools: NOTION_TOKEN not set")
        return None

    try:
        # Use command-based MCP (spawns npx process)
        # The Notion MCP server exposes tools like:
        # - notion_retrieve_page
        # - notion_retrieve_block_children
        # - notion_search
        return MCPTools(
            command="npx @notionhq/notion-mcp-server",
            env={"NOTION_TOKEN": NOTION_TOKEN},
            timeout_seconds=30,
        )
    except Exception as e:
        print(f"[NotionReader] Failed to create MCP tools: {e}")
        return None


# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a Notion Reader agent that fetches and processes content from Notion pages.

## Your Capabilities

You can use MCP tools to:
- Retrieve page content by page ID
- Get block children (content blocks within a page)
- Search for pages

## How to Read a Page

1. If given a Notion URL, extract the page ID (last 32 hex characters)
2. Use `notion_retrieve_page` to get page metadata
3. Use `notion_retrieve_block_children` to get the actual content blocks
4. Convert blocks to clean markdown-like text

## Output Format

Return the page content as clean markdown with:
- Page title as H1
- Headings preserved (H2, H3, etc.)
- Bullet points and numbered lists
- Code blocks if present
- A metadata footer with: source URL, last edited date

## Important

- Only read pages you have access to via the integration
- If a page cannot be read, report the error clearly
- Preserve the document structure exactly
"""

# ============================================================================
# Create Agent
# ============================================================================
notion_mcp = create_notion_mcp_tools()

notion_reader_agent = Agent(
    id="notion-reader",
    name="Notion Reader",
    model=Claude(id="claude-sonnet-4-20250514"),
    db=agent_db,
    tools=[notion_mcp] if notion_mcp else [],
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


# ============================================================================
# Helper Functions
# ============================================================================
def read_notion_page(url_or_id: str, use_fallback: bool = True) -> dict:
    """
    Read a Notion page and return structured content.

    Args:
        url_or_id: Notion page URL or ID
        use_fallback: If True, return fallback content when MCP fails

    Returns:
        dict with keys: title, content, metadata, success, error
    """
    page_id = extract_page_id(url_or_id)

    result = {
        "title": "",
        "content": "",
        "metadata": {
            "page_id": page_id,
            "source_url": url_or_id,
        },
        "success": False,
        "error": None,
    }

    if not notion_mcp:
        result["error"] = "Notion MCP not configured. Set NOTION_TOKEN environment variable."
        if use_fallback:
            result["content"] = "[MCP not available - using fallback content]"
        return result

    try:
        # Use the agent to read the page
        response = notion_reader_agent.run(
            f"Read the Notion page with ID: {page_id}. "
            f"Return the full content as markdown."
        )
        result["content"] = response.content if hasattr(response, 'content') else str(response)
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    # Test the agent
    print("Testing Notion Reader Agent...")
    print(f"MCP Available: {notion_mcp is not None}")

    if notion_mcp:
        notion_reader_agent.print_response(
            "What tools do you have available?",
            stream=True
        )
    else:
        print("NOTION_TOKEN not set. Please set it in .env")
