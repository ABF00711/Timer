from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from timer_app.database import Database
from timer_app.timeutil import end_of_day, local_now, today_local


@dataclass(frozen=True)
class ActiveInfo:
    work_name: str
    started_at: datetime


class SessionService:
    def __init__(self, db: Optional[Database] = None) -> None:
        self._db = db or Database()

    @property
    def db(self) -> Database:
        return self._db

    def active(self) -> Optional[ActiveInfo]:
        row = self._db.get_open_session()
        if not row:
            return None
        return ActiveInfo(work_name=row.work_name, started_at=row.start_ts)

    def start_or_switch(self, work_name: str) -> tuple[bool, Optional[str]]:
        """
        Start tracking `work_name`, closing any open session first.
        Returns (started_or_switched, notify_message).
        """
        work_name = work_name.strip()
        if not work_name:
            raise ValueError("Empty work name")
        notify: Optional[str] = None
        now = local_now()
        open_row = self._db.get_open_session()
        wid = self._db.ensure_work(work_name)

        if open_row:
            if open_row.work_id == wid:
                return False, None
            end_time = min(now, end_of_day(open_row.start_ts.date()))
            self._db.update_session_end(open_row.id, end_time)
            self._db.insert_session(wid, now, None)
            return True, notify

        self._db.insert_session(wid, now, None)
        return True, notify

    def stop(self) -> bool:
        row = self._db.get_open_session()
        if not row:
            return False
        now = local_now()
        end_time = min(now, end_of_day(row.start_ts.date()))
        self._db.update_session_end(row.id, end_time)
        return True

    def reconcile_stale_open_sessions(self) -> list[str]:
        """
        On startup: close any open session that started before today at end of
        that calendar day. Returns tray messages to show.
        messages = []
        """
        messages: list[str] = []
        row = self._db.get_open_session()
        if not row:
            return messages
        today = today_local()
        start_date = row.start_ts.date()
        if start_date >= today:
            return messages
        self._db.update_session_end(row.id, end_of_day(start_date))
        messages.append(
            "Previous work session ended at the end of that day. "
            "Select a work name to start tracking today."
        )
        return messages

    def rollover_if_midnight(self) -> list[str]:
        """
        Called when the clock passes midnight while the app is running.
        Ends active session at end of previous local day.
        """
        messages: list[str] = []
        row = self._db.get_open_session()
        if not row:
            return messages
        today = today_local()
        if row.start_ts.date() >= today:
            return messages
        self._db.update_session_end(row.id, end_of_day(row.start_ts.date()))
        messages.append(
            "A new day started; your last session was stopped at midnight. "
            "Select a work name to continue tracking."
        )
        return messages

    def suspend_end_session(self) -> None:
        """End current session at 'now' when system suspends."""
        row = self._db.get_open_session()
        if not row:
            return
        self._db.update_session_end(row.id, local_now())
