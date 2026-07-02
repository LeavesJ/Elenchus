"""Durable sittings: web-layer persistence (spec 2026-07-01-durable-sittings-design §2a).

The store mirrors the PROJECTED client wire (turns) plus the landed-segment state and a converged
log — never engine internals: no refs in turn payloads (L-13; the write-through layer enforces
what goes in, this module enforces where it lives), no deletions (L-3; closing a sitting flips
status, rows survive).

Connections are opened per operation (short transactions; safe across FastAPI threadpool
threads). First open sets WAL so transcript reads never block the engine's writer. A `:memory:`
db_path makes the store INERT — per-op connections would each see their own empty database, so
pretending to persist would silently lie; the shell-only tests that use `:memory:` never start
sessions and rely on this.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta

_UNSET = object()  # write_state sentinel: "leave this column alone"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS web_sitting (
  id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_web_sitting_live ON web_sitting(status) WHERE status='live';
CREATE TABLE IF NOT EXISTS web_sitting_turn (
  sitting_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS web_sitting_state (
  sitting_id TEXT PRIMARY KEY, record_json TEXT, next_pick_ref TEXT, next_pick_title TEXT,
  inflight_json TEXT, theme_json TEXT);
CREATE TABLE IF NOT EXISTS web_converged (
  sitting_id TEXT NOT NULL, ref TEXT NOT NULL, converged_at TEXT NOT NULL);
"""


class SittingStore:
    def __init__(self, db_path: str):
        self._path = db_path
        self._inert = db_path == ":memory:"
        if self._inert:
            return
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(_SCHEMA)

    @property
    def inert(self) -> bool:
        return self._inert

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path, timeout=5)
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA synchronous=NORMAL")
        return c

    # -- sitting lifecycle -------------------------------------------------------------------

    def live_sitting(self) -> dict | None:
        if self._inert:
            return None
        with self._conn() as c:
            row = c.execute(
                "SELECT id, status, updated_at FROM web_sitting WHERE status='live'"
            ).fetchone()
        return None if row is None else {"id": row[0], "status": row[1], "updated_at": row[2]}

    def create_sitting(self, now: datetime) -> str:
        sitting_id = now.strftime("%Y%m%dT%H%M%S%f") + "-" + secrets.token_hex(3)
        if self._inert:
            return sitting_id
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_sitting (id, status, updated_at) VALUES (?, 'live', ?)",
                (sitting_id, now.isoformat()),
            )
        return sitting_id

    def close_sitting(self, sitting_id: str) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute("UPDATE web_sitting SET status='closed' WHERE id=?", (sitting_id,))

    # -- turns (the rendered transcript) -----------------------------------------------------

    def append_turn(self, sitting_id: str, kind: str, payload: dict, now: datetime) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json) "
                "SELECT ?, COALESCE(MAX(seq), 0) + 1, ?, ? FROM web_sitting_turn "
                "WHERE sitting_id=?",
                (sitting_id, kind, json.dumps(payload), sitting_id),
            )
            c.execute(
                "UPDATE web_sitting SET updated_at=? WHERE id=?",
                (now.isoformat(), sitting_id),
            )

    def turns(self, sitting_id: str) -> list[dict]:
        if self._inert:
            return []
        with self._conn() as c:
            rows = c.execute(
                "SELECT kind, payload_json FROM web_sitting_turn WHERE sitting_id=? ORDER BY seq",
                (sitting_id,),
            ).fetchall()
        return [{"kind": k, "payload": json.loads(p)} for k, p in rows]

    # -- landed-segment state ----------------------------------------------------------------

    def write_state(
        self,
        sitting_id: str,
        record: dict | None = _UNSET,  # type: ignore[assignment]
        next_pick: tuple[str, str] | None = _UNSET,  # type: ignore[assignment]
        inflight: dict | None = _UNSET,  # type: ignore[assignment]
        theme: dict | None = _UNSET,  # type: ignore[assignment]
    ) -> None:
        """Sentinel-partial update: only the keyword arguments actually passed are written."""
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO web_sitting_state (sitting_id) VALUES (?)", (sitting_id,)
            )
            if record is not _UNSET:
                c.execute(
                    "UPDATE web_sitting_state SET record_json=? WHERE sitting_id=?",
                    (None if record is None else json.dumps(record), sitting_id),
                )
            if next_pick is not _UNSET:
                ref, title = (None, None) if next_pick is None else next_pick
                c.execute(
                    "UPDATE web_sitting_state SET next_pick_ref=?, next_pick_title=? "
                    "WHERE sitting_id=?",
                    (ref, title, sitting_id),
                )
            if inflight is not _UNSET:
                c.execute(
                    "UPDATE web_sitting_state SET inflight_json=? WHERE sitting_id=?",
                    (None if inflight is None else json.dumps(inflight), sitting_id),
                )
            if theme is not _UNSET:
                c.execute(
                    "UPDATE web_sitting_state SET theme_json=? WHERE sitting_id=?",
                    (None if theme is None else json.dumps(theme), sitting_id),
                )

    def read_state(self, sitting_id: str) -> dict:
        if self._inert:
            return {"record": None, "next_pick": None, "inflight": None, "theme": None}
        with self._conn() as c:
            row = c.execute(
                "SELECT record_json, next_pick_ref, next_pick_title, inflight_json, theme_json "
                "FROM web_sitting_state WHERE sitting_id=?",
                (sitting_id,),
            ).fetchone()
        if row is None:
            return {"record": None, "next_pick": None, "inflight": None, "theme": None}
        record_j, pick_ref, pick_title, inflight_j, theme_j = row
        return {
            "record": None if record_j is None else json.loads(record_j),
            "next_pick": None if pick_ref is None else (pick_ref, pick_title),
            "inflight": None if inflight_j is None else json.loads(inflight_j),
            "theme": None if theme_j is None else json.loads(theme_j),
        }

    # -- converged log (the rolling repeat guard) --------------------------------------------

    def log_converged(self, sitting_id: str, ref: str, now: datetime) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_converged (sitting_id, ref, converged_at) VALUES (?, ?, ?)",
                (sitting_id, ref, now.isoformat()),
            )

    def converged_within(self, now: datetime, hours: int = 24) -> set[str]:
        """Refs converged within the rolling window — across sittings and processes. A rolling
        window, NOT a calendar date: the founder's incident straddled UTC midnight mid-evening
        (isoformat strings of same-offset datetimes compare lexicographically)."""
        if self._inert:
            return set()
        cutoff = (now - timedelta(hours=hours)).isoformat()
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT ref FROM web_converged WHERE converged_at > ?", (cutoff,)
            ).fetchall()
        return {r[0] for r in rows}
