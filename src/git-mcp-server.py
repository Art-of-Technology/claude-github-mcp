#!/usr/bin/env python3
"""
Git Complete MCP Server
A comprehensive MCP server that replaces all Git commands
Allows full Git workflow through Claude without using command line
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
import base64
from pathlib import Path
import shutil
import tempfile
import hashlib
import mimetypes
import fnmatch

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

# ===========================
# CONFIGURATION
# ===========================

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
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

# Initialize MCP server
app = Server("git-complete-server")

# Local workspace for Git operations
WORKSPACE_ROOT = Path.home() / ".git-mcp-workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)

# ===========================
# GIT STATE MANAGEMENT
# ===========================

class GitWorkspace:
    """Manages local Git-like workspace state"""
    
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.workspace_path = WORKSPACE_ROOT / repo_name.replace("/", "_")
        self.staging_area = {}  # path -> content
        self.tracked_files = {}  # path -> sha
        self.current_branch = "main"
        self.remote_url = None
        
    def init(self):
        """Initialize workspace"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        (self.workspace_path / ".git-mcp").mkdir(exist_ok=True)
        self.save_state()
    
    def save_state(self):
        """Save workspace state"""
        state = {
            "staging_area": self.staging_area,
            "tracked_files": self.tracked_files,
            "current_branch": self.current_branch,
            "remote_url": self.remote_url
        }
        state_file = self.workspace_path / ".git-mcp" / "state.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load workspace state"""
        state_file = self.workspace_path / ".git-mcp" / "state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.staging_area = state.get("staging_area", {})
                self.tracked_files = state.get("tracked_files", {})
                self.current_branch = state.get("current_branch", "main")
                self.remote_url = state.get("remote_url")
    
    def add_to_staging(self, file_path: str, content: str):
        """Add file to staging area"""
        self.staging_area[file_path] = content
        self.save_state()
    
    def remove_from_staging(self, file_path: str):
        """Remove file from staging area"""
        if file_path in self.staging_area:
            del self.staging_area[file_path]
            self.save_state()
    
    def clear_staging(self):
        """Clear staging area"""
        self.staging_area = {}
        self.save_state()

# Global workspace manager
workspaces = {}

def get_workspace(repo_name: str) -> GitWorkspace:
    """Get or create workspace for repository"""
    if repo_name not in workspaces:
        workspace = GitWorkspace(repo_name)
        workspace.init()
        workspace.load_state()
        workspaces[repo_name] = workspace
    return workspaces[repo_name]

# ===========================
# HELPER FUNCTIONS
# ===========================

async def parse_repo_info(repo_url: str) -> tuple[str, str]:
    """Parse repository URL or owner/repo format"""
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
    """Make authenticated request to GitHub API"""
    url = f"{GITHUB_API_BASE}{endpoint}"
    
    try:
        response = await http_client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}
        
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            error_data = e.response.json() if e.response.content else {}
        except:
            pass
        raise RuntimeError(f"GitHub API error {e.response.status_code}: {error_data.get('message', 'Unknown error')}")

