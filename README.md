# STT for Claude Code

A **Speech-to-Text (STT) API service** built with FastAPI that provides audio transcription using Vietnamese ASR models. The service accepts audio files via HTTP POST or WebSocket and returns transcribed text with timestamps.

Includes a desktop client with PyQt6 that provides system tray integration and global hotkey support for quick audio transcription.

## Server Implementations

| Implementation  | Model                                          | Framework    | Recommended |
| --------------- | ---------------------------------------------- | ------------ | ----------- |
| **Sherpa-ONNX** | csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20 | ONNX Runtime | ✅ Yes      |
| ChunkFormer     | khanhld/chunkformer-ctc-large-vie              | PyTorch      | Alternative |

The Sherpa-ONNX implementation is recommended for its simpler setup, faster inference, and smaller model size (~258 MB).

## Features

### Server

- **Audio Transcription**: High-quality Vietnamese speech-to-text
- **Multiple Input Formats**: Supports WAV, MP3, M4A, FLAC, OGG (auto-converts to WAV)
- **Dual Interface**: REST API (`POST /transcribe`) and WebSocket (`/transcribe/ws`)
- **GPU/CPU Support**: Configurable device selection
- **Lazy Loading**: Model loads on first request for faster startup
- **Auto Model Download**: Sherpa-ONNX model downloads automatically on first run

### Desktop Client

- **Global Hotkey Recording**: Quick recording with customizable hotkey (default: `Ctrl+Alt+R`)
- **System Tray Integration**: Runs in background with minimal footprint
- **Auto-copy to Clipboard**: Transcribed text automatically copied to clipboard
- **Desktop Notifications**: Instant feedback on transcription results
- **30-second Max Recording**: Ring buffer for efficient audio capture

## Tech Stack

### Server (Sherpa-ONNX)

- Python 3.12
- FastAPI
- Uvicorn
- Sherpa-ONNX (csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20)
- ONNX Runtime

### Server (ChunkFormer - Alternative)

- Python 3.12
- FastAPI
- Uvicorn
- ChunkFormer (khanhld/chunkformer-ctc-large-vie)
- PyTorch (CPU/GPU)

### Desktop Client

- Python 3.12
- PyQt6
- sounddevice
- numpy
- pynput

## Installation

### Automated Setup (Recommended)

The project includes automated setup scripts that handle:

- Python 3.12 installation check (with automatic installation on Linux)
- Virtual environment creation
- All dependency installation (server & client)
- System dependencies (PortAudio, FFmpeg)

**Linux / macOS:**

```bash
./setup.sh
```

**Windows (PowerShell):**

```powershell
.\setup.ps1
```

**Windows (Batch):**

```cmd
setup.bat
```

If the batch launcher fails to locate the script, run PowerShell directly from the repo root:

```powershell
pwsh -ExecutionPolicy Bypass -File .\setup.ps1
```

The script will guide you through optional dependencies:

- **ChunkFormer server**: Alternative PyTorch-based model (larger, slower)
- **Parakeet server**: English-only NeMo model (experimental)
- **CUDA support**: GPU acceleration for Sherpa-ONNX

### Manual Installation

#### Prerequisites

- Python 3.12+
- pip
- FFmpeg (for audio format conversion)

#### System Dependencies

**Linux (Debian/Ubuntu):**

```bash
sudo apt-get install libportaudio2 ffmpeg python3-pyaudio
```

**Linux (Fedora):**

```bash
sudo dnf install portaudio-devel ffmpeg python3-pyaudio
```

**macOS:**

```bash
brew install portaudio ffmpeg
```

**Windows:**

- Install FFmpeg: `winget install Gyan.FFmpeg`
- PyAudio is included in the setup script

#### Server Setup

**Option 1: Sherpa-ONNX Server (Recommended)**

```bash
# Clone the repository
git clone <repository-url>
cd stt_for_claude_code

# Install server dependencies
pip install -r stt_server/requirements.txt
```

**Option 2: ChunkFormer Server (Alternative)**

```bash
# Install server dependencies
pip install chunkformer torch torchaudio

# For CPU-only mode:
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Desktop Client Setup

```bash
# Install client dependencies
pip install -r stt_desktop_client/requirements.txt
```

## Usage

### Starting the Server

**Sherpa-ONNX Server (Recommended):**

```bash
python stt_server/server_sherpa_onnx.py
```

The model (~258 MB) will be automatically downloaded on first run to `./models/sherpa-onnx-vi/`.

**ChunkFormer Server (Alternative):**

```bash
python stt_server/server_chunkformer_model.py
```

The server will start on `http://localhost:8000`

