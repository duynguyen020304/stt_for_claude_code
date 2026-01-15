#!/bin/bash
# =============================================================================
# STT for Claude Code - Automated Setup Script for Linux/macOS
# =============================================================================
# This script automates:
# - Python 3.12 installation check
# - Virtual environment creation
# - Dependency installation (server & client)
# - System dependencies (PortAudio)
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.12"
VENV_DIR=".venv"
REQUIREMENTS_SERVER="stt_server/requirements.txt"
REQUIREMENTS_CLIENT="stt_desktop_client/requirements.txt"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_python_version() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

        print_info "Found Python $PYTHON_VERSION"

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
            print_success "Python version is compatible (>= 3.12)"
            PYTHON_CMD="python3"
            return 0
        else
            print_warning "Python version is less than 3.12, but may still work"
            PYTHON_CMD="python3"
            return 0
        fi
    else
        print_error "Python 3 is not installed"
        return 1
    fi
}

install_python() {
    print_header "Installing Python 3.12"

    if [ "$(uname -s)" = "Linux" ]; then
        if [ -f /etc/debian_version ]; then
            # Debian/Ubuntu
            print_info "Detected Debian/Ubuntu-based system"

            # Check if deadsnakes PPA is already added
            if ! apt-cache policy | grep -q "deadsnakes/ppa"; then
                print_info "Adding deadsnakes PPA for Python 3.12..."
                sudo apt-get update
                sudo apt-get install -y software-properties-common
                sudo add-apt-repository -y ppa:deadsnakes/ppa
            fi

            sudo apt-get update
            sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
            print_success "Python 3.12 installed successfully"

        elif [ -f /etc/redhat-release ]; then
            # RHEL/CentOS/Fedora
            print_info "Detected Red Hat/Fedora-based system"

            if [ -f /etc/fedora-release ]; then
                sudo dnf install -y python3.12 python3.12-pip python3.12-devel
            else
                sudo dnf install -y python3.12 python3.12-pip python3.12-devel || \
                sudo yum install -y python3.12 python3.12-pip python3.12-devel
            fi
            print_success "Python 3.12 installed successfully"

        elif [ -f /etc/arch-release ]; then
            # Arch Linux
            print_info "Detected Arch Linux system"
            sudo pacman -S --noconfirm python python-pip
            print_success "Python installed successfully"

        else
            print_error "Unsupported Linux distribution"
            print_info "Please install Python 3.12 manually"
            return 1
        fi
    elif [ "$(uname -s)" = "Darwin" ]; then
        # macOS
        print_info "Detected macOS system"

        if command -v brew &> /dev/null; then
            brew install python@3.12
            print_success "Python 3.12 installed via Homebrew"
        else
            print_error "Homebrew not found. Please install it first:"
            print_info "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            return 1
        fi
    fi

    # Re-check after installation
    check_python_version
}

install_system_dependencies() {
    print_header "Installing System Dependencies"

    if [ "$(uname -s)" = "Linux" ]; then
        if [ -f /etc/debian_version ]; then
            # Debian/Ubuntu
            print_info "Installing build tools, PortAudio, and FFmpeg..."
            sudo apt-get update -qq
            sudo apt-get install -y build-essential libportaudio2 ffmpeg python3-pyaudio python3.12-venv python3.12-dev libevdev-dev portaudio19-dev

        elif [ -f /etc/redhat-release ]; then
            # RHEL/CentOS/Fedora
            print_info "Installing build tools, PortAudio, and FFmpeg..."
            if [ -f /etc/fedora-release ]; then
                sudo dnf groupinstall -y "Development Tools"
                sudo dnf install -y portaudio-devel ffmpeg python3-pyaudio
            else
                sudo dnf groupinstall -y "Development Tools" || \
                sudo yum groupinstall -y "Development Tools"
                sudo dnf install -y portaudio-devel ffmpeg python3-pyaudio python3.12-devel portaudio-devel || \
                sudo yum install -y portaudio-devel ffmpeg python3-pyaudio python3.12-devel portaudio-devel
            fi

        elif [ -f /etc/arch-release ]; then
            # Arch Linux
            print_info "Installing PortAudio and FFmpeg..."
            sudo pacman -S --noconfirm portaudio ffmpeg python-pyaudio
        fi

        print_success "System dependencies installed"

    elif [ "$(uname -s)" = "Darwin" ]; then
        # macOS
        print_info "Installing PortAudio and FFmpeg..."
        brew install portaudio ffmpeg
        print_success "System dependencies installed"
    fi
}

