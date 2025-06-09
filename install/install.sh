#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

clear

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       GitHub Complete MCP Server - Automated Setup           ║"
echo "║          All-in-One GitHub Management for Claude             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo "This installer will set up the complete GitHub MCP server with:"
echo "• Pull Requests, Issues, Branches, Releases"
echo "• GitHub Actions, Analytics, Search, and more!"
echo

# Operating system detection
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
else
    OS="Linux"
    CLAUDE_CONFIG_DIR="$HOME/.config/Claude"
fi

echo "Operating System: $OS"
echo

# Check Python
echo "[1/7] Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d" " -f2)
    echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version | cut -d" " -f2)
    echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
    PYTHON_CMD="python"
else
    echo -e "${RED}❌ Python not found!${NC}"
    echo
    echo "To install Python:"
    if [[ "$OS" == "macOS" ]]; then
        echo "  brew install python3"
        echo "  or download from https://python.org"
    else
        echo "  sudo apt-get update"
        echo "  sudo apt-get install python3 python3-pip python3-venv"
    fi
    exit 1
fi

# Check pip
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo -e "${RED}❌ pip not found!${NC}"
    echo "Please install pip:"
    echo "  $PYTHON_CMD -m ensurepip --upgrade"
    exit 1
fi

# Check venv module
if ! $PYTHON_CMD -m venv --help &> /dev/null; then
    echo -e "${RED}❌ venv module not found!${NC}"
    echo "Please install python3-venv:"
    if [[ "$OS" == "Linux" ]]; then
        echo "  sudo apt-get install python3-venv"
    fi
    exit 1
fi

# Check Claude Desktop
echo
echo "[2/7] Checking Claude Desktop..."
if [ ! -d "$CLAUDE_CONFIG_DIR" ]; then
    echo -e "${RED}❌ Claude Desktop not found!${NC}"
    echo
    echo "Please download Claude Desktop from: https://claude.ai/download"
    echo "Run this script again after installation."
    exit 1
fi
echo -e "${GREEN}✅ Claude Desktop found${NC}"

# Create project folder
echo
echo "[3/7] Creating project folder..."
INSTALL_DIR="$HOME/github-complete-mcp"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✅ Folder: $INSTALL_DIR${NC}"

# Create virtual environment
echo
echo "[4/7] Creating Python virtual environment..."

# Remove old venv if exists
if [ -d "venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf venv
fi

$PYTHON_CMD -m venv venv
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to create virtual environment!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Virtual environment created${NC}"

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo
echo "[5/7] Installing required packages..."

# Create requirements.txt
cat > requirements.txt << EOF
mcp==0.9.1
httpx==0.27.0
pydantic==2.5.0
EOF

pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Package installation failed!${NC}"
    echo "Try installing packages manually:"
    echo "  pip install mcp httpx pydantic"
    exit 1
fi
echo -e "${GREEN}✅ Packages installed successfully${NC}"

# Get GitHub Token
echo
echo "[6/7] GitHub Token Setup"
echo "════════════════════════════════════════════════════════════════"
echo
echo -e "${CYAN}To create a GitHub Personal Access Token:${NC}"
echo
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click \"Generate new token (classic)\""
echo "3. Give it a name like \"Claude MCP Complete\""
echo "4. Select these permissions:"
echo "   ✓ repo (Full control of private repositories)"
echo "   ✓ workflow (Update GitHub Action workflows)"
echo "   ✓ write:packages (Upload packages to GitHub Package Registry)"
echo "   ✓ admin:org (Full control of orgs and teams, read and write org projects)"
echo "   ✓ delete_repo (Delete repositories)"
echo "5. Click \"Generate token\" and copy it"
echo
echo "════════════════════════════════════════════════════════════════"
echo
read -p "Paste your GitHub Token (starts with ghp_): " GITHUB_TOKEN

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}❌ No token provided!${NC}"
    exit 1
fi

# Configure Claude
echo
echo "[7/7] Configuring Claude Desktop..."

# Create config directory if it doesn't exist
mkdir -p "$CLAUDE_CONFIG_DIR"

# Backup existing config
if [ -f "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" ]; then
    BACKUP_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.backup.$(date +%Y%m%d_%H%M%S).json"
    cp "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" "$BACKUP_FILE"
    echo "📁 Existing config backed up to: $BACKUP_FILE"
fi

# Create new config
cat > "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" << EOF
{
  "mcpServers": {
    "github-complete": {
      "command": "$INSTALL_DIR/venv/bin/python",
      "args": ["$INSTALL_DIR/github_complete_server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN"
      }
    }
  }
}
EOF

echo -e "${GREEN}✅ Claude configuration completed${NC}"

# Check for main Python file
if [ ! -f "$INSTALL_DIR/github_complete_server.py" ]; then
    echo
    echo -e "${YELLOW}⚠️  WARNING: github_complete_server.py file not found!${NC}"
    echo "📁 Please copy the file to: $INSTALL_DIR/github_complete_server.py"
    echo
fi

# Success message
echo
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 SETUP COMPLETED! 🎉                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo
echo -e "${GREEN}✅ Next steps:${NC}"
echo
echo "1. Copy github_complete_server.py file to:"
echo "   $INSTALL_DIR/"
echo
echo "2. Completely close Claude Desktop"
if [[ "$OS" == "macOS" ]]; then
    echo "   Quit from the menu bar icon"
else
    echo "   Close all windows and check system tray"
fi
echo
echo "3. Restart Claude Desktop"
echo
echo "4. Test with these commands:"
echo "   • \"List my GitHub repositories\""
echo "   • \"Show open issues in owner/repo\""
echo "   • \"Create a new branch called feature-test\""
echo "   • \"Search for machine learning repositories\""
echo
echo "📁 Installation location: $INSTALL_DIR"
echo "📝 Config location: $CLAUDE_CONFIG_DIR/claude_desktop_config.json"
echo
echo -e "${CYAN}🚀 Available features:${NC}"
echo "   • Pull Requests     • Issues          • Branches"
echo "   • Repositories      • Releases        • GitHub Actions"
echo "   • Commits          • Analytics       • Search"
echo "   • Collaborators    • Files           • And more!"
echo

# Make script executable
chmod +x "$0"