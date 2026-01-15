# STT Desktop Client

Cross-platform desktop audio recorder with global hotkey support for Speech-to-Text transcription.

## Features

- **Global Hotkey**: Press `Ctrl+Alt+R` to start/stop recording
- **System Tray**: Minimal UI running in system tray
- **Auto-transcription**: Sends audio to STT server and copies text to clipboard
- **Cross-platform**: Works on Windows, Linux (X11), and macOS
- **Desktop Integration**: Install as a desktop application with icon support (Linux)

## Installation

### Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# For Linux: Install PortAudio development headers
sudo apt-get install libportaudio2  # Debian/Ubuntu
sudo dnf install portaudio-devel     # Fedora
```

### Desktop Integration (Linux)

Install the application as a desktop shortcut with proper icon integration:

```bash
# Run the installation script (no sudo required)
cd stt_desktop_client
./install_shortcuts.sh

# Force overwrite if already installed
./install_shortcuts.sh --force
```

This installs:
- Desktop entry file to `~/.local/share/applications/`
- Icons to `~/.local/share/icons/hicolor/`
- Makes the app available in your application launcher

## Usage

### Running from Source

```bash
# Run the application (requires STT server running)
python src/main.py

# Custom server URL
python src/main.py --server http://192.168.1.100:8000

# Custom hotkey
python src/main.py --hotkey "<ctrl>+<shift>+t"
```

### Using Desktop Shortcut (Linux)

After running the installation script, launch STT Recorder from:

**KDE Plasma:**
1. Open Application Launcher (right-click or press Meta key)
2. Search for "STT Recorder" or "Recorder"
3. Click to launch, or drag to desktop/taskbar for quick access

**GNOME:**
1. Press Super key (Windows key) or click Activities overview
2. Type "STT" or "Recorder" in the search bar
3. Click "STT Recorder" to launch
4. Right-click → "Add to Favorites" for dock access

**Other Desktop Environments:**
- The application will appear in your desktop environment's application menu under "Audio" or "Utilities"

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

## Troubleshooting

### Desktop shortcut not appearing after installation

**Symptom:** Application doesn't show up in launcher after running `install_shortcuts.sh`

**Solutions:**
1. **Clear desktop database cache:**
   ```bash
   rm ~/.cache/desktop-entry-database*
   update-desktop-database ~/.local/share/applications
   ```

2. **Verify installation:**
   ```bash
   ls ~/.local/share/applications/stt-recorder.desktop
   ls ~/.local/share/icons/hicolor/*/apps/stt-recorder.*
   ```

3. **Log out and back in** - Some desktop environments only reload applications on session start

4. **KDE-specific:** Right-click application launcher → "Edit Applications" → verify "Audio" category

5. **GNOME-specific:** Run `gtk-launch stt-recorder` to test if desktop file is valid

### Application won't start from desktop shortcut

**Symptom:** Clicking the desktop shortcut does nothing

**Solutions:**
1. **Check if executable exists:**
   - The desktop file expects `STT-Recorder` in your PATH
   - Either add `dist/` to PATH or run from source with `python src/main.py`

2. **Verify desktop file is executable:**
   ```bash
   chmod +x ~/.local/share/applications/stt-recorder.desktop
   ```

3. **Test from command line:**
   ```bash
   gtk-launch stt-recorder
   ```

4. **Check desktop file for errors:**
   ```bash
   desktop-file-validate ~/.local/share/applications/stt-recorder.desktop
   ```

### Icons not displaying

**Symptom:** Application shows default icon instead of custom microphone icon

**Solutions:**
1. **Reinstall icons:**
   ```bash
   ./install_shortcuts.sh --force
   ```

2. **Clear icon cache:**
   ```bash
   rm -rf ~/.cache/icon-cache.kcache
   gtk-update-icon-cache ~/.local/share/icons/hicolor/ 2>/dev/null || true
   ```

3. **Manually copy icons (fallback):**
   ```bash
   cp icons/stt-recorder.svg ~/.local/share/icons/
   cp icons/stt-recorder-*.png ~/.local/share/icons/
   ```

## Server

Make sure the STT server is running before starting the client:
```bash
python server.py  # From parent directory
```