create_venv() {
    print_header "Setting Up Virtual Environment"

    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists at $VENV_DIR"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            print_info "Using existing virtual environment"
            return 0
        fi
    fi

    print_info "Creating virtual environment at $VENV_DIR..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    print_success "Virtual environment created"
}

activate_venv() {
    print_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    print_success "Virtual environment activated"
}

upgrade_pip() {
    print_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    print_success "pip upgraded"
}

install_dependencies() {
    print_header "Installing Python Dependencies"

    # Install Sherpa-ONNX server dependencies (recommended)
    print_info "Installing Sherpa-ONNX server dependencies..."
    if [ -f "$REQUIREMENTS_SERVER" ]; then
        # Install core dependencies only (Sherpa-ONNX)
        pip install fastapi uvicorn[standard] python-multipart "numpy<2" pydub sherpa-onnx huggingface-hub requests websockets
        print_success "Sherpa-ONNX server dependencies installed"
    else
        print_error "Requirements file not found: $REQUIREMENTS_SERVER"
    fi

    # Install client dependencies
    print_info "Installing desktop client dependencies..."
    if [ -f "$REQUIREMENTS_CLIENT" ]; then
        pip install -r "$REQUIREMENTS_CLIENT"
        print_success "Desktop client dependencies installed"
    else
        print_error "Requirements file not found: $REQUIREMENTS_CLIENT"
    fi
}

install_optional_dependencies() {
    echo
    read -p "Do you want to install ChunkFormer server dependencies? (requires PyTorch) [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installing ChunkFormer dependencies (CPU-only)..."
        pip install chunkformer torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        print_success "ChunkFormer dependencies installed"
    fi

    echo
    read -p "Do you want to install Parakeet server dependencies? (requires NeMo, English-only) [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installing Parakeet dependencies..."
        pip install nemo-toolkit[asr] librosa soundfile
        print_success "Parakeet dependencies installed"
    fi

    echo
    read -p "Do you want to enable CUDA support for Sherpa-ONNX? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installing Sherpa-ONNX with CUDA support..."
        pip uninstall sherpa-onnx -y
        pip install sherpa-onnx --extra-index-url https://pypi.nvidia.com
        print_success "Sherpa-ONNX CUDA support enabled"
    fi
}

print_completion_message() {
    print_header "Setup Complete!"

    echo
    echo -e "${GREEN}Environment is ready to use!${NC}"
    echo
    echo "To activate the virtual environment (from the project root), run:"
    echo -e "  ${YELLOW}source $VENV_DIR/bin/activate${NC}"
    echo "If you are inside stt_desktop_client/src, use:"
    echo -e "  ${YELLOW}source ../$VENV_DIR/bin/activate${NC}"
    echo
    echo "To start the Sherpa-ONNX server (recommended):"
    echo -e "  ${YELLOW}python stt_server/server_sherpa_onnx.py${NC}"
    echo
    echo "To start the desktop client:"
    echo -e "  ${YELLOW}cd stt_desktop_client/src && python main.py${NC}"
    echo
    echo "API documentation will be available at: http://localhost:8000/docs"
    echo
}

# =============================================================================
# Main Setup Flow
# =============================================================================

main() {
    print_header "STT for Claude Code - Automated Setup"

    # Change to script directory
    cd "$(dirname "$0")"

    # Check Python version
    if ! check_python_version; then
        echo
        read -p "Do you want to install Python 3.12 automatically? [Y/n]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            if ! install_python; then
                print_error "Failed to install Python. Please install manually and re-run this script."
                exit 1
            fi
        else
            print_error "Python 3.12 is required. Please install it manually and re-run this script."
            exit 1
        fi
    fi

    # Install system dependencies
    install_system_dependencies

    # Create virtual environment
    create_venv

    # Activate virtual environment
    activate_venv

    # Upgrade pip
    upgrade_pip

    # Install dependencies
    install_dependencies

    # Optional dependencies
    install_optional_dependencies

    # Print completion message
    print_completion_message
}

# Run main function
main
