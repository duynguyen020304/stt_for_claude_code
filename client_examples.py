"""
Desktop Audio Recorder Client Examples for STT Service

This module provides three different approaches for integrating a desktop
audio recorder with the STT service:

1. File-based approach (HTTP POST)
2. Streaming approach (WebSocket)
3. Hybrid approach (VAD + HTTP)

Each approach has different trade-offs in latency, network resilience,
and complexity.

Requirements:
    pip install pyaudio websockets numpy webrtcvad
"""

import asyncio
import base64
import json
import time
import tempfile
import wave
from pathlib import Path
from typing import Optional, Callable
import requests
import websockets
import pyaudio
import numpy as np

# =============================================================================
# Configuration
# =============================================================================

SERVER_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/transcribe/ws"

# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK_SIZE = 1024  # Recording chunk size in bytes
RECORD_SECONDS = 5  # Default recording duration

# =============================================================================
# Approach 1: File-Based Approach (HTTP POST)
# =============================================================================

class FileBasedRecorder:
    """
    File-based recording approach.

    Advantages:
    - Simple implementation
    - Reliable network handling (HTTP retries)
    - Works with any audio format
    - Server handles format conversion

    Disadvantages:
    - Higher latency (wait for recording to finish)
    - No real-time feedback
    - Higher memory usage for long recordings
    """

    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.audio = pyaudio.PyAudio()

    def record_to_file(
        self,
        duration: int = RECORD_SECONDS,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """
        Record audio to a WAV file.

        Args:
            duration: Recording duration in seconds
            filename: Output filename (None for temp file)
            progress_callback: Optional callback(float) for progress updates

        Returns:
            Path to recorded WAV file
        """
        if filename is None:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=".wav"
            )
            filename = temp_file.name
            temp_file.close()

        print(f"🎙️  Recording for {duration} seconds...")
        print("   (Speak now...)")

        stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        frames = []
        start_time = time.time()

        for i in range(int(RATE / CHUNK_SIZE * duration)):
            data = stream.read(CHUNK_SIZE)
            frames.append(data)

            # Progress callback
            if progress_callback:
                elapsed = time.time() - start_time
                progress = elapsed / duration
                progress_callback(progress)

        stream.stop_stream()
        stream.close()

        # Write to WAV file
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))

        print(f"✓ Recording saved to: {filename}")
        return filename

    def transcribe_file(
        self,
        audio_path: str,
        timeout: int = 300
    ) -> dict:
        """
        Upload audio file for transcription.

        Args:
            audio_path: Path to audio file
            timeout: Request timeout in seconds

        Returns:
            Transcription result with 'text' and 'segments' keys
        """
        print(f"📤 Uploading {Path(audio_path).name}...")

        try:
            with open(audio_path, 'rb') as f:
                files = {'audio': (Path(audio_path).name, f, 'audio/wav')}
                response = requests.post(
                    f"{self.server_url}/transcribe",
                    files=files,
                    timeout=timeout
                )

            response.raise_for_status()
            result = response.json()

            print(f"✓ Transcription complete!")
            print(f"   Text: {result['text']}")
            print(f"   Segments: {len(result['segments'])}")

            return result

        except requests.exceptions.Timeout:
            print(f"✗ Request timed out after {timeout}s")
            return {"error": "timeout", "text": "", "segments": []}
        except requests.exceptions.ConnectionError:
            print(f"✗ Could not connect to server at {self.server_url}")
            return {"error": "connection_failed", "text": "", "segments": []}
        except requests.exceptions.HTTPError as e:
            print(f"✗ HTTP error: {e.response.status_code}")
            print(f"   Details: {e.response.text}")
            return {"error": "http_error", "text": "", "segments": []}

    def record_and_transcribe(
        self,
        duration: int = RECORD_SECONDS,
        delete_after: bool = True
    ) -> dict:
        """
        Record audio and transcribe it in one call.

        Args:
            duration: Recording duration in seconds
            delete_after: Whether to delete the audio file after transcription

        Returns:
            Transcription result
        """
        audio_path = None
        try:
            # Record audio
            audio_path = self.record_to_file(duration=duration)

            # Transcribe
            result = self.transcribe_file(audio_path)

            return result

        finally:
            # Cleanup
            if delete_after and audio_path and Path(audio_path).exists():
                Path(audio_path).unlink()
                print(f"✓ Cleaned up temporary file")

    def close(self):
        """Cleanup resources."""
        self.audio.terminate()


# =============================================================================
# Approach 2: Streaming Approach (WebSocket)
# =============================================================================

