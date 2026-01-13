"""
STT Server - Speech-to-Text API Service

A FastAPI-based speech transcription service using ChunkFormer ASR model,
optimized for Vietnamese language transcription.
"""

from .server import app, ChunkFormerService

__all__ = ["app", "ChunkFormerService"]
