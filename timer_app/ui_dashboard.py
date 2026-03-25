from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from timer_app.csv_handler import export_csv, import_csv
from timer_app.session_service import SessionService
from timer_app.stats import session_rows_clipped, totals_by_work
from timer_app.timeutil import start_of_day, today_local

try:
    from PySide6.QtCharts import (
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QChart,
        QChartView,
        QValueAxis,
    )

    _HAS_CHARTS = True
except ImportError:
    _HAS_CHARTS = False


class DashboardDialog(QDialog):
    def __init__(self, service: SessionService, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._db = service.db
        self.setWindowTitle("Timer — Dashboard")
        self.resize(900, 560)

        self._from = QDateEdit()
        self._to = QDateEdit()
        today = today_local()
        qd = QDate(today.year, today.month, today.day)
        self._from.setDate(qd)
        self._to.setDate(qd)
        self._from.setCalendarPopup(True)
        self._to.setCalendarPopup(True)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._reload)

        top = QHBoxLayout()
        top.addWidget(QLabel("From:"))
        top.addWidget(self._from)
        top.addWidget(QLabel("To:"))
        top.addWidget(self._to)
        top.addWidget(refresh)
        top.addStretch()

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Work", "Start (local)", "End (local)", "Hours"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self._chart_view: QWidget | None = None
        self._chart = None
        if _HAS_CHARTS:
            self._chart = QChart()
            self._chart.setTitle("Hours by work")
            self._chart.legend().setVisible(False)
            self._chart_view = QChartView(self._chart)
            self._chart_view.setRenderHint(self._chart_view.RenderHint.Antialiasing)

        self._split = QSplitter(Qt.Orientation.Vertical)
        self._split.addWidget(self._table)
        if self._chart_view is not None:
            self._split.addWidget(self._chart_view)

        exp = QPushButton("Export CSV…")
        exp.clicked.connect(self._export)
        imp = QPushButton("Import CSV…")
        imp.clicked.connect(self._import)

        btn_row = QHBoxLayout()
        btn_row.addWidget(exp)
        btn_row.addWidget(imp)
        btn_row.addStretch()

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self._split)
        root.addLayout(btn_row)

        self._reload()

    def _range(self) -> tuple[datetime, datetime]:
        d0 = self._from.date().toPython()
        d1 = self._to.date().toPython()
        start = start_of_day(d0)
        end = datetime.combine(d1, time(23, 59, 59, 999999))
        if end < start:
            start, end = end, start
        return start, end

    def _reload(self) -> None:
        start, end = self._range()
        rows = session_rows_clipped(self._db, start, end)
        self._table.setRowCount(len(rows))
        for i, (name, s, e, h) in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(
                i, 1, QTableWidgetItem(s.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self._table.setItem(
                i, 2, QTableWidgetItem(e.strftime("%Y-%m-%d %H:%M:%S"))
            )
            it = QTableWidgetItem(f"{h:.3f}")
            it.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 3, it)

        if not _HAS_CHARTS or self._chart is None:
            return
        totals = totals_by_work(self._db, start, end)
        self._chart.removeAllSeries()
        if not totals:
            return
        names = [t[0] for t in totals]
        hours = [t[1] / 3600.0 for t in totals]
        bar_set = QBarSet("Hours")
        for h in hours:
            bar_set.append(float(h))
        series = QBarSeries()
        series.append(bar_set)
        self._chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        for n in names:
            axis_x.append(n)
        self._chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        axis_y.setTitleText("Hours")
        mx = max(hours) if hours else 1.0
        axis_y.setRange(0, max(mx * 1.1, 0.1))
        self._chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _export(self) -> None:
        start, end = self._range()
        rows = session_rows_clipped(self._db, start, end)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV (*.csv)"
        )
        if not path:
            return
        export_csv(Path(path), rows)
        QMessageBox.information(self, "Export", "CSV export finished.")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            n = import_csv(self._db, Path(path))
        except Exception as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return
        QMessageBox.information(self, "Import", f"Imported {n} session row(s).")
        self._reload()
