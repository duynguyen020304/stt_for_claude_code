# =============================================================================
# STT for Claude Code - Automated Setup Script for Windows
# =============================================================================
# This script automates:
# - Python 3.12 installation check
# - Virtual environment creation
# - Dependency installation (server & client)
# =============================================================================

#Requires -Version 5.1

# Configuration
$ErrorActionPreference = "Stop"
$PYTHON_MIN_VERSION = "3.12"
$VENV_DIR = ".venv"
$REQUIREMENTS_SERVER = "stt_server\requirements.txt"
$REQUIREMENTS_CLIENT = "stt_desktop_client\requirements.txt"

# =============================================================================
# Helper Functions
# =============================================================================

function Write-Header {
    param([string]$Message)
    $separator = "============================================================"
    Write-Host "`n$separator" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "$separator`n" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Get-ScriptRoot {
    $candidates = @($PSScriptRoot, $PSCommandPath, ($MyInvocation.MyCommand.Path))
    foreach ($candidate in $candidates) {
        if ($candidate) {
            return (Split-Path -Parent $candidate)
        }
    }

    Write-Warning "Could not determine script path automatically; using current directory"
    return (Get-Location)
}

function Refresh-Path {
    try {
        $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")

        if ($machinePath -or $userPath) {
            $env:Path = ($machinePath, $userPath -join ";").Trim(";")
            Write-Info "Refreshed PATH from system and user scopes"
        }
    }
    catch {
        Write-Warning "Could not refresh PATH; open a new terminal if new tools are missing"
    }
}

function Test-PythonVersion {
    try {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCmd) {
            $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
        }

        if ($null -ne $pythonCmd) {
            $versionOutput = & $pythonCmd --version 2>&1
            if ($versionOutput -match "(\d+)\.(\d+)\.(\d+)") {
                $major = [int]$matches[1]
                $minor = [int]$matches[2]

                Write-Info "Found Python $major.$minor.$($matches[3])"

                if ($major -eq 3 -and $minor -ge 12) {
                    Write-Success "Python version is compatible (>= 3.12)"
                    return @{ Command = $pythonCmd.Source; Compatible = $true }
                } else {
                    Write-Warning "Python version is less than 3.12, but may still work"
                    return @{ Command = $pythonCmd.Source; Compatible = $true }
                }
            }
        }
        return @{ Command = $null; Compatible = $false }
    }
    catch {
        return @{ Command = $null; Compatible = $false }
    }
}

function Install-Python {
    Write-Header "Installing Python 3.12"

    try {
        $wingetCmd = Get-Command winget -ErrorAction Stop
    }
    catch {
        $wingetCmd = $null
    }

    if ($null -eq $wingetCmd) {
        Write-Warning "winget is not available. Please install Python 3.12 manually from: https://www.python.org/downloads/"
        return $false
    }

    Write-Info "Installing Python 3.12 via winget..."
    winget install --id=Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    $wingetExitCode = $LASTEXITCODE

    # Refresh PATH so a newly installed python/py is discoverable in this session
    Refresh-Path
    $postInstallCheck = Test-PythonVersion

    if ($postInstallCheck.Compatible) {
        if ($wingetExitCode -ne 0) {
            Write-Warning "winget reported exit code $wingetExitCode, but Python is available; continuing"
        }
        else {
            Write-Success "Python 3.12 installed via winget"
        }
        return $true
    }

    if ($wingetExitCode -eq 3010 -or $wingetExitCode -eq 1641) {
        Write-Warning "winget reports install completed but requires a restart (exit code $wingetExitCode). Restart your terminal or log off/on, then re-run setup."
        return $false
    }

    Write-Error "Failed to install Python 3.12 via winget (exit code $wingetExitCode). Please install manually from https://www.python.org/downloads/."
    return $false
}

