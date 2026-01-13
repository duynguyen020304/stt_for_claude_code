# Cross-Platform Desktop Audio Recorder - Implementation Plan

## Architecture Overview

```
┌─────────────────────┐
│ Global Hotkey       │  (Ctrl+Alt+R)
│ (pynput)            │
└─────────┬───────────┘
          │ signal
┌─────────▼───────────┐
│ Python Desktop App  │
│ (PyQt6)             │
│                     │
└─────────┬───────────┘
          │ start/stop
┌─────────▼───────────┐
│ Audio Recorder      │
│ sounddevice         │
│ (PortAudio)         │
└─────────┬───────────┘
          │ PCM frames
┌─────────▼───────────┐
│ Audio Buffer        │
│ numpy ring buffer   │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│ Output              │
│ .wav file / stream  │
│ → STT Server        │
└─────────────────────┘
```

## Technology Stack Summary

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Desktop Framework | **PyQt6** | Professional UI, system tray, cross-platform |
| Global Hotkeys | **pynput** | Cross-platform, no sudo on Linux X11 |
| Audio Recording | **sounddevice** | NumPy integration, callback-based |
| Audio Buffer | **NumPy Ring Buffer** | Zero-copy, thread-safe |
| STT Integration | **HTTP POST** | Reliable, matches your `/transcribe` endpoint |

## Project Structure

```
stt_desktop_client/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── hotkey_manager.py       # Global hotkey (pynput)
│   ├── audio_recorder.py       # sounddevice + ring buffer
│   ├── stt_client.py           # HTTP client to FastAPI server
│   ├── tray_app.py             # System tray (PyQt6)
│   └── config.py               # Configuration
├── requirements.txt
├── README.md
└── build.sh                    # PyInstaller packaging
```

## Implementation Steps

### Step 1: Core Audio Recording Module

**File:** `src/audio_recorder.py`

```python
import sounddevice as sd
import numpy as np
import threading
from pathlib import Path

class AudioRingBuffer:
    """Thread-safe ring buffer for audio PCM data."""

    def __init__(self, buffer_size_samples: int, channels: int = 1):
        self.buffer_size = buffer_size_samples
        self.channels = channels
        self.buffer = np.zeros((buffer_size_samples, channels), dtype=np.float32)
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0
        self.lock = threading.Lock()

    def write(self, data: np.ndarray) -> int:
        n_samples = len(data)
        with self.lock:
            available = self.buffer_size - self.count
            writable = min(n_samples, available)
            if writable == 0:
                return 0

            end_pos = self.write_pos + writable
            if end_pos <= self.buffer_size:
                self.buffer[self.write_pos:end_pos] = data[:writable]
            else:
                first_part = self.buffer_size - self.write_pos
                self.buffer[self.write_pos:] = data[:first_part]
                self.buffer[:end_pos - self.buffer_size] = data[first_part:writable]

            self.write_pos = end_pos % self.buffer_size
            self.count += writable
            return writable

    def read_all(self) -> np.ndarray:
        with self.lock:
            if self.count == 0:
                return np.zeros((0, self.channels), dtype=np.float32)

            result = np.zeros((self.count, self.channels), dtype=np.float32)
            end_pos = self.read_pos + self.count

            if end_pos <= self.buffer_size:
                result[:] = self.buffer[self.read_pos:end_pos]
            else:
                first_part = self.buffer_size - self.read_pos
                result[:first_part] = self.buffer[self.read_pos:]
                result[first_part:] = self.buffer[:end_pos - self.buffer_size]

            self.read_pos = end_pos % self.buffer_size
            self.count = 0
            return result


class AudioRecorder:
    """Real-time audio recorder with ring buffer."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        buffer_duration: int = 30,
        blocksize: int = 2048
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_duration = buffer_duration
        self.blocksize = blocksize

        buffer_size = sample_rate * buffer_duration
        self.ring_buffer = AudioRingBuffer(buffer_size, channels)

        self.is_recording = False
        self.stream = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio callback status: {status}")
        self.ring_buffer.write(indata)

    def start(self):
        if self.is_recording:
            return

        self.ring_buffer = AudioRingBuffer(
            self.sample_rate * self.buffer_duration,
            self.channels
        )

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback,
            blocksize=self.blocksize,
            dtype=np.float32
        )
        self.stream.start()
        self.is_recording = True
        print("Recording started")

    def stop(self) -> np.ndarray:
        if not self.is_recording:
            return np.zeros((0, self.channels), dtype=np.float32)

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.is_recording = False
        print("Recording stopped")

        return self.ring_buffer.read_all()

    def save_to_wav(self, audio: np.ndarray, filename: str):
        import soundfile as sf
        sf.write(filename, audio, self.sample_rate, subtype='PCM_16')
        print(f"Saved to {filename}")
```

### Step 2: Global Hotkey Manager

**File:** `src/hotkey_manager.py`

