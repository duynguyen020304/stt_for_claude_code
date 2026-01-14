import subprocess
import sys
import time
from typing import Optional
import requests


class ServerManager:
    """Manages STT server subprocess lifecycle."""

    def __init__(self, server_url: str = "http://localhost:8000", server_script_path: Optional[str] = None):
        """Initialize the server manager.

        Args:
            server_url: URL where the server should be accessible
            server_script_path: Path to the server script to run
        """
        self.server_url = server_url
        self.server_script_path = server_script_path
        self.process: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        """Check if the server is currently running.

        Returns:
            True if server is running and responding to health checks
        """
        try:
            response = requests.get(f"{self.server_url}/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Start the server as a subprocess and wait for it to be ready.

        Returns:
            True if server started successfully and is ready, False otherwise
        """
        if not self.server_script_path:
            raise ValueError("server_script_path not set")

        if self.is_running():
            print("Server already running")
            return True

        python_exe = sys.executable
        try:
            self.process = subprocess.Popen(
                [python_exe, self.server_script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Starting STT server (PID: {self.process.pid})...")
            return self.wait_for_ready()
        except Exception as e:
            raise RuntimeError(f"Failed to start server: {e}")

    def stop(self):
        """Stop the server subprocess."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print(f"Server stopped (PID: {self.process.pid})")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print(f"Server force killed (PID: {self.process.pid})")
            finally:
                self.process = None

    def wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for the server to be ready and respond to health checks.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if server is ready, False if timeout exceeded
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                return True
            time.sleep(0.5)
        return False
