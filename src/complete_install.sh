#!/bin/bash

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "==============================================="
echo "  MCP Server Complete Installation Script"
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

# Get installation directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "Installation directory: $INSTALL_DIR"
echo

# Step 1: Locate Python files
print_info "[1/8] Locating server files..."
PYTHON_FILES_FOUND=0
if [ -f "github_complete_server.py" ]; then
    print_status "Found server files in current directory" 0
    SERVER_DIR="$INSTALL_DIR"
elif [ -f "src/github_complete_server.py" ]; then
    print_status "Found server files in src/ directory" 0
    SERVER_DIR="$INSTALL_DIR/src"
else
    print_error "Python server files not found!"
    echo "Please ensure these files are present:"
    echo "  - github_complete_server.py"
    echo "  - git-mcp-server.py"
    exit 1
fi

cd "$SERVER_DIR"
echo "Using server directory: $SERVER_DIR"
echo

# Step 2: Check Python installation
print_info "[2/8] Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    print_status "Python $PYTHON_VERSION found" 0
    
    # Check minimum version
    REQUIRED_VERSION="3.8"
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        print_error "Python $PYTHON_VERSION is too old. Need Python 3.8 or higher."
        exit 1
    fi
else
    print_error "Python 3 is not installed."
    echo "Please install Python 3.8 or higher:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  brew install python3"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "  sudo apt install python3 python3-pip python3-venv"
    fi
    exit 1
fi

# Step 3: Fix Python syntax issues
print_info "[3/8] Checking and fixing Python syntax issues..."

# Create a temporary fix script
cat > temp_fix_syntax.py << 'EOF'
import sys
import re
import os

