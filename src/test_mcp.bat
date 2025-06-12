@echo off
cd /d "D:\AOT\claude-github-mcp\src"
call venv\Scripts\activate.bat
echo Testing MCP import...
python -c "import mcp; print('MCP imported successfully')"
echo.
echo Testing server imports...
python -c "import mcp.server.stdio; import mcp.types; print('All imports successful')"
pause