function Install-FFmpeg {
    Write-Header "Installing FFmpeg"

    $ffmpegPath = "ffmpeg.exe"
    $ffmpegInstalled = $false

    # Check if ffmpeg is already in PATH
    try {
        $null = Get-Command ffmpeg -ErrorAction Stop
        Write-Success "FFmpeg is already installed"
        $ffmpegInstalled = $true
    }
    catch {
        # Not in PATH, check if we can use winget
        Write-Info "Attempting to install FFmpeg via winget..."

        try {
            winget install --id=Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
            Write-Success "FFmpeg installed via winget"
            Write-Warning "You may need to restart your terminal for FFmpeg to be available in PATH"
            $ffmpegInstalled = $true
        }
        catch {
            Write-Warning "Could not install FFmpeg via winget"
            Write-Info "Audio format conversion (MP3, M4A) may not work properly"
            Write-Info "To install FFmpeg manually, visit: https://ffmpeg.org/download.html"
        }
    }

    return $ffmpegInstalled
}

function New-VirtualEnvironment {
    Write-Header "Setting Up Virtual Environment"

    if (Test-Path $VENV_DIR) {
        Write-Warning "Virtual environment already exists at $VENV_DIR"
        $response = Read-Host "Do you want to recreate it? (y/N)"

        if ($response -eq 'y' -or $response -eq 'Y') {
            Write-Info "Removing existing virtual environment..."
            Remove-Item -Path $VENV_DIR -Recurse -Force
        }
        else {
            Write-Info "Using existing virtual environment"
            return
        }
    }

    Write-Info "Creating virtual environment at $VENV_DIR..."
    & python -m venv $VENV_DIR

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Virtual environment created"
    }
    else {
        Write-Error "Failed to create virtual environment"
        exit 1
    }
}

function Install-Dependencies {
    Write-Header "Installing Python Dependencies"

    $pipScript = if (Test-Path "$VENV_DIR\Scripts\pip.exe") {
        "$VENV_DIR\Scripts\pip.exe"
    }
    else {
        "$VENV_DIR\Scripts\pip3.exe"
    }

    # Upgrade pip first
    Write-Info "Upgrading pip..."
    & $pipScript install --upgrade pip setuptools wheel
    Write-Success "pip upgraded"

    # Install Sherpa-ONNX server dependencies (recommended)
    Write-Info "Installing Sherpa-ONNX server dependencies..."
    & $pipScript install fastapi uvicorn[standard] python-multipart numpy pydub sherpa-onnx huggingface-hub requests websockets

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Sherpa-ONNX server dependencies installed"
    }
    else {
        Write-Error "Failed to install some server dependencies"
    }

    # Install client dependencies
    Write-Info "Installing desktop client dependencies..."

    # PyAudio needs special handling on Windows
    Write-Info "Installing PyAudio (may require pre-built wheel)..."
    try {
        & $pipScript install pyaudio
    }
    catch {
        Write-Warning "Standard PyAudio installation failed, trying pre-built wheel..."
        # Try to install from Christoph Gohlke's archive (commonly used for Windows PyAudio wheels)
        $pythonVersion = & python --version
        if ($pythonVersion -match "3\.(\d+)") {
            $minorVersion = $matches[1]
            Write-Warning "You may need to download PyAudio wheel manually from:"
            Write-Info "  https://github.com/intxcc/pyaudio_portaudio/releases"
            Write-Info "  Or use: pip install pipwin && pipwin install pyaudio"
        }
    }

    # Install other client dependencies
    $clientDeps = @(
        "PyQt6",
        "sounddevice",
        "numpy",
        "soundfile",
        "pynput",
        "requests",
        "websockets"
    )

    foreach ($dep in $clientDeps) {
        Write-Info "Installing $dep..."
        & $pipScript install $dep
    }

    Write-Success "Desktop client dependencies installed"
}

