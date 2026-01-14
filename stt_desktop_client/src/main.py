import sys
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from hotkey_manager import GlobalHotkeyManager
from server_manager import ServerManager
from tray_app import TrayApplication
import threading
import time


class STTDesktopClient:
    """Main application combining hotkeys, recording, and tray UI."""

    def __init__(
        self,
        stt_server_url: str = "http://localhost:8000",
        hotkey_combo: str = '<ctrl>+<alt>+r'
    ):
        self.stt_server_url = stt_server_url
        self.hotkey_combo = hotkey_combo

        # Initialize components
        self.hotkey_manager = GlobalHotkeyManager()
        self.server_manager = ServerManager(server_url=stt_server_url)
        self.tray_app = None
        self.hotkey_thread = None

    def run(self):
        """Start the application."""
        # Check server connection and start if needed
        print(f"Checking STT server at {self.stt_server_url}...")

        if not self.server_manager.is_running():
            if self.server_manager.server_script_path:
                print("Server not running, attempting to start...")
                if not self.server_manager.start():
                    raise RuntimeError("Failed to start STT server")
            else:
                print("Server not running and no server script configured")

        # Create tray app (this starts QApplication)
        self.tray_app = TrayApplication(
            stt_server_url=self.stt_server_url,
            hotkey=self.hotkey_combo
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
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Run Qt event loop
        return self.tray_app.run()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print("\nShutting down...")
        self.hotkey_manager.stop()
        sys.exit(0)


def main():
    """Application entry point."""
    import argparse

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

    args = parser.parse_args()

    app = STTDesktopClient(
        stt_server_url=args.server,
        hotkey_combo=args.hotkey
    )

    sys.exit(app.run() or 0)


if __name__ == "__main__":
    main()
