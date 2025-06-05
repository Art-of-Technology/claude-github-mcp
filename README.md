# GitHub PR MCP Server for Claude 🚀

Manage GitHub Pull Requests by talking to Claude AI!

## 🎯 What is this?

This tool lets Claude AI manage your GitHub PRs. Instead of clicking through GitHub's interface, just tell Claude what you want:
- "Create a PR from feature branch to main"
- "Approve PR #42"
- "List all open PRs"
- And much more!

## 📋 Quick Install

### Windows:
1. Download all files to a folder
2. Double-click `install.bat`
3. Enter your GitHub token when asked
4. Restart Claude Desktop
5. Done! 🎉

### Mac/Linux:
1. Download all files to a folder
2. Open Terminal in that folder
3. Run: `chmod +x install.sh && ./install.sh`
4. Enter your GitHub token when asked
5. Restart Claude Desktop
6. Done! 🎉

## 📁 Required Files

Make sure you have all these files:
- `github_pr_server.py` - The main server file
- `install.bat` - Windows installer
- `install.sh` - Mac/Linux installer
- `README.md` - This file

## 🔑 Getting GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name like "Claude MCP"
4. Select these permissions:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `write:discussion` (Read and write discussions)
5. Click "Generate token"
6. Copy the token (starts with `ghp_`)

## 🧪 Testing

After installation, open Claude and try:
- "List PRs in github.com/microsoft/vscode"
- "Show me details of PR #123 in my repo"

## ❓ Troubleshooting

**"Python not found"**
- Install Python from https://python.org
- Make sure to check "Add to PATH" during installation

**"Claude Desktop not found"**
- Install Claude from https://claude.ai/download

**No tool icon in Claude**
- Make sure Claude is completely closed before running installer
- Check if the config file exists at:
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - Linux: `~/.config/Claude/claude_desktop_config.json`

## 📞 Need Help?

Create an issue on GitHub or check the detailed setup guide.

---
Made with ❤️ for the Claude community
