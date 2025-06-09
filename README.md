# GitHub MCP Server

This project is a complete [Model Context Protocol (MCP)](https://github.com/mcprotocol) server that exposes GitHub functionality for LLMs like Claude.

It allows natural language control over GitHub via Claude using 30+ tools, including pull requests, branches, issues, actions, commits, analytics, and more.

---

## 🚀 Features

All GitHub operations are accessible through natural language:

### 🔁 Pull Requests
- Create, list, view, and merge PRs

### 📦 Repository Management
- Create repositories
- List and fetch repo metadata

### 🌿 Branch Operations
- List, create, delete branches

### 🐞 Issues
- Create, list, and update issues
- Add labels or close issues

### 🏷️ Releases & Tags
- Create and list GitHub releases

### ⚙️ GitHub Actions
- List workflows
- Trigger workflows
- View recent workflow runs

### 📝 Commits
- List recent commits
- Get commit details

### 📊 Analytics
- Get repository statistics
- View contributor activity
- Analyze commit trends

### 👥 Collaboration
- Add collaborators to repos
- List existing collaborators

### 📁 File Operations
- Read files from repos
- Create or update files with commits

### 🔍 Search
- Search repositories
- Search for code in a repo or globally

---

## 🤖 Using with Claude

Claude can automatically understand and use the exposed tools via MCP.

### Example Prompts
> "Create a pull request from `feature/api` to `main` titled 'Add new endpoint'"  
> "List all open issues in `weezboo/core`"  
> "Trigger the `ci.yml` workflow on branch `dev`"  
> "Get commit details for SHA `abc1234`"  
> "Search for `useEffect` in `weezboo/ui` repo"

No tool name is required—Claude interprets intent and constructs the call automatically based on the schema.

---

## 🛠️ Requirements

- Python 3.8+
- Environment variable `GITHUB_TOKEN` must be set

```bash
export GITHUB_TOKEN=ghp_...


