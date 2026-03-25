from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from timer_app.paths import app_executable_path
from timer_app.settings_store import AppSettings
from timer_app.windows_autostart import set_autostart


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Timer — Settings")
        self.setModal(True)

        self._hotkey = QLineEdit(settings.hotkey())
        self._hotkey.setPlaceholderText("<ctrl>+<alt>+t")
        self._auto = QCheckBox("Start with Windows")
        self._auto.setChecked(settings.autostart())

        hint = QLabel(
            "Hotkey uses pynput format (e.g. <ctrl>+<alt>+t). "
            "Restart the app after changing the hotkey."
        )
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.TextFormat.PlainText)

        form = QFormLayout()
        form.addRow("Global hotkey:", self._hotkey)
        form.addRow(self._auto)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(hint)
        root.addWidget(buttons)

    def _save(self) -> None:
        hk = self._hotkey.text().strip() or "<ctrl>+<alt>+t"
        self._settings.set_hotkey(hk)
        self._settings.set_autostart(self._auto.isChecked())
        exe = app_executable_path()
        self._settings.set_autostart_executable(exe)
        set_autostart(self._auto.isChecked(), exe)
        self.accept()
