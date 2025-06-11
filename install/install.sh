#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "==============================================="
echo "  MCP Server Installation Script"
echo "  GitHub & Git Complete Servers"
echo "==============================================="
echo

# Function to print colored output
print_status() {
    if [ $2 -eq 0 ]; then
        echo -e "${GREEN}[✓]${NC} $1"
    else
        echo -e "${RED}[✗]${NC} $1"
    fi
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is installed
if command -v python3 &> /dev/null; then
    print_status "Python is installed" 0
    python3 --version
else
    print_error "Python 3 is not installed."
    echo "Please install Python 3.8 or higher:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  macOS: brew install python3"
    echo "  Fedora: sudo dnf install python3 python3-pip"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 is not installed."
    echo "Please install pip3 for Python package management."
    exit 1
fi

# Check if Node.js is installed (optional, for web-automation)
if command -v node &> /dev/null; then
    print_status "Node.js is installed" 0
    node --version
else
    print_warning "Node.js is not installed."
    echo "If you plan to use web-automation-mcp, install Node.js from https://nodejs.org"
fi

# Get installation directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "Installation directory: $INSTALL_DIR"
echo

# Create virtual environment
print_info "[1/6] Creating Python virtual environment..."
python3 -m venv venv
if [ $? -eq 0 ]; then
    print_status "Virtual environment created" 0
else
    print_error "Failed to create virtual environment."
    echo "Make sure python3-venv is installed."
    exit 1
fi

# Activate virtual environment
print_info "[2/6] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "[3/6] Upgrading pip..."
pip install --upgrade pip

# Install required packages
print_info "[4/6] Installing required Python packages..."
pip install httpx mcp pydantic

# Check if GitHub token is provided
if [ -z "$GITHUB_TOKEN" ]; then
    echo
    echo "==============================================="
    echo "  GITHUB TOKEN REQUIRED"
    echo "==============================================="
    echo
    echo "Please enter your GitHub Personal Access Token:"
    echo "(Create one at: https://github.com/settings/tokens)"
    echo "Required scopes: repo, workflow, read:org"
    echo
    read -p "GitHub Token: " GITHUB_TOKEN
fi

# Validate GitHub token format
if [[ ! "$GITHUB_TOKEN" =~ ^ghp_[a-zA-Z0-9]+$ ]]; then
    print_warning "Token doesn't look like a valid GitHub token format."
    echo "GitHub tokens should start with 'ghp_'"
    echo
fi

# Detect OS and set config directory
print_info "[5/6] Detecting operating system..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
    OS_TYPE="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CLAUDE_CONFIG_DIR="$HOME/.config/Claude"
    OS_TYPE="Linux"
else
    # Other Unix-like
    CLAUDE_CONFIG_DIR="$HOME/.claude"
    OS_TYPE="Unix"
fi

print_status "Detected $OS_TYPE" 0

# Create config directory if it doesn't exist
if [ ! -d "$CLAUDE_CONFIG_DIR" ]; then
    print_info "Creating Claude configuration directory..."
    mkdir -p "$CLAUDE_CONFIG_DIR"
fi

# Generate Claude desktop config
print_info "[6/6] Generating Claude desktop configuration..."
CONFIG_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

# Create the config file
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "github-complete": {
      "command": "$INSTALL_DIR/venv/bin/python",
      "args": ["$INSTALL_DIR/github_complete_server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN",
        "PYTHONIOENCODING": "utf-8"
      }
    },
    "git-server": {
      "command": "$INSTALL_DIR/venv/bin/python",
      "args": ["$INSTALL_DIR/git-mcp-server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN",
        "PYTHONIOENCODING": "utf-8",
        "HOME": "$HOME"
      },
      "workingDirectory": "$HOME/Documents"
    }
  }
}
EOF

# Create test scripts
print_info "Creating test scripts..."

# Test GitHub server script
cat > test_github_server.sh << 'EOF'
#!/bin/bash
echo "Testing GitHub Complete Server..."
source venv/bin/activate
export GITHUB_TOKEN
python3 github_complete_server.py
EOF
chmod +x test_github_server.sh

# Test Git server script
cat > test_git_server.sh << 'EOF'
#!/bin/bash
echo "Testing Git MCP Server..."
source venv/bin/activate
export GITHUB_TOKEN
python3 git-mcp-server.py
EOF
chmod +x test_git_server.sh

# Start servers script
cat > start_servers.sh << EOF
#!/bin/bash
echo "Starting MCP Servers..."
echo "Press Ctrl+C to stop the servers."
source venv/bin/activate
export GITHUB_TOKEN="$GITHUB_TOKEN"

# Start servers in background
python3 github_complete_server.py &
PID1=\$!
python3 git-mcp-server.py &
PID2=\$!

# Wait for interrupt
trap "kill \$PID1 \$PID2; exit" INT
wait
EOF
chmod +x start_servers.sh

# Create uninstall script
cat > uninstall.sh << EOF
#!/bin/bash
echo "Uninstalling MCP Servers..."
rm -rf venv
rm -f "$CONFIG_FILE"
echo "Uninstallation complete."
echo "Server files have been preserved."
EOF
chmod +x uninstall.sh

echo
echo "==============================================="
echo "  INSTALLATION COMPLETE!"
echo "==============================================="
echo
print_info "Configuration file created at:"
echo "  $CONFIG_FILE"
echo
print_info "Next steps:"
echo "1. Make sure github_complete_server.py and git-mcp-server.py are in:"
echo "   $INSTALL_DIR"
echo
echo "2. Restart Claude Desktop application"
echo
echo "3. The MCP servers should now be available in Claude"
echo
print_info "Test scripts created:"
echo "  - ./test_github_server.sh (Test GitHub server)"
echo "  - ./test_git_server.sh (Test Git server)"
echo "  - ./start_servers.sh (Start both servers)"
echo "  - ./uninstall.sh (Uninstall MCP servers)"
echo
print_info "Your GitHub token has been saved securely in the configuration."
echo "To update it later, edit: $CONFIG_FILE"
echo
echo "==============================================="
echo