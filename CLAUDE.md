# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Speech-to-Text (STT) API service** built with FastAPI that provides audio transcription using Vietnamese ASR models. The service supports multiple model backends and accepts audio files via HTTP POST or WebSocket, returning transcribed text with timestamps.

### Available Server Implementations

| Server                        | Model                        | Framework    | Language   | Port | Status                    |
| ----------------------------- | ---------------------------- | ------------ | ---------- | ---- | ------------------------- |
| `server_sherpa_onnx.py`       | Sherpa-ONNX Zipformer Vi     | ONNX Runtime | Vietnamese | 8000 | **Primary** (Recommended) |
| `server_chunkformer_model.py` | ChunkFormer CTC Vi           | PyTorch      | Vietnamese | 8000 | Alternative               |
| `server_parakeet_model.py`    | NVIDIA Parakeet TDT CTC 110M | NeMo         | English    | 8000 | Experimental              |

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Sherpa-ONNX (csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20)

## Development Commands

**Windows setup note:** Run the installer with `pwsh -ExecutionPolicy Bypass -File .\setup.ps1` from the repo root for the most reliable path detection. The `setup.bat` launcher is available as a convenience.

**Start the Sherpa-ONNX server (recommended):**

```bash
python stt_server/server_sherpa_onnx.py
```

**Start the ChunkFormer server (alternative):**

```bash
python stt_server/server_chunkformer_model.py
```

**Start the Parakeet server (experimental, English):**

```bash
python stt_server/server_parakeet_model.py
```

**Install dependencies:**

```bash
# For Sherpa-ONNX server (recommended, CPU-only)
pip install -r stt_server/requirements.txt

# For ChunkFormer server (requires PyTorch)
pip install chunkformer torch torchaudio

# For Parakeet server (requires NeMo)
pip install nemo-toolkit[asr] librosa soundfile
```

**Test transcription:**

```bash
curl -X POST "http://localhost:8000/transcribe" -F "audio=@audio_samples/sample_0000.wav"
```

**Interactive API documentation:** `http://localhost:8000/docs`

## Architecture

### SherpaONNXService (Singleton Pattern)

The recommended service implementation in `stt_server/sherpa_onnx_service.py` manages the ASR model lifecycle:

- **Lazy Loading:** Model loads on first request to reduce startup time
- **Thread-safe initialization:** Uses asyncio for concurrent safety
- **Auto-download:** Downloads model from Hugging Face on first run
- **Configurable:** CPU/CUDA support, configurable threads

**Configuration** (`stt_server/server_sherpa_onnx.py`, lines 29-39):

```python
SHERPA_ONNX_MODEL = "csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20"
MODEL_DIR = "./models/sherpa-onnx-vi"
NUM_THREADS = 4
DEVICE = "cpu"  # Options: "cpu", "cuda"
```

### ChunkFormerService (Alternative)

An alternative service implementation using PyTorch-based ChunkFormer model:

- **Lazy Loading:** Model loads on first request to reduce startup time
- **Thread-safe initialization:** Uses asyncio for concurrent safety
- **Long-form audio:** Uses `endless_decode()` for transcribing audio up to 4 hours

### ParakeetService (Experimental)

An experimental implementation using NVIDIA NeMo's Parakeet TDT CTC 110M model for English transcription:

- **Language:** English only (Vietnamese models use Sherpa-ONNX or ChunkFormer)
- **Lazy Loading:** Model loads on first request to reduce startup time
- **Thread-safe initialization:** Uses asyncio for concurrent safety
- **Long-form audio:** Auto-splits audio longer than 20 minutes into chunks
- **Timestamp estimation:** Uses chunk-based processing for timestamps when enabled
- **CPU/GPU auto-detection:** Automatically detects and uses CUDA if available

**Configuration** (`stt_server/server_parakeet_model.py`, lines 34-41):

```python
PARAKEET_MODEL = "nvidia/parakeet-tdt_ctc-110m"
CHUNK_DURATION_SECONDS = 30  # For timestamp estimation
MAX_AUDIO_DURATION_MINUTES = 20  # Max single pass duration
DEVICE = "cpu"  # Auto-detects CUDA if available
```

### Request Processing Flow

```
Client Upload → Temp File Creation → Format Conversion (if needed)
→ Service.transcribe() → Model Decode → JSON Response → Cleanup
```

### Endpoints

All servers implement identical API endpoints:

- `GET /` - API information
- `GET /health` - Health check and model loading status
- `POST /transcribe` - File upload transcription
- `WS /transcribe/ws` - WebSocket streaming transcription

## Important Implementation Details

### Audio Format Handling

Both servers auto-convert non-WAV formats (MP3, M4A, FLAC, OGG) to WAV using pydub before transcription.

### Model Comparison

