import sys
import signal
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from hotkey_manager import GlobalHotkeyManager
from server_manager import ServerManager
from tray_app import TrayApplication
import threading
import time

# Global flag for signal handling
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Set shutdown flag when signal received."""
    global _shutdown_requested
    _shutdown_requested = True


class STTDesktopClient:
    """Main application combining hotkeys, recording, and tray UI."""

    def __init__(
        self,
        stt_server_url: str = "http://localhost:8000",
        hotkey_combo: str = '<ctrl>+<alt>+r',
        server_script: str = None,
        auto_start: bool = True
    ):
        self.stt_server_url = stt_server_url
        self.hotkey_combo = hotkey_combo
        self.auto_start = auto_start

        # Initialize components
        self.hotkey_manager = GlobalHotkeyManager()
        self.server_manager = ServerManager(
            server_url=stt_server_url,
            server_script_path=server_script
        )
        self.tray_app = None
        self.hotkey_thread = None

    def run(self):
        """Start the application."""
        # Check server connection and start if needed
        print(f"Checking STT server at {self.stt_server_url}...")

        if not self.server_manager.is_running():
            if self.auto_start and self.server_manager.server_script_path:
                print("Server not running, attempting to start...")
                if not self.server_manager.start():
                    raise RuntimeError("Failed to start STT server")
            else:
                print("Server not running and no server script configured")
        else:
            print("Server already running")

        # Create tray app (this starts QApplication)
        self.tray_app = TrayApplication(
            stt_server_url=self.stt_server_url,
            hotkey=self.hotkey_combo,
            cleanup_callback=self._cleanup
        )

        # Register hotkey that triggers tray app toggle
        def on_hotkey():
            self.tray_app.toggle_recording()

        self.hotkey_manager.register_hotkey(self.hotkey_combo, on_hotkey)

        # Start hotkey listener in separate thread
        self.hotkey_thread = threading.Thread(
            target=self.hotkey_manager.start,
            daemon=True
        )
        self.hotkey_thread.start()

        print(f"Global hotkey registered: {self.hotkey_combo}")
        print("Press the hotkey to start/stop recording")
        print("Right-click the tray icon for options")

        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        # Setup QTimer to check for shutdown flag (Qt-aware signal handling)
        from PyQt6.QtCore import QTimer
        self._shutdown_timer = QTimer()
        self._shutdown_timer.timeout.connect(self._check_shutdown)
        self._shutdown_timer.start(500)  # Check every 500ms

        # Run Qt event loop
        return self.tray_app.run()

    def _check_shutdown(self):
        """Check if shutdown was requested via signal."""
        global _shutdown_requested
        if _shutdown_requested:
            print("\nShutting down...")
            self._cleanup()
            if self.tray_app and self.tray_app.app:
                self.tray_app.app.quit()

    def _cleanup(self):
        """Cleanup resources on application exit."""
        self.hotkey_manager.stop()
        self.server_manager.stop()


def main():
    """Application entry point."""
    import argparse

    # Default server script path (relative to this file)
    default_server_script = str(Path(__file__).parent.parent.parent / "stt_server" / "server_sherpa_onnx.py")

    parser = argparse.ArgumentParser(
        description="STT Desktop Client - Record and transcribe audio"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="STT server URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--hotkey",
        default="<ctrl>+<alt>+r",
        help="Global hotkey combination (default: <ctrl>+<alt>+r)"
    )
    parser.add_argument(
        "--server-script",
        default=default_server_script,
        help=f"Path to STT server script for auto-start (default: {default_server_script})"
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Disable automatic server starting"
    )

    args = parser.parse_args()

    app = STTDesktopClient(
        stt_server_url=args.server,
        hotkey_combo=args.hotkey,
        server_script=args.server_script,
        auto_start=not args.no_auto_start
    )

    sys.exit(app.run() or 0)


if __name__ == "__main__":
    main()
