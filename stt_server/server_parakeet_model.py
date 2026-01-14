"""
Audio Transcription Server using NVIDIA Parakeet TDT CTC 110M

A FastAPI-based server that receives audio from microphone recording apps
and returns transcriptions with timestamps.

Run with: python server_parakeet_model.py
API docs will be available at: http://localhost:8001/docs
"""

import os
import sys
import tempfile
import base64
import asyncio
from pathlib import Path
from typing import Optional, List

# IMPORTANT: Set CUDA environment variables BEFORE any torch imports
# This prevents errors when running on CPU-only systems
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU mode (GPU can be enabled with "0")
os.environ["TORCH_CUDA_ARCH_LIST"] = ""  # Disable CUDA arch check

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


# ============================================================================
# Configuration
# ============================================================================

PARAKEET_MODEL = "nvidia/parakeet-tdt_ctc-110m"
CHUNK_DURATION_SECONDS = 30  # For timestamp estimation
MAX_AUDIO_DURATION_MINUTES = 20  # Max single pass duration
HOST = "localhost"
PORT = 8000

# Device configuration - auto-detect with fallback
DEVICE = "cpu"  # Default to CPU
try:
    import torch
    if torch.cuda.is_available():
        # Allow GPU if available - unset CUDA_VISIBLE_DEVICES
        # Comment out the line below to force GPU mode
        # os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        DEVICE = "cuda"
        print(f"✓ CUDA detected - using GPU")
    else:
        DEVICE = "cpu"
        print(f"✓ No CUDA detected - using CPU")
except Exception as e:
    DEVICE = "cpu"
    print(f"✓ PyTorch not available or error ({e}) - using CPU fallback")


# ============================================================================
# Parakeet Service (Singleton)
# ============================================================================

class ParakeetService:
    """Singleton service for managing Parakeet ASR model."""

    _instance = None
    _model = None
    _is_loading = False
    _device = DEVICE

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_model(self):
        """Lazy load the model on first request."""
        if self._model is None:
            if self._is_loading:
                # Wait if another request is loading the model
                while self._is_loading:
                    await asyncio.sleep(0.1)
                return self._model
            self._is_loading = True
            try:
                # Import NeMo after environment variables are set
                import nemo.collections.asr as nemo_asr

                # Load model from Hugging Face
                self._model = nemo_asr.models.ASRModel.from_pretrained(
                    model_name=PARAKEET_MODEL,
                    map_location=self._device
                )

                # Move to device (GPU or CPU)
                if self._device == "cuda":
                    try:
                        self._model = self._model.to(self._device)
                        print(f"✓ Model moved to GPU")
                    except Exception as e:
                        print(f"⚠ Failed to use GPU: {e}")
                        print(f"✓ Falling back to CPU")
                        self._device = "cpu"
                else:
                    print(f"✓ Model running on CPU")

                self._model.eval()
                print(f"✓ Parakeet model loaded successfully from {PARAKEET_MODEL}")
            finally:
                self._is_loading = False
        return self._model

    async def transcribe(
        self,
        audio_path: str,
        return_timestamps: bool = True
    ) -> dict:
        """
        Transcribe audio file using Parakeet.

        Args:
            audio_path: Path to audio file
            return_timestamps: Whether to include timestamps

        Returns:
            Dictionary with 'text' and 'segments' keys
        """
        model = await self.get_model()

        # Check if audio is longer than 20 minutes
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(audio_path)
            duration_minutes = len(audio) / 60000

            if duration_minutes > MAX_AUDIO_DURATION_MINUTES:
                print(f"⚠ Audio duration ({duration_minutes:.1f} min) exceeds {MAX_AUDIO_DURATION_MINUTES} min, splitting...")
                text = await self._transcribe_long_audio(audio_path)
                segments = []
            else:
                text, segments = await self._transcribe_single(audio_path, return_timestamps)
        except Exception:
            # Fallback to simple transcription if pydub fails
            text, segments = await self._transcribe_single(audio_path, return_timestamps)

        return {
            "text": text,
            "segments": segments
        }

    async def _transcribe_single(
        self,
        audio_path: str,
        return_timestamps: bool
    ) -> tuple:
        """Transcribe a single audio file."""
        import torch
        model = await self.get_model()

        with torch.no_grad():
            output = model.transcribe([audio_path])

        text = output[0].text

        if return_timestamps:
            # Use chunk-based timestamp estimation
            segments = self._get_segments_with_timestamps(audio_path, text)
        else:
            segments = []

        return text, segments

    def _get_segments_with_timestamps(
        self,
        audio_path: str,
        full_text: str
    ) -> List[dict]:
        """
        Estimate timestamps using chunk-based processing.

        This splits the audio into chunks and transcribes each chunk
        to estimate segment boundaries.
        """
        try:
            import torch
            import librosa
            import soundfile as sf

            # Load audio
            audio, sr = librosa.load(audio_path, sr=16000)
            duration = len(audio) / sr
            chunk_samples = CHUNK_DURATION_SECONDS * sr

            # If audio is shorter than chunk duration, return single segment
            if duration <= CHUNK_DURATION_SECONDS:
                return [{
                    "start": 0.0,
                    "end": duration,
                    "text": full_text,
                    "decode": full_text
                }]

            # Process chunks to get timestamps
            segments = []
            model = self._model

            with torch.no_grad():
                for i, start_idx in enumerate(range(0, len(audio), chunk_samples)):
                    chunk = audio[start_idx:start_idx + chunk_samples]

                    if len(chunk) < 1000:  # Skip very small chunks
                        continue

                    # Save chunk to temp file
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        sf.write(tmp.name, chunk, sr)
                        chunk_path = tmp.name

                    try:
                        # Transcribe chunk
                        output = model.transcribe([chunk_path])
                        chunk_text = output[0].text

                        if chunk_text.strip():  # Only add non-empty segments
                            start_time = start_idx / sr
                            end_time = min((start_idx + chunk_samples) / sr, duration)

                            segments.append({
                                "start": round(start_time, 2),
                                "end": round(end_time, 2),
                                "text": chunk_text,
                                "decode": chunk_text
                            })
                    finally:
                        os.remove(chunk_path)

            return segments

        except Exception as e:
            print(f"⚠ Failed to generate timestamps: {e}")
            # Return single segment covering full audio
            return [{
                "start": 0.0,
                "end": 0.0,
                "text": full_text,
                "decode": full_text
            }]

    async def _transcribe_long_audio(self, audio_path: str) -> str:
        """
        Handle audio longer than 20 minutes by splitting into chunks.

        Args:
            audio_path: Path to long audio file

        Returns:
            Combined transcription text
        """
        from pydub import AudioSegment
        import torch

        # Split into 20-minute chunks
        audio = AudioSegment.from_wav(audio_path)
        chunk_length_ms = MAX_AUDIO_DURATION_MINUTES * 60 * 1000

        transcriptions = []
        model = await self.get_model()

        with torch.no_grad():
            for i in range(0, len(audio), chunk_length_ms):
                chunk = audio[i:i + chunk_length_ms]

                # Save chunk to temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    chunk.export(tmp.name, format="wav")
                    chunk_path = tmp.name

                try:
                    output = model.transcribe([chunk_path])
                    transcriptions.append(output[0].text)
                finally:
                    os.remove(chunk_path)

        return " ".join(transcriptions)