function Install-OptionalDependencies {
    Write-Header "Optional Dependencies"

    $pipScript = if (Test-Path "$VENV_DIR\Scripts\pip.exe") {
        "$VENV_DIR\Scripts\pip.exe"
    }
    else {
        "$VENV_DIR\Scripts\pip3.exe"
    }

    $response = Read-Host "Do you want to install ChunkFormer server dependencies? (requires PyTorch) [y/N]"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Info "Installing ChunkFormer dependencies (CPU-only)..."
        & $pipScript install chunkformer torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        Write-Success "ChunkFormer dependencies installed"
    }

    $response = Read-Host "Do you want to install Parakeet server dependencies? (requires NeMo, English-only) [y/N]"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Info "Installing Parakeet dependencies..."
        & $pipScript install nemo-toolkit[asr] librosa soundfile
        Write-Success "Parakeet dependencies installed"
    }

    $response = Read-Host "Do you want to enable CUDA support for Sherpa-ONNX? [y/N]"
    if ($response -eq 'y' -or $response -eq 'Y') {
        Write-Info "Installing Sherpa-ONNX with CUDA support..."
        & $pipScript uninstall sherpa-onnx -y
        & $pipScript install sherpa-onnx --extra-index-url https://pypi.nvidia.com
        Write-Success "Sherpa-ONNX CUDA support enabled"
    }
}

function Show-CompletionMessage {
    Write-Header "Setup Complete!"

    Write-Host "`nEnvironment is ready to use!`n" -ForegroundColor Green
    Write-Host "To activate the virtual environment, run:" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\Activate.ps1`n" -ForegroundColor Yellow
    Write-Host "Or for CMD:" -ForegroundColor White
    Write-Host "  .\.venv\Scripts\activate.bat`n" -ForegroundColor Yellow
    Write-Host "To start the Sherpa-ONNX server (recommended):" -ForegroundColor White
    Write-Host "  python stt_server\server_sherpa_onnx.py`n" -ForegroundColor Yellow
    Write-Host "To start the desktop client:" -ForegroundColor White
    Write-Host "  cd stt_desktop_client\src && python main.py`n" -ForegroundColor Yellow
    Write-Host "API documentation will be available at: http://localhost:8000/docs`n"
}

function Set-ExecutionPolicyIfNeeded {
    # Check if running PowerShell and if execution policy allows scripts
    if ($PSVersionTable.PSVersion.Major -ge 3) {
        $currentPolicy = Get-ExecutionPolicy -Scope CurrentUser

        if ($currentPolicy -eq "Restricted" -or $currentPolicy -eq "Undefined") {
            Write-Warning "PowerShell execution policy is restricted; attempting to set to RemoteSigned for CurrentUser"
            try {
                Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction Stop
                Write-Success "Execution policy set to RemoteSigned for CurrentUser"
            }
            catch {
                Write-Warning "Automatic Set-ExecutionPolicy failed: $($_.Exception.Message)"
                Write-Info "Run manually: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
                Write-Info "Or use CMD with: .\\.venv\\Scripts\\activate.bat"
            }
        }
        else {
            Write-Info "Execution policy already allows scripts (CurrentUser: $currentPolicy)"
        }
    }
}

# =============================================================================
# Main Setup Flow
# =============================================================================

function Main {
    Write-Header "STT for Claude Code - Automated Setup (Windows)"

    # Change to script directory
    $scriptPath = Get-ScriptRoot
    Set-Location $scriptPath

    # Anchor the virtual environment path to the script's directory to avoid creating it elsewhere
    $script:VENV_DIR = Join-Path $scriptPath ".venv"

    # Check Python version
    $pythonInfo = Test-PythonVersion

    if (-not $pythonInfo.Compatible) {
        $response = Read-Host "`nDo you want to install Python 3.12 automatically? [Y/n]"
        if ($response -ne 'n' -and $response -ne 'N') {
            if (-not (Install-Python)) {
                Write-Error "Python 3.12 is required. Please install it manually and re-run this script."
                exit 1
            }
            # Refresh python version info after installation attempt
            Refresh-Path
            $pythonInfo = Test-PythonVersion
            if (-not $pythonInfo.Compatible) {
                Write-Error "Python installation via winget did not complete successfully. Please install manually and re-run."
                exit 1
            }
        }
        else {
            Write-Error "Python 3.12 is required. Please install it manually and re-run this script."
            exit 1
        }
    }

    # Install FFmpeg (optional but recommended)
    Install-FFmpeg

    # Create virtual environment
    New-VirtualEnvironment

    # Install dependencies
    Install-Dependencies

    # Optional dependencies
    Install-OptionalDependencies

    # Check execution policy
    Set-ExecutionPolicyIfNeeded

    # Print completion message
    Show-CompletionMessage
}

# Run main function
Main
