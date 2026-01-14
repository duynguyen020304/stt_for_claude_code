"""
Sherpa-ONNX Service Layer

Provides speech-to-text transcription using sherpa-onnx with Vietnamese
Zipformer Transducer model.

Model: csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20
"""

import os
import wave
import asyncio
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# Lazy import of sherpa_onnx to avoid blocking if not installed
sherpa_onnx = None


def get_sherpa_onnx():
    """Lazy import of sherpa_onnx."""
    global sherpa_onnx
    if sherpa_onnx is None:
        try:
            import sherpa_onnx as _sherpa_onnx
            sherpa_onnx = _sherpa_onnx
        except ImportError:
            raise ImportError(
                "sherpa-onnx is not installed. Please install it with:\n"
                "  pip install sherpa-onnx"
            )
    return sherpa_onnx


# ============================================================================
# Configuration
# ============================================================================

SHERPA_ONNX_MODEL = "csukuangfj/sherpa-onnx-zipformer-vi-2025-04-20"
DEFAULT_MODEL_DIR = "./models/sherpa-onnx-vi"
DEFAULT_NUM_THREADS = 4
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_DEVICE = "cpu"


# ============================================================================
# Helper Functions
# ============================================================================

def ensure_model_downloaded(
    model_id: str,
    local_dir: str
) -> str:
    """
    Download model from Hugging Face if not present.

    Args:
        model_id: Hugging Face model ID
        local_dir: Local directory to store model

    Returns:
        Path to model directory
    """
    model_path = Path(local_dir)

    if model_path.exists():
        # Check if required files exist
        required_files = [
            "encoder-epoch-12-avg-8.onnx",
            "decoder-epoch-12-avg-8.onnx",
            "joiner-epoch-12-avg-8.onnx",
            "tokens.txt"
        ]
        if all((model_path / f).exists() for f in required_files):
            print(f"✓ Model found at {local_dir}")
            return str(model_path)

    # Download model
    print(f"Downloading model {model_id} to {local_dir}...")
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=model_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False
        )
        print(f"✓ Model downloaded successfully")
        return str(model_path)
    except ImportError:
        raise ImportError(
            "huggingface-hub is not installed. Please install it with:\n"
            "  pip install huggingface-hub"
        )


def convert_timestamps_to_segments(
    text: str,
    timestamps: List[float]
) -> List[Dict]:
    """
    Convert token-level timestamps to word/segment format.

    Args:
        text: Transcribed text
        timestamps: End timestamps for each token

    Returns:
        List of segment dicts with 'decode', 'start', 'end' keys
    """
    words = text.split()
    segments = []

    for i, word in enumerate(words):
        # Calculate start and end time for each word
        if i == 0:
            start = 0.0
        elif i - 1 < len(timestamps):
            start = timestamps[i - 1]
        else:
            start = timestamps[-1] if timestamps else 0.0

        if i < len(timestamps):
            end = timestamps[i]
        else:
            end = timestamps[-1] if timestamps else start

        segments.append({
            "decode": word,
            "start": start,
            "end": end
        })

    return segments


def read_wav_file(audio_path: str) -> np.ndarray:
    """
    Read WAV file and return normalized float32 numpy array.

    Args:
        audio_path: Path to WAV file

    Returns:
        Normalized audio array (float32, range [-1, 1])
    """
    with wave.open(audio_path, 'rb') as wf:
        frames = wf.getnframes()
        audio = np.frombuffer(wf.readframes(frames), dtype=np.int16)
        # Normalize to [-1, 1] range
        audio = audio.astype(np.float32) / 32768.0
        return audio


# ============================================================================
# SherpaONNXService (Singleton)
# ============================================================================

class SherpaONNXService:
    """Singleton service for managing Sherpa-ONNX model."""

    _instance = None
    _recognizer = None
    _is_loading = False
    _model_dir = None
    _device = DEFAULT_DEVICE
    _num_threads = DEFAULT_NUM_THREADS

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_id: str = SHERPA_ONNX_MODEL,
        model_dir: str = DEFAULT_MODEL_DIR,
        num_threads: int = DEFAULT_NUM_THREADS,
        device: str = DEFAULT_DEVICE
    ):
        """
        Initialize the service (only called once due to singleton).

        Args:
            model_id: Hugging Face model ID
            model_dir: Local model directory
            num_threads: Number of CPU threads
            device: Execution provider (cpu, cuda, coreml)
        """
        # Only set these if not already set (singleton pattern)
        if self._model_dir is None:
            self._model_id = model_id
            self._model_dir = model_dir
            self._num_threads = num_threads
            self._device = device

    async def get_model(self):
        """Lazy load the model on first request."""
        if self._recognizer is None:
            if self._is_loading:
                # Wait if another request is loading the model
                while self._is_loading:
                    await asyncio.sleep(0.1)
                return self._recognizer

            self._is_loading = True
            try:
                # Ensure model is downloaded
                model_path = ensure_model_downloaded(
                    self._model_id,
                    self._model_dir
                )

                # Import sherpa-onnx
                sherpa = get_sherpa_onnx()

                # Build model file paths
                encoder_path = str(Path(model_path) / "encoder-epoch-12-avg-8.onnx")
                decoder_path = str(Path(model_path) / "decoder-epoch-12-avg-8.onnx")
                joiner_path = str(Path(model_path) / "joiner-epoch-12-avg-8.onnx")
                tokens_path = str(Path(model_path) / "tokens.txt")

                # Verify files exist
                for path, name in [
                    (encoder_path, "encoder"),
                    (decoder_path, "decoder"),
                    (joiner_path, "joiner"),
                    (tokens_path, "tokens")
                ]:
                    if not Path(path).exists():
                        raise FileNotFoundError(f"{name} file not found: {path}")

                # Create recognizer using transducer model
                self._recognizer = sherpa.OfflineRecognizer.from_transducer(
                    encoder=encoder_path,
                    decoder=decoder_path,
                    joiner=joiner_path,
                    tokens=tokens_path,
                    num_threads=self._num_threads,
                    sample_rate=DEFAULT_SAMPLE_RATE,
                    feature_dim=80,
                    decoding_method="greedy_search",
                    provider=self._device,
                    debug=False
                )

                device_upper = self._device.upper()
                print(f"✓ Sherpa-ONNX model loaded on {device_upper}")
                print(f"✓ Model: {self._model_id}")
            finally:
                self._is_loading = False

        return self._recognizer

    async def transcribe(
        self,
        audio_path: str,
        return_timestamps: bool = True
    ) -> Dict:
        """
        Transcribe audio file using Sherpa-ONNX.

        Args:
            audio_path: Path to audio file (WAV, 16kHz, mono)
            return_timestamps: Whether to include timestamps

        Returns:
            Dictionary with 'text' and 'segments' keys
        """
        recognizer = await self.get_model()

        # Load audio file
        audio = read_wav_file(audio_path)

        # Create stream and accept waveform
        stream = recognizer.create_stream()
        stream.accept_waveform(DEFAULT_SAMPLE_RATE, audio)

        # Decode
        recognizer.decode_stream(stream)

        # Get result from stream
        result = stream.result

        text = result.text

        if return_timestamps:
            # Convert token timestamps to segments
            timestamps = getattr(result, 'timestamps', [])

            if timestamps:
                segments = convert_timestamps_to_segments(text, timestamps)
            else:
                # No timestamps available, create a single segment
                segments = [{
                    "decode": text,
                    "start": 0.0,
                    "end": 0.0
                }]

            return {
                "text": text,
                "segments": segments
            }
        else:
            # Return text only
            return {
                "text": text,
                "segments": []
            }
