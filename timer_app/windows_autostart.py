from __future__ import annotations

import sys

if sys.platform != "win32":
    def set_autostart(enabled: bool, exe_path: str) -> None:
        return
else:
    import winreg

    _KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _APP_VALUE = "TimerApp"

    def set_autostart(enabled: bool, exe_path: str) -> None:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _KEY_PATH, 0, winreg.KEY_SET_VALUE
        )
        try:
            if enabled:
                quoted = exe_path if exe_path.startswith('"') else f'"{exe_path}"'
                winreg.SetValueEx(key, _APP_VALUE, 0, winreg.REG_SZ, quoted)
            else:
                try:
                    winreg.DeleteValue(key, _APP_VALUE)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
