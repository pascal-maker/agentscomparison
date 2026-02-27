"""
Notion Reader Agent
===================

Reads Notion pages using MCP (Model Context Protocol).

Uses the official Notion MCP server to access private pages.

SAFETY FEATURES:
- SAFE_MODE: When enabled, only allows access to allowlisted pages/workspaces
- Prevents accidental access to production workspaces (e.g., Sweetspot client data)
"""

import os
import re
import logging
from typing import Optional, List, Set

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.tools.mcp import MCPTools

# ============================================================================
# Logging Setup
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NotionReader")

# ============================================================================
# Setup
# ============================================================================
# Notion token for MCP (masked for security)
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
if NOTION_TOKEN:
    masked = f"{NOTION_TOKEN[:6]}...{NOTION_TOKEN[-4:]}"
    logger.info(f"NOTION_TOKEN loaded: {masked}")
else:
    logger.warning("NOTION_TOKEN not set - MCP will not work")

# ============================================================================
# Safety Configuration
# ============================================================================
# SAFE_MODE prevents access to pages outside the allowlist
SAFE_MODE = os.getenv("NOTION_SAFE_MODE", "true").lower() in ("true", "1", "yes")

# Allowlisted workspace IDs (comma-separated in env)
ALLOWED_WORKSPACES: Set[str] = set(
    ws.strip() for ws in os.getenv("NOTION_ALLOWED_WORKSPACES", "").split(",") if ws.strip()
)

# Allowlisted page IDs (comma-separated in env)
ALLOWED_PAGES: Set[str] = set(
    pg.strip() for pg in os.getenv("NOTION_ALLOWED_PAGES", "").split(",") if pg.strip()
)

# Blocked workspace patterns (always blocked, even if SAFE_MODE is off)
BLOCKED_WORKSPACE_PATTERNS = [
    "sweetspot",
    "sweetspot-experts",
]

logger.info(f"SAFE_MODE: {SAFE_MODE}")
logger.info(f"Allowed workspaces: {len(ALLOWED_WORKSPACES)}")
logger.info(f"Allowed pages: {len(ALLOWED_PAGES)}")


class NotionAccessError(Exception):
    """Raised when access to a Notion page is blocked by safety rules."""
    pass


def is_page_allowed(url_or_id: str) -> tuple[bool, str]:
    """
    Check if a page is allowed based on safety rules.

    Returns:
        Tuple of (is_allowed, reason)
    """
    page_id = extract_page_id(url_or_id)

    # Check for blocked workspace patterns in URL
    url_lower = url_or_id.lower()
    for pattern in BLOCKED_WORKSPACE_PATTERNS:
        if pattern in url_lower:
            reason = f"BLOCKED: URL contains blocked workspace pattern '{pattern}'"
            logger.warning(f"🚫 {reason} - URL: {url_or_id}")
            return False, reason

    # If SAFE_MODE is off, allow (unless blocked above)
    if not SAFE_MODE:
        logger.info(f"✅ SAFE_MODE off - allowing access to: {page_id}")
        return True, "SAFE_MODE disabled"

    # Check if page is in allowlist
    if page_id in ALLOWED_PAGES:
        logger.info(f"✅ Page {page_id} is in allowlist")
        return True, "Page in allowlist"

    # Check if page ID (without dashes) is in allowlist
    page_id_nodash = page_id.replace("-", "")
    for allowed in ALLOWED_PAGES:
        if allowed.replace("-", "") == page_id_nodash:
            logger.info(f"✅ Page {page_id} matches allowlist entry")
            return True, "Page in allowlist"

    # Check workspace in URL
    workspace_match = re.search(r"notion\.so/([^/]+)/", url_or_id)
    if workspace_match:
        workspace = workspace_match.group(1)
        if workspace in ALLOWED_WORKSPACES:
            logger.info(f"✅ Workspace '{workspace}' is in allowlist")
            return True, f"Workspace '{workspace}' in allowlist"

    # Default: deny in SAFE_MODE
    reason = f"DENIED: Page {page_id} not in allowlist (SAFE_MODE=true)"
    logger.warning(f"🚫 {reason}")
    return False, reason