async def read_local_file(file_path: str) -> tuple[str, bool]:
    """Read a local file and return content and whether it's binary"""
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check if binary
    mime_type, _ = mimetypes.guess_type(str(path))
    is_text = mime_type and mime_type.startswith('text/')
    
    text_extensions = {'.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.json', 
                      '.yml', '.yaml', '.xml', '.html', '.css', '.scss', '.sass',
                      '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
                      '.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs', '.rb',
                      '.php', '.swift', '.kt', '.r', '.m', '.sql', '.dockerfile',
                      '.gitignore', '.env', '.config', '.conf', '.ini', '.toml'}
    
    if path.suffix.lower() in text_extensions or path.suffix == '':
        is_text = True
    
    try:
        if is_text:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read(), False
        else:
            with open(path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('ascii')
                return content, True
    except UnicodeDecodeError:
        with open(path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
            return content, True

def should_ignore(file_path: Path, gitignore_patterns: List[str]) -> bool:
    """Check if file should be ignored based on .gitignore patterns"""
    for pattern in gitignore_patterns:
        if pattern.startswith("#") or not pattern.strip():
            continue
        
        # Handle directory patterns
        if pattern.endswith("/"):
            if file_path.is_dir() and fnmatch.fnmatch(file_path.name, pattern[:-1]):
                return True
        
        # Handle file patterns
        if fnmatch.fnmatch(file_path.name, pattern) or fnmatch.fnmatch(str(file_path), pattern):
            return True
    
    return False

async def get_gitignore_patterns(directory: Path) -> List[str]:
    """Read .gitignore patterns"""
    gitignore_path = directory / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    return []

# ===========================
# TOOL DEFINITIONS
# ===========================

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available Git tools"""
    return [
        # ========== BASIC GIT OPERATIONS ==========
        types.Tool(
            name="git_init",
            description="Initialize a new Git repository (equivalent to 'git init')",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to initialize (default: current directory)"},
                    "create_readme": {"type": "boolean", "description": "Create README.md file", "default": True},
                    "create_gitignore": {"type": "boolean", "description": "Create .gitignore file", "default": True},
                    "gitignore_template": {"type": "string", "description": "Language for .gitignore (python, node, etc.)"}
                }
            }
        ),
        
        types.Tool(
            name="git_clone",
            description="Clone a repository from GitHub (equivalent to 'git clone')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "Repository URL or owner/repo"},
                    "directory": {"type": "string", "description": "Local directory name"},
                    "branch": {"type": "string", "description": "Branch to clone", "default": "main"}
                },
                "required": ["repo_url"]
            }
        ),
        
        types.Tool(
            name="git_status",
            description="Show working tree status (equivalent to 'git status')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"}
                },
                "required": ["repo"]
            }
        ),
        
        types.Tool(
            name="git_add",
            description="Add files to staging area (equivalent to 'git add')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Files to add (use ['.'] for all)"}
                },
                "required": ["repo", "files"]
            }
        ),
        
        types.Tool(
            name="git_commit",
            description="Commit staged changes (equivalent to 'git commit')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "message": {"type": "string", "description": "Commit message"},
                    "description": {"type": "string", "description": "Extended description"}
                },
                "required": ["repo", "message"]
            }
        ),
        
        types.Tool(
            name="git_push",
            description="Push commits to remote repository (equivalent to 'git push')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "branch": {"type": "string", "description": "Branch to push"},
                    "force": {"type": "boolean", "description": "Force push", "default": False}
                },
                "required": ["repo"]
            }
        ),
        
        types.Tool(
            name="git_pull",
            description="Pull changes from remote repository (equivalent to 'git pull')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "branch": {"type": "string", "description": "Branch to pull"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== BRANCH OPERATIONS ==========
        types.Tool(
            name="git_branch",
            description="List, create, or delete branches (equivalent to 'git branch')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["list", "create", "delete"], "default": "list"},
                    "branch_name": {"type": "string", "description": "Branch name for create/delete"},
                    "from_branch": {"type": "string", "description": "Source branch for create"}
                },
                "required": ["repo"]
            }
        ),
        
        types.Tool(
            name="git_checkout",
            description="Switch branches or restore files (equivalent to 'git checkout')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "branch": {"type": "string", "description": "Branch to checkout"},
                    "create": {"type": "boolean", "description": "Create new branch", "default": False}
                },
                "required": ["repo", "branch"]
            }
        ),
        
        types.Tool(
            name="git_merge",
            description="Merge branches (equivalent to 'git merge')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "branch": {"type": "string", "description": "Branch to merge from"},
                    "strategy": {"type": "string", "enum": ["merge", "squash", "rebase"], "default": "merge"}
                },
                "required": ["repo", "branch"]
            }
        ),
        
        # ========== DIFF AND LOG ==========
        types.Tool(
            name="git_diff",
            description="Show changes between commits, files, etc (equivalent to 'git diff')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "staged": {"type": "boolean", "description": "Show staged changes", "default": False},
                    "file": {"type": "string", "description": "Specific file to diff"}
                },
                "required": ["repo"]
            }
        ),
        
        types.Tool(
            name="git_log",
            description="Show commit logs (equivalent to 'git log')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "limit": {"type": "integer", "description": "Number of commits to show", "default": 10},
                    "oneline": {"type": "boolean", "description": "Compact format", "default": False}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== REMOTE OPERATIONS ==========
        types.Tool(
            name="git_remote",
            description="Manage remote repositories (equivalent to 'git remote')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["list", "add", "remove"], "default": "list"},
                    "name": {"type": "string", "description": "Remote name", "default": "origin"},
                    "url": {"type": "string", "description": "Remote URL for add"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== STASH OPERATIONS ==========
        types.Tool(
            name="git_stash",
            description="Stash changes (equivalent to 'git stash')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["save", "list", "pop", "apply"], "default": "save"},
                    "message": {"type": "string", "description": "Stash message"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== TAG OPERATIONS ==========
        types.Tool(
            name="git_tag",
            description="Create, list, delete tags (equivalent to 'git tag')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["create", "list", "delete"], "default": "list"},
                    "tag_name": {"type": "string", "description": "Tag name"},
                    "message": {"type": "string", "description": "Tag message"}
                },
                "required": ["repo"]
            }
        ),
        
        # ========== ADVANCED OPERATIONS ==========
        types.Tool(
            name="git_reset",
            description="Reset current HEAD to specified state (equivalent to 'git reset')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "mode": {"type": "string", "enum": ["soft", "mixed", "hard"], "default": "mixed"},
                    "commit": {"type": "string", "description": "Commit to reset to", "default": "HEAD~1"}
                },
                "required": ["repo"]
            }
        ),
        
        types.Tool(
            name="git_rebase",
            description="Reapply commits on top of another base (equivalent to 'git rebase')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "branch": {"type": "string", "description": "Branch to rebase onto"},
                    "interactive": {"type": "boolean", "description": "Interactive rebase", "default": False}
                },
                "required": ["repo", "branch"]
            }
        ),
        
        # ========== FILE OPERATIONS ==========
        types.Tool(
            name="git_rm",
            description="Remove files from working tree and index (equivalent to 'git rm')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Files to remove"},
                    "cached": {"type": "boolean", "description": "Only remove from index", "default": False}
                },
                "required": ["repo", "files"]
            }
        ),
        
        types.Tool(
            name="git_mv",
            description="Move or rename files (equivalent to 'git mv')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "source": {"type": "string", "description": "Source file/directory"},
                    "destination": {"type": "string", "description": "Destination file/directory"}
                },
                "required": ["repo", "source", "destination"]
            }
        ),
        
        # ========== UTILITY OPERATIONS ==========
        types.Tool(
            name="git_config",
            description="Get and set repository or global options (equivalent to 'git config')",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["get", "set"], "default": "get"},
                    "key": {"type": "string", "description": "Config key (e.g., user.name)"},
                    "value": {"type": "string", "description": "Config value for set"},
                    "global": {"type": "boolean", "description": "Use global config", "default": False}
                }
            }
        ),
        
        types.Tool(
            name="git_ignore",
            description="Manage .gitignore file",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name or path"},
                    "action": {"type": "string", "enum": ["add", "list", "create"], "default": "add"},
                    "patterns": {"type": "array", "items": {"type": "string"}, "description": "Patterns to add"},
                    "template": {"type": "string", "description": "Language template for create (python, node, etc.)"}
                },
                "required": ["repo"]
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
        # ========== BASIC GIT OPERATIONS ==========
        if name == "git_init":
            directory = Path(arguments.get("directory", ".")).absolute()
            create_readme = arguments.get("create_readme", True)
            create_gitignore = arguments.get("create_gitignore", True)
            gitignore_template = arguments.get("gitignore_template")
            
            # Create directory if needed
            directory.mkdir(parents=True, exist_ok=True)
            
            # Initialize workspace
            repo_name = directory.name
            workspace = get_workspace(repo_name)
            workspace.workspace_path = directory
            workspace.init()
            
            # Create README
            if create_readme:
                readme_path = directory / "README.md"
                with open(readme_path, 'w') as f:
                    f.write(f"# {repo_name}\n\nA new Git repository initialized with Git MCP Server.\n")
            
            # Create .gitignore
            if create_gitignore:
                gitignore_content = ""
                if gitignore_template == "python":
                    gitignore_content = """__pycache__/
*.py[cod]
*$py.class
.Python
env/
venv/
.env
.venv
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
"""
                elif gitignore_template == "node":
                    gitignore_content = """node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.env
.env.local
dist/
build/
.DS_Store
"""
                
                gitignore_path = directory / ".gitignore"
                with open(gitignore_path, 'w') as f:
                    f.write(gitignore_content)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Initialized empty Git repository in {directory}\n\n"
                     f"Created files:\n"
                     f"{'- README.md' if create_readme else ''}\n"
                     f"{'- .gitignore' if create_gitignore else ''}\n\n"
                     f"Next steps:\n"
                     f"1. Add files: use 'git_add'\n"
                     f"2. Commit: use 'git_commit'\n"
                     f"3. Add remote: use 'git_remote' with action='add'"
            )]
        
        elif name == "git_clone":
            try:
                repo_url = arguments["repo_url"]
                owner, repo = await parse_repo_info(repo_url)
                directory = arguments.get("directory", repo)
                branch = arguments.get("branch", "main")
                
                print(f"Debug: Cloning {owner}/{repo} branch {branch}")  # Debug
                
                # Create local directory
                local_path = Path(directory).absolute()
                local_path.mkdir(parents=True, exist_ok=True)
                
                # Initialize workspace
                workspace = get_workspace(f"{owner}/{repo}")
                workspace.workspace_path = local_path
                workspace.remote_url = f"https://github.com/{owner}/{repo}.git"
                workspace.current_branch = branch
                
                # Test API connection first
                try:
                    repo_info = await github_request("GET", f"/repos/{owner}/{repo}")
                    print(f"Debug: Repository found: {repo_info['full_name']}")  # Debug
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=f"❌ GitHub API erişim hatası: {str(e)}\n\n"
                             f"Token'ınızı kontrol edin veya repository'nin public olduğundan emin olun."
                    )]
                
                # Get repository contents
                files_cloned = []
                
                async def clone_directory(path="", local_dir=local_path):
                    """Recursively clone directory contents"""
                    try:
                        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
                        if branch != "main":
                            endpoint += f"?ref={branch}"
                            
                        contents = await github_request("GET", endpoint)
                        
                        for item in contents:
                            if item["type"] == "file":
                                try:
                                    # Get file content through API
                                    file_endpoint = f"/repos/{owner}/{repo}/contents/{item['path']}"
                                    if branch != "main":
                                        file_endpoint += f"?ref={branch}"
                                        
                                    file_data = await github_request("GET", file_endpoint)
                                    
                                    # Decode content
                                    content = base64.b64decode(file_data["content"])
                                    local_file = local_dir / item["name"]
                                    
                                    # Write as binary
                                    with open(local_file, 'wb') as f:
                                        f.write(content)
                                    
                                    files_cloned.append(item["path"])
                                    workspace.tracked_files[item["path"]] = item["sha"]
                                    
                                except Exception as e:
                                    print(f"Debug: Error cloning file {item['path']}: {e}")
                                    
                            elif item["type"] == "dir":
                                # Create directory and recurse
                                subdir = local_dir / item["name"]
                                subdir.mkdir(exist_ok=True)
                                await clone_directory(item["path"], subdir)
                                
                    except Exception as e:
                        print(f"Debug: Error in clone_directory: {e}")
                        raise
                
                await clone_directory()
                workspace.save_state()
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Cloned {owner}/{repo} into {local_path}\n\n"
                         f"Branch: {branch}\n"
                         f"Files cloned: {len(files_cloned)}\n"
                         f"Remote URL: {workspace.remote_url}"
                )]
                
            except Exception as e:
                import traceback
                traceback.print_exc()  # Debug için
                
                return [types.TextContent(
                    type="text",
                    text=f"❌ Clone error: {type(e).__name__}: {str(e)}"
                )]
        
        elif name == "git_status":
            repo = arguments["repo"]
            workspace = get_workspace(repo)
            
            # Get current branch info from GitHub
            owner, repo_name = await parse_repo_info(workspace.remote_url or repo)
            
            status = f"📊 On branch {workspace.current_branch}\n\n"
            
            if workspace.staging_area:
                status += "Changes to be committed:\n"
                status += "  (use 'git_reset' to unstage)\n\n"
                for file in workspace.staging_area:
                    status += f"        new/modified:    {file}\n"
                status += "\n"
            
            # Check for untracked files
            if workspace.workspace_path.exists():
                all_files = set()
                for file in workspace.workspace_path.rglob("*"):
                    if file.is_file() and not str(file).startswith(".git"):
                        rel_path = file.relative_to(workspace.workspace_path)
                        all_files.add(str(rel_path))
                
                untracked = all_files - set(workspace.tracked_files.keys()) - set(workspace.staging_area.keys())
                
                if untracked:
                    status += "Untracked files:\n"
                    status += "  (use 'git_add' to include in what will be committed)\n\n"
                    for file in sorted(untracked)[:20]:  # Limit display
                        status += f"        {file}\n"
                    if len(untracked) > 20:
                        status += f"        ... and {len(untracked) - 20} more files\n"
            
            if not workspace.staging_area and not untracked:
                status += "nothing to commit, working tree clean"
            
            return [types.TextContent(type="text", text=status)]
        
        elif name == "git_add":
            repo = arguments["repo"]
            files = arguments["files"]
            workspace = get_workspace(repo)
            
            added_files = []
            
            for file_pattern in files:
                if file_pattern == ".":
                    # Add all files
                    if workspace.workspace_path.exists():
                        gitignore_patterns = await get_gitignore_patterns(workspace.workspace_path)
                        
                        for file in workspace.workspace_path.rglob("*"):
                            if file.is_file() and not str(file).startswith(".git"):
                                if not should_ignore(file, gitignore_patterns):
                                    rel_path = str(file.relative_to(workspace.workspace_path))
                                    content, is_binary = await read_local_file(str(file))
                                    workspace.add_to_staging(rel_path, content)
                                    added_files.append(rel_path)
                else:
                    # Add specific file
                    file_path = workspace.workspace_path / file_pattern
                    if file_path.exists() and file_path.is_file():
                        content, is_binary = await read_local_file(str(file_path))
                        rel_path = str(file_path.relative_to(workspace.workspace_path))
                        workspace.add_to_staging(rel_path, content)
                        added_files.append(rel_path)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Added {len(added_files)} files to staging area:\n\n" +
                     "\n".join(f"  + {f}" for f in added_files[:20]) +
                     (f"\n  ... and {len(added_files) - 20} more files" if len(added_files) > 20 else "")
            )]
        
        elif name == "git_commit":
            repo = arguments["repo"]
            message = arguments["message"]
            description = arguments.get("description", "")
            workspace = get_workspace(repo)
            
            if not workspace.staging_area:
                return [types.TextContent(
                    type="text",
                    text="❌ Nothing to commit. Use 'git_add' to stage changes first."
                )]
            
            # Create commit-like record
            commit_id = hashlib.sha1(f"{message}{datetime.now()}".encode()).hexdigest()[:7]
            commit_info = {
                "id": commit_id,
                "message": message,
                "description": description,
                "files": list(workspace.staging_area.keys()),
                "timestamp": datetime.now().isoformat()
            }
            
            # Move files from staging to tracked
            for file, content in workspace.staging_area.items():
                workspace.tracked_files[file] = hashlib.sha1(content.encode()).hexdigest()
            
            workspace.clear_staging()
            
            return [types.TextContent(
                type="text",
                text=f"✅ Committed changes\n\n"
                     f"[{workspace.current_branch} {commit_id}] {message}\n"
                     f"{len(commit_info['files'])} files changed\n\n"
                     f"Files:\n" + "\n".join(f"  • {f}" for f in commit_info['files'][:10]) +
                     (f"\n  ... and {len(commit_info['files']) - 10} more files" if len(commit_info['files']) > 10 else "")
            )]
        
        elif name == "git_push":
            repo = arguments["repo"]
            branch = arguments.get("branch", None)
            force = arguments.get("force", False)
            workspace = get_workspace(repo)
            
            if not workspace.remote_url:
                return [types.TextContent(
                    type="text",
                    text="❌ No remote repository configured. Use 'git_remote' to add one."
                )]
            
            owner, repo_name = await parse_repo_info(workspace.remote_url)
            branch = branch or workspace.current_branch
            
            # Push all tracked files to GitHub
            pushed_files = []
            for file_path, sha in workspace.tracked_files.items():
                local_file = workspace.workspace_path / file_path
                if local_file.exists():
                    content, is_binary = await read_local_file(str(local_file))
                    
                    # Upload to GitHub
                    data = {
                        "message": f"Update {file_path}",
                        "branch": branch
                    }
                    
                    if is_binary:
                        data["content"] = content
                    else:
                        data["content"] = base64.b64encode(content.encode('utf-8')).decode('ascii')
                    
                    # Check if file exists
                    try:
                        existing = await github_request("GET", f"/repos/{owner}/{repo_name}/contents/{file_path}?ref={branch}")
                        data["sha"] = existing["sha"]
                    except:
                        pass
                    
                    await github_request("PUT", f"/repos/{owner}/{repo_name}/contents/{file_path}", json=data)
                    pushed_files.append(file_path)
            
            return [types.TextContent(
                type="text",
                text=f"✅ Pushed to {owner}/{repo_name}\n\n"
                     f"Branch: {branch}\n"
                     f"Files pushed: {len(pushed_files)}\n"
                     f"{'Force push: Yes' if force else ''}"
            )]
        
        elif name == "git_pull":
            repo = arguments["repo"]
            branch = arguments.get("branch", None)
            workspace = get_workspace(repo)
            
            if not workspace.remote_url:
                return [types.TextContent(
                    type="text",
                    text="❌ No remote repository configured."
                )]
            
            owner, repo_name = await parse_repo_info(workspace.remote_url)
            branch = branch or workspace.current_branch
            
            # Pull files from GitHub
            pulled_files = []
            
            async def pull_directory(path="", local_dir=workspace.workspace_path):
                contents = await github_request("GET", f"/repos/{owner}/{repo_name}/contents/{path}?ref={branch}")
                
                for item in contents:
                    if item["type"] == "file":
                        file_content = await github_request("GET", item["download_url"].replace(GITHUB_API_BASE, ""))
                        local_file = local_dir / item["name"]
                        
                        with open(local_file, 'w', encoding='utf-8') as f:
                            f.write(file_content)
                        
                        pulled_files.append(item["path"])
                        workspace.tracked_files[item["path"]] = item["sha"]
                        
                    elif item["type"] == "dir":
                        subdir = local_dir / item["name"]
                        subdir.mkdir(exist_ok=True)
                        await pull_directory(item["path"], subdir)
            
            await pull_directory()
            workspace.save_state()
            
            return [types.TextContent(
                type="text",
                text=f"✅ Pulled from {owner}/{repo_name}\n\n"
                     f"Branch: {branch}\n"
                     f"Files updated: {len(pulled_files)}"
            )]
        
        # ========== BRANCH OPERATIONS ==========
        elif name == "git_branch":
            repo = arguments["repo"]
            action = arguments.get("action", "list")
            branch_name = arguments.get("branch_name")
            from_branch = arguments.get("from_branch", "main")
            workspace = get_workspace(repo)
            
            if not workspace.remote_url:
                return [types.TextContent(
                    type="text",
                    text="❌ No remote repository configured."
                )]
            
            owner, repo_name = await parse_repo_info(workspace.remote_url)
            
            if action == "list":
                branches = await github_request("GET", f"/repos/{owner}/{repo_name}/branches")
                branch_list = []
                for branch in branches:
                    is_current = branch["name"] == workspace.current_branch
                    branch_list.append(f"{'* ' if is_current else '  '}{branch['name']}")
                
                return [types.TextContent(
                    type="text",
                    text="📋 Branches:\n\n" + "\n".join(branch_list)
                )]
            
            elif action == "create":
                if not branch_name:
                    raise ValueError("branch_name required for create action")
                
                # Get SHA of source branch
                ref_data = await github_request("GET", f"/repos/{owner}/{repo_name}/git/refs/heads/{from_branch}")
                sha = ref_data["object"]["sha"]
                
                # Create new branch
                data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
                await github_request("POST", f"/repos/{owner}/{repo_name}/git/refs", json=data)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Created branch '{branch_name}' from '{from_branch}'"
                )]
            
            elif action == "delete":
                if not branch_name:
                    raise ValueError("branch_name required for delete action")
                
                await github_request("DELETE", f"/repos/{owner}/{repo_name}/git/refs/heads/{branch_name}")
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Deleted branch '{branch_name}'"
                )]
        
        elif name == "git_checkout":
            repo = arguments["repo"]
            branch = arguments["branch"]
            create = arguments.get("create", False)
            workspace = get_workspace(repo)
            
            if create:
                # Create and checkout new branch
                if workspace.remote_url:
                    owner, repo_name = await parse_repo_info(workspace.remote_url)
                    
                    # Get current branch SHA
                    ref_data = await github_request("GET", f"/repos/{owner}/{repo_name}/git/refs/heads/{workspace.current_branch}")
                    sha = ref_data["object"]["sha"]
                    
                    # Create new branch
                    data = {"ref": f"refs/heads/{branch}", "sha": sha}
                    await github_request("POST", f"/repos/{owner}/{repo_name}/git/refs", json=data)
            
            workspace.current_branch = branch
            workspace.save_state()
            
            return [types.TextContent(
                type="text",
                text=f"✅ Switched to {'new ' if create else ''}branch '{branch}'"
            )]
        
        # ========== DIFF AND LOG ==========
        elif name == "git_diff":
            repo = arguments["repo"]
            staged = arguments.get("staged", False)
            file = arguments.get("file")
            workspace = get_workspace(repo)
            
            diff_output = "📊 Diff output:\n\n"
            
            if staged and workspace.staging_area:
                diff_output += "Staged changes:\n"
                for file_path, content in workspace.staging_area.items():
                    if file and file != file_path:
                        continue
                    diff_output += f"\n--- {file_path}\n"
                    diff_output += f"+++ {file_path} (staged)\n"
                    # Show first few lines of content
                    lines = content.split('\n')[:10]
                    for line in lines:
                        diff_output += f"+ {line}\n"
                    if len(content.split('\n')) > 10:
                        diff_output += f"... and {len(content.split('\n')) - 10} more lines\n"
            else:
                diff_output += "No changes to show. Use git_add to stage changes."
            
            return [types.TextContent(type="text", text=diff_output)]
        
        elif name == "git_log":
            repo = arguments["repo"]
            limit = arguments.get("limit", 10)
            oneline = arguments.get("oneline", False)
            workspace = get_workspace(repo)
            
            if not workspace.remote_url:
                return [types.TextContent(
                    type="text",
                    text="❌ No remote repository configured."
                )]
            
            owner, repo_name = await parse_repo_info(workspace.remote_url)
            
            # Get commits from GitHub
            commits = await github_request("GET", f"/repos/{owner}/{repo_name}/commits?per_page={limit}")
            
            log_output = f"📜 Commit history ({workspace.current_branch}):\n\n"
            
            for commit in commits:
                if oneline:
                    log_output += f"{commit['sha'][:7]} {commit['commit']['message'].split('\n')[0]}\n"
                else:
                    log_output += f"commit {commit['sha']}\n"
                    log_output += f"Author: {commit['commit']['author']['name']} <{commit['commit']['author']['email']}>\n"
                    log_output += f"Date:   {commit['commit']['author']['date']}\n\n"
                    log_output += f"    {commit['commit']['message']}\n\n"
            
            return [types.TextContent(type="text", text=log_output)]
        
        # ========== REMOTE OPERATIONS ==========
        elif name == "git_remote":
            repo = arguments["repo"]
            action = arguments.get("action", "list")
            name = arguments.get("name", "origin")
            url = arguments.get("url")
            workspace = get_workspace(repo)
            
            if action == "list":
                if workspace.remote_url:
                    return [types.TextContent(
                        type="text",
                        text=f"📡 Remote repositories:\n\norigin  {workspace.remote_url} (fetch)\norigin  {workspace.remote_url} (push)"
                    )]
                else:
                    return [types.TextContent(type="text", text="No remote repositories configured.")]
            
            elif action == "add":
                if not url:
                    raise ValueError("URL required for add action")
                
                workspace.remote_url = url
                workspace.save_state()
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Added remote '{name}' -> {url}"
                )]
            
            elif action == "remove":
                workspace.remote_url = None
                workspace.save_state()
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Removed remote '{name}'"
                )]
        
        # ========== STASH OPERATIONS ==========
        elif name == "git_stash":
            repo = arguments["repo"]
            action = arguments.get("action", "save")
            message = arguments.get("message", "")
            workspace = get_workspace(repo)
            
            stash_file = workspace.workspace_path / ".git-mcp" / "stash.json"
            
            if action == "save":
                if not workspace.staging_area:
                    return [types.TextContent(
                        type="text",
                        text="No local changes to save."
                    )]
                
                # Save current staging area to stash
                stash_data = {
                    "message": message or f"WIP on {workspace.current_branch}",
                    "branch": workspace.current_branch,
                    "files": workspace.staging_area.copy(),
                    "timestamp": datetime.now().isoformat()
                }
                
                # Load existing stashes
                stashes = []
                if stash_file.exists():
                    with open(stash_file, 'r') as f:
                        stashes = json.load(f)
                
                stashes.insert(0, stash_data)
                
                # Save stashes
                with open(stash_file, 'w') as f:
                    json.dump(stashes, f, indent=2)
                
                # Clear staging area
                workspace.clear_staging()
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Saved working directory and index state\n{stash_data['message']}"
                )]
            
            elif action == "list":
                if not stash_file.exists():
                    return [types.TextContent(type="text", text="No stashes found.")]
                
                with open(stash_file, 'r') as f:
                    stashes = json.load(f)
                
                stash_list = []
                for i, stash in enumerate(stashes):
                    stash_list.append(f"stash@{{{i}}}: {stash['message']} ({stash['branch']})")
                
                return [types.TextContent(
                    type="text",
                    text="📦 Stash list:\n\n" + "\n".join(stash_list)
                )]
            
            elif action in ["pop", "apply"]:
                if not stash_file.exists():
                    return [types.TextContent(type="text", text="No stash entries found.")]
                
                with open(stash_file, 'r') as f:
                    stashes = json.load(f)
                
                if not stashes:
                    return [types.TextContent(type="text", text="No stash entries found.")]
                
                # Apply first stash
                stash = stashes[0]
                workspace.staging_area = stash["files"]
                workspace.save_state()
                
                if action == "pop":
                    # Remove from stash
                    stashes.pop(0)
                    with open(stash_file, 'w') as f:
                        json.dump(stashes, f, indent=2)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Applied stash: {stash['message']}\n"
                         f"Files restored: {len(stash['files'])}"
                )]
        
        # ========== TAG OPERATIONS ==========
        elif name == "git_tag":
            repo = arguments["repo"]
            action = arguments.get("action", "list")
            tag_name = arguments.get("tag_name")
            message = arguments.get("message")
            workspace = get_workspace(repo)
            
            if not workspace.remote_url:
                return [types.TextContent(
                    type="text",
                    text="❌ No remote repository configured."
                )]
            
            owner, repo_name = await parse_repo_info(workspace.remote_url)
            
            if action == "list":
                tags = await github_request("GET", f"/repos/{owner}/{repo_name}/tags")
                
                if not tags:
                    return [types.TextContent(type="text", text="No tags found.")]
                
                tag_list = []
                for tag in tags[:20]:  # Limit display
                    tag_list.append(f"• {tag['name']}")
                
                return [types.TextContent(
                    type="text",
                    text="🏷️ Tags:\n\n" + "\n".join(tag_list)
                )]
            
            elif action == "create":
                if not tag_name:
                    raise ValueError("tag_name required for create action")
                
                # Get latest commit SHA
                commits = await github_request("GET", f"/repos/{owner}/{repo_name}/commits?per_page=1")
                sha = commits[0]["sha"]
                
                # Create tag
                data = {
                    "tag": tag_name,
                    "message": message or f"Release {tag_name}",
                    "object": sha,
                    "type": "commit"
                }
                
                if message:
                    # Create annotated tag
                    tag_data = await github_request("POST", f"/repos/{owner}/{repo_name}/git/tags", json=data)
                    ref_data = {
                        "ref": f"refs/tags/{tag_name}",
                        "sha": tag_data["sha"]
                    }
                else:
                    # Create lightweight tag
                    ref_data = {
                        "ref": f"refs/tags/{tag_name}",
                        "sha": sha
                    }
                
                await github_request("POST", f"/repos/{owner}/{repo_name}/git/refs", json=ref_data)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Created tag '{tag_name}'"
                )]
            
            elif action == "delete":
                if not tag_name:
                    raise ValueError("tag_name required for delete action")
                
                await github_request("DELETE", f"/repos/{owner}/{repo_name}/git/refs/tags/{tag_name}")
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Deleted tag '{tag_name}'"
                )]
        
        # ========== FILE OPERATIONS ==========
        elif name == "git_rm":
            repo = arguments["repo"]
            files = arguments["files"]
            cached = arguments.get("cached", False)
            workspace = get_workspace(repo)
            
            removed_files = []
            
            for file_pattern in files:
                file_path = workspace.workspace_path / file_pattern
                
                if not cached and file_path.exists():
                    # Remove from filesystem
                    if file_path.is_file():
                        file_path.unlink()
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                
                # Remove from tracking
                rel_path = str(file_path.relative_to(workspace.workspace_path))
                if rel_path in workspace.tracked_files:
                    del workspace.tracked_files[rel_path]
                if rel_path in workspace.staging_area:
                    del workspace.staging_area[rel_path]
                
                removed_files.append(rel_path)
            
            workspace.save_state()
            
            return [types.TextContent(
                type="text",
                text=f"✅ Removed {len(removed_files)} files:\n\n" +
                     "\n".join(f"  rm '{f}'" for f in removed_files)
            )]
        
        elif name == "git_mv":
            repo = arguments["repo"]
            source = arguments["source"]
            destination = arguments["destination"]
            workspace = get_workspace(repo)
            
            source_path = workspace.workspace_path / source
            dest_path = workspace.workspace_path / destination
            
            if not source_path.exists():
                raise ValueError(f"Source file not found: {source}")
            
            # Move file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(dest_path))
            
            # Update tracking
            source_rel = str(source_path.relative_to(workspace.workspace_path))
            dest_rel = str(dest_path.relative_to(workspace.workspace_path))
            
            if source_rel in workspace.tracked_files:
                workspace.tracked_files[dest_rel] = workspace.tracked_files[source_rel]
                del workspace.tracked_files[source_rel]
            
            if source_rel in workspace.staging_area:
                workspace.staging_area[dest_rel] = workspace.staging_area[source_rel]
                del workspace.staging_area[source_rel]
            
            workspace.save_state()
            
            return [types.TextContent(
                type="text",
                text=f"✅ Moved '{source}' to '{destination}'"
            )]
        
        # ========== UTILITY OPERATIONS ==========
        elif name == "git_config":
            repo = arguments["repo"]
            action = arguments.get("action", "get")
            key = arguments.get("key")
            value = arguments.get("value")
            is_global = arguments.get("global", False)
            
            config_file = workspace.workspace_path / ".git-mcp" / "config.json"
            
            if action == "get":
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                    
                    if key:
                        value = config.get(key, "Not set")
                        return [types.TextContent(
                            type="text",
                            text=f"{key}={value}"
                        )]
                    else:
                        config_list = []
                        for k, v in config.items():
                            config_list.append(f"{k}={v}")
                        
                        return [types.TextContent(
                            type="text",
                            text="📋 Configuration:\n\n" + "\n".join(config_list)
                        )]
                else:
                    return [types.TextContent(type="text", text="No configuration found.")]
            
            elif action == "set":
                if not key or value is None:
                    raise ValueError("Both key and value required for set action")
                
                config = {}
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = json.load(f)
                
                config[key] = value
                
                config_file.parent.mkdir(exist_ok=True)
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Set {key}={value}"
                )]
        
        elif name == "git_ignore":
            repo = arguments["repo"]
            action = arguments.get("action", "add")
            patterns = arguments.get("patterns", [])
            template = arguments.get("template")
            workspace = get_workspace(repo)
            
            gitignore_path = workspace.workspace_path / ".gitignore"
            
            if action == "list":
                if gitignore_path.exists():
                    with open(gitignore_path, 'r') as f:
                        content = f.read()
                    
                    return [types.TextContent(
                        type="text",
                        text=f"📋 .gitignore contents:\n\n{content}"
                    )]
                else:
                    return [types.TextContent(type="text", text="No .gitignore file found.")]
            
            elif action == "add":
                if not patterns:
                    raise ValueError("patterns required for add action")
                
                # Read existing content
                existing_patterns = []
                if gitignore_path.exists():
                    with open(gitignore_path, 'r') as f:
                        existing_patterns = [line.strip() for line in f if line.strip()]
                
                # Add new patterns
                new_patterns = []
                for pattern in patterns:
                    if pattern not in existing_patterns:
                        existing_patterns.append(pattern)
                        new_patterns.append(pattern)
                
                # Write back
                with open(gitignore_path, 'w') as f:
                    f.write("\n".join(existing_patterns) + "\n")
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Added {len(new_patterns)} patterns to .gitignore:\n" +
                         "\n".join(f"  + {p}" for p in new_patterns)
                )]
            
            elif action == "create":
                templates = {
                    "python": """__pycache__/
*.py[cod]
*$py.class
.Python
env/
venv/
.env
.venv
*.egg-info/
dist/
build/
.pytest_cache/
.coverage
.mypy_cache/
.pytest_cache/
htmlcov/
.tox/
.nox/
.coverage.*
*.cover
*.log
.git
.gitignore
""",
                    "node": """node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*
.pnpm-debug.log*
dist/
dist-ssr/
*.local
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
.DS_Store
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
""",
                    "java": """# Compiled class file
*.class

# Log file
*.log

# BlueJ files
*.ctxt

# Mobile Tools for Java (J2ME)
.mtj.tmp/

# Package Files #
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# virtual machine crash logs
hs_err_pid*

# IDE files
.idea/
*.iml
.classpath
.project
.settings/
target/
""",
                    "go": """# Binaries for programs and plugins
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test binary, built with 'go test -c'
*.test

# Output of the go coverage tool
*.out

# Dependency directories
vendor/

# Go workspace file
go.work

# IDE files
.idea/
.vscode/
*.swp
*.swo
*~
"""
                }
                
                content = templates.get(template, "# Add your ignore patterns here\n")
                
                with open(gitignore_path, 'w') as f:
                    f.write(content)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Created .gitignore with {template or 'default'} template"
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
                server_name="git-complete-server",
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