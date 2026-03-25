from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QStyle, QSystemTrayIcon

from timer_app.hotkey_listener import HotkeyListener
from timer_app.paths import app_executable_path, app_icon_path
from timer_app.power_suspend import SuspendFilter
from timer_app.session_service import SessionService
from timer_app.settings_store import AppSettings
from timer_app.timeutil import ms_until, next_midnight
from timer_app.ui_main import MainWindow
from timer_app.windows_autostart import set_autostart


SERVER_NAME = "TimerAppSingleInstance"


class Bridge(QObject):
    show_window = Signal()
    hotkey_pressed = Signal()


class TimerApplication(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app_icon = self._resolve_app_icon()
        self._app.setWindowIcon(self._app_icon)
        self._settings = AppSettings()
        self._service = SessionService()
        self._bridge = Bridge()
        self._bridge.show_window.connect(self._show_main)
        self._bridge.hotkey_pressed.connect(self._show_main)

        self._server: Optional[QLocalServer] = None
        if not self._try_single_instance():
            sys.exit(0)

        self._win = MainWindow(self._service, settings=self._settings)
        self._win.setWindowIcon(self._app_icon)
        self._win.request_hide.connect(self._hide_main)
        self._win.tracking_changed.connect(self._update_tray_tooltip)
        self._win.settings_changed.connect(self._restart_hotkey)

        self._tray = QSystemTrayIcon(self._app)
        self._tray.setIcon(self._app_icon)
        self._tray.setToolTip("Timer")
        self._build_tray_menu()
        self._tray.show()
        self._tray.showMessage(
            "Timer",
            "Timer is running in the background.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

        self._hotkey = HotkeyListener()
        self._restart_hotkey()

        for msg in self._service.reconcile_stale_open_sessions():
            self._tray.showMessage("Timer", msg, QSystemTrayIcon.MessageIcon.Warning, 8000)

        self._schedule_midnight()

        if SuspendFilter is not None:
            filt = SuspendFilter(self._on_suspend)
            self._app.installNativeEventFilter(filt)

        self._sync_autostart_with_settings()
        self._update_tray_tooltip()

    def _try_single_instance(self) -> bool:
        sock = QLocalSocket()
        sock.connectToServer(SERVER_NAME)
        if sock.waitForConnected(300):
            sock.write(b"SHOW\n")
            sock.waitForBytesWritten(500)
            sock.disconnectFromServer()
            return False
        sock.abort()

        self._server = QLocalServer(self)
        if not self._server.listen(SERVER_NAME):
            self._server.removeServer(SERVER_NAME)
            self._server.listen(SERVER_NAME)
        self._server.newConnection.connect(self._on_secondary_instance)
        return True

    @Slot()
    def _on_secondary_instance(self) -> None:
        client = self._server.nextPendingConnection()
        if client is None:
            return
        client.waitForReadyRead(200)
        client.readAll()
        self._bridge.show_window.emit()

    def _build_tray_menu(self) -> None:
        menu = self._tray.contextMenu()
        if menu is None:
            from PySide6.QtWidgets import QMenu

            menu = QMenu()
            self._tray.setContextMenu(menu)

        menu.clear()
        act_show = QAction("Show", self)
        act_show.triggered.connect(self._show_main)
        menu.addAction(act_show)
        act_stop = QAction("Stop tracking", self)
        act_stop.triggered.connect(self._win._on_stop)
        menu.addAction(act_stop)
        act_dash = QAction("Dashboard…", self)
        act_dash.triggered.connect(self._win._open_dashboard)
        menu.addAction(act_dash)
        act_set = QAction("Settings…", self)
        act_set.triggered.connect(self._win._open_settings)
        menu.addAction(act_set)
        menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

    def _sync_autostart_with_settings(self) -> None:
        if self._settings.autostart():
            set_autostart(True, self._settings.autostart_executable() or app_executable_path())

    def _restart_hotkey(self) -> None:
        self._hotkey.stop()
        combo = self._settings.hotkey()

        def on_activate() -> None:
            self._bridge.hotkey_pressed.emit()

        try:
            self._hotkey.start(combo, on_activate)
        except Exception as e:
            QMessageBox.warning(
                None,
                "Hotkey",
                f"Could not register hotkey {combo!r}: {e}\n"
                "Change it in Settings and restart the app.",
            )

    def _schedule_midnight(self) -> None:
        ms = ms_until(next_midnight())
        QTimer.singleShot(ms, self._on_midnight)

    @Slot()
    def _on_midnight(self) -> None:
        for msg in self._service.rollover_if_midnight():
            self._tray.showMessage("Timer", msg, QSystemTrayIcon.MessageIcon.Warning, 8000)
        self._update_tray_tooltip()
        self._schedule_midnight()

    def _on_suspend(self) -> None:
        self._service.suspend_end_session()
        self._update_tray_tooltip()

    @Slot()
    def _show_main(self) -> None:
        self._win.showNormal()
        self._win.raise_()
        self._win.activateWindow()
        self._win._refresh_work_list()
        le = self._win._combo.lineEdit()
        le.setFocus()
        le.selectAll()

    @Slot()
    def _hide_main(self) -> None:
        self._win.hide()

    @Slot()
    def _update_tray_tooltip(self) -> None:
        a = self._service.active()
        if a:
            self._tray.setToolTip(f"Timer — {a.work_name} (since {a.started_at:%H:%M})")
        else:
            self._tray.setToolTip("Timer — not tracking")

    def _quit(self) -> None:
        self._hotkey.stop()
        self._app.quit()

    def run(self) -> int:
        return self._app.exec()

    def _resolve_app_icon(self) -> QIcon:
        p = app_icon_path()
        if p is not None:
            ic = QIcon(str(p))
            if not ic.isNull():
                return ic
        return self._app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
