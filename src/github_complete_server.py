#!/usr/bin/env python3
"""
GitHub Complete MCP Server
A comprehensive Model Context Protocol server for GitHub operations
Supports: PRs, Issues, Repos, Branches, Actions, Analytics, and more
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import base64
from urllib.parse import urlparse

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

# ===========================
# CONFIGURATION AND CONSTANTS
# ===========================

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
    sys.exit(1)

# Global HTTP client with proper headers
http_client = httpx.AsyncClient(
    headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    },
    timeout=30.0
)

# Initialize MCP server
app = Server("github-complete-server")

# ===========================
# HELPER FUNCTIONS
# ===========================

async def parse_repo_info(repo_url: str) -> tuple[str, str]:
    """
    Parse repository URL or owner/repo format
    Accepts:
    - https://github.com/owner/repo
    - github.com/owner/repo
    - owner/repo
    """
    repo_url = repo_url.rstrip("/").replace(".git", "")
    
    if "github.com" in repo_url:
        parts = repo_url.split("/")
        owner = parts[-2]
        repo = parts[-1]
    else:
        parts = repo_url.split("/")
        if len(parts) == 2:
            owner = parts[0]
            repo = parts[1]
        else:
            raise ValueError("Invalid repository format. Use 'owner/repo' or GitHub URL")
    
    return owner, repo

async def github_request(
    method: str, 
    endpoint: str, 
    **kwargs
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Make authenticated request to GitHub API
    Handles errors and rate limiting
    """
    url = f"{GITHUB_API_BASE}{endpoint}"
    
    try:
        response = await http_client.request(method, url, **kwargs)
        
        # Check rate limit
        if "X-RateLimit-Remaining" in response.headers:
            remaining = int(response.headers["X-RateLimit-Remaining"])
            if remaining < 100:
                reset_time = int(response.headers["X-RateLimit-Reset"])
                reset_dt = datetime.fromtimestamp(reset_time)
                print(f"Warning: Only {remaining} API calls remaining. Resets at {reset_dt}", file=sys.stderr)
        
        response.raise_for_status()
        return response.json() if response.content else {}
        
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            error_data = e.response.json() if e.response.content else {}
        except:
            pass
        raise RuntimeError(f"GitHub API error {e.response.status_code}: {error_data.get('message', 'Unknown error')}")
    except Exception as e:
        raise RuntimeError(f"Request failed: {str(e)}")