class StreamingRecorder:
    """
    Real-time streaming approach with WebSocket.

    Advantages:
    - Lower latency (real-time transcription)
    - Continuous feedback during recording
    - Lower memory footprint (stream processing)

    Disadvantages:
    - Requires persistent connection
    - More complex error handling
    - Network interruptions lose data
    - Server processes chunks independently (no context)
    """

    def __init__(self, ws_url: str = WS_URL):
        self.ws_url = ws_url
        self.audio = pyaudio.PyAudio()
        self._stop_recording = False

    async def stream_audio_chunk(self, websocket, audio_chunk: bytes):
        """
        Send a single audio chunk to the server.

        Args:
            websocket: WebSocket connection
            audio_chunk: Raw audio bytes (must be valid WAV format)
        """
        try:
            # Encode as base64
            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')

            # Send to server
            message = {
                "audio_data": audio_b64,
                "sample_rate": RATE
            }

            await websocket.send_json(message)

            # Wait for response
            response = await websocket.recv_json()

            if response.get("type") == "transcription":
                return response
            elif response.get("type") == "error":
                print(f"✗ Server error: {response.get('message')}")
                return None

        except websockets.exceptions.ConnectionClosed:
            print("✗ WebSocket connection closed")
            return None
        except Exception as e:
            print(f"✗ Error streaming chunk: {e}")
            return None

    async def record_and_stream(
        self,
        chunk_duration: float = 2.0,
        max_duration: int = 30,
        callback: Optional[Callable[[str], None]] = None
    ) -> list:
        """
        Record audio and stream chunks to server.

        Args:
            chunk_duration: Duration of each chunk in seconds
            max_duration: Maximum recording duration in seconds
            callback: Optional callback(text) for each transcription

        Returns:
            List of transcription results
        """
        transcriptions = []

        print(f"🎙️  Recording (max {max_duration}s, chunks of {chunk_duration}s)...")
        print("   (Speak now, press Ctrl+C to stop early)")

        try:
            async with websockets.connect(self.ws_url) as websocket:
                print("✓ Connected to server")

                stream = self.audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK_SIZE
                )

                chunk_frames = int(RATE / CHUNK_SIZE * chunk_duration)
                frames = []
                chunk_count = 0
                start_time = time.time()

                try:
                    while not self._stop_recording:
                        # Read audio frames
                        for _ in range(chunk_frames):
                            if self._stop_recording:
                                break
                            data = stream.read(CHUNK_SIZE)
                            frames.append(data)

                        # Check max duration
                        elapsed = time.time() - start_time
                        if elapsed >= max_duration:
                            print(f"\n⏱️  Reached maximum duration ({max_duration}s)")
                            break

                        # Create WAV from frames
                        import io
                        wav_buffer = io.BytesIO()
                        with wave.open(wav_buffer, 'wb') as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
                            wf.setframerate(RATE)
                            wf.writeframes(b''.join(frames))

                        wav_bytes = wav_buffer.getvalue()
                        frames.clear()

                        # Stream to server
                        print(f"\n📤 Streaming chunk {chunk_count + 1}...", end=" ")
                        result = await self.stream_audio_chunk(websocket, wav_bytes)

                        if result:
                            text = result.get("text", "")
                            transcriptions.append(result)
                            print(f"✓")

                            if text.strip():
                                print(f"   📝 {text}")

                            if callback:
                                callback(text)

                        chunk_count += 1

                except KeyboardInterrupt:
                    print("\n⏹️  Recording stopped by user")

                finally:
                    stream.stop_stream()
                    stream.close()

        except websockets.exceptions.WebSocketException as e:
            print(f"✗ WebSocket error: {e}")
        except Exception as e:
            print(f"✗ Error: {e}")

        return transcriptions

    def stop_recording(self):
        """Signal to stop recording (for use from another thread)."""
        self._stop_recording = True

    def close(self):
        """Cleanup resources."""
        self.audio.terminate()


# =============================================================================
# Approach 3: Hybrid Approach (VAD + HTTP)
# =============================================================================

