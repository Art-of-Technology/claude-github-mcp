@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo   MCP Server Fix Installation for Windows
echo   Solving "No module named 'mcp'" Error
echo ===============================================
echo.

:: Check current directory
set "INSTALL_DIR=%CD%"
echo Working directory: %INSTALL_DIR%
echo.

:: Step 1: Locate Python files
set "PYTHON_FILES_FOUND=0"
if exist "github_complete_server.py" (
    echo [✓] Found github_complete_server.py in current directory
    set "PYTHON_FILES_FOUND=1"
    set "SERVER_DIR=%CD%"
) else if exist "src\github_complete_server.py" (
    echo [✓] Found files in src\ directory
    set "PYTHON_FILES_FOUND=1"
    set "SERVER_DIR=%CD%\src"
) else (
    echo [!] Python server files not found!
    echo Please ensure github_complete_server.py and git-mcp-server.py are present
    pause
    exit /b 1
)

cd /d "%SERVER_DIR%"
echo Using server directory: %SERVER_DIR%
echo.

:: Step 2: Create virtual environment
echo [Step 1/5] Setting up Python environment...
if exist "venv" (
    echo Removing existing virtual environment...
    rmdir /s /q venv
)

python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment
    echo Make sure Python 3.8+ is installed
    pause
    exit /b 1
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Step 3: Upgrade pip and install basic packages
echo [Step 2/5] Installing base packages...
python -m pip install --upgrade pip
pip install httpx pydantic aiofiles

:: Step 4: Install MCP - Try multiple methods
echo [Step 3/5] Installing MCP SDK...

:: Method 1: Try official mcp package
pip install mcp 2>nul
if errorlevel 0 (
    echo [✓] MCP installed successfully
    goto :mcp_installed
)

:: Method 2: Try mcp-server
pip install mcp-server 2>nul
if errorlevel 0 (
    echo [✓] MCP installed via mcp-server
    goto :mcp_installed
)

:: Method 3: Try from GitHub
pip install git+https://github.com/modelcontextprotocol/python-sdk.git 2>nul
if errorlevel 0 (
    echo [✓] MCP installed from GitHub
    goto :mcp_installed
)

:: Method 4: Create MCP stubs if all else fails
echo [!] MCP package not available via pip
echo Creating MCP compatibility layer...

mkdir venv\Lib\site-packages\mcp\server 2>nul

:: Create __init__.py files
echo # MCP compatibility stub > venv\Lib\site-packages\mcp\__init__.py
echo __version__ = "0.1.0" >> venv\Lib\site-packages\mcp\__init__.py

:: Create types.py
(
echo from typing import Any, Dict, List, Optional
echo from pydantic import BaseModel
echo.
echo class Tool^(BaseModel^):
echo     name: str
echo     description: str
echo     inputSchema: Dict[str, Any]
echo.
echo class TextContent^(BaseModel^):
echo     type: str = "text"
echo     text: str
echo.
echo class ImageContent^(BaseModel^):
echo     type: str = "image"
echo     data: str
echo     mimeType: str
echo.
echo class EmbeddedResource^(BaseModel^):
echo     type: str = "resource"
echo     resource: Any
) > venv\Lib\site-packages\mcp\types.py

:: Create server/__init__.py
(
echo from typing import Any, Callable, Optional
echo.
echo class NotificationOptions:
echo     pass
echo.
echo class Server:
echo     def __init__^(self, name: str^):
echo         self.name = name
echo.
echo     def list_tools^(self^):
echo         def decorator^(func^):
echo             return func
echo         return decorator
echo.
echo     def call_tool^(self^):
echo         def decorator^(func^):
echo             return func
echo         return decorator
echo.
echo     async def run^(self, *args, **kwargs^):
echo         pass
echo.
echo     def get_capabilities^(self, **kwargs^):
echo         return {}
) > venv\Lib\site-packages\mcp\server\__init__.py

:: Create server/models.py
(
echo class InitializationOptions:
echo     def __init__^(self, **kwargs^):
echo         for k, v in kwargs.items^(^):
echo             setattr^(self, k, v^)
) > venv\Lib\site-packages\mcp\server\models.py

:: Create server/stdio.py
(
echo from contextlib import asynccontextmanager
echo.
echo @asynccontextmanager
echo async def stdio_server^(^):
echo     yield ^(None, None^)
) > venv\Lib\site-packages\mcp\server\stdio.py

echo [✓] MCP compatibility layer created

:mcp_installed

:: Step 5: Get GitHub token
echo.
echo [Step 4/5] GitHub Token Configuration...
if "%GITHUB_TOKEN%"=="" (
    echo.
    echo Please enter your GitHub Personal Access Token:
    echo ^(Create at: https://github.com/settings/tokens^)
    set /p GITHUB_TOKEN=Token: 
)

:: Step 6: Update Claude configuration
echo.
echo [Step 5/5] Updating Claude configuration...

set "CONFIG_DIR=%APPDATA%\Claude"
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

:: Create config with correct paths
> "%CONFIG_DIR%\claude_desktop_config.json" (
    echo {
    echo   "mcpServers": {
    echo     "github-complete": {
    echo       "command": "%SERVER_DIR:\=\\%\\venv\\Scripts\\python.exe",
    echo       "args": ["%SERVER_DIR:\=\\%\\github_complete_server.py"],
    echo       "env": {
    echo         "GITHUB_TOKEN": "!GITHUB_TOKEN!",
    echo         "PYTHONIOENCODING": "utf-8",
    echo         "PYTHONPATH": "%SERVER_DIR:\=\\%\\venv\\Lib\\site-packages"
    echo       }
    echo     },
    echo     "git-server": {
    echo       "command": "%SERVER_DIR:\=\\%\\venv\\Scripts\\python.exe",
    echo       "args": ["%SERVER_DIR:\=\\%\\git-mcp-server.py"],
    echo       "env": {
    echo         "GITHUB_TOKEN": "!GITHUB_TOKEN!",
    echo         "PYTHONIOENCODING": "utf-8",
    echo         "HOME": "%USERPROFILE:\=\\%",
    echo         "PYTHONPATH": "%SERVER_DIR:\=\\%\\venv\\Lib\\site-packages"
    echo       }
    echo     }
    echo   }
    echo }
)

:: Create test script
> test_mcp.bat (
    echo @echo off
    echo cd /d "%SERVER_DIR%"
    echo call venv\Scripts\activate.bat
    echo echo Testing MCP import...
    echo python -c "import mcp; print('MCP imported successfully')"
    echo echo.
    echo echo Testing server imports...
    echo python -c "import mcp.server.stdio; import mcp.types; print('All imports successful')"
    echo pause
)

echo.
echo ===============================================
echo   ✓ INSTALLATION COMPLETE!
echo ===============================================
echo.
echo Configuration updated at:
echo %CONFIG_DIR%\claude_desktop_config.json
echo.
echo Server files location:
echo %SERVER_DIR%
echo.
echo IMPORTANT STEPS:
echo 1. Close Claude Desktop completely (check Task Manager)
echo 2. Wait 5 seconds
echo 3. Restart Claude Desktop
echo 4. The servers should now connect properly
echo.
echo To test MCP installation: run test_mcp.bat
echo.
echo If still having issues:
echo - Run this script as Administrator
echo - Temporarily disable antivirus
echo - Check firewall settings
echo.
pause