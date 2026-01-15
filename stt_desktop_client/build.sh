#!/bin/bash

# Install PyInstaller
pip install pyinstaller

# Build for current platform
pyinstaller \
  --onefile \
  --windowed \
  --name "STT-Recorder" \
  --add-data "src:src" \
  --hidden-import PyQt6 \
  --hidden-import sounddevice \
  src/main.py

# Check if build succeeded and install desktop shortcuts
if [ $? -eq 0 ]; then
    echo "Build successful! Installing desktop shortcuts..."
    bash install_shortcuts.sh
else
    echo "Build failed. Skipping desktop shortcut installation."
    exit 1
fi

# Output in dist/STT-Recorder (or .exe on Windows)
