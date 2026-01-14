@echo off
REM =============================================================================
REM STT for Claude Code - Setup Script Launcher for Windows
REM =============================================================================
REM This batch file launches the PowerShell setup script
REM =============================================================================

echo.
echo ==============================================================================
echo   STT for Claude Code - Automated Setup
echo ==============================================================================
echo.

REM Check if PowerShell is available
where powershell >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PowerShell is not available on this system.
    echo Please install PowerShell or run setup.ps1 manually.
    pause
    exit /b 1
)

REM Launch PowerShell with the setup script
echo Launching PowerShell setup script...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Setup script encountered an error. Please check the output above.
    pause
    exit /b 1
)

pause
