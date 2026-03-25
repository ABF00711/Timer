from __future__ import annotations

import threading
from typing import Callable, Optional

from pynput import keyboard


class HotkeyListener:
    """Runs pynput GlobalHotKeys in a daemon thread."""

    def __init__(self) -> None:
        self._listener: Optional[keyboard.Listener] = None
        self._hotkeys: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

    def start(self, combo: str, on_activate: Callable[[], None]) -> None:
        self.stop()
        gh = keyboard.GlobalHotKeys({combo: on_activate})
        self._hotkeys = gh
        gh.start()

    def stop(self) -> None:
        with self._lock:
            if self._hotkeys is not None:
                try:
                    self._hotkeys.stop()
                except Exception:
                    pass
                self._hotkeys = None