| Aspect          | Sherpa-ONNX (Recommended) | ChunkFormer (Alternative)      | Parakeet (Experimental)          |
| --------------- | ------------------------- | ------------------------------ | -------------------------------- |
| Framework       | ONNX Runtime              | PyTorch                        | NeMo                             |
| Language        | Vietnamese                | Vietnamese                     | English                          |
| Model Size      | ~258 MB                   | Larger                         | ~110M parameters                 |
| Dependencies    | sherpa-onnx only          | torch, torchaudio, chunkformer | nemo-toolkit, librosa, soundfile |
| Startup Time    | Fast (small model)        | Slower (large model)           | Moderate                         |
| Inference Speed | Fast (optimized ONNX)     | Moderate                       | Fast (optimized)                 |
| Long-form Audio | Processes entire file     | Supports hours-long audio      | Auto-splits >20min               |
| GPU Support     | CUDA via ONNX             | Native PyTorch CUDA            | Native PyTorch CUDA              |
| Installation    | Simple pip install        | Requires PyTorch setup         | Requires NeMo setup              |

### CPU/GPU Handling

**Sherpa-ONNX Server:** Set `DEVICE = "cuda"` in `server_sherpa_onnx.py` to enable GPU support. For CUDA, install with: `pip install sherpa-onnx --extra-index-url https://pypi.nvidia.com`

**ChunkFormer Server:** The server sets `CUDA_VISIBLE_DEVICES=""` to force CPU-only mode by default. To enable GPU, modify the environment setup.

**Parakeet Server:** Auto-detects CUDA availability on startup. Falls back to CPU if CUDA is not available. To force GPU mode, uncomment line 47 in `server_parakeet_model.py`.

### Resource Cleanup

All temporary files created during upload are cleaned up using try/finally blocks.

### Known Issues and Solutions

**Sherpa-ONNX Model Download:**
On first run, the model (~258 MB) is automatically downloaded from Hugging Face to `./models/sherpa-onnx-vi/`. Ensure you have internet connection and sufficient disk space.

**ChunkFormer CUDA Errors:**
If you encounter `OSError: libtorch_cuda.so` or CUDA-related errors:

```bash
pip uninstall torchaudio -y
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Parakeet NeMo Installation:**
NeMo requires `numpy<2`. If you encounter numpy compatibility issues, ensure you have the correct version installed. The requirements.txt includes `numpy<2` for this reason.

## Project Structure

```
.
├── stt_server/           # Server package
│   ├── __init__.py
│   ├── server_sherpa_onnx.py              # Sherpa-ONNX FastAPI server (recommended)
│   ├── sherpa_onnx_service.py             # Sherpa-ONNX service layer
│   ├── server_chunkformer_model.py        # ChunkFormer FastAPI server (alternative)
│   ├── server_parakeet_model.py           # Parakeet FastAPI server (experimental, English)
│   ├── requirements.txt                   # Server dependencies
│   └── models/
│       └── sherpa-onnx-vi/                # Auto-downloaded Sherpa-ONNX model
├── audio_samples/        # Test audio files (Vietnamese WAV)
├── stt_desktop_client/   # Desktop client application
│   ├── build.sh            # PyInstaller build script
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

**Install dependencies:**

```bash
pip install -r stt_desktop_client/requirements.txt
```

**Linux PortAudio dependency:**

```bash
sudo apt-get install libportaudio2  # Debian/Ubuntu
sudo dnf install portaudio-devel     # Fedora
```

**Building executable:**

```bash
cd stt_desktop_client
chmod +x build.sh
./build.sh
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
- **AudioRecorder** (`audio_recorder.py`) - Real-time audio recording with ring buffer
- **STTClient** (`stt_client.py`) - HTTP client for server communication
- **GlobalHotkeyManager** (`hotkey_manager.py`) - Cross-platform hotkeys

**Signal Flow:**

```
Hotkey Press (listener thread) → toggle_recording()
→ start_recording() → status_changed signal → Tray tooltip update
→ stop_recording() → Save WAV → STTClient.transcribe_file()
→ result_ready signal → on_transcription_result() → Clipboard + Notification
```

**Threading Model:**

The application uses a multi-threaded architecture:

- **Main Thread:** Qt event loop, UI updates, signal handling
- **Hotkey Listener Thread:** `pynput.keyboard.Listener` runs in daemon thread
- **Audio Callback Thread:** `sounddevice` callback writes to ring buffer

Qt signals are thread-safe and automatically marshal calls from the hotkey listener thread to the main Qt thread.

**Ring Buffer Implementation:**

The `AudioRingBuffer` class (`audio_recorder.py:7-56`) is a thread-safe circular buffer using numpy arrays:

- Fixed size: `sample_rate × buffer_duration` (default: 16000 × 30 = 480,000 samples)
- Wrap-around writing with `write_pos`, `read_pos`, and `count` tracking
- Lock-protected operations via `threading.Lock` for concurrent callback/main thread access
- `read_all()` consumes all buffered data and resets buffer
- Fresh buffer created on each `start()` to avoid cross-session contamination

**Programmatic Icon Generation:**

The tray icon is generated programmatically via QPainter (`tray_app.py:24-78`), eliminating external icon dependencies:

- Blue circle background with white microphone graphics
- Sound waves indicating recording capability
- No external image files required

**PyInstaller Build:**

The build script (`stt_desktop_client/build.sh`) creates a standalone executable using PyInstaller. Output: `dist/STT-Recorder` (Linux) or `STT-Recorder.exe` (Windows).
