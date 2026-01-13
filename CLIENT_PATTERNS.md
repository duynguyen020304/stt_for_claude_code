# Desktop Audio Recorder Integration Patterns

## Overview

This document analyzes three approaches for integrating a desktop audio recorder with the ChunkFormer STT service at `/home/duypc/stt_for_claude_code/server.py`.

## Server Endpoints

Your STT server provides two endpoints:

1. **HTTP POST `/transcribe`** - File upload endpoint
   - Accepts audio file via multipart/form-data
   - Supports WAV, MP3, M4A, FLAC, OGG (auto-converts to WAV)
   - Returns transcription with timestamps
   - Timeout: 300 seconds default

2. **WebSocket `/transcribe/ws`** - Streaming endpoint
   - Accepts JSON messages with base64-encoded audio
   - Returns JSON responses per chunk
   - Message format: `{"audio_data": "<base64>", "sample_rate": 16000}`

---

## Approach 1: File-Based (HTTP POST)

### Architecture

```
[Desktop App] -> Record Audio -> Save .wav -> HTTP POST -> [Server] -> Transcribe -> Response
```

### Code Example

```python
import requests
import pyaudio
import wave
import tempfile
from pathlib import Path

def record_and_transcribe(duration=5):
    # 1. Record audio
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1024
    )

    frames = []
    for _ in range(int(16000 / 1024 * duration)):
        frames.append(stream.read(1024))

    stream.stop_stream()
    stream.close()

    # 2. Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        temp_path = f.name

    with wave.open(temp_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))

    # 3. Upload to server
    with open(temp_path, 'rb') as f:
        response = requests.post(
            "http://localhost:8000/transcribe",
            files={'audio': ('recording.wav', f, 'audio/wav')}
        )

    # 4. Handle response
    if response.status_code == 200:
        result = response.json()
        print(f"Text: {result['text']}")
        print(f"Segments: {len(result['segments'])}")

    # 5. Cleanup
    Path(temp_path).unlink()
    audio.terminate()

    return result
```

### Latency Analysis

| Stage | Time | Notes |
|-------|------|-------|
| Recording | 5s | Fixed duration |
| File write | <0.1s | Local disk I/O |
| Upload | 0.5-2s | Network latency + file size |
| Transcription | 2-5s | Server processing |
| **Total** | **7.5-12s** | End-to-end latency |

### Advantages

- **Simplicity**: Straightforward implementation
- **Reliability**: HTTP supports automatic retries
- **Error recovery**: Can retry failed uploads
- **Format support**: Server handles conversion (MP3→WAV, etc.)
- **No connection state**: No persistent connection needed

### Disadvantages

- **High latency**: Must wait for full recording
- **Memory usage**: Entire recording in memory
- **No feedback**: User waits without progress indication
- **Blocking**: UI freezes during transcription

### Network Resilience

- **Connection loss**: Retry with exponential backoff
- **Server timeout**: Configure `timeout` parameter (default 300s)
- **Partial upload**: HTTP automatically handles
- **Recovery**: Resume from retry, no data loss

### Error Handling

```python
try:
    response = requests.post(
        f"{SERVER_URL}/transcribe",
        files={'audio': ('audio.wav', f, 'audio/wav')},
        timeout=60  # Connection + read timeout
    )
    response.raise_for_status()  # Raise HTTPError for 4xx/5xx

except requests.exceptions.Timeout:
    print("Request timed out - retry or increase timeout")
except requests.exceptions.ConnectionError:
    print("Cannot reach server - check if server is running")
except requests.exceptions.HTTPError as e:
    print(f"Server error: {e.response.status_code}")
    print(f"Details: {e.response.text}")
```

### UI Feedback Pattern

```
┌─────────────────────────────────────────────┐
│  [Record Button]                            │
│                                             │
│  Status: Ready                              │
│                                             │
│  Duration: [5▼] seconds                     │
└─────────────────────────────────────────────┘
           ↓ (click)
┌─────────────────────────────────────────────┐
│  ● Recording... (3/5s)                      │
│                                             │
│  ████████████░░░░░░░                        │
└─────────────────────────────────────────────┘
           ↓ (recording complete)
┌─────────────────────────────────────────────┐
│  ⏳ Uploading...                            │
│                                             │
│  📤 2.3 MB / 2.3 MB                         │
└─────────────────────────────────────────────┘
           ↓ (upload complete)
┌─────────────────────────────────────────────┐
│  ⏳ Transcribing...                         │
│                                             │
│  This may take a few seconds...             │
└─────────────────────────────────────────────┘
           ↓ (complete)
┌─────────────────────────────────────────────┐
│  ✅ Complete!                               │
│                                             │
│  Text: "lại hai bên nên cũng oải lắm..."   │
│                                             │
│  [Copy] [Save] [Record Again]              │
└─────────────────────────────────────────────┘
```

