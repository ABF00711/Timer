from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from timer_app.session_service import SessionService
from timer_app.settings_store import AppSettings
from timer_app.work_resolve import resolve_work_name


class MainWindow(QWidget):
    """Quick launcher: pick work, Enter to start tracking and hide."""

    tracking_changed = Signal()
    request_hide = Signal()
    settings_changed = Signal()

    def __init__(
        self,
        service: SessionService,
        settings: AppSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._settings = settings
        self._db = service.db
        self.setWindowTitle("Timer")
        self.setMinimumWidth(420)

        self._status = QLabel()
        self._status.setWordWrap(True)

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        le = self._combo.lineEdit()
        assert isinstance(le, QLineEdit)
        le.setPlaceholderText("Type work name, Enter to start tracking…")

        self._refresh_work_list()
        self._completer = QCompleter(self._combo.model(), self._combo)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self._combo.setCompleter(self._completer)

        le.returnPressed.connect(self._on_confirm)

        self._btn_stop = QPushButton("Stop tracking")
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_dash = QPushButton("Dashboard…")
        self._btn_dash.clicked.connect(self._open_dashboard)

        self._btn_settings = QPushButton("Settings…")
        self._btn_settings.clicked.connect(self._open_settings)

        row = QHBoxLayout()
        row.addWidget(self._btn_stop)
        row.addWidget(self._btn_dash)
        row.addWidget(self._btn_settings)

        root = QVBoxLayout(self)
        root.addWidget(self._status)
        root.addWidget(self._combo)
        root.addLayout(row)

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_status)
        self._tick.start(15_000)
        self._refresh_status()

    def _refresh_work_list(self) -> None:
        names = self._db.list_work_names()
        self._combo.clear()
        self._combo.addItems(names)

    def refresh_after_settings(self) -> None:
        self._refresh_work_list()

    def _refresh_status(self) -> None:
        active = self._service.active()
        if active:
            self._status.setText(
                f"Tracking: {active.work_name} — started "
                f"{active.started_at.strftime('%Y-%m-%d %H:%M:%S')} (local)"
            )
        else:
            self._status.setText("Not tracking. Select a work and press Enter.")

    def _on_confirm(self) -> None:
        text = self._combo.currentText()
        names = self._db.list_work_names()
        name = resolve_work_name(text, names)
        if not name:
            return
        try:
            self._service.start_or_switch(name)
        except ValueError as e:
            QMessageBox.warning(self, "Timer", str(e))
            return
        self._refresh_work_list()
        self._combo.setEditText(name)
        self._refresh_status()
        self.tracking_changed.emit()
        self.request_hide.emit()

    def _on_stop(self) -> None:
        if self._service.stop():
            self._refresh_status()
            self.tracking_changed.emit()
        self.request_hide.emit()

    def _open_dashboard(self) -> None:
        from timer_app.ui_dashboard import DashboardDialog

        dlg = DashboardDialog(self._service, self)
        dlg.exec()

    def _open_settings(self) -> None:
        from timer_app.ui_settings import SettingsDialog

        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self.refresh_after_settings()
            self.settings_changed.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hide instead of quitting when user closes window."""
        event.ignore()
        self.request_hide.emit()
