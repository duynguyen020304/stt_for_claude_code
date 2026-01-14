"""
STT Server - Speech-to-Text API Service

A FastAPI-based speech transcription service supporting multiple ASR backends:
- ChunkFormer: khanhld/chunkformer-rnnt-large-vie
- Parakeet: nvidia/parakeet-tdt_ctc-110m
- Sherpa-ONNX: k2-fsa/sherpa-onnx Zipformer
"""

# Default server (can be changed by modifying this import)
from .server_chunkformer_model import app, ChunkFormerService

# Alternative servers (available for direct import)
from .server_parakeet_model import app as parakeet_app, ParakeetService
from .server_sherpa_onnx import app as sherpa_app, SherpaONNXService

__all__ = [
    "app",
    "ChunkFormerService",
    "parakeet_app",
    "ParakeetService",
    "sherpa_app",
    "SherpaONNXService",
]
