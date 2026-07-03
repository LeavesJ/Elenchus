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
  sitting_id TEXT NOT NULL, ref TEXT NOT NULL, converged_at TEXT NOT NULL,
  experience_id TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS web_world (
  sitting_id TEXT PRIMARY KEY, situation TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS web_generated_problem (
  ref TEXT PRIMARY KEY, sitting_id TEXT NOT NULL, experience_id TEXT NOT NULL,
  scenario TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class SittingStore:
    def __init__(self, db_path: str):
        self._path = db_path
        self._inert = db_path == ":memory:"
        if self._inert:
            return
        try:
            with self._conn() as c:
                c.execute("PRAGMA journal_mode=WAL")
                c.executescript(_SCHEMA)
                # Defensive migration: dbs created before the living sitting lack the column
                # (the CREATE above carries it, so fresh dbs raise duplicate-column here).
                try:
                    c.execute(
                        "ALTER TABLE web_converged "
                        "ADD COLUMN experience_id TEXT NOT NULL DEFAULT ''"
                    )
                except sqlite3.OperationalError:
                    pass
        except sqlite3.OperationalError:
            # An unopenable path must not crash the registry at construction — the WORKER surfaces
            # the db error per-session (its build_store fails the same way and emits `error`).
            # Durability is off; the session error is the loud signal.
            self._inert = True

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
        try:
            with self._conn() as c:
                c.execute(
                    "INSERT INTO web_sitting (id, status, updated_at) VALUES (?, 'live', ?)",
                    (sitting_id, now.isoformat()),
                )
        except sqlite3.IntegrityError:
            # The partial unique live index fired: another PROCESS won the cold-start race (the
            # registry lock only serializes within one process). The loser ADOPTS the winning
            # live sitting instead of 500ing (spec §2c "the loser resumes"; batch-review C6).
            row = self.live_sitting()
            if row is not None:
                return row["id"]
            raise
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

    # -- the world (living sitting §2f: one generated world per sitting) ----------------------

    def write_world(self, sitting_id: str, situation: str, now: datetime) -> None:
        """Persist the sitting's world (her situation). Upsert: the world survives fallbacks —
        the NEXT Continue retries the forge on it (§2b) — and outlives restarts (mid-front-door
        is a durable state, §2g)."""
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_world (sitting_id, situation, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(sitting_id) DO UPDATE SET situation=excluded.situation, "
                "updated_at=excluded.updated_at",
                (sitting_id, situation, now.isoformat()),
            )

    def read_world(self, sitting_id: str) -> str | None:
        if self._inert:
            return None
        with self._conn() as c:
            row = c.execute(
                "SELECT situation FROM web_world WHERE sitting_id=?", (sitting_id,)
            ).fetchone()
        return None if row is None else row[0]

    # -- generated problems (instance grain: gen:{sitting}:{n} — rebuild fidelity, §2f/M2) ----

    def add_generated_problem(
        self, ref: str, sitting_id: str, experience_id: str, scenario: str, now: datetime
    ) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_generated_problem "
                "(ref, sitting_id, experience_id, scenario, created_at) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(ref) DO UPDATE SET experience_id=excluded.experience_id, "
                "scenario=excluded.scenario",  # upsert, never delete (L-3); freshest forge wins
                (ref, sitting_id, experience_id, scenario, now.isoformat()),
            )

    def read_generated_problem(self, ref: str) -> dict | None:
        """The scenario a `gen:` record must rebuild over (M2) — None degrades to statics."""
        if self._inert:
            return None
        with self._conn() as c:
            row = c.execute(
                "SELECT experience_id, scenario FROM web_generated_problem WHERE ref=?", (ref,)
            ).fetchone()
        return None if row is None else {"experience_id": row[0], "scenario": row[1]}

    def generated_territories(self, sitting_id: str) -> set[str]:
        """Every territory FORGED this sitting, landed or not (batch-review fold: the D1 union
        screens must cover plateaued/errored segments too — their dialogue feeds the brief and
        the close author even though the converged log never saw them)."""
        if self._inert:
            return set()
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT experience_id FROM web_generated_problem WHERE sitting_id=?",
                (sitting_id,),
            ).fetchall()
        return {r[0] for r in rows if r[0]}

    # -- converged log (the rolling repeat guard) --------------------------------------------

    def log_converged(
        self, sitting_id: str, ref: str, now: datetime, experience_id: str = ""
    ) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_converged (sitting_id, ref, converged_at, experience_id) "
                "VALUES (?, ?, ?, ?)",
                (sitting_id, ref, now.isoformat(), experience_id),
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

    def converged_log(self) -> list[dict]:
        """Every converged row, oldest first (converged_at, then insertion order). One read that
        serves the living sitting's converged-derived needs — the return-visit counts, the
        per-sitting engaged frames, the least-recent territory on an informed re-serve — and
        L5's houses. Read-only; rows are retained forever (L-3)."""
        if self._inert:
            return []
        with self._conn() as c:
            rows = c.execute(
                "SELECT sitting_id, ref, converged_at, experience_id FROM web_converged "
                "ORDER BY converged_at, rowid"
            ).fetchall()
        return [
            {"sitting_id": s, "ref": r, "converged_at": at, "experience_id": eid}
            for s, r, at, eid in rows
        ]

    def max_generated_n(self, sitting_id: str) -> int:
        """Highest instance n among this sitting's gen:{sitting}:{n} rows. The forge counter
        seeds PAST it after a restart so a reused n can never upsert-overwrite a prior instance
        row (the rebuild-fidelity substrate, §2f/M2)."""
        if self._inert:
            return 0
        with self._conn() as c:
            rows = c.execute(
                "SELECT ref FROM web_generated_problem WHERE sitting_id=?", (sitting_id,)
            ).fetchall()
        best = 0
        for (ref,) in rows:
            tail = ref.rsplit(":", 1)[-1]
            if tail.isdigit():
                best = max(best, int(tail))
        return best

    def territories_within(self, now: datetime, hours: int = 24) -> set[str]:
        """Territories (experience_ids) converged within the rolling window — same clock as
        converged_within, keyed on the world-independent TERRITORY identity (living sitting
        §2c/M3: within a sitting the policy clock is frozen; this window is the only rotation).
        Rows logged without a territory (the pre-forge curated path) never enter it."""
        if self._inert:
            return set()
        cutoff = (now - timedelta(hours=hours)).isoformat()
        with self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT experience_id FROM web_converged "
                "WHERE converged_at > ? AND experience_id != ''",
                (cutoff,),
            ).fetchall()
        return {r[0] for r in rows}
