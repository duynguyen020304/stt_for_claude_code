import requests
from pathlib import Path
from typing import Dict, Any


class STTClient:
    """HTTP client for the ChunkFormer STT service."""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.transcribe_url = f"{server_url}/transcribe"

    def transcribe_file(self, audio_file: Path) -> Dict[str, Any]:
        """Send audio file to STT server for transcription.

        Args:
            audio_file: Path to WAV audio file

        Returns:
            Transcription result with text and timestamps
        """
        try:
            with open(audio_file, 'rb') as f:
                files = {'audio': (audio_file.name, f, 'audio/wav')}
                response = requests.post(
                    self.transcribe_url,
                    files=files,
                    timeout=60
                )
                response.raise_for_status()
                return response.json()

        except requests.exceptions.ConnectionError:
            return {"error": "Cannot connect to STT server. Is it running?"}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out"}
        except requests.exceptions.HTTPError as e:
            return {"error": f"HTTP error: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}

    def check_health(self) -> bool:
        """Check if STT server is running."""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def close(self):
        """Close the client and release resources."""
        # No persistent connections to close in current implementation
        # This method is provided for future extensibility
        pass
