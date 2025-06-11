@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo   MCP Server Installation Script for Windows
echo   GitHub & Git Complete Servers
echo ===============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [✓] Python is installed
python --version

:: Check if Node.js is installed (for web-automation-mcp if needed)
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Node.js is not installed. 
    echo If you plan to use web-automation-mcp, install Node.js from https://nodejs.org
    echo.
) else (
    echo [✓] Node.js is installed
    node --version
)

:: Get installation directory
set "INSTALL_DIR=%~dp0"
echo.
echo Installation directory: %INSTALL_DIR%
echo.

:: Create virtual environment
echo [1/6] Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    echo Make sure python-venv is installed.
    pause
    exit /b 1
)

:: Activate virtual environment
echo [2/6] Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
echo [3/6] Upgrading pip...
python -m pip install --upgrade pip

:: Install required packages
echo [4/6] Installing required Python packages...
pip install httpx mcp pydantic

:: Check if GitHub token is provided
if "%GITHUB_TOKEN%"=="" (
    echo.
    echo ===============================================
    echo   GITHUB TOKEN REQUIRED
    echo ===============================================
    echo.
    echo Please enter your GitHub Personal Access Token:
    echo (Create one at: https://github.com/settings/tokens)
    echo Required scopes: repo, workflow, read:org
    echo.
    set /p GITHUB_TOKEN=GitHub Token: 
)

:: Validate GitHub token format
echo !GITHUB_TOKEN! | findstr /r "^ghp_[a-zA-Z0-9]*$" >nul
if errorlevel 1 (
    echo.
    echo [WARNING] Token doesn't look like a valid GitHub token format.
    echo GitHub tokens should start with 'ghp_'
    echo.
)

:: Create config directory for Claude
set "CLAUDE_CONFIG_DIR=%APPDATA%\Claude"
if not exist "%CLAUDE_CONFIG_DIR%" (
    echo [5/6] Creating Claude configuration directory...
    mkdir "%CLAUDE_CONFIG_DIR%"
)

:: Generate Claude desktop config
echo [6/6] Generating Claude desktop configuration...
set "CONFIG_FILE=%CLAUDE_CONFIG_DIR%\claude_desktop_config.json"

:: Create the config file
echo { > "%CONFIG_FILE%"
echo   "mcpServers": { >> "%CONFIG_FILE%"
echo     "github-complete": { >> "%CONFIG_FILE%"
echo       "command": "%INSTALL_DIR%venv\Scripts\python.exe", >> "%CONFIG_FILE%"
echo       "args": ["%INSTALL_DIR%github_complete_server.py"], >> "%CONFIG_FILE%"
echo       "env": { >> "%CONFIG_FILE%"
echo         "GITHUB_TOKEN": "!GITHUB_TOKEN!", >> "%CONFIG_FILE%"
echo         "PYTHONIOENCODING": "utf-8" >> "%CONFIG_FILE%"
echo       } >> "%CONFIG_FILE%"
echo     }, >> "%CONFIG_FILE%"
echo     "git-server": { >> "%CONFIG_FILE%"
echo       "command": "%INSTALL_DIR%venv\Scripts\python.exe", >> "%CONFIG_FILE%"
echo       "args": ["%INSTALL_DIR%git-mcp-server.py"], >> "%CONFIG_FILE%"
echo       "env": { >> "%CONFIG_FILE%"
echo         "GITHUB_TOKEN": "!GITHUB_TOKEN!", >> "%CONFIG_FILE%"
echo         "PYTHONIOENCODING": "utf-8", >> "%CONFIG_FILE%"
echo         "HOME": "%USERPROFILE%" >> "%CONFIG_FILE%"
echo       }, >> "%CONFIG_FILE%"
echo       "workingDirectory": "%USERPROFILE%\Documents" >> "%CONFIG_FILE%"
echo     } >> "%CONFIG_FILE%"
echo   } >> "%CONFIG_FILE%"
echo } >> "%CONFIG_FILE%"

:: Create a batch file to test the servers
echo Creating test scripts...
echo @echo off > test_github_server.bat
echo echo Testing GitHub Complete Server... >> test_github_server.bat
echo call venv\Scripts\activate.bat >> test_github_server.bat
echo set GITHUB_TOKEN=!GITHUB_TOKEN! >> test_github_server.bat
echo python github_complete_server.py >> test_github_server.bat
echo pause >> test_github_server.bat

echo @echo off > test_git_server.bat
echo echo Testing Git MCP Server... >> test_git_server.bat
echo call venv\Scripts\activate.bat >> test_git_server.bat
echo set GITHUB_TOKEN=!GITHUB_TOKEN! >> test_git_server.bat
echo python git-mcp-server.py >> test_git_server.bat
echo pause >> test_git_server.bat

:: Create start script
echo @echo off > start_servers.bat
echo echo Starting MCP Servers... >> start_servers.bat
echo echo Close this window to stop the servers. >> start_servers.bat
echo call venv\Scripts\activate.bat >> start_servers.bat
echo set GITHUB_TOKEN=!GITHUB_TOKEN! >> start_servers.bat
echo start "GitHub Complete Server" python github_complete_server.py >> start_servers.bat
echo start "Git MCP Server" python git-mcp-server.py >> start_servers.bat
echo pause >> start_servers.bat

echo.
echo ===============================================
echo   INSTALLATION COMPLETE!
echo ===============================================
echo.
echo Configuration file created at:
echo   %CONFIG_FILE%
echo.
echo Next steps:
echo 1. Make sure github_complete_server.py and git-mcp-server.py are in:
echo    %INSTALL_DIR%
echo.
echo 2. Restart Claude Desktop application
echo.
echo 3. The MCP servers should now be available in Claude
echo.
echo Test scripts created:
echo   - test_github_server.bat (Test GitHub server)
echo   - test_git_server.bat (Test Git server)
echo   - start_servers.bat (Start both servers)
echo.
echo Your GitHub token has been saved securely in the configuration.
echo To update it later, edit: %CONFIG_FILE%
echo.
echo ===============================================
echo.
pause