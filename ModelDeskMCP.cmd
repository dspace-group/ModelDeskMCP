@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher 'py' was not found on PATH.
    exit /b 1
)

py -3.14 -m modeldesk_mcp.server %*
exit /b %ERRORLEVEL%