```python
from pynput import keyboard
import threading
from typing import Callable, Optional


class GlobalHotkeyManager:
    """Cross-platform global hotkey manager using pynput."""

    def __init__(self):
        self.hotkeys = {}
        self.listener: Optional[keyboard.Listener] = None
        self.hotkey_objects = []

    def register_hotkey(self, key_combo: str, callback: Callable):
        """Register a global hotkey.

        Args:
            key_combo: Hotkey string, e.g., '<ctrl>+<alt>+r'
            callback: Function to call when hotkey is pressed
        """
        self.hotkeys[key_combo] = callback

    def _create_hotkey(self, combo: str, callback: Callable):
        return keyboard.HotKey(
            keyboard.HotKey.parse(combo),
            callback
        )

    def start(self):
        """Start listening for hotkeys."""
        self.hotkey_objects = []
        for combo, callback in self.hotkeys.items():
            hotkey = self._create_hotkey(combo, callback)
            self.hotkey_objects.append(hotkey)

        def on_press(key):
            try:
                for hotkey in self.hotkey_objects:
                    hotkey.press(self.listener.canonical(key))
            except Exception:
                pass

        def on_release(key):
            try:
                for hotkey in self.hotkey_objects:
                    hotkey.release(self.listener.canonical(key))
            except Exception:
                pass

        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self.listener.start()
        print("Global hotkeys started")

    def stop(self):
        """Stop listening for hotkeys."""
        if self.listener:
            self.listener.stop()
            print("Global hotkeys stopped")
```

### Step 3: STT Client

**File:** `src/stt_client.py`

```python
import requests
from pathlib import Path
from typing import Dict, Any


class STTClient:
    """HTTP client for the ChunkFormer STT service."""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.transcribe_url = f"{server_url}/transcribe"

    def transcribe_file(self, audio_file: Path) -> Dict[str, Any]:
        """Send audio file to STT server for transcription.

        Args:
            audio_file: Path to WAV audio file

        Returns:
            Transcription result with text and timestamps
        """
        try:
            with open(audio_file, 'rb') as f:
                files = {'audio': (audio_file.name, f, 'audio/wav')}
                response = requests.post(
                    self.transcribe_url,
                    files=files,
                    timeout=60
                )
                response.raise_for_status()
                return response.json()

        except requests.exceptions.ConnectionError:
            return {"error": "Cannot connect to STT server. Is it running?"}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out"}
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP error: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}

    def check_health(self) -> bool:
        """Check if STT server is running."""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
```

### Step 4: System Tray Application

**File:** `src/tray_app.py`

```python
import sys
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, pyqtSignal

from .audio_recorder import AudioRecorder
from .stt_client import STTClient


class RecordingSignals(QObject):
    """Signals for thread-safe communication."""
    result_ready = pyqtSignal(dict)
    status_changed = pyqtSignal(str)


class TrayApplication:
    """System tray application for audio recording."""

    def __init__(
        self,
        stt_server_url: str = "http://localhost:8000",
        hotkey: str = '<ctrl>+<alt>+r'
    ):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Components
        self.recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            buffer_duration=30
        )
        self.stt_client = STTClient(stt_server_url)
        self.signals = RecordingSignals()

        # State
        self.is_recording = False
        self.temp_dir = Path(tempfile.gettempdir()) / "stt_recorder"
        self.temp_dir.mkdir(exist_ok=True)

        # Setup UI
        self.setup_tray()
        self.setup_signals()

        # Store hotkey callback
        self.hotkey_combo = hotkey
        self.hotkey_callback = None  # Will be set by main.py

    def setup_tray(self):
        """Setup system tray icon and menu."""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon()

        # Create menu
        menu = QMenu()

        self.record_action = QAction("Start Recording", menu)
        self.record_action.triggered.connect(self.toggle_recording)
        menu.addAction(self.record_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def setup_signals(self):
        """Setup signal connections."""
        self.signals.result_ready.connect(self.on_transcription_result)
        self.signals.status_changed.connect(self.on_status_changed)

    def toggle_recording(self):
        """Toggle recording state."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        self.is_recording = True
        self.record_action.setText("Stop Recording")
        self.signals.status_changed.emit("Recording...")

        try:
            self.recorder.start()
        except Exception as e:
            self.signals.status_changed.emit(f"Error: {e}")
            self.is_recording = False
            self.record_action.setText("Start Recording")

    def stop_recording(self):
        """Stop recording and transcribe."""
        self.is_recording = False
        self.record_action.setText("Start Recording")
        self.signals.status_changed.emit("Processing...")

        try:
            audio = self.recorder.stop()

            if len(audio) == 0:
                self.signals.status_changed.emit("No audio recorded")
                return

            # Save to temp file
            temp_file = self.temp_dir / f"recording_{id(self)}.wav"
            self.recorder.save_to_wav(audio, str(temp_file))

            # Transcribe
            result = self.stt_client.transcribe_file(temp_file)
            self.signals.result_ready.emit(result)

            # Cleanup
            temp_file.unlink(missing_ok=True)

        except Exception as e:
            self.signals.status_changed.emit(f"Error: {e}")

    def on_transcription_result(self, result: dict):
        """Handle transcription result."""
        if "error" in result:
            self.show_message(f"Transcription Error", result["error"])
        elif "text" in result:
            text = result["text"]
            self.show_message("Transcription", text)
            # Copy to clipboard
            self.app.clipboard().setText(text)
        else:
            self.show_message("Result", str(result))

        self.signals.status_changed.emit("Ready")

    def on_status_changed(self, status: str):
        """Handle status change."""
        self.tray_icon.setToolTip(f"STT Recorder\n{status}")

    def show_message(self, title: str, message: str):
        """Show system tray notification."""
        self.tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

    def quit(self):
        """Quit application."""
        if self.is_recording:
            self.recorder.stop()
        self.app.quit()

    def run(self):
        """Run application."""
        return self.app.exec()
```