async def paginate_github_request(
    method: str,
    endpoint: str,
    max_items: int = 100,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Handle paginated GitHub API responses
    Automatically fetches all pages up to max_items
    """
    all_items = []
    page = 1
    per_page = min(100, max_items)  # GitHub max is 100 per page
    
    while len(all_items) < max_items:
        params = kwargs.get("params", {})
        params.update({"page": page, "per_page": per_page})
        kwargs["params"] = params
        
        response = await github_request(method, endpoint, **kwargs)
        
        if isinstance(response, list):
            all_items.extend(response)
            if len(response) < per_page:  # No more pages
                break
        else:
            # Single item response
            return [response]
        
        page += 1
    
    return all_items[:max_items]

def format_datetime(dt_string: str) -> str:
    """Convert ISO datetime string to human-readable format"""
    if not dt_string:
        return "N/A"
    dt = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

# ===========================
# TOOL DEFINITIONS
# ===========================

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available GitHub tools"""
    return [
        # ========== PULL REQUEST TOOLS ==========
        types.Tool(
            name="create_pull_request",
            description="Create a new pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "head": {"type": "string", "description": "Source branch"},
                    "base": {"type": "string", "description": "Target branch", "default": "main"},
                    "draft": {"type": "boolean", "description": "Create as draft", "default": False}
                },
                "required": ["repo", "title", "body", "head"]
            }
        ),
        types.Tool(
            name="list_pull_requests",
            description="List pull requests in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="get_pull_request",
            description="Get details of a specific pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"},
                    "pr_number": {"type": "integer", "description": "PR number"}
                },
                "required": ["repo", "pr_number"]
            }
        ),
        types.Tool(
            name="merge_pull_request",
            description="Merge a pull request",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "pr_number": {"type": "integer", "description": "PR number"},
                    "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"], "default": "merge"}
                },
                "required": ["repo", "pr_number"]
            }
        ),
        
        # ========== REPOSITORY TOOLS ==========
        types.Tool(
            name="create_repository",
            description="Create a new GitHub repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Repository name"},
                    "description": {"type": "string", "description": "Repository description"},
                    "private": {"type": "boolean", "description": "Make repository private", "default": False},
                    "auto_init": {"type": "boolean", "description": "Initialize with README", "default": True}
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="get_repository",
            description="Get repository information",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="list_user_repositories",
            description="List repositories for the authenticated user",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["all", "owner", "public", "private"], "default": "all"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 30}
                }
            }
        ),
        
        # ========== BRANCH TOOLS ==========
        types.Tool(
            name="list_branches",
            description="List all branches in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository (owner/repo or URL)"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="create_branch",
            description="Create a new branch",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "branch_name": {"type": "string", "description": "New branch name"},
                    "from_branch": {"type": "string", "description": "Source branch", "default": "main"}
                },
                "required": ["repo", "branch_name"]
            }
        ),
        types.Tool(
            name="delete_branch",
            description="Delete a branch",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "branch_name": {"type": "string", "description": "Branch to delete"}
                },
                "required": ["repo", "branch_name"]
            }
        ),
        
        # ========== ISSUE TOOLS ==========
        types.Tool(
            name="create_issue",
            description="Create a new issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue description"},
                    "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add"},
                    "assignees": {"type": "array", "items": {"type": "string"}, "description": "Assignees"}
                },
                "required": ["repo", "title"]
            }
        ),
        types.Tool(
            name="list_issues",
            description="List issues in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                    "labels": {"type": "string", "description": "Comma-separated labels"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="update_issue",
            description="Update an issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "issue_number": {"type": "integer", "description": "Issue number"},
                    "title": {"type": "string", "description": "New title"},
                    "body": {"type": "string", "description": "New description"},
                    "state": {"type": "string", "enum": ["open", "closed"]},
                    "labels": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["repo", "issue_number"]
            }
        ),
        
        # ========== RELEASE/TAG TOOLS ==========
        types.Tool(
            name="create_release",
            description="Create a new release",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "tag_name": {"type": "string", "description": "Tag name (e.g., v1.0.0)"},
                    "name": {"type": "string", "description": "Release name"},
                    "body": {"type": "string", "description": "Release notes"},
                    "draft": {"type": "boolean", "default": False},
                    "prerelease": {"type": "boolean", "default": False}
                },
                "required": ["repo", "tag_name", "name"]
            }
        ),
        types.Tool(
            name="list_releases",
            description="List releases in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== GITHUB ACTIONS TOOLS ==========
        types.Tool(
            name="list_workflows",
            description="List GitHub Actions workflows",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="trigger_workflow",
            description="Trigger a GitHub Actions workflow",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "workflow_id": {"type": "string", "description": "Workflow ID or filename"},
                    "ref": {"type": "string", "description": "Branch/tag reference", "default": "main"},
                    "inputs": {"type": "object", "description": "Workflow inputs"}
                },
                "required": ["repo", "workflow_id"]
            }
        ),
        types.Tool(
            name="list_workflow_runs",
            description="List recent workflow runs",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "workflow_id": {"type": "string", "description": "Optional workflow ID"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== COMMIT TOOLS ==========
        types.Tool(
            name="list_commits",
            description="List commits in a repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "branch": {"type": "string", "description": "Branch name", "default": "main"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="get_commit",
            description="Get details of a specific commit",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "sha": {"type": "string", "description": "Commit SHA"}
                },
                "required": ["repo", "sha"]
            }
        ),
        
        # ========== ANALYTICS TOOLS ==========
        types.Tool(
            name="get_repository_stats",
            description="Get repository statistics and analytics",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="get_contributor_stats",
            description="Get contributor statistics",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="get_commit_activity",
            description="Get commit activity for the last year",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== COLLABORATION TOOLS ==========
        types.Tool(
            name="add_collaborator",
            description="Add a collaborator to repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "username": {"type": "string", "description": "GitHub username"},
                    "permission": {"type": "string", "enum": ["pull", "push", "admin"], "default": "push"}
                },
                "required": ["repo", "username"]
            }
        ),
        types.Tool(
            name="list_collaborators",
            description="List repository collaborators",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== FILE OPERATIONS ==========
        types.Tool(
            name="get_file_content",
            description="Get content of a file from repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "path": {"type": "string", "description": "File path"},
                    "branch": {"type": "string", "description": "Branch name", "default": "main"}
                },
                "required": ["repo", "path"]
            }
        ),
        types.Tool(
            name="create_or_update_file",
            description="Create or update a file in repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository"},
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "File content"},
                    "message": {"type": "string", "description": "Commit message"},
                    "branch": {"type": "string", "description": "Branch name", "default": "main"}
                },
                "required": ["repo", "path", "content", "message"]
            }
        ),
        
        # ========== SEARCH TOOLS ==========
        types.Tool(
            name="search_repositories",
            description="Search for repositories on GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10}
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="search_code",
            description="Search for code on GitHub",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "repo": {"type": "string", "description": "Optional: limit to specific repo"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10}
                },
                "required": ["query"]
            }
        )
    ]