---

## Approach 2: Streaming (WebSocket)

### Architecture

```
[Desktop App] -> Record Chunks -> WebSocket Send -> [Server] -> Transcribe -> Response (per chunk)
                     ↑                                                              ↓
                     └─────────────────────── Real-time display ───────────────────┘
```

### Code Example

```python
import asyncio
import base64
import websockets
import pyaudio
import wave
import io

async def stream_transcription(chunk_duration=2, max_chunks=5):
    audio = pyaudio.PyAudio()
    transcriptions = []

    try:
        async with websockets.connect("ws://localhost:8000/transcribe/ws") as ws:
            print("Connected to server")

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )

            chunk_frames = int(16000 / 1024 * chunk_duration)

            for i in range(max_chunks):
                # Record one chunk
                frames = []
                for _ in range(chunk_frames):
                    frames.append(stream.read(1024))

                # Create WAV in memory
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(16000)
                    wf.writeframes(b''.join(frames))

                # Encode and send
                audio_b64 = base64.b64encode(wav_buffer.getvalue()).decode('utf-8')
                await ws.send_json({
                    "audio_data": audio_b64,
                    "sample_rate": 16000
                })

                # Receive transcription
                result = await ws.recv_json()
                if result.get("type") == "transcription":
                    text = result.get("text", "")
                    transcriptions.append(result)
                    print(f"Chunk {i+1}: {text}")

            stream.stop_stream()
            stream.close()

    except websockets.exceptions.ConnectionClosed:
        print("Connection closed")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        audio.terminate()

    return transcriptions
```

### Latency Analysis

| Stage | Time | Notes |
|-------|------|-------|
| First chunk | 2s | Recording duration |
| Processing | 1-2s | Server transcription |
| **First result** | **3-4s** | Initial latency |
| Subsequent | 2s | Chunks pipeline |

### Advantages

- **Low perceived latency**: Results appear while recording
- **Real-time feedback**: User sees transcription live
- **Lower memory**: Only current chunk in memory
- **Continuous recording**: No fixed duration limit
- **Interactive**: Can stop based on transcription content

### Disadvantages

- **Complexity**: Requires async/await, WebSocket handling
- **Connection fragility**: Network interruption loses data
- **No context**: Server processes each chunk independently
- **State management**: Must handle reconnection
- **Debugging**: Harder to troubleshoot than HTTP

### Network Resilience

- **Connection loss**: Must implement reconnection logic
- **Lost chunks**: Data not buffered, need retransmission
- **Server restart**: Client must detect and reconnect
- **Recovery**: Must resend lost chunks or accept data loss

### Error Handling

```python
async def stream_with_reconnect(max_retries=3):
    retry_count = 0

    while retry_count < max_retries:
        try:
            async with websockets.connect(WS_URL) as ws:
                # Connection successful
                while True:
                    try:
                        await ws.send_json(message)
                        result = await ws.recv_json()
                        retry_count = 0  # Reset on success
                    except websockets.exceptions.ConnectionClosed:
                        print("Connection lost, reconnecting...")
                        break

        except (websockets.exceptions.InvalidURI,
                websockets.exceptions.InvalidHandshake):
            print(f"Cannot connect to server")
            break

        except Exception as e:
            print(f"Error: {e}")

        retry_count += 1
        if retry_count < max_retries:
            await asyncio.sleep(2 ** retry_count)  # Exponential backoff
```

### UI Feedback Pattern

```
┌─────────────────────────────────────────────┐
│  🎙️  Listening...                           │
│                                             │
│  ✅ Connected                               │
│                                             │
│  ─────────────────────────────────────      │
│                                             │
│  Transcript:                                │
│  "lại hai bên"                              │
│  "nên cũng oải lắm"                         │
│  "nhưng vẫn"                                │
│  _                                          │
│  ─────────────────────────────────────      │
│                                             │
│  [Stop]                                      │
└─────────────────────────────────────────────┘
```

---

## Approach 3: Hybrid (VAD + HTTP)

### Architecture

```
[Desktop App] -> VAD Detection -> Buffer Speech -> Silence Detected -> HTTP POST -> [Server]
                     ↑                                                               ↓
                     └─────────────────────── Display per segment ───────────────────┘
```

### Code Example

