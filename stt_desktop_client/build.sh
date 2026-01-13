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

# Output in dist/STT-Recorder (or .exe on Windows)
