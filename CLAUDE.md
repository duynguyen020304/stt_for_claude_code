# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Speech-to-Text (STT) API service** built with FastAPI that provides audio transcription using the ChunkFormer ASR model, optimized for Vietnamese language transcription. The service accepts audio files via HTTP POST or WebSocket and returns transcribed text with timestamps.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, ChunkFormer (khanhld/chunkformer-ctc-large-vie), PyTorch (CPU-only)

## Development Commands

**Start the server:**

```bash
python stt_server/server.py
# Or: python stt_server/start_server.py
```

**Install dependencies:**

```bash
pip install -r stt_server/requirements.txt
```

**Test transcription:**

```bash
curl -X POST "http://localhost:8000/transcribe" -F "audio=@audio_samples/sample_0000.wav"
```

**Interactive API documentation:** `http://localhost:8000/docs`

## Architecture

### ChunkFormerService (Singleton Pattern)

The core service is implemented as a singleton in `stt_server/server.py` that manages the ASR model lifecycle:

- **Lazy Loading:** Model loads on first request to reduce startup time
- **Thread-safe initialization:** Uses asyncio for concurrent safety
- **Device auto-detection:** Automatically detects and uses GPU if available, otherwise CPU
- **Long-form audio:** Uses `endless_decode()` for transcribing audio up to 4 hours

### Request Processing Flow

```
Client Upload → Temp File Creation → Format Conversion (if needed)
→ ChunkFormerService.transcribe() → Model.endless_decode()
→ JSON Response → Cleanup
```

### Configuration (stt_server/server.py, lines 44-70)

Key parameters:

- `CHUNKFORMER_MODEL = "khanhld/chunkformer-ctc-large-vie"` - Model identifier
- `CHUNK_SIZE = 64` - Audio chunk size for processing
- `LEFT_CONTEXT_SIZE = 128` / `RIGHT_CONTEXT_SIZE = 128` - Context windows
- `TOTAL_BATCH_DURATION = 14400` - Max batch duration (4 hours)

### Endpoints

- `GET /` - API information
- `GET /health` - Health check and model loading status
- `POST /transcribe` - File upload transcription
- `WS /transcribe/ws` - WebSocket streaming transcription

## Important Implementation Details

### Audio Format Handling

The service auto-converts non-WAV formats (MP3, M4A, FLAC, OGG) to WAV using pydub before transcription.

### CPU/GPU Handling

The service sets `CUDA_VISIBLE_DEVICES=""` environment variable to force CPU-only mode by default. This prevents `OSError: libtorch_cuda.so` errors when torch is compiled with CUDA but no GPU is available. To enable GPU, modify the environment setup in `stt_server/start_server.py` or `stt_server/server.py`.

### Resource Cleanup

All temporary files created during upload are cleaned up using try/finally blocks.

### Known Issues and Solutions

If you encounter `OSError: libtorch_cuda.so` or CUDA-related errors:

```bash
pip uninstall torchaudio -y
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## Project Structure

```
.
├── stt_server/           # Server package
│   ├── __init__.py
│   ├── server_chunkformer_model.py         # FastAPI server with ChunkFormerService
│   └── requirements.txt  # Server dependencies
├── audio_samples/        # Test audio files (Vietnamese WAV)
├── stt_desktop_client/   # Desktop client application
│   └── src/
│       ├── main.py           # Entry point
│       ├── tray_app.py       # PyQt6 system tray UI
│       ├── audio_recorder.py # Audio recording with ring buffer
│       ├── stt_client.py     # HTTP client for STT server
│       └── hotkey_manager.py # Global hotkey support
```

---

## Desktop Client

The desktop client (`stt_desktop_client/`) is a PyQt6-based system tray application that provides quick audio transcription with global hotkey support.

### Tech Stack

Python 3.12, PyQt6, sounddevice, numpy, pynput, requests

### Starting the Desktop Client

```bash
cd stt_desktop_client/src && python main.py
# Optional: Specify server URL or hotkey
python main.py --server http://localhost:8000 --hotkey <ctrl>+<alt>+r
```

### Features

- **Global hotkey recording** (default: `Ctrl+Alt+R`)
- **System tray notifications** for transcription results
- **Auto-copy to clipboard** - Transcribed text is automatically copied
- **30-second max recording** with ring buffer

### KDE Plasma Wayland Clipboard Fix

**Issue:** On KDE Plasma with Wayland, the clipboard functionality does not work with Qt6's native Wayland backend due to known bugs in KDE Klipper and Qt6 Wayland integration.

**Solution:** The client forces Qt to use the XCB (X11) backend via XWayland for reliable clipboard support.

**Implementation:** (`stt_desktop_client/src/tray_app.py`, lines 85-88)
```python
# Force Qt to use XCB backend on Linux for better clipboard support
# This works around KDE Plasma Wayland clipboard bugs
if sys.platform.startswith('linux'):
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
```

This workaround is necessary because:
1. Qt6's native Wayland clipboard has timing and ownership issues
2. KDE Klipper may not properly sync with Qt Wayland apps
3. XWayland provides stable clipboard support via the X11 protocol

### Desktop Client Architecture

**Key Components:**

- **TrayApplication** (`tray_app.py`) - Main UI and orchestration
- **AudioRecorder** (`audio_recorder.py`) - Real-time audio recording
- **STTClient** (`stt_client.py`) - HTTP client for server communication
- **GlobalHotkeyManager** (`hotkey_manager.py`) - Cross-platform hotkeys

**Signal Flow:**
```
Hotkey Press → start_recording() → AudioRecorder.start()
Hotkey Press → stop_recording() → Save WAV → STTClient.transcribe_file()
→ result_ready signal → on_transcription_result() → Clipboard + Notification
```
