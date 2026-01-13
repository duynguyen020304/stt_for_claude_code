"""
Simple Desktop Audio Recorder Client for STT Service

Minimal examples for integrating with the ChunkFormer STT server.

Requirements:
    pip install pyaudio requests websockets
"""

import asyncio
import base64
import tempfile
import wave
from pathlib import Path
import requests
import websockets
import pyaudio


# =============================================================================
# Configuration
# =============================================================================

SERVER_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/transcribe/ws"

# Audio parameters
RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024


# =============================================================================
# Example 1: Simple File Upload (HTTP POST)
# =============================================================================

def record_and_upload(duration_seconds=5):
    """
    Record audio and upload via HTTP POST.

    Simplest approach - good for dictation, voice notes.
    """

    # 1. Record audio
    audio = pyaudio.PyAudio()

    print(f"Recording for {duration_seconds} seconds...")
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                       rate=RATE, input=True, frames_per_buffer=CHUNK)

    frames = []
    for _ in range(int(RATE / CHUNK * duration_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    # 2. Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        temp_path = f.name

    with wave.open(temp_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print(f"Saved to: {temp_path}")

    # 3. Upload to server
    print("Uploading to server...")
    with open(temp_path, 'rb') as f:
        response = requests.post(
            f"{SERVER_URL}/transcribe",
            files={'audio': ('recording.wav', f, 'audio/wav')}
        )

    # 4. Print result
    if response.status_code == 200:
        result = response.json()
        print(f"\nTranscription: {result['text']}")
        print(f"Segments: {len(result['segments'])}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

    # 5. Cleanup
    Path(temp_path).unlink()
    audio.terminate()

    return response.json() if response.status_code == 200 else None


# =============================================================================
# Example 2: Real-time Streaming (WebSocket)
# =============================================================================

async def record_and_stream(chunk_duration=2, max_chunks=5):
    """
    Stream audio chunks via WebSocket.

    Good for live captioning, real-time feedback.
    """

    audio = pyaudio.PyAudio()
    transcriptions = []

    print(f"Streaming {max_chunks} chunks of {chunk_duration}s each...")

    try:
        async with websockets.connect(WS_URL) as ws:
            print("Connected!")

            stream = audio.open(format=FORMAT, channels=CHANNELS,
                               rate=RATE, input=True, frames_per_buffer=CHUNK)

            chunk_frames = int(RATE / CHUNK * chunk_duration)

            for i in range(max_chunks):
                # Record one chunk
                frames = []
                for _ in range(chunk_frames):
                    data = stream.read(CHUNK)
                    frames.append(data)

                # Create WAV in memory
                import io
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(audio.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))

                wav_bytes = wav_buffer.getvalue()

                # Send to server
                audio_b64 = base64.b64encode(wav_bytes).decode('utf-8')
                await ws.send_json({
                    "audio_data": audio_b64,
                    "sample_rate": RATE
                })

                # Get transcription
                result = await ws.recv_json()
                if result.get("type") == "transcription":
                    text = result.get("text", "")
                    transcriptions.append(result)
                    print(f"Chunk {i+1}: {text}")

            stream.stop_stream()
            stream.close()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        audio.terminate()

    return transcriptions


# =============================================================================
# Example 3: Pause-Based Recording (VAD-lite)
# =============================================================================

def record_with_pauses(max_duration=30, silence_threshold=500):
    """
    Record speech segments separated by silence.

    Detects when you stop speaking and processes each segment.
    Good for conversations, multi-part dictation.
    """

    import numpy as np

    audio = pyaudio.PyAudio()
    transcriptions = []

    print("Recording with silence detection...")
    print("(Speak naturally, silence will process each segment)")

    stream = audio.open(format=FORMAT, channels=CHANNELS,
                       rate=RATE, input=True, frames_per_buffer=CHUNK)

    speech_frames = []
    silence_count = 0
    is_speaking = False
    silence_limit = int(RATE / CHUNK * 1.0)  # 1 second of silence

    import time
    start_time = time.time()

    try:
        while time.time() - start_time < max_duration:
            data = stream.read(CHUNK)

            # Simple energy-based speech detection
            energy = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(float)**2))

            if energy > silence_threshold:
                speech_frames.append(data)
                silence_count = 0

                if not is_speaking:
                    is_speaking = True
                    print("\n[Speaking...]")

            else:
                if is_speaking:
                    silence_count += 1

                    # End of speech segment
                    if silence_count > silence_limit and len(speech_frames) > int(RATE/CHUNK * 0.5):
                        print("[Silence detected - transcribing...]")

                        # Save segment
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                            temp_path = f.name

                        with wave.open(temp_path, 'wb') as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(audio.get_sample_size(FORMAT))
                            wf.setframerate(RATE)
                            wf.writeframes(b''.join(speech_frames))

                        # Transcribe
                        with open(temp_path, 'rb') as f:
                            response = requests.post(
                                f"{SERVER_URL}/transcribe",
                                files={'audio': ('segment.wav', f, 'audio/wav')},
                                timeout=30
                            )

                        if response.status_code == 200:
                            result = response.json()
                            text = result.get("text", "")
                            transcriptions.append(result)
                            print(f"  -> {text}")

                        # Cleanup
                        Path(temp_path).unlink()
                        speech_frames.clear()
                        is_speaking = False

    except KeyboardInterrupt:
        print("\nStopped.")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    return transcriptions


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python simple_client.py http [duration]     # File upload")
        print("  python simple_client.py ws [chunks]         # WebSocket stream")
        print("  python simple_client.py vad [max_duration]  # Voice activity detection")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "http":
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        record_and_upload(duration)

    elif mode == "ws":
        chunks = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        asyncio.run(record_and_stream(max_chunks=chunks))

    elif mode == "vad":
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        record_with_pauses(max_duration=duration)

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
