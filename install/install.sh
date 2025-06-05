#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          GitHub PR MCP Server - Automated Setup              ║"
echo "║                    GitHub PR Tool for Claude                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
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
    else
        echo "  sudo apt-get install python3 python3-pip"
    fi
    exit 1
fi

# Check pip
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo -e "${RED}❌ pip not found!${NC}"
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
INSTALL_DIR="$HOME/github-pr-mcp"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✅ Folder: $INSTALL_DIR${NC}"

# Create virtual environment
echo
echo "[4/7] Creating Python virtual environment..."
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
    exit 1
fi
echo -e "${GREEN}✅ Packages installed${NC}"

# Get GitHub Token
echo
echo "[6/7] GitHub Token Setup"
echo "════════════════════════════════════════════════════════════════"
echo
echo "To create a GitHub Personal Access Token:"
echo "1. Go to https://github.com/settings/tokens"
echo "2. Click \"Generate new token (classic)\""
echo "3. Select these permissions:"
echo "   ✓ repo (Full control)"
echo "   ✓ write:discussion"
echo "4. Copy the token"
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
    cp "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" "$CLAUDE_CONFIG_DIR/claude_desktop_config.backup.json"
    echo "📁 Existing config backed up"
fi

# Create new config
cat > "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" << EOF
{
  "mcpServers": {
    "github-pr": {
      "command": "$INSTALL_DIR/venv/bin/python",
      "args": ["$INSTALL_DIR/github_pr_server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN"
      }
    }
  }
}
EOF

echo -e "${GREEN}✅ Claude configuration completed${NC}"

# Check for main Python file
if [ ! -f "$INSTALL_DIR/github_pr_server.py" ]; then
    echo
    echo -e "${YELLOW}⚠️  WARNING: github_pr_server.py file not found!${NC}"
    echo "📁 Please copy the file to: $INSTALL_DIR/github_pr_server.py"
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
echo "1. Copy github_pr_server.py file to:"
echo "   $INSTALL_DIR/"
echo
echo "2. Completely close Claude Desktop"
echo
echo "3. Restart Claude"
echo
echo "4. Test with: \"List GitHub PRs\""
echo
echo "📁 Installation location: $INSTALL_DIR"
echo "📝 Config backup: $CLAUDE_CONFIG_DIR/claude_desktop_config.backup.json"
echo

# Make script executable
chmod +x "$0"