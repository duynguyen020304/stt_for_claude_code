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

REM Prefer PowerShell 7 (pwsh) if available, otherwise fall back to Windows PowerShell
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%setup.ps1"
set "PSH_EXE="

where pwsh >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PSH_EXE=pwsh"
) else (
    where powershell >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PSH_EXE=powershell"
    )
)

if "%PSH_EXE%"=="" (
    echo ERROR: PowerShell is not available on this system.
    echo Please install PowerShell or run setup.ps1 manually.
    pause
    exit /b 1
)

REM Launch PowerShell with the setup script from its directory to ensure correct relative paths
pushd "%SCRIPT_DIR%" >nul
echo Launching PowerShell setup script with %PSH_EXE%...
echo.

%PSH_EXE% -NoLogo -ExecutionPolicy Bypass -File .\setup.ps1
set "EXITCODE=%ERRORLEVEL%"
popd >nul

if %EXITCODE% NEQ 0 (
    exit /b %EXITCODE%
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Setup script encountered an error. Please check the output above.
    pause
    exit /b 1
)

pause