# ============================================================================
# Pydantic Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    device: str


class TranscribeResponse(BaseModel):
    """Transcription response."""
    text: str
    segments: List[dict]


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Audio Transcription Server (Parakeet)",
    description="Transcribe audio using NVIDIA Parakeet TDT CTC 110M ASR model",
    version="1.0.0"
)

# Singleton service instance
service = ParakeetService()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", summary="Root")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Audio Transcription Server (Parakeet)",
        "version": "1.0.0",
        "model": PARAKEET_MODEL,
        "endpoints": {
            "health": "GET /health",
            "transcribe": "POST /transcribe",
            "websocket": "WS /transcribe/ws",
            "docs": "GET /docs"
        }
    }


@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health():
    """Check server health and model status."""
    model_loaded = service._model is not None
    return {
        "status": "healthy" if model_loaded else "initializing",
        "model_loaded": model_loaded,
        "device": service._device.upper()
    }


@app.post("/transcribe", response_model=TranscribeResponse, summary="Transcribe audio file")
async def transcribe(
    audio: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, FLAC, OGG)"),
    return_timestamps: bool = True
):
    """
    Transcribe an audio file.

    Upload an audio file and receive the transcription with timestamps.
    Supported formats: WAV, MP3, M4A, FLAC, OGG

    Note: This model is optimized for English transcription.
    """
    # Create temp file for processing
    temp_path = None
    try:
        # Get file extension
        filename = audio.filename or "audio.wav"
        ext = Path(filename).suffix.lower() or ".wav"

        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            content = await audio.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # For non-WAV files, convert using pydub
        if ext != ".wav":
            try:
                from pydub import AudioSegment

                # Load audio and convert to WAV
                audio_segment = AudioSegment.from_file(temp_path)
                wav_path = temp_path.replace(ext, ".wav")
                audio_segment.export(wav_path, format="wav")
                os.remove(temp_path)
                temp_path = wav_path
            except Exception as e:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Failed to process audio format: {str(e)}"}
                )

        # Transcribe
        result = await service.transcribe(temp_path, return_timestamps)
        return result

    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


@app.websocket("/transcribe/ws")
async def transcribe_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming.

    Client sends: {"audio_data": "<base64_audio_bytes>", "sample_rate": 16000}
    Server responds: {"type": "transcription", "text": "...", "segments": [...]}

    For continuous recording, send audio chunks. The server will transcribe
    each chunk independently.
    """
    await websocket.accept()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            audio_data_b64 = data.get("audio_data")
            if not audio_data_b64:
                await websocket.send_json({
                    "type": "error",
                    "message": "Missing 'audio_data' field"
                })
                continue

            # Decode base64 audio data
            try:
                audio_bytes = base64.b64decode(audio_data_b64)
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid base64 encoding: {str(e)}"
                })
                continue

            # Save to temp file
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name

                # Transcribe
                result = await service.transcribe(temp_path, return_timestamps=True)

                # Send result
                await websocket.send_json({
                    "type": "transcription",
                    "text": result["text"],
                    "segments": result["segments"]
                })

            finally:
                # Cleanup
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass

    except WebSocketDisconnect:
        print("WebSocket client disconnected")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Audio Transcription Server (Parakeet)")
    print("=" * 60)
    print(f"  Model:  {PARAKEET_MODEL}")
    print(f"  Device: {DEVICE.upper()}")
    print(f"  Server: http://{HOST}:{PORT}")
    print(f"  Docs:   http://{HOST}:{PORT}/docs")
    print("=" * 60)
    print()

    uvicorn.run(
        "server_parakeet_model:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
