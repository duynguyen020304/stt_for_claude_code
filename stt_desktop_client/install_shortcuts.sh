#!/bin/bash

# Installation script for STT Recorder desktop integration
# Installs .desktop file and icons to user-specific XDG directories
# No root/sudo required - uses ~/.local/share/

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# XDG directories
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APPS_DIR="$XDG_DATA_HOME/applications"
ICONS_DIR="$XDG_DATA_HOME/icons/hicolor"

# Force installation without confirmation
FORCE=false
if [[ "$1" == "--force" ]]; then
    FORCE=true
fi

echo "STT Recorder Desktop Integration Installer"
echo "==========================================="
echo ""

# Check if desktop file exists
DESKTOP_FILE="$SCRIPT_DIR/stt-recorder.desktop"
if [[ ! -f "$DESKTOP_FILE" ]]; then
    echo "Error: $DESKTOP_FILE not found!"
    exit 1
fi

# Check if icons directory exists
ICONS_SOURCE="$SCRIPT_DIR/icons"
if [[ ! -d "$ICONS_SOURCE" ]]; then
    echo "Error: $ICONS_SOURCE not found!"
    echo "Please run 'python icons/generate_icons.py' first."
    exit 1
fi

# Create target directories
echo "Creating XDG directories..."
mkdir -p "$APPS_DIR"
mkdir -p "$ICONS_DIR"

# Install desktop file
echo "Installing desktop file to $APPS_DIR..."
TARGET_DESKTOP="$APPS_DIR/stt-recorder.desktop"

if [[ -f "$TARGET_DESKTOP" ]] && [[ "$FORCE" != "true" ]]; then
    echo ""
    echo "Warning: Desktop file already exists at $TARGET_DESKTOP"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

cp "$DESKTOP_FILE" "$TARGET_DESKTOP"
chmod +x "$TARGET_DESKTOP"
echo "Desktop file installed."

# Install icons
echo ""
echo "Installing icons to $ICONS_DIR..."

for SIZE_DIR in "$ICONS_SOURCE"/*/; do
    if [[ -d "$SIZE_DIR" ]]; then
        SIZE=$(basename "$SIZE_DIR")
        TARGET_DIR="$ICONS_DIR/$SIZE"

        # Create target size directory
        mkdir -p "$TARGET_DIR"

        # Copy apps subdirectory if it exists
        if [[ -d "$SIZE_DIR/apps" ]]; then
            mkdir -p "$TARGET_DIR/apps"
            cp -f "$SIZE_DIR/apps"/stt-recorder.* "$TARGET_DIR/apps/" 2>/dev/null || true
            echo "  Installed $SIZE icons"
        fi
    fi
done

# Run update-desktop-database
echo ""
echo "Updating desktop database..."
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    echo "Desktop database updated."
else
    echo "Warning: update-desktop-database not found. Skipping."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Desktop file: $TARGET_DESKTOP"
echo "Icons: $ICONS_DIR"
echo ""
echo "To verify installation:"
echo "  KDE: Look for 'STT Recorder' in the application launcher"
echo "  GNOME: Press Super key and type 'STT' or 'Recorder'"
echo ""
echo "To create a desktop shortcut (KDE):"
echo "  Drag 'STT Recorder' from the launcher to your desktop"
