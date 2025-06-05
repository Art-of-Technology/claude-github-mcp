@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul
cls

echo ╔══════════════════════════════════════════════════════════════╗
echo ║          GitHub PR MCP Server - Automated Setup              ║
echo ║                    GitHub PR Tool for Claude                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: Check Python
echo [1/7] Checking Python installation...
py --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found!
    echo.
    echo Please download Python from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('py --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% found

:: Check Claude Desktop
echo.
echo [2/7] Checking Claude Desktop...
if not exist "%APPDATA%\Claude" (
    echo ❌ Claude Desktop not found!
    echo.
    echo Please download Claude Desktop from: https://claude.ai/download
    echo Run this script again after installation.
    echo.
    pause
    exit /b 1
)
echo ✅ Claude Desktop found

:: Create project folder
echo.
echo [3/7] Creating project folder...
set INSTALL_DIR=%USERPROFILE%\github-pr-mcp
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"
echo ✅ Folder: %INSTALL_DIR%

:: Create virtual environment
echo.
echo [4/7] Creating Python virtual environment...
py -m venv venv
if %errorlevel% neq 0 (
    echo ❌ Failed to create virtual environment!
    pause
    exit /b 1
)
echo ✅ Virtual environment created

:: Install dependencies
echo.
echo [5/7] Installing required packages...
call venv\Scripts\activate.bat

:: Create requirements.txt
echo mcp==0.9.1 > requirements.txt
echo httpx==0.27.0 >> requirements.txt
echo pydantic==2.5.0 >> requirements.txt

pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ❌ Package installation failed!
    pause
    exit /b 1
)
echo ✅ Packages installed

:: Get GitHub Token
echo.
echo [6/7] GitHub Token Setup
echo ════════════════════════════════════════════════════════════════
echo.
echo To create a GitHub Personal Access Token:
echo 1. Go to https://github.com/settings/tokens
echo 2. Click "Generate new token (classic)"
echo 3. Select these permissions:
echo    ✓ repo (Full control)
echo    ✓ write:discussion
echo 4. Copy the token
echo.
echo ════════════════════════════════════════════════════════════════
echo.
set /p GITHUB_TOKEN="Paste your GitHub Token (starts with ghp_): "

if "%GITHUB_TOKEN%"=="" (
    echo ❌ No token provided!
    pause
    exit /b 1
)

:: Configure Claude
echo.
echo [7/7] Configuring Claude Desktop...

:: Create config directory if it doesn't exist
if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"

:: Backup existing config
if exist "%APPDATA%\Claude\claude_desktop_config.json" (
    copy "%APPDATA%\Claude\claude_desktop_config.json" "%APPDATA%\Claude\claude_desktop_config.backup.json" >nul
    echo 📁 Existing config backed up
)

:: Create new config
echo { > "%APPDATA%\Claude\claude_desktop_config.json"
echo   "mcpServers": { >> "%APPDATA%\Claude\claude_desktop_config.json"
echo     "github-pr": { >> "%APPDATA%\Claude\claude_desktop_config.json"
echo       "command": "%INSTALL_DIR:\=\\%\\venv\\Scripts\\python.exe", >> "%APPDATA%\Claude\claude_desktop_config.json"
echo       "args": ["%INSTALL_DIR:\=\\%\\github_pr_server.py"], >> "%APPDATA%\Claude\claude_desktop_config.json"
echo       "env": { >> "%APPDATA%\Claude\claude_desktop_config.json"
echo         "GITHUB_TOKEN": "%GITHUB_TOKEN%" >> "%APPDATA%\Claude\claude_desktop_config.json"
echo       } >> "%APPDATA%\Claude\claude_desktop_config.json"
echo     } >> "%APPDATA%\Claude\claude_desktop_config.json"
echo   } >> "%APPDATA%\Claude\claude_desktop_config.json"
echo } >> "%APPDATA%\Claude\claude_desktop_config.json"

echo ✅ Claude configuration completed

:: Check for main Python file
if not exist "%INSTALL_DIR%\github_pr_server.py" (
    echo.
    echo ⚠️  WARNING: github_pr_server.py file not found!
    echo 📁 Please copy the file to: %INSTALL_DIR%\github_pr_server.py
    echo.
)

:: Success message
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    🎉 SETUP COMPLETED! 🎉                     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo ✅ Next steps:
echo.
echo 1. Copy github_pr_server.py file to:
echo    %INSTALL_DIR%\
echo.
echo 2. Completely close Claude Desktop (including system tray)
echo.
echo 3. Restart Claude
echo.
echo 4. Test with: "List GitHub PRs"
echo.
echo 📁 Installation location: %INSTALL_DIR%
echo 📝 Config backup: %APPDATA%\Claude\claude_desktop_config.backup.json
echo.
pause