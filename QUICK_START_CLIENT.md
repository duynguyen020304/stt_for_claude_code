# Desktop Audio Recorder - Quick Start

## Installation

```bash
# Install server dependencies
pip install -r requirements.txt

# Install client dependencies (for recording)
pip install -r requirements-client.txt

# On Linux, you may also need:
# sudo apt-get install portaudio19-dev python3-pyaudio
```

## Start the Server

```bash
python /home/duypc/stt_for_claude_code/server.py
```

Server will be available at `http://localhost:8000`

## Quick Test

### Method 1: Simple HTTP Upload (Easiest)

```bash
python /home/duypc/stt_for_claude_code/simple_client.py http 5
```

This will:
1. Record 5 seconds of audio
2. Upload to server
3. Display transcription

### Method 2: WebSocket Streaming

```bash
python /home/duypc/stt_for_claude_code/simple_client.py ws 3
```

This will:
1. Stream 3 chunks of 2 seconds each
2. Show real-time transcriptions

### Method 3: VAD-Based Recording

```bash
python /home/duypc/stt_for_claude_code/simple_client.py vad 30
```

This will:
1. Listen for up to 30 seconds
2. Automatically detect speech segments
3. Transcribe each segment separately

## Minimal Code Examples

### HTTP Upload (20 lines)

```python
import requests, pyaudio, wave, tempfile
from pathlib import Path

audio = pyaudio.PyAudio()
stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                   input=True, frames_per_buffer=1024)

frames = [stream.read(1024) for _ in range(int(16000/1024*5))]
stream.close()

with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
    with wave.open(f.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))
    temp_path = f.name

with open(temp_path, 'rb') as f:
    result = requests.post(
        "http://localhost:8000/transcribe",
        files={'audio': ('test.wav', f, 'audio/wav')}
    ).json()

print(f"Transcription: {result['text']}")
Path(temp_path).unlink()
audio.terminate()
```

### WebSocket Streaming (25 lines)

```python
import asyncio, base64, websockets, pyaudio, wave, io

async def stream():
    audio = pyaudio.PyAudio()
    async with websockets.connect("ws://localhost:8000/transcribe/ws") as ws:
        stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                           input=True, frames_per_buffer=1024)

        for i in range(3):
            frames = [stream.read(1024) for _ in range(int(16000/1024*2))]
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
                wf.writeframes(b''.join(frames))

            await ws.send_json({"audio_data": base64.b64encode(buf.getvalue()).decode(),
                               "sample_rate": 16000})
            result = await ws.recv_json()
            print(f"Chunk {i+1}: {result.get('text', '')}")

        stream.close()
    audio.terminate()

asyncio.run(stream())
```

## Which Approach to Use?

| Need | Approach | Command |
|------|----------|---------|
| Simple voice memo | HTTP Upload | `simple_client.py http 5` |
| Real-time captioning | WebSocket | `simple_client.py ws 5` |
| Voice commands | VAD | `simple_client.py vad 30` |
| Dictation app | HTTP Upload | See `client_examples.py` |
| Meeting notes | VAD | See `client_examples.py` |

## Files Reference

| File | Purpose |
|------|---------|
| `/home/duypc/stt_for_claude_code/server.py` | STT server (HTTP + WebSocket) |
| `/home/duypc/stt_for_claude_code/simple_client.py` | Simple examples (50-100 lines) |
| `/home/duypc/stt_for_claude_code/client_examples.py` | Complete implementations (300+ lines) |
| `/home/duypc/stt_for_claude_code/CLIENT_PATTERNS.md` | Detailed analysis and patterns |
| `/home/duypc/stt_for_claude_code/QUICK_START_CLIENT.md` | This file |

## Troubleshooting

### "No module named 'pyaudio'"
```bash
# Linux
sudo apt-get install portaudio19-dev python3-pyaudio

# macOS
brew install portaudio
pip install pyaudio

# Windows
pip install pyaudio
```

### "Cannot connect to server"
Make sure server is running:
```bash
python /home/duypc/stt_for_claude_code/server.py
```

### "OSError: Invalid input device"
Check microphone:
```python
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    print(p.get_device_info_by_index(i)['name'])
```

## Next Steps

1. Read `CLIENT_PATTERNS.md` for detailed analysis
2. Explore `client_examples.py` for production-ready code
3. Integrate into your desktop application
4. Add UI feedback and error handling