class HybridRecorder:
    """
    Hybrid approach with Voice Activity Detection.

    Advantages:
    - Efficient bandwidth (only sends speech segments)
    - Better context (segments contain complete utterances)
    - HTTP reliability for each segment
    - Natural pause-based segmentation

    Disadvantages:
    - Higher complexity (VAD implementation)
    - Requires silence threshold tuning
    - Dependent on VAD accuracy
    - Slight delay while detecting silence
    """

    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.audio = pyaudio.PyAudio()
        self._stop_recording = False

        # VAD parameters
        self.silence_threshold = 500  # Energy threshold for silence
        self.speech_timeout = 1.0  # Seconds of silence to end segment
        self.min_speech_duration = 0.5  # Minimum speech duration

    def calculate_energy(self, audio_chunk: bytes) -> float:
        """Calculate RMS energy of audio chunk."""
        # Convert bytes to numpy array
        data = np.frombuffer(audio_chunk, dtype=np.int16)
        # Calculate RMS energy
        rms = np.sqrt(np.mean(data.astype(np.float32) ** 2))
        return rms

    def is_speech(self, audio_chunk: bytes) -> bool:
        """
        Simple energy-based VAD.

        For production, consider using webrtcvad:
        import webrtcvad
        vad = webrtcvad.Vad(2)  # Aggressiveness 0-3
        """
        energy = self.calculate_energy(audio_chunk)
        return energy > self.silence_threshold

    def record_with_vad(
        self,
        max_duration: int = 60,
        callback: Optional[Callable[[str], None]] = None
    ) -> list:
        """
        Record audio with VAD-based segmentation.

        Automatically detects speech segments and transcribes each.

        Args:
            max_duration: Maximum recording duration in seconds
            callback: Optional callback(text) for each transcription

        Returns:
            List of transcription results
        """
        print(f"🎙️  Recording with VAD (max {max_duration}s)...")
        print("   (Speak now, silence will end each segment)")
        print("   (Press Ctrl+C to stop)")

        transcriptions = []
        stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        speech_frames = []
        silence_frames = 0
        is_speaking = False
        segment_start = None
        start_time = time.time()

        try:
            while not self._stop_recording:
                # Check max duration
                elapsed = time.time() - start_time
                if elapsed >= max_duration:
                    print(f"\n⏱️  Reached maximum duration ({max_duration}s)")
                    break

                # Read audio chunk
                data = stream.read(CHUNK_SIZE)

                # Check for speech
                if self.is_speech(data):
                    speech_frames.append(data)

                    if not is_speaking:
                        is_speaking = True
                        segment_start = elapsed
                        print(f"\n🗣️  Speech detected at {segment_start:.1f}s")

                    silence_frames = 0

                else:
                    # Silence detected
                    if is_speaking:
                        silence_frames += 1
                        silence_duration = silence_frames * CHUNK_SIZE / RATE

                        # Check if speech segment ended
                        if silence_duration >= self.speech_timeout:
                            # Calculate speech duration
                            speech_duration = elapsed - segment_start

                            # Only process if minimum duration met
                            if speech_duration >= self.min_speech_duration:
                                print(f"⏸️  Segment ended ({speech_duration:.1f}s)")

                                # Create WAV file
                                temp_file = tempfile.NamedTemporaryFile(
                                    delete=False, suffix=".wav"
                                )
                                temp_path = temp_file.name
                                temp_file.close()

                                with wave.open(temp_path, 'wb') as wf:
                                    wf.setnchannels(CHANNELS)
                                    wf.setsampwidth(
                                        self.audio.get_sample_size(FORMAT)
                                    )
                                    wf.setframerate(RATE)
                                    wf.writeframes(b''.join(speech_frames))

                                # Transcribe segment
                                print(f"📤 Transcribing segment...")
                                result = self._transcribe_file(temp_path)

                                if result and "error" not in result:
                                    text = result.get("text", "")
                                    transcriptions.append(result)

                                    if text.strip():
                                        print(f"   📝 {text}")

                                    if callback:
                                        callback(text)

                                # Cleanup
                                Path(temp_path).unlink()

                            # Reset for next segment
                            speech_frames.clear()
                            is_speaking = False
                            silence_frames = 0

        except KeyboardInterrupt:
            print("\n⏹️  Recording stopped by user")

        finally:
            stream.stop_stream()
            stream.close()

        print(f"\n✓ Recorded {len(transcriptions)} segments")
        return transcriptions

    def _transcribe_file(self, audio_path: str) -> dict:
        """Transcribe a single audio file (internal method)."""
        try:
            with open(audio_path, 'rb') as f:
                files = {'audio': (Path(audio_path).name, f, 'audio/wav')}
                response = requests.post(
                    f"{self.server_url}/transcribe",
                    files=files,
                    timeout=30
                )

            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"✗ Transcription error: {e}")
            return {"error": str(e)}

    def stop_recording(self):
        """Signal to stop recording (for use from another thread)."""
        self._stop_recording = True

    def close(self):
        """Cleanup resources."""
        self.audio.terminate()