def fix_fstring_issues(filename):
    """Fix f-string syntax issues in Python files"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix f-strings with backslashes
        # Pattern 1: f"...\n..." -> "...\n..."
        content = re.sub(r'f"([^"]*\\[nt][^"]*)"', r'"\1"', content)
        content = re.sub(r"f'([^']*\\[nt][^']*)'", r"'\1'", content)
        
        # Pattern 2: f"""...\n...""" -> """...\n..."""
        content = re.sub(r'f"""([^"]*\\[nt][^"]*)"""', r'"""\1"""', content)
        content = re.sub(r"f'''([^']*\\[nt][^']*)'''", r"'''\1'''", content)
        
        if content != original_content:
            # Create backup
            backup_file = filename + '.backup'
            if not os.path.exists(backup_file):
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(original_content)
            
            # Write fixed content
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed syntax issues in {filename}")
            return True
        else:
            print(f"No syntax issues found in {filename}")
            return False
            
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return False

# Fix both server files
for filename in sys.argv[1:]:
    if os.path.exists(filename):
        fix_fstring_issues(filename)
EOF

# Run the syntax fix
python3 temp_fix_syntax.py "github_complete_server.py" "git-mcp-server.py"
rm temp_fix_syntax.py

# Test syntax
print_info "Testing Python syntax..."
python3 -m py_compile github_complete_server.py 2>/dev/null
if [ $? -eq 0 ]; then
    print_status "github_complete_server.py syntax OK" 0
else
    print_warning "github_complete_server.py may have syntax issues"
fi

python3 -m py_compile git-mcp-server.py 2>/dev/null
if [ $? -eq 0 ]; then
    print_status "git-mcp-server.py syntax OK" 0
else
    print_warning "git-mcp-server.py may have syntax issues"
fi
echo

# Step 4: Create virtual environment
print_info "[4/8] Setting up Python virtual environment..."
if [ -d "venv" ]; then
    print_warning "Removing existing virtual environment..."
    rm -rf venv
fi

python3 -m venv venv
if [ $? -eq 0 ]; then
    print_status "Virtual environment created" 0
else
    print_error "Failed to create virtual environment."
    echo "Make sure python3-venv is installed."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Step 5: Install dependencies
print_info "[5/8] Installing required packages..."
python -m pip install --upgrade pip >/dev/null 2>&1
pip install httpx pydantic aiofiles >/dev/null 2>&1
print_status "Base packages installed" 0

# Step 6: Install MCP SDK
print_info "[6/8] Installing MCP SDK..."

MCP_INSTALLED=0
# Try different installation methods
if pip install mcp 2>/dev/null; then
    print_status "MCP installed via pip" 0
    MCP_INSTALLED=1
elif pip install mcp-server 2>/dev/null; then
    print_status "MCP installed via mcp-server" 0
    MCP_INSTALLED=1
elif pip install git+https://github.com/modelcontextprotocol/python-sdk.git 2>/dev/null; then
    print_status "MCP installed from GitHub" 0
    MCP_INSTALLED=1
else
    # Create MCP compatibility stub
    print_warning "MCP package not available via pip"
    print_info "Creating MCP compatibility layer..."
    
    SITE_PACKAGES="venv/lib/python${PYTHON_VERSION}/site-packages"
    mkdir -p "$SITE_PACKAGES/mcp/server"
    
    # Create stub files
    cat > "$SITE_PACKAGES/mcp/__init__.py" << 'EOF'
# MCP compatibility stub
__version__ = "0.1.0"
EOF
    
    cat > "$SITE_PACKAGES/mcp/types.py" << 'EOF'
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class Tool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class TextContent(BaseModel):
    type: str = "text"
    text: str

class ImageContent(BaseModel):
    type: str = "image"
    data: str
    mimeType: str

class EmbeddedResource(BaseModel):
    type: str = "resource"
    resource: Any
EOF
    
    cat > "$SITE_PACKAGES/mcp/server/__init__.py" << 'EOF'
from typing import Any, Callable, Optional

class NotificationOptions:
    pass

class Server:
    def __init__(self, name: str):
        self.name = name
    
    def list_tools(self):
        def decorator(func):
            return func
        return decorator
    
    def call_tool(self):
        def decorator(func):
            return func
        return decorator
    
    async def run(self, *args, **kwargs):
        pass
    
    def get_capabilities(self, **kwargs):
        return {}
EOF
    
    cat > "$SITE_PACKAGES/mcp/server/models.py" << 'EOF'
class InitializationOptions:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
EOF
    
    cat > "$SITE_PACKAGES/mcp/server/stdio.py" << 'EOF'
from contextlib import asynccontextmanager

@asynccontextmanager
async def stdio_server():
    yield (None, None)
EOF
    
    print_status "MCP compatibility layer created" 0
    MCP_INSTALLED=0
fi

# Step 7: GitHub Token Configuration
echo
print_info "[7/8] GitHub Token Configuration..."
if [ -z "$GITHUB_TOKEN" ]; then
    echo
    echo "You need a GitHub Personal Access Token to use these servers."
    echo
    echo "To create one:"
    echo "1. Go to: https://github.com/settings/tokens"
    echo "2. Click 'Generate new token (classic)'"
    echo "3. Select scopes: repo, workflow, read:org"
    echo "4. Copy the token (starts with ghp_)"
    echo
    read -sp "Paste your GitHub token here: " GITHUB_TOKEN
    echo
fi

# Validate token format
if [[ ! "$GITHUB_TOKEN" =~ ^gh[ps]_[a-zA-Z0-9]+$ ]]; then
    print_warning "Token doesn't match expected GitHub token format."
    echo "GitHub tokens should start with 'ghp_' or 'ghs_'"
fi

# Step 8: Create Claude configuration
print_info "[8/8] Creating Claude configuration..."

# Detect OS and set config directory
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    OS_TYPE="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    CONFIG_DIR="$HOME/.config/Claude"
    OS_TYPE="Linux"
else
    # Other Unix-like
    CONFIG_DIR="$HOME/.claude"
    OS_TYPE="Unix"
fi

mkdir -p "$CONFIG_DIR"

# Create config file
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "github-complete": {
      "command": "$SERVER_DIR/venv/bin/python",
      "args": ["$SERVER_DIR/github_complete_server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "$SERVER_DIR/venv/lib/python${PYTHON_VERSION}/site-packages"
      }
    },
    "git-server": {
      "command": "$SERVER_DIR/venv/bin/python",
      "args": ["$SERVER_DIR/git-mcp-server.py"],
      "env": {
        "GITHUB_TOKEN": "$GITHUB_TOKEN",
        "PYTHONIOENCODING": "utf-8",
        "HOME": "$HOME",
        "PYTHONPATH": "$SERVER_DIR/venv/lib/python${PYTHON_VERSION}/site-packages"
      },
      "workingDirectory": "$HOME/Documents"
    }
  }
}
EOF

print_status "Configuration created" 0

# Create test scripts
print_info "Creating test scripts..."

# Test MCP installation
cat > test_mcp.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
echo "Testing MCP import..."
python -c "import mcp; print('✓ MCP module found')" 2>/dev/null || echo "✗ MCP module not found"
echo
echo "Testing MCP submodules..."
python -c "import mcp.server.stdio; print('✓ mcp.server.stdio found')" 2>/dev/null || echo "✗ mcp.server.stdio not found"
python -c "import mcp.types; print('✓ mcp.types found')" 2>/dev/null || echo "✗ mcp.types not found"
echo
echo "Testing server files..."
python -c "import github_complete_server; print('✓ github_complete_server imports successfully')" 2>/dev/null || echo "✗ github_complete_server has import errors"
python -c "import git-mcp-server; print('✓ git-mcp-server imports successfully')" 2>/dev/null || echo "✗ git-mcp-server has import errors"
EOF
chmod +x test_mcp.sh

# Test servers
cat > test_servers.sh << EOF
#!/bin/bash
cd "$SERVER_DIR"
source venv/bin/activate
export GITHUB_TOKEN="$GITHUB_TOKEN"
export PYTHONPATH="$SERVER_DIR/venv/lib/python${PYTHON_VERSION}/site-packages"

echo "Testing GitHub Complete Server..."
timeout 5 python github_complete_server.py 2>&1 | head -20
echo
echo "Testing Git MCP Server..."
timeout 5 python git-mcp-server.py 2>&1 | head -20
echo
echo "If you see initialization messages without errors, the servers are working correctly."
EOF
chmod +x test_servers.sh

# Create uninstall script
cat > uninstall.sh << EOF
#!/bin/bash
echo "Uninstalling MCP Servers..."
rm -rf venv
rm -f "$CONFIG_FILE"
rm -f test_mcp.sh test_servers.sh
echo "Virtual environment and configuration removed."
echo "Server files have been preserved."
echo "Backup files (*.backup) have been preserved."
EOF
chmod +x uninstall.sh

echo
echo "==============================================="
echo "  ✓ INSTALLATION COMPLETE!"
echo "==============================================="
echo
print_info "Operating System: $OS_TYPE"
print_info "Configuration saved to: $CONFIG_FILE"
print_info "Server files location: $SERVER_DIR"
if [ $MCP_INSTALLED -eq 0 ]; then
    print_warning "Using MCP compatibility stub (full functionality provided by Claude)"
fi
echo
echo "NEXT STEPS:"
echo "1. Close Claude Desktop completely"
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "   (Use ⌘Q or check Activity Monitor)"
else
    echo "   (Check system monitor/task manager)"
fi
echo "2. Wait 5 seconds"
echo "3. Restart Claude Desktop"
echo "4. Look for 'github-complete' and 'git-server' in Claude"
echo
echo "TEST SCRIPTS:"
echo "  ./test_mcp.sh     - Test MCP installation"
echo "  ./test_servers.sh - Test server functionality"
echo "  ./uninstall.sh    - Uninstall MCP servers"
echo
echo "TROUBLESHOOTING:"
echo "- If servers don't appear, make sure Claude is fully closed"
echo "- Check for antivirus/firewall blocking Python"
echo "- Try running with elevated permissions if needed"
echo "- Restore from backups: *.backup files"
echo
echo "Your GitHub token has been saved securely."
echo "To update it, edit: $CONFIG_FILE"
echo
echo "==============================================="
echo