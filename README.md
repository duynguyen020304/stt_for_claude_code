# STT for Claude Code

A **Speech-to-Text (STT) API service** built with FastAPI that provides audio transcription using the ChunkFormer ASR model, optimized for Vietnamese language transcription. The service accepts audio files via HTTP POST or WebSocket and returns transcribed text with timestamps.

Includes a desktop client with PyQt6 that provides system tray integration and global hotkey support for quick audio transcription.

## Features

### Server
- **Audio Transcription**: High-quality Vietnamese speech-to-text using ChunkFormer ASR model
- **Multiple Input Formats**: Supports WAV, MP3, M4A, FLAC, OGG (auto-converts to WAV)
- **Dual Interface**: REST API (`POST /transcribe`) and WebSocket (`/transcribe/ws`)
- **Long-form Audio**: Transcribe audio up to 4 hours
- **GPU/CPU Support**: Automatically detects and uses GPU if available
- **Lazy Loading**: Model loads on first request for faster startup

### Desktop Client
- **Global Hotkey Recording**: Quick recording with customizable hotkey (default: `Ctrl+Alt+R`)
- **System Tray Integration**: Runs in background with minimal footprint
- **Auto-copy to Clipboard**: Transcribed text automatically copied to clipboard
- **Desktop Notifications**: Instant feedback on transcription results
- **30-second Max Recording**: Ring buffer for efficient audio capture

## Tech Stack

### Server
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

### Prerequisites
- Python 3.12+
- pip

### Server Setup

```bash
# Clone the repository
git clone <repository-url>
cd stt_for_claude_code

# Install server dependencies
pip install -r stt_server/requirements.txt
```

### Desktop Client Setup

```bash
# Install client dependencies
pip install -r stt_desktop_client/requirements.txt
```

## Usage

### Starting the Server

```bash
python stt_server/server.py
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

### Server Configuration (`stt_server/server.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CHUNKFORMER_MODEL` | `"khanhld/chunkformer-ctc-large-vie"` | Model identifier |
| `CHUNK_SIZE` | `64` | Audio chunk size for processing |
| `LEFT_CONTEXT_SIZE` | `128` | Left context window |
| `RIGHT_CONTEXT_SIZE` | `128` | Right context window |
| `TOTAL_BATCH_DURATION` | `14400` | Max batch duration (4 hours) |

### GPU Support

By default, the server runs in CPU-only mode. To enable GPU:

Remove or comment out this line in `stt_server/server.py`:
```python
os.environ['CUDA_VISIBLE_DEVICES'] = ""
```

## Project Structure

```
.
├── stt_server/           # Server package
│   ├── __init__.py
│   ├── server.py         # FastAPI server with ChunkFormerService
│   └── requirements.txt  # Server dependencies
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

### CUDA-related Errors

If you encounter `OSError: libtorch_cuda.so` or CUDA-related errors:

```bash
pip uninstall torchaudio -y
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### KDE Plasma Wayland Clipboard

On KDE Plasma with Wayland, the clipboard may not work with Qt6's native Wayland backend. The desktop client automatically forces Qt to use the XCB (X11) backend via XWayland for reliable clipboard support.

## License

MIT License