# =============================================================================
# Demo / Testing Functions
# =============================================================================

def demo_file_based():
    """Demonstrate file-based approach."""
    print("\n" + "="*60)
    print("  File-Based Approach Demo")
    print("="*60)

    recorder = FileBasedRecorder()

    try:
        # Simple usage
        result = recorder.record_and_transcribe(duration=5)

        # With progress callback
        # def progress(p):
        #     print(f"\rProgress: {p*100:.0f}%", end="", flush=True)
        #
        # result = recorder.record_and_transcribe(
        #     duration=10,
        #     progress_callback=progress
        # )

    finally:
        recorder.close()


async def demo_streaming():
    """Demonstrate streaming approach."""
    print("\n" + "="*60)
    print("  Streaming Approach Demo")
    print("="*60)

    recorder = StreamingRecorder()

    try:
        def on_transcription(text):
            # Real-time callback
            pass

        transcriptions = await recorder.record_and_stream(
            chunk_duration=2.0,
            max_duration=10,
            callback=on_transcription
        )

        print(f"\n✓ Got {len(transcriptions)} transcriptions")

    finally:
        recorder.close()


def demo_hybrid():
    """Demonstrate hybrid approach."""
    print("\n" + "="*60)
    print("  Hybrid VAD Approach Demo")
    print("="*60)

    recorder = HybridRecorder()

    try:
        def on_transcription(text):
            # Callback for each segment
            pass

        transcriptions = recorder.record_with_vad(
            max_duration=30,
            callback=on_transcription
        )

        print(f"\n✓ Got {len(transcriptions)} segments")

    finally:
        recorder.close()


# =============================================================================
# Comparison Summary
# =============================================================================

"""
APPROACH COMPARISON
==================

1. FILE-BASED (HTTP POST)
   Latency:        High (wait for full recording)
   Network:        Reliable (HTTP retries)
   Complexity:     Low
   Use case:       Dictation, voicemail, podcast transcription
   Best for:       Short recordings, one-off transcriptions

2. STREAMING (WebSocket)
   Latency:        Low (real-time)
   Network:        Fragile (connection loss = data loss)
   Complexity:     Medium
   Use case:       Live captioning, real-time dictation
   Best for:       Continuous monitoring, live events

3. HYBRID (VAD + HTTP)
   Latency:        Medium (segment-based)
   Network:        Reliable (per-segment HTTP)
   Complexity:     High
   Use case:       Voice commands, conversation transcription
   Best for:       Multi-utterance sessions, pause-separated speech

LATENCY BREAKDOWN
=================

File-based:
  - Recording: 5s
  - Upload: 0.5s
  - Transcription: 2-5s
  - Total: 7.5-10.5s

Streaming:
  - First chunk: 2s recording + 2s processing = 4s
  - Subsequent: 2s chunk + 2s processing = 4s (overlapping)
  - Perceived: ~2s latency

Hybrid:
  - Speech detection: Immediate
  - Segment end: 1s silence
  - Transcription: 2-5s per segment
  - Total: 3-6s per utterance

ERROR HANDLING STRATEGIES
=========================

Network Resilience:
  - File-based: Automatic retries with requests
  - Streaming: Manual reconnection, lost chunks
  - Hybrid: Per-segment retries, minimal data loss

Server Errors:
  - File-based: Get error response, retry with backoff
  - Streaming: Error message in JSON, continue or reconnect
  - Hybrid: Skip failed segment, continue recording

Audio Issues:
  - File-based: Validate format before upload
  - Streaming: Server may reject malformed chunks
  - Hybrid: Discard too-short segments

UI FEEDBACK PATTERNS
====================

File-based:
  1. Show "Recording..." with progress bar
  2. Show "Uploading..." spinner
  3. Show "Transcribing..." indicator
  4. Show final result
  5. Handle errors at each stage

Streaming:
  1. Show "Listening..." status
  2. Show live transcription updates
  3. Show connection status (connected/disconnected)
  4. Buffer/transcript history

Hybrid:
  1. Show "Listening..." (always on)
  2. Show "🗣️ Speaking..." when speech detected
  3. Show "⏸️ Processing..." during transcription
  4. Show results per segment
  5. Show running transcript
"""

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nUsage:")
        print("  python client_examples.py file      # File-based demo")
        print("  python client_examples.py stream    # Streaming demo")
        print("  python client_examples.py hybrid    # Hybrid VAD demo")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "file":
        demo_file_based()
    elif mode == "stream":
        asyncio.run(demo_streaming())
    elif mode == "hybrid":
        demo_hybrid()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
