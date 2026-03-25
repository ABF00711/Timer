from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

from PySide6.QtCore import QDate, QMargins, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from timer_app.timeutil import format_duration_hms, start_of_day, today_local

try:
    from PySide6.QtCharts import (
        QBarCategoryAxis,
        QBarSet,
        QChart,
        QChartView,
        QHorizontalBarSeries,
        QValueAxis,
    )

    class OutsideLabelBarChartView(QChartView):
        """Paints value labels to the right of each bar (Qt's LabelsOutsideEnd is broken for QHorizontalBarSeries)."""

        def __init__(self, chart: QChart, parent=None) -> None:
            super().__init__(chart)
            self._bar_series: QHorizontalBarSeries | None = None
            self._bar_axis_values: list[float] = []
            self._label_texts: list[str] = []

        def set_bar_outside_labels(
            self,
            series: QHorizontalBarSeries,
            bar_axis_values: list[float],
            label_texts: list[str],
        ) -> None:
            self._bar_series = series
            self._bar_axis_values = list(bar_axis_values)
            self._label_texts = list(label_texts)
            QTimer.singleShot(0, self._repaint_viewport)
            QTimer.singleShot(80, self._repaint_viewport)

        def clear_bar_labels(self) -> None:
            self._bar_series = None
            self._bar_axis_values = []
            self._label_texts = []
            self._repaint_viewport()

        def _repaint_viewport(self) -> None:
            self.viewport().update()

        def resizeEvent(self, event) -> None:
            super().resizeEvent(event)
            self.viewport().update()

        def paintEvent(self, event) -> None:
            super().paintEvent(event)
            if not self._bar_series or not self._bar_axis_values:
                return
            chart = self.chart()
            if chart is None:
                return
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.setPen(QColor(30, 30, 30))
            font = p.font()
            font.setPointSize(9)
            p.setFont(font)
            fm = p.fontMetrics()
            for i, (val, text) in enumerate(
                zip(self._bar_axis_values, self._label_texts)
            ):
                pt = chart.mapToPosition(QPointF(float(val), i), self._bar_series)
                vp = self.mapFromScene(chart.mapToScene(pt))
                h = fm.height()
                baseline = int(vp.y() - h / 2 + fm.ascent())
                p.drawText(int(vp.x()) + 6, baseline, text)
            p.end()

    _HAS_CHARTS = True
