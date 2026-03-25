from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Tuple

from timer_app.database import Database


EXPORT_HEADERS = ("work_name", "start_local", "end_local", "duration_hours")


def export_csv(path: Path, rows: Iterable[Tuple[str, datetime, datetime, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(EXPORT_HEADERS)
        for work_name, start, end, hours in rows:
            w.writerow(
                (
                    work_name,
                    start.isoformat(timespec="seconds"),
                    end.isoformat(timespec="seconds"),
                    f"{hours:.4f}",
                )
            )


def import_csv(db: Database, path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        # Accept flexible column names
        def col(*names: str) -> str:
            for n in names:
                if n in reader.fieldnames:
                    return n
                for h in reader.fieldnames:
                    if h and h.strip().lower() == n:
                        return h
            raise KeyError(names[0])

        wn = col("work_name", "work", "category")
        st = col("start_local", "start", "start_ts")
        et = col("end_local", "end", "end_ts")
        inserted = 0
        batch: List[Tuple[int, datetime, datetime]] = []
        for row in reader:
            name = (row.get(wn) or "").strip()
            if not name:
                continue
            ss = (row.get(st) or "").strip()
            es = (row.get(et) or "").strip()
            if not ss or not es:
                continue
            start = datetime.fromisoformat(ss)
            end = datetime.fromisoformat(es)
            if end < start:
                continue
            wid = db.ensure_work(name)
            batch.append((wid, start, end))
            inserted += 1
        if batch:
            db.import_sessions(batch)
    return inserted


def export_to_string(rows: Iterable[Tuple[str, datetime, datetime, float]]) -> str:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_HEADERS)
    for work_name, start, end, hours in rows:
        w.writerow(
            (
                work_name,
                start.isoformat(timespec="seconds"),
                end.isoformat(timespec="seconds"),
                f"{hours:.4f}",
            )
        )
    return buf.getvalue()
