from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray

if sys.platform != "win32":
    SuspendFilter = None  # type: ignore[misc, assignment]
else:
    import ctypes
    from ctypes import wintypes

    WM_POWERBROADCAST = 0x0218
    PBT_APMSUSPEND = 0x04

    class SuspendFilter(QAbstractNativeEventFilter):
        def __init__(self, on_suspend: Callable[[], None]) -> None:
            super().__init__()
            self._on_suspend = on_suspend

        def nativeEvent(self, eventType: QByteArray, message: int) -> tuple[bool, int]:
            try:
                if bytes(eventType) != b"windows_generic_MSG":
                    return False, 0
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_POWERBROADCAST and int(msg.wParam) == PBT_APMSUSPEND:
                    self._on_suspend()
            except Exception:
                pass
            return False, 0