def extract_page_id(url_or_id: str) -> str:
    """
    Extract Notion page ID from URL or return as-is if already an ID.

    Returns the raw 32-character hex ID (without dashes) as required by Notion API.

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
        # ID is the last 32 chars (with dashes removed)
        match = re.search(r"([a-f0-9]{32})$", last_part.replace("-", ""))
        if match:
            return match.group(1)  # Return raw hex without dashes
    # If already an ID, remove any dashes
    clean_id = url_or_id.replace("-", "")
    if re.match(r"^[a-f0-9]{32}$", clean_id):
        return clean_id
    return url_or_id


# ============================================================================
# Notion Client Configuration
# ============================================================================
# Using notion-client directly for more reliable page reading

try:
    from notion_client import Client as NotionClient
    NOTION_CLIENT = NotionClient(auth=NOTION_TOKEN) if NOTION_TOKEN else None
    if NOTION_CLIENT:
        logger.info("Notion client initialized")
except ImportError:
    logger.warning("notion-client not installed, using MCP fallback")
    NOTION_CLIENT = None
except Exception as e:
    logger.warning(f"Failed to initialize Notion client: {e}")
    NOTION_CLIENT = None


def get_page_content_direct(page_id: str, depth: int = 0, max_depth: int = 3) -> dict:
    """
    Read a Notion page directly using the Notion API client.
    Recursively reads child pages up to max_depth levels deep.

    Returns:
        dict with 'title', 'content', 'success', 'error'
    """
    result = {
        "title": "",
        "content": "",
        "success": False,
        "error": None,
    }

    if not NOTION_CLIENT:
        result["error"] = "Notion client not available"
        return result

    try:
        # Get page metadata
        page = NOTION_CLIENT.pages.retrieve(page_id=page_id)

        # Extract title (works for both regular pages and database entries)
        title_prop = page.get("properties", {}).get("title", {})
        if title_prop.get("title"):
            result["title"] = title_prop["title"][0].get("plain_text", "")
        if not result["title"]:
            # Try Name property (database pages)
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title" and prop.get("title"):
                    result["title"] = prop["title"][0].get("plain_text", "")
                    break

        heading_prefix = "#" * max(1, depth + 1)
        content_lines = [f"{heading_prefix} {result['title']}\n"] if result["title"] else []

        # Paginate through all blocks
        all_blocks = []
        cursor = None
        while True:
            kwargs = {"block_id": page_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = NOTION_CLIENT.blocks.children.list(**kwargs)
            all_blocks.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

        for block in all_blocks:
            block_type = block.get("type")
            block_data = block.get(block_type, {})

            # Extract plain text from rich_text
            text = ""
            if "rich_text" in block_data:
                text = "".join([t.get("plain_text", "") for t in block_data["rich_text"]])

            if block_type == "heading_1":
                content_lines.append(f"\n# {text}")
            elif block_type == "heading_2":
                content_lines.append(f"\n## {text}")
            elif block_type == "heading_3":
                content_lines.append(f"\n### {text}")
            elif block_type == "paragraph":
                if text:
                    content_lines.append(text)
            elif block_type == "bulleted_list_item":
                content_lines.append(f"- {text}")
            elif block_type == "numbered_list_item":
                content_lines.append(f"1. {text}")
            elif block_type == "to_do":
                checked = "x" if block_data.get("checked") else " "
                content_lines.append(f"- [{checked}] {text}")
            elif block_type == "code":
                lang = block_data.get("language", "")
                content_lines.append(f"```{lang}\n{text}\n```")
            elif block_type == "quote":
                content_lines.append(f"> {text}")
            elif block_type == "divider":
                content_lines.append("\n---\n")
            elif block_type == "callout":
                if text:
                    content_lines.append(f"> {text}")
            elif block_type == "toggle":
                if text:
                    content_lines.append(f"\n### {text}")
                # Toggle children are fetched via has_children below
            elif block_type == "child_page":
                # Sub-page — recurse if within depth limit
                child_title = block_data.get("title", "")
                child_id = block.get("id", "").replace("-", "")
                if depth < max_depth and child_id:
                    logger.info(f"  {'  ' * depth}↳ Reading sub-page: {child_title} ({child_id})")
                    child_result = get_page_content_direct(child_id, depth=depth + 1, max_depth=max_depth)
                    if child_result["success"]:
                        content_lines.append(f"\n{child_result['content']}")
                    else:
                        content_lines.append(f"\n## {child_title}\n[Could not read sub-page: {child_result['error']}]")
                else:
                    content_lines.append(f"\n## {child_title}\n[Sub-page not expanded — max depth reached]")
                continue
            elif block_type == "link_to_page":
                # Explicit link-to-page block
                linked_id = (
                    block_data.get("page_id", "") or block_data.get("database_id", "")
                ).replace("-", "")
                if depth < max_depth and linked_id:
                    logger.info(f"  {'  ' * depth}↳ Following linked page: {linked_id}")
                    child_result = get_page_content_direct(linked_id, depth=depth + 1, max_depth=max_depth)
                    if child_result["success"]:
                        content_lines.append(f"\n{child_result['content']}")
                continue

            # Recurse into blocks that have children (e.g. toggles, synced blocks)
            if block.get("has_children") and block_type not in ("child_page", "link_to_page") and depth < max_depth:
                child_block_id = block.get("id", "").replace("-", "")
                if child_block_id:
                    child_result = get_page_content_direct(child_block_id, depth=depth + 1, max_depth=max_depth)
                    if child_result["success"] and child_result["content"]:
                        # Append child content without the H1 title line
                        child_lines = [
                            l for l in child_result["content"].split("\n")
                            if not l.startswith("# ")
                        ]
                        content_lines.extend(child_lines)

        result["content"] = "\n".join(content_lines)
        result["success"] = True
        logger.info(f"{'  ' * depth}✅ Read page: {result['title']} ({len(all_blocks)} blocks)")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Failed to read page: {e}")

    return result


# MCP fallback (for compatibility)
def create_notion_mcp_tools() -> Optional[MCPTools]:
    """Create MCPTools configured for Notion MCP server (fallback)."""
    if not NOTION_TOKEN:
        return None
    try:
        return MCPTools(
            command="npx @notionhq/notion-mcp-server",
            transport="stdio",
            env={"NOTION_TOKEN": NOTION_TOKEN},
            timeout_seconds=60,
        )
    except Exception as e:
        logger.warning(f"Failed to create MCP tools: {e}")
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
    tools=[notion_mcp] if notion_mcp else [],
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)


# ============================================================================
# Helper Functions
# ============================================================================
def read_notion_page(url_or_id: str, use_fallback: bool = True, bypass_safety: bool = False) -> dict:
    """
    Read a Notion page and return structured content.

    Uses the direct Notion API client for reliability.

    Args:
        url_or_id: Notion page URL or ID
        use_fallback: If True, return fallback content when API fails
        bypass_safety: If True, skip safety checks (USE WITH CAUTION)

    Returns:
        dict with keys: title, content, metadata, success, error, blocked
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
        "blocked": False,
    }

    # Safety check (unless bypassed)
    if not bypass_safety:
        is_allowed, reason = is_page_allowed(url_or_id)
        if not is_allowed:
            result["error"] = reason
            result["blocked"] = True
            logger.error(f"Access blocked: {reason}")
            return result

    # Try direct Notion client first (more reliable)
    if NOTION_CLIENT:
        logger.info(f"📖 Reading Notion page via API: {page_id}")
        direct_result = get_page_content_direct(page_id)

        if direct_result["success"]:
            result["title"] = direct_result["title"]
            result["content"] = direct_result["content"]
            result["success"] = True
            logger.info(f"✅ Successfully read page: {direct_result['title']}")
            return result
        else:
            logger.warning(f"Direct API failed: {direct_result['error']}, trying MCP...")

    # Fallback to MCP if direct client fails
    if notion_mcp:
        try:
            logger.info(f"📖 Reading Notion page via MCP: {page_id}")
            response = notion_reader_agent.run(
                f"Read the Notion page with ID: {page_id}. "
                f"Return the full content as markdown."
            )
            result["content"] = response.content if hasattr(response, 'content') else str(response)
            result["success"] = True
            logger.info(f"✅ Successfully read page via MCP: {page_id}")
            return result
        except Exception as e:
            logger.error(f"❌ MCP failed: {e}")
            result["error"] = str(e)

    # Neither worked
    if not NOTION_CLIENT and not notion_mcp:
        result["error"] = "No Notion client available. Set NOTION_TOKEN in .env"

    if use_fallback and not result["success"]:
        result["content"] = "[Content unavailable - using fallback]"

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
