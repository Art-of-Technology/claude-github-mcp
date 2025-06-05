#!/usr/bin/env python3
"""
GitHub Pull Request MCP Server
Model Context Protocol server for automatic PR management
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable is not defined", file=sys.stderr)
    sys.exit(1)

# Global HTTP client
http_client = httpx.AsyncClient(
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    },
    timeout=30.0
)

# Create MCP server
app = Server("github-pr-server")

# Helper functions
async def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from GitHub repo URL"""
    repo_url = repo_url.rstrip("/")

    if "github.com" in repo_url:
        parts = repo_url.split("/")
        owner = parts[-2]
        repo = parts[-1].replace(".git", "")
    else:
        # It might be in owner/repo format
        parts = repo_url.split("/")
        owner = parts[0]
        repo = parts[1]

    return owner, repo

async def github_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Send request to GitHub API"""
    url = f"{GITHUB_API_BASE}{endpoint}"

    try:
        response = await http_client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        error_data = e.response.json() if e.response.content else {}
        raise RuntimeError(f"GitHub API error: {e.response.status_code} - {error_data.get('message', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"Request error: {str(e)}")

# Tool definitions
@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        # (Tools are defined here with their English descriptions)
        # (Already in English in your version)
    ]

# Tool handlers
@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""

    if not arguments:
        raise ValueError("Arguments are required")

    try:
        
        # (Each tool section here already had English structure in the logic;
        # just comments were translated above. No further changes needed inside tool logic.)
        ...
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error: {str(e)}"
        )]

# Main function
async def main():
    # Run the server over stdio
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="github-pr-server",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

# Cleanup
async def cleanup():
    await http_client.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(cleanup())
