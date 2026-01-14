import os
import sys
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QMimeData

from audio_recorder import AudioRecorder
from stt_client import STTClient


class RecordingSignals(QObject):
    """Signals for thread-safe communication."""
    result_ready = pyqtSignal(dict)
    status_changed = pyqtSignal(str)


class TrayApplication:
    """System tray application for audio recording."""

    @staticmethod
    def create_microphone_icon(size: int = 64) -> QIcon:
        """Create a microphone icon programmatically."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors
        bg_color = QColor(74, 144, 217)
        stroke_color = QColor(44, 95, 141)
        white = QColor(255, 255, 255)

        # Circle background
        center = size // 2
        radius = size // 2 - 2
        painter.setBrush(bg_color)
        painter.setPen(QPen(stroke_color, 2))
        painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)

        # Microphone body (rounded rectangle)
        mic_width = 12
        mic_height = 20
        mic_x = center - mic_width // 2
        mic_y = center - 8
        painter.setBrush(white)
        painter.setPen(QPen(stroke_color, 1.5))
        painter.drawRoundedRect(mic_x, mic_y, mic_width, mic_height, 6, 6)

        # Microphone grille lines
        painter.setPen(QPen(QColor(224, 224, 224), 1))
        for y in range(mic_y + 6, mic_y + mic_height - 2, 4):
            painter.drawLine(mic_x + 2, y, mic_x + mic_width - 2, y)

        # Microphone stand
        pen = QPen(white, 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(center, mic_y + mic_height, center, mic_y + mic_height + 8)
        painter.drawLine(center - 6, mic_y + mic_height + 8, center + 6, mic_y + mic_height + 8)

        # Sound waves
        pen = QPen(white, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # First wave
        wave1_x = center + 10
        painter.drawArc(wave1_x, center - 6, 8, 12, 140 * 16, 80 * 16)
        # Second wave
        wave2_x = center + 16
        painter.drawArc(wave2_x, center - 8, 12, 16, 140 * 16, 80 * 16)

        painter.end()
        return QIcon(pixmap)

    def __init__(
        self,
        stt_server_url: str = "http://localhost:8000",
        hotkey: str = '<ctrl>+<alt>+r',
        cleanup_callback = None
    ):
        # Force Qt to use XCB backend on Linux for better clipboard support
        # This works around KDE Plasma Wayland clipboard bugs
        if sys.platform.startswith('linux'):
            os.environ['QT_QPA_PLATFORM'] = 'xcb'

        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Store cleanup callback for server cleanup
        self.cleanup_callback = cleanup_callback

        # Components
        self.recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            buffer_duration=30
        )
        self.stt_client = STTClient(stt_server_url)
        self.signals = RecordingSignals()

        # State
        self.is_recording = False
        self.temp_dir = Path(tempfile.gettempdir()) / "stt_recorder"
        self.temp_dir.mkdir(exist_ok=True)

        # Setup UI
        self.setup_tray()
        self.setup_signals()

        # Store hotkey callback
        self.hotkey_combo = hotkey
        self.hotkey_callback = None  # Will be set by main.py

    def setup_tray(self):
        """Setup system tray icon and menu."""
        # Create tray icon with microphone icon
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.create_microphone_icon())

        # Create menu
        menu = QMenu()

        self.record_action = QAction("Start Recording", menu)
        self.record_action.triggered.connect(self.toggle_recording)
        menu.addAction(self.record_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def setup_signals(self):
        """Setup signal connections."""
        self.signals.result_ready.connect(self.on_transcription_result)
        self.signals.status_changed.connect(self.on_status_changed)

    def toggle_recording(self):
        """Toggle recording state."""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        self.is_recording = True
        self.record_action.setText("Stop Recording")
        self.signals.status_changed.emit("Recording...")

        try:
            self.recorder.start()
        except Exception as e:
            self.signals.status_changed.emit(f"Error: {e}")
            self.is_recording = False
            self.record_action.setText("Start Recording")

    def stop_recording(self):
        """Stop recording and transcribe."""
        self.is_recording = False
        self.record_action.setText("Start Recording")
        self.signals.status_changed.emit("Processing...")

        try:
            audio = self.recorder.stop()

            if len(audio) == 0:
                self.signals.status_changed.emit("No audio recorded")
                return

            # Save to temp file
            temp_file = self.temp_dir / f"recording_{id(self)}.wav"
            self.recorder.save_to_wav(audio, str(temp_file))

            # Transcribe
            result = self.stt_client.transcribe_file(temp_file)
            self.signals.result_ready.emit(result)

            # Cleanup
            temp_file.unlink(missing_ok=True)

        except Exception as e:
            self.signals.status_changed.emit(f"Error: {e}")

    def on_transcription_result(self, result: dict):
        """Handle transcription result."""
        if "error" in result:
            self.show_message(f"Transcription Error", result["error"])
        elif "text" in result:
            text = result["text"]
            # Copy to clipboard using setMimeData for better Wayland support
            mime_data = QMimeData()
            mime_data.setText(text)
            self.app.clipboard().setMimeData(mime_data)
            # Show notification with clipboard confirmation
            self.show_message("Transcription", f"{text}\n\n(Copied to clipboard)")
        else:
            self.show_message("Result", str(result))

        self.signals.status_changed.emit("Ready")

    def on_status_changed(self, status: str):
        """Handle status change."""
        self.tray_icon.setToolTip(f"STT Recorder\n{status}")

    def show_message(self, title: str, message: str):
        """Show system tray notification."""
        self.tray_icon.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

    def quit(self):
        """Quit application."""
        if self.is_recording:
            self.recorder.stop()
        self.stt_client.close()
        # Call cleanup callback to stop server
        if self.cleanup_callback:
            self.cleanup_callback()
        self.app.quit()

    def run(self):
        """Run application."""
        return self.app.exec()