# ===========================
# TOOL HANDLERS
# ===========================

@app.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool invocations"""
    
    if not arguments:
        raise ValueError("Arguments required")
    
    try:
        # ========== PULL REQUEST HANDLERS ==========
        if name == "create_pull_request":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            data = {
                "title": arguments["title"],
                "body": arguments["body"],
                "head": arguments["head"],
                "base": arguments.get("base", "main"),
                "draft": arguments.get("draft", False)
            }
            
            result = await github_request("POST", f"/repos/{owner}/{repo}/pulls", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Pull Request #{result['number']} created!\n\n"
                     f"**Title:** {result['title']}\n"
                     f"**URL:** {result['html_url']}\n"
                     f"**State:** {result['state']}\n"
                     f"**Draft:** {'Yes' if result['draft'] else 'No'}"
            )]
        
        elif name == "list_pull_requests":
            owner, repo = await parse_repo_info(arguments["repo"])
            state = arguments.get("state", "open")
            limit = arguments.get("limit", 20)
            
            params = {"state": state}
            results = await paginate_github_request(
                "GET", 
                f"/repos/{owner}/{repo}/pulls", 
                max_items=limit,
                params=params
            )
            
            if not results:
                return [types.TextContent(type="text", text=f"No {state} pull requests found.")]
            
            pr_list = []
            for pr in results:
                pr_list.append(
                    f"**#{pr['number']}** - {pr['title']}\n"
                    f"   By: @{pr['user']['login']} | State: {pr['state']}\n"
                    f"   Created: {format_datetime(pr['created_at'])}\n"
                    f"   URL: {pr['html_url']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"📋 Pull Requests in {owner}/{repo} ({state}):\n\n" + "\n\n".join(pr_list)
            )]
        
        elif name == "get_pull_request":
            owner, repo = await parse_repo_info(arguments["repo"])
            pr_number = arguments["pr_number"]
            
            pr = await github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
            reviews = await github_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
            
            review_summary = []
            for review in reviews[:5]:  # Limit to 5 most recent
                review_summary.append(f"- @{review['user']['login']}: {review['state']}")
            
            return [types.TextContent(
                type="text",
                text=f"🔍 Pull Request #{pr_number} Details:\n\n"
                     f"**Title:** {pr['title']}\n"
                     f"**Description:** {pr['body'] or 'No description'}\n"
                     f"**State:** {pr['state']}\n"
                     f"**Author:** @{pr['user']['login']}\n"
                     f"**Branch:** {pr['head']['ref']} → {pr['base']['ref']}\n"
                     f"**Created:** {format_datetime(pr['created_at'])}\n"
                     f"**Changes:** +{pr['additions']} / -{pr['deletions']}\n"
                     f"**Reviews:**\n" + ("\n".join(review_summary) if review_summary else "No reviews yet") + "\n"
                     f"**URL:** {pr['html_url']}"
            )]
        
        elif name == "merge_pull_request":
            owner, repo = await parse_repo_info(arguments["repo"])
            pr_number = arguments["pr_number"]
            
            data = {"merge_method": arguments.get("merge_method", "merge")}
            result = await github_request("PUT", f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"🎉 Pull Request #{pr_number} merged successfully!\n\n"
                     f"**SHA:** {result['sha']}\n"
                     f"**Message:** {result['message']}"
            )]
        
        # ========== REPOSITORY HANDLERS ==========
        elif name == "create_repository":
            data = {
                "name": arguments["name"],
                "description": arguments.get("description", ""),
                "private": arguments.get("private", False),
                "auto_init": arguments.get("auto_init", True)
            }
            
            result = await github_request("POST", "/user/repos", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Repository created!\n\n"
                     f"**Name:** {result['full_name']}\n"
                     f"**URL:** {result['html_url']}\n"
                     f"**Private:** {'Yes' if result['private'] else 'No'}\n"
                     f"**Clone URL:** {result['clone_url']}"
            )]
        
        elif name == "get_repository":
            owner, repo = await parse_repo_info(arguments["repo"])
            result = await github_request("GET", f"/repos/{owner}/{repo}")
            
            return [types.TextContent(
                type="text",
                text=f"📦 Repository: {result['full_name']}\n\n"
                     f"**Description:** {result['description'] or 'No description'}\n"
                     f"**Language:** {result['language'] or 'Not detected'}\n"
                     f"**Stars:** ⭐ {result['stargazers_count']}\n"
                     f"**Forks:** 🍴 {result['forks_count']}\n"
                     f"**Issues:** 🐛 {result['open_issues_count']}\n"
                     f"**Created:** {format_datetime(result['created_at'])}\n"
                     f"**Updated:** {format_datetime(result['updated_at'])}\n"
                     f"**URL:** {result['html_url']}"
            )]
        
        elif name == "list_user_repositories":
            repo_type = arguments.get("type", "all")
            limit = arguments.get("limit", 30)
            
            params = {"type": repo_type, "sort": "updated"}
            results = await paginate_github_request(
                "GET", 
                "/user/repos", 
                max_items=limit,
                params=params
            )
            
            repo_list = []
            for repo in results:
                visibility = "🔒 Private" if repo['private'] else "🌍 Public"
                repo_list.append(
                    f"**{repo['name']}** {visibility}\n"
                    f"   {repo['description'] or 'No description'}\n"
                    f"   ⭐ {repo['stargazers_count']} | 🍴 {repo['forks_count']} | "
                    f"Language: {repo['language'] or 'N/A'}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"📚 Your Repositories ({repo_type}):\n\n" + "\n\n".join(repo_list)
            )]
        
        # ========== BRANCH HANDLERS ==========
        elif name == "list_branches":
            owner, repo = await parse_repo_info(arguments["repo"])
            results = await paginate_github_request("GET", f"/repos/{owner}/{repo}/branches", max_items=100)
            
            branch_names = [f"• {branch['name']}" for branch in results]
            
            return [types.TextContent(
                type="text",
                text=f"🌳 Branches in {owner}/{repo}:\n\n" + "\n".join(branch_names)
            )]
        
        elif name == "create_branch":
            owner, repo = await parse_repo_info(arguments["repo"])
            branch_name = arguments["branch_name"]
            from_branch = arguments.get("from_branch", "main")
            
            # Get the SHA of the source branch
            ref_data = await github_request("GET", f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}")
            sha = ref_data["object"]["sha"]
            
            # Create new branch
            data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
            await github_request("POST", f"/repos/{owner}/{repo}/git/refs", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Branch '{branch_name}' created from '{from_branch}'!"
            )]
        
        elif name == "delete_branch":
            owner, repo = await parse_repo_info(arguments["repo"])
            branch_name = arguments["branch_name"]
            
            await github_request("DELETE", f"/repos/{owner}/{repo}/git/refs/heads/{branch_name}")
            
            return [types.TextContent(
                type="text",
                text=f"✅ Branch '{branch_name}' deleted successfully!"
            )]
        
        # ========== ISSUE HANDLERS ==========
        elif name == "create_issue":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            data = {
                "title": arguments["title"],
                "body": arguments.get("body", ""),
                "labels": arguments.get("labels", []),
                "assignees": arguments.get("assignees", [])
            }
            
            result = await github_request("POST", f"/repos/{owner}/{repo}/issues", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Issue #{result['number']} created!\n\n"
                     f"**Title:** {result['title']}\n"
                     f"**URL:** {result['html_url']}\n"
                     f"**Labels:** {', '.join([l['name'] for l in result['labels']])}"
            )]
        
        elif name == "list_issues":
            owner, repo = await parse_repo_info(arguments["repo"])
            state = arguments.get("state", "open")
            labels = arguments.get("labels", "")
            limit = arguments.get("limit", 20)
            
            params = {"state": state}
            if labels:
                params["labels"] = labels
            
            results = await paginate_github_request(
                "GET", 
                f"/repos/{owner}/{repo}/issues", 
                max_items=limit,
                params=params
            )
            
            # Filter out pull requests (they appear in issues endpoint too)
            issues = [issue for issue in results if "pull_request" not in issue]
            
            if not issues:
                return [types.TextContent(type="text", text=f"No {state} issues found.")]
            
            issue_list = []
            for issue in issues:
                labels = ", ".join([l['name'] for l in issue['labels']])
                issue_list.append(
                    f"**#{issue['number']}** - {issue['title']}\n"
                    f"   By: @{issue['user']['login']} | State: {issue['state']}\n"
                    f"   Labels: {labels or 'None'}\n"
                    f"   Created: {format_datetime(issue['created_at'])}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"🐛 Issues in {owner}/{repo} ({state}):\n\n" + "\n\n".join(issue_list)
            )]
        
        elif name == "update_issue":
            owner, repo = await parse_repo_info(arguments["repo"])
            issue_number = arguments["issue_number"]
            
            data = {}
            if "title" in arguments:
                data["title"] = arguments["title"]
            if "body" in arguments:
                data["body"] = arguments["body"]
            if "state" in arguments:
                data["state"] = arguments["state"]
            if "labels" in arguments:
                data["labels"] = arguments["labels"]
            
            result = await github_request("PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Issue #{issue_number} updated!\n\n"
                     f"**Title:** {result['title']}\n"
                     f"**State:** {result['state']}\n"
                     f"**URL:** {result['html_url']}"
            )]
        
        # ========== RELEASE/TAG HANDLERS ==========
        elif name == "create_release":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            data = {
                "tag_name": arguments["tag_name"],
                "name": arguments["name"],
                "body": arguments.get("body", ""),
                "draft": arguments.get("draft", False),
                "prerelease": arguments.get("prerelease", False)
            }
            
            result = await github_request("POST", f"/repos/{owner}/{repo}/releases", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Release created!\n\n"
                     f"**Tag:** {result['tag_name']}\n"
                     f"**Name:** {result['name']}\n"
                     f"**URL:** {result['html_url']}\n"
                     f"**Draft:** {'Yes' if result['draft'] else 'No'}\n"
                     f"**Pre-release:** {'Yes' if result['prerelease'] else 'No'}"
            )]
        
        elif name == "list_releases":
            owner, repo = await parse_repo_info(arguments["repo"])
            limit = arguments.get("limit", 10)
            
            results = await paginate_github_request(
                "GET", 
                f"/repos/{owner}/{repo}/releases", 
                max_items=limit
            )
            
            if not results:
                return [types.TextContent(type="text", text="No releases found.")]
            
            release_list = []
            for release in results:
                release_list.append(
                    f"**{release['tag_name']}** - {release['name']}\n"
                    f"   Published: {format_datetime(release['published_at'])}\n"
                    f"   Pre-release: {'Yes' if release['prerelease'] else 'No'}\n"
                    f"   URL: {release['html_url']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"🏷️ Releases in {owner}/{repo}:\n\n" + "\n\n".join(release_list)
            )]
        
        # ========== GITHUB ACTIONS HANDLERS ==========
        elif name == "list_workflows":
            owner, repo = await parse_repo_info(arguments["repo"])
            result = await github_request("GET", f"/repos/{owner}/{repo}/actions/workflows")
            
            if not result["workflows"]:
                return [types.TextContent(type="text", text="No workflows found.")]
            
            workflow_list = []
            for workflow in result["workflows"]:
                workflow_list.append(
                    f"**{workflow['name']}**\n"
                    f"   ID: {workflow['id']}\n"
                    f"   File: {workflow['path']}\n"
                    f"   State: {workflow['state']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"⚙️ GitHub Actions Workflows:\n\n" + "\n\n".join(workflow_list)
            )]
        
        elif name == "trigger_workflow":
            owner, repo = await parse_repo_info(arguments["repo"])
            workflow_id = arguments["workflow_id"]
            ref = arguments.get("ref", "main")
            inputs = arguments.get("inputs", {})
            
            data = {"ref": ref}
            if inputs:
                data["inputs"] = inputs
            
            await github_request(
                "POST", 
                f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                json=data
            )
            
            return [types.TextContent(
                type="text",
                text=f"✅ Workflow '{workflow_id}' triggered on branch '{ref}'!"
            )]
        
        elif name == "list_workflow_runs":
            owner, repo = await parse_repo_info(arguments["repo"])
            workflow_id = arguments.get("workflow_id")
            limit = arguments.get("limit", 10)
            
            endpoint = f"/repos/{owner}/{repo}/actions/runs"
            params = {}
            if workflow_id:
                # Get workflow ID if filename provided
                if not workflow_id.isdigit():
                    workflows = await github_request("GET", f"/repos/{owner}/{repo}/actions/workflows")
                    for w in workflows["workflows"]:
                        if w["path"].endswith(workflow_id):
                            workflow_id = str(w["id"])
                            break
                params["workflow_id"] = workflow_id
            
            result = await github_request("GET", endpoint, params=params)
            runs = result["workflow_runs"][:limit]
            
            if not runs:
                return [types.TextContent(type="text", text="No workflow runs found.")]
            
            run_list = []
            for run in runs:
                run_list.append(
                    f"**{run['name']}** - {run['status']}\n"
                    f"   Conclusion: {run['conclusion'] or 'In progress'}\n"
                    f"   Branch: {run['head_branch']}\n"
                    f"   Started: {format_datetime(run['created_at'])}\n"
                    f"   URL: {run['html_url']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"🔄 Recent Workflow Runs:\n\n" + "\n\n".join(run_list)
            )]
        
        # ========== COMMIT HANDLERS ==========
        elif name == "list_commits":
            owner, repo = await parse_repo_info(arguments["repo"])
            branch = arguments.get("branch", "main")
            limit = arguments.get("limit", 20)
            
            params = {"sha": branch}
            results = await paginate_github_request(
                "GET",
                f"/repos/{owner}/{repo}/commits",
                max_items=limit,
                params=params
            )
            
            commit_list = []
            for commit in results:
                commit_list.append(
                    f"**{commit['sha'][:7]}** - {commit['commit']['message'].split('\n')[0]}\n"
                    f"   By: {commit['commit']['author']['name']}\n"
                    f"   Date: {format_datetime(commit['commit']['author']['date'])}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"📝 Recent Commits on '{branch}':\n\n" + "\n\n".join(commit_list)
            )]
        
        elif name == "get_commit":
            owner, repo = await parse_repo_info(arguments["repo"])
            sha = arguments["sha"]
            
            result = await github_request("GET", f"/repos/{owner}/{repo}/commits/{sha}")
            
            files_changed = len(result["files"])
            additions = sum(f["additions"] for f in result["files"])
            deletions = sum(f["deletions"] for f in result["files"])
            
            file_list = []
            for file in result["files"][:10]:  # Limit to 10 files
                file_list.append(f"• {file['filename']} (+{file['additions']}/-{file['deletions']})")
            
            return [types.TextContent(
                type="text",
                text=f"🔍 Commit Details:\n\n"
                     f"**SHA:** {result['sha']}\n"
                     f"**Message:** {result['commit']['message']}\n"
                     f"**Author:** {result['commit']['author']['name']}\n"
                     f"**Date:** {format_datetime(result['commit']['author']['date'])}\n"
                     f"**Stats:** {files_changed} files changed, +{additions}/-{deletions}\n\n"
                     f"**Files Changed:**\n" + "\n".join(file_list) +
                     (f"\n... and {files_changed - 10} more files" if files_changed > 10 else "")
            )]
        
        # ========== ANALYTICS HANDLERS ==========
        elif name == "get_repository_stats":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            # Get multiple stats in parallel
            repo_data = await github_request("GET", f"/repos/{owner}/{repo}")
            languages = await github_request("GET", f"/repos/{owner}/{repo}/languages")
            contributors = await github_request("GET", f"/repos/{owner}/{repo}/contributors?per_page=5")
            
            # Calculate language percentages
            total_bytes = sum(languages.values())
            lang_percentages = []
            for lang, bytes_count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (bytes_count / total_bytes) * 100
                lang_percentages.append(f"• {lang}: {percentage:.1f}%")
            
            # Top contributors
            top_contributors = []
            for contrib in contributors[:5]:
                top_contributors.append(f"• @{contrib['login']}: {contrib['contributions']} commits")
            
            return [types.TextContent(
                type="text",
                text=f"📊 Repository Statistics: {owner}/{repo}\n\n"
                     f"**General Stats:**\n"
                     f"• Stars: ⭐ {repo_data['stargazers_count']}\n"
                     f"• Forks: 🍴 {repo_data['forks_count']}\n"
                     f"• Watchers: 👀 {repo_data['watchers_count']}\n"
                     f"• Open Issues: 🐛 {repo_data['open_issues_count']}\n"
                     f"• Size: {repo_data['size']} KB\n\n"
                     f"**Languages:**\n" + "\n".join(lang_percentages) + "\n\n"
                     f"**Top Contributors:**\n" + "\n".join(top_contributors)
            )]
        
        elif name == "get_contributor_stats":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            contributors = await github_request("GET", f"/repos/{owner}/{repo}/stats/contributors")
            
            # Sort by total contributions
            contributors.sort(key=lambda x: x['total'], reverse=True)
            
            stats_list = []
            for contrib in contributors[:10]:  # Top 10 contributors
                author = contrib['author']['login']
                total = contrib['total']
                
                # Get recent activity (last 4 weeks)
                recent_additions = sum(week['a'] for week in contrib['weeks'][-4:])
                recent_deletions = sum(week['d'] for week in contrib['weeks'][-4:])
                recent_commits = sum(week['c'] for week in contrib['weeks'][-4:])
                
                stats_list.append(
                    f"**@{author}**\n"
                    f"   Total commits: {total}\n"
                    f"   Last 4 weeks: {recent_commits} commits (+{recent_additions}/-{recent_deletions})"
                )
            
            return [types.TextContent(
                type="text",
                text=f"👥 Contributor Statistics:\n\n" + "\n\n".join(stats_list)
            )]
        
        elif name == "get_commit_activity":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            # Get commit activity for the last year
            activity = await github_request("GET", f"/repos/{owner}/{repo}/stats/commit_activity")
            
            # Calculate summary
            total_commits = sum(week['total'] for week in activity)
            
            # Find most active week
            most_active_week = max(activity, key=lambda x: x['total'])
            most_active_date = datetime.fromtimestamp(most_active_week['week'])
            
            # Recent trend (last 4 weeks)
            recent_weeks = activity[-4:]
            recent_commits = sum(week['total'] for week in recent_weeks)
            
            # Day of week analysis
            day_totals = [0] * 7  # Sunday to Saturday
            for week in activity:
                for i, count in enumerate(week['days']):
                    day_totals[i] += count
            
            days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            day_stats = []
            for i, day in enumerate(days):
                day_stats.append(f"• {day}: {day_totals[i]} commits")
            
            return [types.TextContent(
                type="text",
                text=f"📈 Commit Activity (Last Year):\n\n"
                     f"**Summary:**\n"
                     f"• Total commits: {total_commits}\n"
                     f"• Average per week: {total_commits / len(activity):.1f}\n"
                     f"• Most active week: {most_active_date.strftime('%Y-%m-%d')} ({most_active_week['total']} commits)\n"
                     f"• Last 4 weeks: {recent_commits} commits\n\n"
                     f"**Commits by Day of Week:**\n" + "\n".join(day_stats)
            )]
        
        # ========== COLLABORATION HANDLERS ==========
        elif name == "add_collaborator":
            owner, repo = await parse_repo_info(arguments["repo"])
            username = arguments["username"]
            permission = arguments.get("permission", "push")
            
            data = {"permission": permission}
            await github_request("PUT", f"/repos/{owner}/{repo}/collaborators/{username}", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Added @{username} as collaborator with '{permission}' permission!"
            )]
        
        elif name == "list_collaborators":
            owner, repo = await parse_repo_info(arguments["repo"])
            
            results = await paginate_github_request("GET", f"/repos/{owner}/{repo}/collaborators")
            
            collab_list = []
            for collab in results:
                # Get permissions for each collaborator
                perm_data = await github_request("GET", f"/repos/{owner}/{repo}/collaborators/{collab['login']}/permission")
                permission = perm_data['permission']
                
                collab_list.append(f"• @{collab['login']} - {permission}")
            
            return [types.TextContent(
                type="text",
                text=f"👥 Collaborators in {owner}/{repo}:\n\n" + "\n".join(collab_list)
            )]
        
        # ========== FILE OPERATIONS HANDLERS ==========
        elif name == "get_file_content":
            owner, repo = await parse_repo_info(arguments["repo"])
            path = arguments["path"]
            branch = arguments.get("branch", "main")
            
            params = {"ref": branch}
            result = await github_request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params)
            
            if result.get("type") != "file":
                return [types.TextContent(type="text", text=f"Error: {path} is not a file")]
            
            # Decode content
            content = base64.b64decode(result["content"]).decode('utf-8')
            
            # Limit content size for display
            if len(content) > 5000:
                content = content[:5000] + "\n\n... (truncated)"
            
            return [types.TextContent(
                type="text",
                text=f"📄 File: {path}\n"
                     f"Branch: {branch}\n"
                     f"Size: {result['size']} bytes\n\n"
                     f"```\n{content}\n```"
            )]
        
        elif name == "create_or_update_file":
            owner, repo = await parse_repo_info(arguments["repo"])
            path = arguments["path"]
            content = arguments["content"]
            message = arguments["message"]
            branch = arguments.get("branch", "main")
            
            # Encode content
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('ascii')
            
            data = {
                "message": message,
                "content": encoded_content,
                "branch": branch
            }
            
            # Check if file exists (for update)
            try:
                existing = await github_request("GET", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}")
                data["sha"] = existing["sha"]
                action = "updated"
            except:
                action = "created"
            
            result = await github_request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=data)
            
            return [types.TextContent(
                type="text",
                text=f"✅ File {action}!\n\n"
                     f"**Path:** {path}\n"
                     f"**Branch:** {branch}\n"
                     f"**Commit:** {result['commit']['sha'][:7]}\n"
                     f"**Message:** {message}"
            )]
        
        # ========== SEARCH HANDLERS ==========
        elif name == "search_repositories":
            query = arguments["query"]
            limit = arguments.get("limit", 10)
            
            params = {"q": query, "sort": "stars", "order": "desc", "per_page": limit}
            result = await github_request("GET", "/search/repositories", params=params)
            
            if not result["items"]:
                return [types.TextContent(type="text", text=f"No repositories found for '{query}'")]
            
            repo_list = []
            for repo in result["items"]:
                repo_list.append(
                    f"**{repo['full_name']}**\n"
                    f"   {repo['description'] or 'No description'}\n"
                    f"   ⭐ {repo['stargazers_count']} | 🍴 {repo['forks_count']} | "
                    f"Language: {repo['language'] or 'N/A'}\n"
                    f"   URL: {repo['html_url']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"🔍 Search Results for '{query}':\n\n" + "\n\n".join(repo_list)
            )]
        
        elif name == "search_code":
            query = arguments["query"]
            repo_filter = arguments.get("repo")
            limit = arguments.get("limit", 10)
            
            # Add repo filter if specified
            if repo_filter:
                owner, repo = await parse_repo_info(repo_filter)
                query = f"{query} repo:{owner}/{repo}"
            
            params = {"q": query, "per_page": limit}
            result = await github_request("GET", "/search/code", params=params)
            
            if not result["items"]:
                return [types.TextContent(type="text", text=f"No code found for '{query}'")]
            
            code_list = []
            for item in result["items"]:
                code_list.append(
                    f"**{item['name']}** in {item['repository']['full_name']}\n"
                    f"   Path: {item['path']}\n"
                    f"   URL: {item['html_url']}"
                )
            
            return [types.TextContent(
                type="text",
                text=f"🔍 Code Search Results for '{query}':\n\n" + "\n\n".join(code_list)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error: {str(e)}"
        )]

# ===========================
# MAIN FUNCTION
# ===========================

async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="github-complete-server",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

# ===========================
# CLEANUP
# ===========================

async def cleanup():
    """Clean up resources"""
    await http_client.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(cleanup())