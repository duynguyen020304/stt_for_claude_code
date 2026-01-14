"""
Audio Transcription Server using ChunkFormer

A FastAPI-based server that receives audio from microphone recording apps
and returns transcriptions with timestamps.

Run with: python server.py
API docs will be available at: http://localhost:8000/docs
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

# Lazy import ChunkFormerModel - only import when needed
# This allows environment variables to take effect first
ChunkFormerModel = None


def get_chunkformer_model():
    """Lazy import of ChunkFormerModel."""
    global ChunkFormerModel
    if ChunkFormerModel is None:
        from chunkformer import ChunkFormerModel as _CFM
        ChunkFormerModel = _CFM
    return ChunkFormerModel


# ============================================================================
# Configuration
# ============================================================================

CHUNKFORMER_MODEL = "khanhld/chunkformer-rnnt-large-vie"
CHUNK_SIZE = 64
LEFT_CONTEXT_SIZE = 128
RIGHT_CONTEXT_SIZE = 128
TOTAL_BATCH_DURATION = 14400
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
# ChunkFormer Service (Singleton)
# ============================================================================

class ChunkFormerService:
    """Singleton service for managing ChunkFormer model."""

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
                # Lazy import ChunkFormer (after environment variables are set)
                CFModel = get_chunkformer_model()

                # Load model
                self._model = CFModel.from_pretrained(CHUNKFORMER_MODEL)

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
                print(f"✓ ChunkFormer model loaded successfully from {CHUNKFORMER_MODEL}")
            finally:
                self._is_loading = False
        return self._model

    async def transcribe(
        self,
        audio_path: str,
        return_timestamps: bool = True
    ) -> dict:
        """
        Transcribe audio file using ChunkFormer.

        Args:
            audio_path: Path to audio file
            return_timestamps: Whether to include timestamps

        Returns:
            Dictionary with 'text' and 'segments' keys
        """
        model = await self.get_model()

        # Use endless_decode for long-form audio
        result = model.endless_decode(
            audio_path=audio_path,
            chunk_size=CHUNK_SIZE,
            left_context_size=LEFT_CONTEXT_SIZE,
            right_context_size=RIGHT_CONTEXT_SIZE,
            total_batch_duration=TOTAL_BATCH_DURATION,
            return_timestamps=return_timestamps
        )

        if return_timestamps:
            # Result is list of segments with timestamps
            segments = result
            text = " ".join(seg.get("decode", "") for seg in segments)
            return {
                "text": text,
                "segments": segments
            }
        else:
            # Result is just text string
            return {
                "text": result,
                "segments": []
            }


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
    title="Audio Transcription Server",
    description="Transcribe audio using ChunkFormer ASR model",
    version="1.0.0"
)

# Singleton service instance
service = ChunkFormerService()


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", summary="Root")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Audio Transcription Server",
        "version": "1.0.0",
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
    print("  Audio Transcription Server")
    print("=" * 60)
    print(f"  Model:  {CHUNKFORMER_MODEL}")
    print(f"  Device: {DEVICE.upper()}")
    print(f"  Server: http://{HOST}:{PORT}")
    print(f"  Docs:   http://{HOST}:{PORT}/docs")
    print("=" * 60)
    print()

    uvicorn.run(
        "server_chunkformer_model:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
