# STT Desktop Client

Cross-platform desktop audio recorder with global hotkey support for Speech-to-Text transcription.

## Features

- **Global Hotkey**: Press `Ctrl+Alt+R` to start/stop recording
- **System Tray**: Minimal UI running in system tray
- **Auto-transcription**: Sends audio to STT server and copies text to clipboard
- **Cross-platform**: Works on Windows, Linux (X11), and macOS

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# For Linux: Install PortAudio development headers
sudo apt-get install libportaudio2  # Debian/Ubuntu
sudo dnf install portaudio-devel     # Fedora
```

## Usage

```bash
# Run the application (requires STT server running)
python src/main.py

# Custom server URL
python src/main.py --server http://192.168.1.100:8000

# Custom hotkey
python src/main.py --hotkey "<ctrl>+<shift>+t"
```

## Building Executable

```bash
chmod +x build.sh
./build.sh
```

Output will be in `dist/STT-Recorder` (or `STT-Recorder.exe` on Windows).

## Platform Notes

### Auto-Paste
The auto-paste feature simulates the standard paste keystroke:
- **Windows/Linux**: Ctrl+V
- **macOS**: Cmd+V

The delay gives you time to switch to your target application before the paste occurs.

### Linux (Wayland)
Global hotkeys have limited support on Wayland. Consider:
- Using XWayland
- Running with `XDG_SESSION_TYPE=x11`
- Using compositor-specific DBus APIs

### Linux Permissions
No sudo required for global hotkeys on X11.

## Server

Make sure the STT server is running before starting the client:
```bash
python server.py  # From parent directory
```