### Testing Transcription

```bash
curl -X POST "http://localhost:8000/transcribe" -F "audio=@audio_samples/sample_0000.wav"
```

### Interactive API Documentation

Open your browser and navigate to: `http://localhost:8000/docs`

### Starting the Desktop Client

```bash
cd stt_desktop_client/src && python main.py
```

**Optional arguments:**

```bash
python main.py --server http://localhost:8000 --hotkey <ctrl>+<alt>+r
```

**Using the client:**

1. Press `Ctrl+Alt+R` to start recording
2. Press `Ctrl+Alt+R` again to stop recording
3. Wait for transcription to complete
4. Text is automatically copied to clipboard
5. Desktop notification shows the result

## API Endpoints

### `GET /`

API information and available endpoints.

### `GET /health`

Health check endpoint. Returns model loading status.

### `POST /transcribe`

Transcribe an audio file.

**Request:**

- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `audio` (file)

**Response:**

```json
{
  "text": "Transcribed text here",
  "segments": [
    {
      "start": 0.0,
      "end": 2.5,
      "text": "First segment"
    }
  ]
}
```

### `WS /transcribe/ws`

WebSocket endpoint for streaming transcription.

## Configuration

### Server Configuration

**Sherpa-ONNX Server** (`stt_server/server_sherpa_onnx.py`):

| Parameter           | Default                                            | Description                   |
| ------------------- | -------------------------------------------------- | ----------------------------- |
| `SHERPA_ONNX_MODEL` | `"csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20"` | Model identifier              |
| `MODEL_DIR`         | `"./models/sherpa-onnx-vi"`                        | Local model cache directory   |
| `NUM_THREADS`       | `4`                                                | CPU threads for inference     |
| `DEVICE`            | `"cpu"`                                            | Execution provider (cpu/cuda) |

**ChunkFormer Server** (`stt_server/server_chunkformer_model.py`):

| Parameter              | Default                               | Description                     |
| ---------------------- | ------------------------------------- | ------------------------------- |
| `CHUNKFORMER_MODEL`    | `"khanhld/chunkformer-ctc-large-vie"` | Model identifier                |
| `CHUNK_SIZE`           | `64`                                  | Audio chunk size for processing |
| `LEFT_CONTEXT_SIZE`    | `128`                                 | Left context window             |
| `RIGHT_CONTEXT_SIZE`   | `128`                                 | Right context window            |
| `TOTAL_BATCH_DURATION` | `14400`                               | Max batch duration (4 hours)    |

### GPU Support

**Sherpa-ONNX:** Set `DEVICE = "cuda"` in `server_sherpa_onnx.py`. Install CUDA support with:

```bash
pip install sherpa-onnx --extra-index-url https://pypi.nvidia.com
```

**ChunkFormer:** Remove or comment out `CUDA_VISIBLE_DEVICES = ""` in the server file.

## Project Structure

```
.
├── stt_server/           # Server package
│   ├── __init__.py
│   ├── server_sherpa_onnx.py              # Sherpa-ONNX FastAPI server (recommended)
│   ├── sherpa_onnx_service.py             # Sherpa-ONNX service layer
│   ├── server_chunkformer_model.py        # ChunkFormer FastAPI server (alternative)
│   ├── requirements.txt                   # Server dependencies
│   └── models/
│       └── sherpa-onnx-vi/                # Auto-downloaded Sherpa-ONNX model
├── stt_desktop_client/   # Desktop client application
│   └── src/
│       ├── main.py           # Entry point
│       ├── tray_app.py       # PyQt6 system tray UI
│       ├── audio_recorder.py # Audio recording with ring buffer
│       ├── stt_client.py     # HTTP client for STT server
│       └── hotkey_manager.py # Global hotkey support
├── audio_samples/        # Test audio files (Vietnamese WAV)
├── CLAUDE.md            # Project instructions for Claude Code
└── README.md            # This file
```

## Known Issues

### Sherpa-ONNX Model Download

On first run, the Sherpa-ONNX server will download the model (~258 MB) from Hugging Face. Ensure you have:

- Internet connection
- Sufficient disk space (~300 MB recommended)
- Write permissions in the project directory

### CUDA-related Errors (ChunkFormer Only)

If you encounter `OSError: libtorch_cuda.so` or CUDA-related errors with the ChunkFormer server:

```bash
pip uninstall torchaudio -y
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### KDE Plasma Wayland Clipboard

On KDE Plasma with Wayland, the clipboard may not work with Qt6's native Wayland backend. The desktop client automatically forces Qt to use the XCB (X11) backend via XWayland for reliable clipboard support.

## License

MIT License
