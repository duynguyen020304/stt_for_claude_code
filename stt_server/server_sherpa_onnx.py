"""
Audio Transcription Server using Sherpa-ONNX

A FastAPI-based server that receives audio from microphone recording apps
and returns transcriptions with timestamps.

Uses the Sherpa-ONNX Vietnamese Zipformer Transducer model:
csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20

Run with: python server_sherpa_onnx.py
API docs will be available at: http://localhost:8001/docs
"""

import os
import tempfile
import base64
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Import service layer
from sherpa_onnx_service import SherpaONNXService

# ============================================================================
# Configuration
# ============================================================================

SHERPA_ONNX_MODEL = "csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20"
MODEL_DIR = "./models/sherpa-onnx-vi"
NUM_THREADS = 4
HOST = "localhost"
PORT = 8000  # Different port to avoid conflict with ChunkFormer server

# Device configuration
DEVICE = "cpu"  # Options: "cpu", "cuda", "coreml"

# ============================================================================
# Pydantic Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    model: str
    device: str


class TranscribeResponse(BaseModel):
    """Transcription response."""
    text: str
    segments: List[dict]

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Audio Transcription Server (Sherpa-ONNX)",
    description="Transcribe Vietnamese audio using Sherpa-ONNX Zipformer Transducer model",
    version="1.0.0"
)

# Singleton service instance
service = SherpaONNXService(
    model_id=SHERPA_ONNX_MODEL,
    model_dir=MODEL_DIR,
    num_threads=NUM_THREADS,
    device=DEVICE
)

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", summary="Root")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Audio Transcription Server (Sherpa-ONNX)",
        "version": "1.0.0",
        "model": SHERPA_ONNX_MODEL,
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
    model_loaded = service._recognizer is not None
    return {
        "status": "healthy" if model_loaded else "initializing",
        "model_loaded": model_loaded,
        "model": SHERPA_ONNX_MODEL,
        "device": DEVICE.upper()
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

    The audio should be Vietnamese speech for best results with this model.
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

    Client sends: {"audio_data": "<base64_audio_bytes>"}
    Server responds: {"type": "transcription", "text": "...", "segments": [...]}

    Note: Each audio chunk is transcribed independently without context
    from previous chunks. For continuous recording, send discrete audio
    segments (e.g., 5-10 seconds each).
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
    print("  Audio Transcription Server (Sherpa-ONNX)")
    print("=" * 60)
    print(f"  Model:  {SHERPA_ONNX_MODEL}")
    print(f"  Device: {DEVICE.upper()}")
    print(f"  Server: http://{HOST}:{PORT}")
    print(f"  Docs:   http://{HOST}:{PORT}/docs")
    print("=" * 60)
    print()

    uvicorn.run(
        "server_sherpa_onnx:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info"
    )