```python
import requests
import pyaudio
import wave
import tempfile
import numpy as np
from pathlib import Path

def record_with_vad(max_duration=30):
    audio = pyaudio.PyAudio()
    transcriptions = []

    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=1024
    )

    # VAD parameters
    silence_threshold = 500
    silence_duration = int(16000 / 1024 * 1.0)  # 1 second
    min_speech_frames = int(16000 / 1024 * 0.5)  # 0.5 second minimum

    speech_frames = []
    silence_count = 0
    is_speaking = False

    import time
    start_time = time.time()

    try:
        while time.time() - start_time < max_duration:
            data = stream.read(1024)

            # Energy-based speech detection
            energy = np.sqrt(
                np.mean(np.frombuffer(data, dtype=np.int16).astype(float)**2)
            )

            if energy > silence_threshold:
                speech_frames.append(data)
                silence_count = 0

                if not is_speaking:
                    is_speaking = True
                    print("[Speech detected]")

            else:
                if is_speaking:
                    silence_count += 1

                    # Speech segment ended
                    if (silence_count > silence_duration and
                        len(speech_frames) > min_speech_frames):

                        print("[Transcribing segment...]")

                        # Save segment to temp file
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".wav"
                        ) as f:
                            temp_path = f.name

                        with wave.open(temp_path, 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
                            wf.setframerate(16000)
                            wf.writeframes(b''.join(speech_frames))

                        # Transcribe via HTTP
                        with open(temp_path, 'rb') as f:
                            response = requests.post(
                                "http://localhost:8000/transcribe",
                                files={'audio': ('segment.wav', f, 'audio/wav')},
                                timeout=30
                            )

                        if response.status_code == 200:
                            result = response.json()
                            text = result.get("text", "")
                            transcriptions.append(result)
                            print(f"  → {text}")

                        # Cleanup
                        Path(temp_path).unlink()
                        speech_frames.clear()
                        is_speaking = False

    except KeyboardInterrupt:
        print("\nStopped")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    return transcriptions
```

### Latency Analysis

| Stage | Time | Notes |
|-------|------|-------|
| Speech detection | Immediate | Real-time |
| Silence wait | 1s | Post-speech buffer |
| Transcription | 2-5s | Server processing |
| **Total** | **3-6s** | Per segment |

### Advantages

- **Natural interaction**: Pause-based like human conversation
- **Reliable transport**: HTTP per segment (retries)
- **Better context**: Complete utterances transcribed together
- **Efficient**: Only sends speech, not silence
- **Graceful degradation**: Failed segments don't stop session

### Disadvantages

- **Higher complexity**: VAD implementation required
- **Tuning needed**: Silence threshold must be calibrated
- **False triggers**: Noise can trigger speech detection
- **Split words**: Can split mid-word if silence is short
- **Dependency**: Accuracy depends on VAD quality

### Network Resilience

- **Per-segment retries**: Failed segments don't affect others
- **Connection loss**: Reconnect between segments
- **Server timeout**: Per-segment timeout (shorter than full file)
- **Recovery**: Continue recording after error

### Error Handling

```python
# Enhanced VAD with retry and validation
def transcribe_segment(audio_frames, max_retries=2):
    """Transcribe a speech segment with retry logic."""

    for attempt in range(max_retries):
        try:
            # Validate segment length
            duration = len(audio_frames) * 1024 / 16000
            if duration < 0.3:  # Too short
                return None

            # Save and upload
            temp_path = save_segment(audio_frames)

            response = requests.post(
                f"{SERVER_URL}/transcribe",
                files={'audio': ('segment.wav', open(temp_path, 'rb'), 'audio/wav')},
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            # Validate result
            text = result.get("text", "").strip()
            if not text:
                print("(Empty transcription, skipping)")
                return None

            Path(temp_path).unlink()
            return result

        except requests.exceptions.Timeout:
            print(f"Timeout (attempt {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                print("(Segment failed)")
            return None

        except Exception as e:
            print(f"Error: {e}")
            return None

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()
```

### UI Feedback Pattern