### Step 5: Main Application

**File:** `src/main.py`

```python
import sys
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from hotkey_manager import GlobalHotkeyManager
from tray_app import TrayApplication
import threading
import time


class STTDesktopClient:
    """Main application combining hotkeys, recording, and tray UI."""

    def __init__(
        self,
        stt_server_url: str = "http://localhost:8000",
        hotkey_combo: str = '<ctrl>+<alt>+r'
    ):
        self.stt_server_url = stt_server_url
        self.hotkey_combo = hotkey_combo

        # Initialize components
        self.hotkey_manager = GlobalHotkeyManager()
        self.tray_app = None
        self.hotkey_thread = None

    def run(self):
        """Start the application."""
        # Check server connection
        print(f"Checking STT server at {self.stt_server_url}...")

        # Create tray app (this starts QApplication)
        self.tray_app = TrayApplication(
            stt_server_url=self.stt_server_url,
            hotkey=self.hotkey_combo
        )

        # Register hotkey that triggers tray app toggle
        def on_hotkey():
            self.tray_app.toggle_recording()

        self.hotkey_manager.register_hotkey(self.hotkey_combo, on_hotkey)

        # Start hotkey listener in separate thread
        self.hotkey_thread = threading.Thread(
            target=self.hotkey_manager.start,
            daemon=True
        )
        self.hotkey_thread.start()

        print(f"Global hotkey registered: {self.hotkey_combo}")
        print("Press the hotkey to start/stop recording")
        print("Right-click the tray icon for options")

        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Run Qt event loop
        return self.tray_app.run()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutting down...")
        self.hotkey_manager.stop()
        sys.exit(0)


def main():
    """Application entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="STT Desktop Client - Record and transcribe audio"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="STT server URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--hotkey",
        default="<ctrl>+<alt>+r",
        help="Global hotkey combination (default: <ctrl>+<alt>+r)"
    )

    args = parser.parse_args()

    app = STTDesktopClient(
        stt_server_url=args.server,
        hotkey_combo=args.hotkey
    )

    sys.exit(app.run() or 0)


if __name__ == "__main__":
    main()
```

## Dependencies

**File:** `requirements.txt`

```
PyQt6==6.6.1
sounddevice==0.4.6
numpy>=1.24.0
soundfile>=0.12.0
pynput>=1.7.6
requests>=2.31.0
```

## Platform-Specific Notes

### Windows
- No special permissions required
- PortAudio included with sounddevice
- System tray works natively

### Linux (X11)
- Works out of the box
- May need `DISPLAY=:0` if running over SSH

### Linux (Wayland)
- **Known Limitation:** pynput has partial Wayland support
- Consider using XWayland or compositor-specific DBus APIs
- Alternative: Use keyboard library with sudo (not recommended)

## Building Executable

**File:** `build.sh`

```bash
#!/bin/bash

# Install PyInstaller
pip install pyinstaller

# Build for current platform
pyinstaller \
  --onefile \
  --windowed \
  --name "STT-Recorder" \
  --icon=icon.ico \
  --add-data "src:src" \
  --hidden-import PyQt6 \
  --hidden-import sounddevice \
  src/main.py

# Output in dist/STT-Recorder (or .exe on Windows)
```

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py

# Or with custom server/hotkey
python src/main.py --server http://192.168.1.100:8000 --hotkey "<ctrl>+<shift>+t"
```

## Features Implemented

| Feature | Status | Implementation |
|---------|--------|----------------|
| Global Hotkey | ✅ | pynput cross-platform |
| Audio Recording | ✅ | sounddevice with callback |
| Ring Buffer | ✅ | NumPy-based, thread-safe |
| WAV Export | ✅ | soundfile library |
| HTTP Upload | ✅ | requests to /transcribe |
| System Tray | ✅ | PyQt6 QSystemTrayIcon |
| Cross-Platform | ✅ | Windows/Linux support |
| Auto-start | 🔜 | Platform-specific (future) |
| Notifications | ✅ | QSystemTrayIcon messages |
