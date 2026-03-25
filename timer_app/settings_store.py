from __future__ import annotations

from PySide6.QtCore import QSettings

from timer_app.paths import app_executable_path


class AppSettings:
    def __init__(self) -> None:
        self._s = QSettings("ABF", "TimerApp")

    def hotkey(self) -> str:
        return str(self._s.value("hotkey", "<ctrl>+<alt>+t"))

    def set_hotkey(self, value: str) -> None:
        self._s.setValue("hotkey", value)

    def autostart(self) -> bool:
        return bool(self._s.value("autostart", False))

    def set_autostart(self, enabled: bool) -> None:
        self._s.setValue("autostart", enabled)

    def autostart_executable(self) -> str:
        return str(self._s.value("autostart_exe", app_executable_path()))

    def set_autostart_executable(self, path: str) -> None:
        self._s.setValue("autostart_exe", path)