```
┌─────────────────────────────────────────────┐
│  🎙️  Listening...                           │
│                                             │
│  ─────────────────────────────────────      │
│                                             │
│  Detected segments:                         │
│                                             │
│  1. "lại hai bên nên cũng oải lắm"          │
│  2. "nhưng vẫn"                              │
│                                             │
│  [Stop]                                      │
└─────────────────────────────────────────────┘

                ↓ (speech detected)

┌─────────────────────────────────────────────┐
│  🗣️  Speaking...                            │
│                                             │
│  ─────────────────────────────────────      │
│                                             │
│  1. "lại hai bên nên cũng oải lắm"          │
│  2. "nhưng vẫn"                              │
│                                             │
│  [Stop]                                      │
└─────────────────────────────────────────────┘

                ↓ (silence detected)

┌─────────────────────────────────────────────┐
│  ⏸️  Processing segment...                  │
│                                             │
│  ─────────────────────────────────────      │
│                                             │
│  1. "lại hai bên nên cũng oải lắm"          │
│  2. "nhưng vẫn"                              │
│  3. 📝 "đang thử"                            │
│                                             │
│  [Stop]                                      │
└─────────────────────────────────────────────┘
```

---

## Comparison Summary

| Aspect | File-Based | Streaming | Hybrid VAD |
|--------|-----------|-----------|------------|
| **Latency** | High (7-12s) | Low (3-4s first) | Medium (3-6s) |
| **Complexity** | Low | Medium | High |
| **Network Resilience** | Excellent (HTTP retries) | Poor (connection loss) | Good (per segment) |
| **Context Quality** | Best (full audio) | Poor (no context) | Good (per utterance) |
| **Memory Usage** | High (full recording) | Low (chunk only) | Medium (segment buffer) |
| **User Experience** | One-shot, wait | Real-time streaming | Natural pauses |
| **Best For** | Voicemail, dictation | Live captioning | Voice commands, conversation |
| **Code Size** | ~50 lines | ~80 lines | ~120 lines |

---

## Recommendations

### Use File-Based When:

- Recording voice memos, voicemails, dictation
- Short recordings (< 30 seconds)
- Simplicity is priority
- Network reliability is concern
- Format conversion needed (MP3, M4A, etc.)

**Example**: Voice memo app, podcast transcription

### Use Streaming When:

- Real-time feedback required
- Continuous monitoring needed
- Low latency is critical
- Network is stable (local network)
- Live captioning use case

**Example**: Live meeting transcription, accessibility captions

### Use Hybrid VAD When:

- Natural conversation flow
- Multi-utterance sessions
- Voice command interface
- Need both reliability and interactivity
- Bandwidth efficiency matters

**Example**: Voice assistant, meeting notes, interview transcription

---

## Implementation Files

- **`/home/duypc/stt_for_claude_code/client_examples.py`**
  Complete implementations with all three approaches, error handling, progress callbacks, and detailed documentation.

- **`/home/duypc/stt_for_claude_code/simple_client.py`**
  Simplified examples for quick testing and understanding.

- **`/home/duypc/stt_for_claude_code/server.py`**
  Your existing STT server with both HTTP and WebSocket endpoints.

---

## Testing the Examples

```bash
# Start the server
python /home/duypc/stt_for_claude_code/server.py

# In another terminal, test clients:

# File-based approach
python /home/duypc/stt_for_claude_code/simple_client.py http 5

# WebSocket streaming
python /home/duypc/stt_for_claude_code/simple_client.py ws 3

# VAD-based recording
python /home/duypc/stt_for_claude_code/simple_client.py vad 30
```

---

## Advanced Topics

### Using webrtcvad for Better VAD

The simple energy-based VAD in the examples can be replaced with webrtcvad for better accuracy:

```bash
pip install webrtcvad
```

```python
import webrtcvad

vad = webrtcvad.Vad(2)  # Aggressiveness 0-3
is_speech = vad.is_speech(frame, sample_rate=16000)
```

### Handling Reconnections

For production streaming clients, implement automatic reconnection with exponential backoff:

```python
async def connect_with_retry(url, max_retries=5):
    for i in range(max_retries):
        try:
            return await websockets.connect(url)
        except Exception as e:
            if i == max_retries - 1:
                raise
            wait_time = 2 ** i
            await asyncio.sleep(wait_time)
```

### Audio Quality Optimization

- Use noise suppression (RNNoise, spectral subtraction)
- Implement automatic gain control
- Add audio level monitoring UI
- Support different sample rates (resample to 16kHz)

### Security Considerations

- Use HTTPS/WSS in production
- Add authentication tokens
- Validate audio file sizes
- Rate limiting per client
- Sanitize filenames

---

## References

- **Server Code**: `/home/duypc/stt_for_claude_code/server.py`
- **Project Docs**: `/home/duypc/stt_for_claude_code/CLAUDE.md`
- **Client Examples**: `/home/duypc/stt_for_claude_code/client_examples.py`
- **Simple Client**: `/home/duypc/stt_for_claude_code/simple_client.py`
