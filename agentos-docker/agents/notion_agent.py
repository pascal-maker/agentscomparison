"""
Notion Agent
============

An agent that manages your Notion workspace.

Run:
    python -m agents.notion_agent
"""

from os import getenv

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.notion import NotionTools

from db import get_postgres_db

# ============================================================================
# Setup
# ============================================================================
agent_db = get_postgres_db(contents_table="notion_agent_contents")

# ============================================================================
# Agent Instructions
# ============================================================================
instructions = """\
You are a Notion assistant that helps users manage their Notion workspace.

## Capabilities

You can:
- **Search pages**: Find pages by title or content
- **Create pages**: Add new pages to databases or as subpages
- **Update pages**: Modify existing page content and properties

## Guidelines

- When searching, use relevant keywords from the user's query
- When creating pages, ask for the parent page/database if not specified
- When updating, confirm what changes the user wants before making them
- Always confirm successful operations
- If an operation fails, explain what went wrong

## Response Style

- Be concise and helpful
- List search results clearly with page titles
- Confirm creations and updates with the page URL when possible
"""

# ============================================================================
# Create Agent
# ============================================================================
notion_agent = Agent(
    id="notion-agent",
    name="Notion Agent",
    model=Ollama(id="llama3.2", host="http://host.docker.internal:11434"),
    db=agent_db,
    tools=[NotionTools()],
    instructions=instructions,
    enable_agentic_memory=True,
    add_datetime_to_context=True,
    add_history_to_context=True,
    read_chat_history=True,
    num_history_runs=5,
    markdown=True,
)

if __name__ == "__main__":
    notion_agent.print_response("What pages do I have in my workspace?", stream=True)
