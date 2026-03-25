from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from timer_app.database import Database
from timer_app.timeutil import local_now


def overlap_seconds(
    range_start: datetime, range_end: datetime, seg_start: datetime, seg_end: datetime
) -> float:
    s = max(range_start, seg_start)
    e = min(range_end, seg_end)
    if e <= s:
        return 0.0
    return (e - s).total_seconds()


def totals_by_work(
    db: Database, range_start: datetime, range_end: datetime
) -> List[Tuple[str, float]]:
    rows = db.sessions_in_range(range_start, range_end)
    now = local_now()
    totals: Dict[str, float] = defaultdict(float)
    for r in rows:
        eff_end = r.end_ts if r.end_ts else now
        sec = overlap_seconds(range_start, range_end, r.start_ts, eff_end)
        if sec > 0:
            totals[r.work_name] += sec
    return sorted(totals.items(), key=lambda x: (-x[1], x[0].lower()))


def session_rows_clipped(
    db: Database, range_start: datetime, range_end: datetime
) -> List[Tuple[str, datetime, datetime, float]]:
    """Rows for table: work_name, start, end (clipped), hours."""
    rows = db.sessions_in_range(range_start, range_end)
    now = local_now()
    out: List[Tuple[str, datetime, datetime, float]] = []
    for r in rows:
        eff_end = r.end_ts if r.end_ts else now
        s = max(r.start_ts, range_start)
        e = min(eff_end, range_end)
        if e <= s:
            continue
        sec = (e - s).total_seconds()
        out.append((r.work_name, s, e, sec / 3600.0))
    return sorted(out, key=lambda x: x[1])
