from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable, Optional

from timer_app.paths import db_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id),
    start_ts TEXT NOT NULL,
    end_ts TEXT,
    CHECK (end_ts IS NULL OR end_ts >= start_ts)
);

CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_ts);
CREATE INDEX IF NOT EXISTS idx_sessions_work ON sessions(work_id);
"""


@dataclass(frozen=True)
class WorkRow:
    id: int
    name: str


@dataclass(frozen=True)
class SessionRow:
    id: int
    work_id: int
    work_name: str
    start_ts: datetime
    end_ts: Optional[datetime]


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _fmt_ts(dt: datetime) -> str:
    return dt.isoformat(timespec="microseconds")


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or db_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            try:
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_works_lower ON works(lower(name))"
                )
            except sqlite3.OperationalError:
                pass

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_work(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Work name is empty")
        with self._connect() as conn:
            cur = conn.execute("INSERT INTO works (name) VALUES (?)", (name,))
            return int(cur.lastrowid)

    def get_work_by_name(self, name: str) -> Optional[WorkRow]:
        name = name.strip()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name FROM works WHERE name = ?", (name,)
            ).fetchone()
        if not row:
            return None
        return WorkRow(id=row["id"], name=row["name"])

    def find_work_id_case_insensitive(self, name: str) -> Optional[int]:
        needle = name.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM works WHERE lower(name) = ?", (needle,)
            ).fetchone()
        return int(row["id"]) if row else None

    def list_work_names(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM works ORDER BY lower(name)"
            ).fetchall()
        return [r["name"] for r in rows]

    def ensure_work(self, name: str) -> int:
        existing = self.find_work_id_case_insensitive(name)
        if existing is not None:
            return existing
        try:
            return self.add_work(name.strip())
        except sqlite3.IntegrityError:
            got = self.find_work_id_case_insensitive(name)
            if got is not None:
                return got
            raise

    def insert_session(
        self, work_id: int, start: datetime, end: Optional[datetime]
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (work_id, start_ts, end_ts) VALUES (?,?,?)",
                (work_id, _fmt_ts(start), _fmt_ts(end) if end else None),
            )
            return int(cur.lastrowid)

    def update_session_end(self, session_id: int, end: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET end_ts = ? WHERE id = ?",
                (_fmt_ts(end), session_id),
            )

    def delete_session(self, session_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    def get_open_session(self) -> Optional[SessionRow]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, s.work_id, w.name AS work_name, s.start_ts, s.end_ts
                FROM sessions s
                JOIN works w ON w.id = s.work_id
                WHERE s.end_ts IS NULL
                LIMIT 1
                """
            ).fetchone()
        if not row:
            return None
        return SessionRow(
            id=row["id"],
            work_id=row["work_id"],
            work_name=row["work_name"],
            start_ts=_parse_ts(row["start_ts"]),
            end_ts=_parse_ts(row["end_ts"]) if row["end_ts"] else None,
        )

    def sessions_in_range(
        self, start: datetime, end: datetime
    ) -> list[SessionRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.work_id, w.name AS work_name, s.start_ts, s.end_ts
                FROM sessions s
                JOIN works w ON w.id = s.work_id
                WHERE s.start_ts < ? AND (s.end_ts IS NULL OR s.end_ts > ?)
                ORDER BY s.start_ts
                """,
                (_fmt_ts(end), _fmt_ts(start)),
            ).fetchall()
        out: list[SessionRow] = []
        for r in rows:
            out.append(
                SessionRow(
                    id=r["id"],
                    work_id=r["work_id"],
                    work_name=r["work_name"],
                    start_ts=_parse_ts(r["start_ts"]),
                    end_ts=_parse_ts(r["end_ts"]) if r["end_ts"] else None,
                )
            )
        return out

    def import_sessions(self, rows: Iterable[tuple[int, datetime, datetime]]) -> int:
        n = 0
        with self._connect() as conn:
            for work_id, start, end in rows:
                conn.execute(
                    "INSERT INTO sessions (work_id, start_ts, end_ts) VALUES (?,?,?)",
                    (work_id, _fmt_ts(start), _fmt_ts(end)),
                )
                n += 1
        return n