except ImportError:
    OutsideLabelBarChartView = None  # type: ignore[misc, assignment]
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

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Delete", "Work", "Start (local)", "End (local)", "Duration"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 56)
        for col in range(1, 5):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)

        self._chart_view: QWidget | None = None
        self._chart = None
        if _HAS_CHARTS:
            self._chart = QChart()
            self._chart.setTitle("Time by work")
            self._chart.legend().setVisible(False)
            self._chart_view = OutsideLabelBarChartView(self._chart)
            self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._chart_view.setMinimumHeight(240)

        self._split = QSplitter(Qt.Orientation.Vertical)
        self._split.addWidget(self._table)
        if self._chart_view is not None:
            self._split.addWidget(self._chart_view)

        self._btn_delete = QPushButton("Delete selected")
        self._btn_delete.clicked.connect(self._delete_selected_sessions)

        exp = QPushButton("Export CSV…")
        exp.clicked.connect(self._export)
        imp = QPushButton("Import CSV…")
        imp.clicked.connect(self._import)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_delete)
        btn_row.addWidget(exp)
        btn_row.addWidget(imp)
        btn_row.addStretch()

        root = QVBoxLayout(self)
        root.addLayout(top)
        root.addWidget(self._split)
        root.addLayout(btn_row)

        self._reload()

    def _delete_selected_sessions(self) -> None:
        ids: list[int] = []
        for row in range(self._table.rowCount()):
            it = self._table.item(row, 0)
            if it is None:
                continue
            if it.checkState() != Qt.CheckState.Checked:
                continue
            sid = it.data(Qt.ItemDataRole.UserRole)
            if sid is not None:
                ids.append(int(sid))
        if not ids:
            QMessageBox.information(
                self, "Delete", "Check one or more sessions in the Delete column first."
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete sessions",
            f"Permanently delete {len(ids)} session(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for sid in ids:
            self._db.delete_session(sid)
        self._reload()

    def _range(self) -> tuple[datetime, datetime]:
        q0 = self._from.date()
        q1 = self._to.date()
        d0 = date(q0.year(), q0.month(), q0.day())
        d1 = date(q1.year(), q1.month(), q1.day())
        start = start_of_day(d0)
        end = datetime.combine(d1, time(23, 59, 59, 999999))
        if end < start:
            start, end = end, start
        return start, end

    def _reload(self) -> None:
        start, end = self._range()
        rows = session_rows_clipped(self._db, start, end)
        self._table.setRowCount(len(rows))
        for i, (sid, name, s, e, _) in enumerate(rows):
            cb = QTableWidgetItem()
            cb.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            cb.setCheckState(Qt.CheckState.Unchecked)
            cb.setData(Qt.ItemDataRole.UserRole, sid)
            cb.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 0, cb)

            w_it = QTableWidgetItem(name)
            w_it.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            self._table.setItem(i, 1, w_it)

            s_it = QTableWidgetItem(s.strftime("%Y-%m-%d %H:%M:%S"))
            s_it.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            self._table.setItem(i, 2, s_it)

            e_it = QTableWidgetItem(e.strftime("%Y-%m-%d %H:%M:%S"))
            e_it.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            self._table.setItem(i, 3, e_it)

            dur_sec = (e - s).total_seconds()
            d_it = QTableWidgetItem(format_duration_hms(dur_sec))
            d_it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            d_it.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(i, 4, d_it)

        if not _HAS_CHARTS or self._chart is None:
            return
        totals = totals_by_work(self._db, start, end)
        self._chart.removeAllSeries()
        for ax in list(self._chart.axes()):
            self._chart.removeAxis(ax)
        if not totals:
            self._chart_view.clear_bar_labels()
            return

        names = [t[0] for t in totals]
        seconds = [float(t[1]) for t in totals]
        max_sec = max(seconds) if seconds else 0.0
        # Minutes are easier to read than 0.003 h for short sessions.
        if max_sec < 3600.0:
            values = [s / 60.0 for s in seconds]
            unit = "Minutes"
        else:
            values = [s / 3600.0 for s in seconds]
            unit = "Hours"
        mx = max(values) if values else 0.0
        hi = max(mx * 1.15, 1e-6)
        if hi < 0.05:
            hi = max(0.05, mx * 2.0)

        self._chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)

        max_name_len = max((len(n) for n in names), default=8)
        left_margin = min(32 + max_name_len * 8, 480)
        # Room for outside labels (e.g. "123:45:67") past the bar end.
        self._chart.setMargins(QMargins(int(left_margin), 20, 100, 44))

        bar_set = QBarSet(unit)
        for v in values:
            bar_set.append(float(v))
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(False)
        self._chart.addSeries(series)

        axis_y = QBarCategoryAxis()
        # Do not use append(str) in a loop: PySide6 binds append to an overload that
        # iterates the string and adds one category per character ("input" -> i,n,p,u,t).
        axis_y.setCategories(names)
        axis_y.setTruncateLabels(False)
        self._chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        axis_x = QValueAxis()
        axis_x.setTitleText(unit)
        axis_x.setRange(0.0, hi)
        axis_x.setLabelFormat("%.2f" if max_sec < 3600.0 else "%.3f")
        axis_x.setMinorTickCount(0)
        self._chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        hms_labels = [format_duration_hms(sec) for sec in seconds]
        self._chart_view.set_bar_outside_labels(series, values, hms_labels)

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
