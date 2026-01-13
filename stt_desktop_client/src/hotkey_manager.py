from pynput import keyboard
import threading
from typing import Callable, Optional


class GlobalHotkeyManager:
    """Cross-platform global hotkey manager using pynput."""

    def __init__(self):
        self.hotkeys = {}
        self.listener: Optional[keyboard.Listener] = None
        self.hotkey_objects = []

    def register_hotkey(self, key_combo: str, callback: Callable):
        """Register a global hotkey.

        Args:
            key_combo: Hotkey string, e.g., '<ctrl>+<alt>+r'
            callback: Function to call when hotkey is pressed
        """
        self.hotkeys[key_combo] = callback

    def _create_hotkey(self, combo: str, callback: Callable):
        return keyboard.HotKey(
            keyboard.HotKey.parse(combo),
            callback
        )

    def start(self):
        """Start listening for hotkeys."""
        self.hotkey_objects = []
        for combo, callback in self.hotkeys.items():
            hotkey = self._create_hotkey(combo, callback)
            self.hotkey_objects.append(hotkey)

        def on_press(key):
            try:
                for hotkey in self.hotkey_objects:
                    hotkey.press(self.listener.canonical(key))
            except Exception:
                pass

        def on_release(key):
            try:
                for hotkey in self.hotkey_objects:
                    hotkey.release(self.listener.canonical(key))
            except Exception:
                pass

        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        self.listener.start()
        print("Global hotkeys started")

    def stop(self):
        """Stop listening for hotkeys."""
        if self.listener:
            self.listener.stop()
            print("Global hotkeys stopped")
