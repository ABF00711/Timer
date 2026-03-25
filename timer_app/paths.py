from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def package_root() -> Path:
    """Directory that contains `assets/` (dev: repo root; frozen: PyInstaller bundle)."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def app_icon_path() -> Optional[Path]:
    p = package_root() / "assets" / "app.ico"
    return p if p.is_file() else None


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / ".local" / "share")
    root = Path(base) / "TimerApp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_path() -> Path:
    return app_data_dir() / "sessions.db"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_executable_path() -> str:
    if is_frozen():
        return sys.executable
    return sys.argv[0]
