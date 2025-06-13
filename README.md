# GitHub Complete MCP Server 🚀

A powerful Model Context Protocol (MCP) server that enables Claude AI to manage all aspects of GitHub through natural language commands.

## ✨ Features

### 📋 Pull Request Management
- **Create PRs** - Create pull requests with title, description, and branch selection
- **List PRs** - View open, closed, or all pull requests with filters
- **Get PR details** - See comprehensive PR information including reviews and changes
- **Merge PRs** - Merge using different strategies (merge, squash, rebase)
- **Add comments & reviews** - Comment on PRs and add approval/change requests
- **Manage reviewers** - Add or remove reviewers from pull requests

### 📁 Repository Operations
- **Create repositories** - Initialize new repos with README and .gitignore
- **Clone repositories** - Clone repos to local machine
- **Get repository info** - View stats, languages, and contributors
- **Manage settings** - Update repository settings and visibility
- **Add collaborators** - Invite users with specific permissions

### 🌳 Branch Management
- **List branches** - View all branches in a repository
- **Create branches** - Create new branches from any base branch
- **Delete branches** - Remove merged or unused branches
- **Compare branches** - See differences between branches

### 🐛 Issue Tracking
- **Create issues** - Open new issues with labels and assignees
- **List issues** - Filter by state, labels, or assignee
- **Update issues** - Modify title, description, labels, or state
- **Close issues** - Mark issues as resolved
- **Add comments** - Discuss and collaborate on issues

### 🏷️ Releases & Tags
- **Create releases** - Publish new versions with release notes
- **List releases** - View published releases and pre-releases
- **Create tags** - Tag specific commits
- **Generate changelogs** - Auto-create release notes from commits

### ⚙️ GitHub Actions
- **List workflows** - View all GitHub Actions workflows
- **Trigger workflows** - Manually run workflows with inputs
- **View run history** - Check workflow execution status and logs
- **Manage secrets** - Update repository secrets (with proper permissions)

### 📊 Analytics & Insights
- **Repository statistics** - Stars, forks, contributors, languages
- **Commit activity** - Contribution graphs and patterns
- **Contributor stats** - Who's contributing what and when
- **Code frequency** - Lines added/removed over time

### 🔍 Search Capabilities
- **Search repositories** - Find repos by keywords, language, or topic
- **Search code** - Look for specific code snippets across GitHub
- **Search issues** - Find issues and PRs across repositories

### 📝 File Operations
- **Read files** - Get content from any file in the repository
- **Create/Update files** - Commit changes directly through Claude
- **Delete files** - Remove files with commit messages

### 🔧 Git Operations
- **Init repository** - Initialize new Git repositories
- **Add files** - Stage files for commit
- **Commit changes** - Create commits with messages
- **Push/Pull** - Sync with remote repositories
- **View diff** - See changes between commits
- **Stash changes** - Temporarily store work in progress

## 🚀 Quick Start

### Prerequisites
- Python 3.8 - 3.12 (Note: Python 3.13 may have compatibility issues)
- Claude Desktop app
- GitHub account with Personal Access Token

### Installation

#### Windows
1. Download all files to a folder
2. Double-click `install.bat`
3. Enter your GitHub token when prompted
4. Restart Claude Desktop

#### Mac/Linux
1. Download all files to a folder
2. Open Terminal in that folder
3. Run: `chmod +x install.sh && ./install.sh`
4. Enter your GitHub token when prompted
5. Restart Claude Desktop

### Manual Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/github-complete-mcp.git
cd github-complete-mcp
```

2. **Create virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install mcp httpx pydantic
```

4. **Get GitHub Token**
- Go to https://github.com/settings/tokens
- Click "Generate new token (classic)"
- Select required permissions:
  - `repo` - Full repository access
  - `workflow` - GitHub Actions access
  - `admin:org` - Organization management (optional)

5. **Configure Claude**

Find your Claude config file:
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Add this configuration:
```json
{
  "mcpServers": {
    "github-complete": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/github_complete_server.py"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

6. **Restart Claude Desktop**

## 💬 Example Commands

```
"Create a new repository called my-awesome-project"
"List open pull requests in microsoft/vscode"
"Create a new issue titled 'Bug in login system'"
"Merge PR #42 using squash method"
"Show me the latest commits in main branch"
"Create a new feature branch from develop"
"Search for machine learning repositories"
"Get repository statistics for torvalds/linux"
"Trigger the deploy workflow on main branch"
"Add @johndoe as a reviewer to PR #55"
```

## 🛠️ Troubleshooting

### Python 3.13 Compatibility
If you encounter installation errors with Python 3.13:
- Install Python 3.12 instead
- Or install Visual Studio Build Tools
- Or use pre-built wheels

### Token Permissions
Ensure your GitHub token has these permissions:
- `repo` - Required for basic operations
- `workflow` - For GitHub Actions
- `write:discussion` - For comments
- `admin:org` - For organization features (optional)

### MCP Not Found
If Claude doesn't recognize the GitHub tools:
1. Ensure Claude is completely closed (check system tray)
2. Verify config file JSON syntax
3. Check file paths are absolute, not relative
4. Restart Claude and check for tools icon

## 📄 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📞 Support

- Create an issue in this repository
- Check existing issues for solutions
- Ensure you're using a compatible Python version

---
