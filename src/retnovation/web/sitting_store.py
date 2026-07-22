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
  inflight_json TEXT, theme_json TEXT, territory_rank_json TEXT, landed_at TEXT);
CREATE TABLE IF NOT EXISTS web_converged (
  sitting_id TEXT NOT NULL, ref TEXT NOT NULL, converged_at TEXT NOT NULL,
  experience_id TEXT NOT NULL DEFAULT '', position TEXT);
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
                # Same pattern: dbs created before the mapper rank persisted (triage fold,
                # 2026-07-03) lack the column.
                try:
                    c.execute("ALTER TABLE web_sitting_state ADD COLUMN territory_rank_json TEXT")
                except sqlite3.OperationalError:
                    pass
                # Same pattern: dbs created before the landed_at decoupling (cross-arc fix,
                # 2026-07-09) lack the column. landed_at stamps the actual LANDING moment so the
                # homebase selector no longer keys on updated_at (which append_turn — and, in the
                # since-removed re-entry path, a sitting reopen — bump without a landing, the
                # vanishing-houses bug).
                try:
                    c.execute("ALTER TABLE web_sitting_state ADD COLUMN landed_at TEXT")
                    # Backfill legacy landed records to their sitting's updated_at ONCE, at
                    # migration time — otherwise the fix is inert on an existing (all-NULL) db
                    # until a fresh landing, so re-entering a pre-fix saga would still hide newer
                    # houses (whole-branch review, 2 lenses). A frozen migration-time value is
                    # immune to later reopen/append_turn bumps (they never pass `now`).
                    c.execute(
                        "UPDATE web_sitting_state SET landed_at = "
                        "(SELECT s.updated_at FROM web_sitting s WHERE s.id = "
                        "web_sitting_state.sitting_id) "
                        "WHERE landed_at IS NULL AND record_json IS NOT NULL"
                    )
                except sqlite3.OperationalError:
                    pass
                # Same pattern: dbs created before the memory capture (Spec 1, 2026-07-21) lack
                # the column. position = the convergence's committed final student turn, captured
                # at log time (only genuine convergences log -> capture unambiguous; L-4: recalled,
                # never graded). Legacy rows stay NULL -> the bubble shows a placeholder.
                try:
                    c.execute("ALTER TABLE web_converged ADD COLUMN position TEXT")
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
        territory_rank: list[str] | None = _UNSET,  # type: ignore[assignment]
        now: datetime | None = None,
    ) -> None:
        """Sentinel-partial update: only the keyword arguments actually passed are written. When a
        non-None `record` is written WITH `now`, `landed_at` is stamped — the LANDING moment. The
        homebase selector orders by landed_at, so only genuine terrain-freezing landings promote a
        saga's record; a converse rewrite (no `now`) or a reopen/turn (updated_at only) never
        does. Callers that omit `now` leave landed_at untouched (back-compat / non-landing writes)."""
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO web_sitting_state (sitting_id) VALUES (?)", (sitting_id,)
            )
            if record is not _UNSET:
                if record is not None and now is not None:
                    c.execute(
                        "UPDATE web_sitting_state SET record_json=?, landed_at=? WHERE sitting_id=?",
                        (json.dumps(record), now.isoformat(), sitting_id),
                    )
                else:
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
            if territory_rank is not _UNSET:
                c.execute(
                    "UPDATE web_sitting_state SET territory_rank_json=? WHERE sitting_id=?",
                    (None if territory_rank is None else json.dumps(territory_rank), sitting_id),
                )

    def read_state(self, sitting_id: str) -> dict:
        empty = {
            "record": None,
            "next_pick": None,
            "inflight": None,
            "theme": None,
            "territory_rank": None,
        }
        if self._inert:
            return empty
        with self._conn() as c:
            row = c.execute(
                "SELECT record_json, next_pick_ref, next_pick_title, inflight_json, theme_json, "
                "territory_rank_json FROM web_sitting_state WHERE sitting_id=?",
                (sitting_id,),
            ).fetchone()
        if row is None:
            return empty
        record_j, pick_ref, pick_title, inflight_j, theme_j, rank_j = row
        return {
            "record": None if record_j is None else json.loads(record_j),
            "next_pick": None if pick_ref is None else (pick_ref, pick_title),
            "inflight": None if inflight_j is None else json.loads(inflight_j),
            "theme": None if theme_j is None else json.loads(theme_j),
            "territory_rank": None if rank_j is None else json.loads(rank_j),
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

    def _latest_landed_record(self) -> dict | None:
        """The parsed record of the most-recently-LANDED sitting that has a non-empty terrain —
        i.e. the exact cumulative village the user last SAW at a close. ONE definition shared by
        latest_terrain and latest_homebase, so the return-line caption and the rendered homebase
        can never pick different records (spec §3). Ordered by `landed_at` (the terrain-freezing
        moment), NOT web_sitting.updated_at: append_turn (and, in the since-removed re-entry path,
        a sitting reopen) bump updated_at without a new landing, so keying on it let
        re-entering/conversing in an OLDER saga promote a stale, smaller record and hide newer
        sagas' houses (cross-arc hunt 2026-07-09). Non-null landed_at
        (post-fix landings) always outranks legacy NULL rows, which fall back to updated_at among
        themselves."""
        if self._inert:
            return None
        with self._conn() as c:
            rows = c.execute(
                "SELECT st.record_json FROM web_sitting_state st "
                "JOIN web_sitting s ON s.id = st.sitting_id "
                "WHERE st.record_json IS NOT NULL "
                "ORDER BY st.landed_at IS NULL, st.landed_at DESC, s.updated_at DESC"
            ).fetchall()
        for (record_j,) in rows:
            record = json.loads(record_j)
            if record.get("terrain"):
                return record
        return None

    def latest_terrain(self) -> list | None:
        """The frozen learner_view from the most recently updated sitting that landed a record —
        i.e. the exact village the user last SAW at a close. The return-visit line counts its
        rendered regions so it can never contradict the close copy (batch-review fold: counting
        territories as 'regions' diverged from the village's frame-component geometry)."""
        record = self._latest_landed_record()
        return record.get("terrain") if record is not None else None

    def latest_homebase(self) -> dict:
        """The homebase load payload (spec §3/§6): the cumulative (terrain, houses) pair a close
        already froze together from the SAME post-session state (session_runner.py:1072-1086) —
        returned from ONE record so every house.region ordinal indexes into the served terrain
        (no fresh-terrain-with-stale-houses drift). Empty pair when nothing has landed / inert —
        `{"terrain": [], "houses": []}` EXACTLY (tests/test_sitting_store.py:300 asserts this by
        equality; no `house_refs` key on the empty shape).
        L-13: houses stay {region, bucket}; terrain stays the coarse learner_view; `house_refs`
        (the frozen convergence refs behind those houses, Task 2) is returned ONLY in the record
        branch, for SERVER-SIDE callers (the memory click map) — it is never projected to the
        wire (`_emit` in web/app.py attaches only `terrain`/`houses`, never `house_refs`)."""
        record = self._latest_landed_record()
        if record is None:
            return {"terrain": [], "houses": []}
        return {
            "terrain": record.get("terrain") or [],
            "houses": record.get("houses") or [],
            "house_refs": record.get("house_refs") or [],
        }

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
        self,
        sitting_id: str,
        ref: str,
        now: datetime,
        experience_id: str = "",
        position: str | None = None,
    ) -> None:
        if self._inert:
            return
        with self._conn() as c:
            c.execute(
                "INSERT INTO web_converged (sitting_id, ref, converged_at, experience_id, "
                "position) VALUES (?, ?, ?, ?, ?)",
                (sitting_id, ref, now.isoformat(), experience_id, position),
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
                "SELECT sitting_id, ref, converged_at, experience_id, position FROM web_converged "
                "ORDER BY converged_at, rowid"
            ).fetchall()
        return [
            {
                "sitting_id": s,
                "ref": r,
                "converged_at": at,
                "experience_id": eid,
                "position": position,
            }
            for s, r, at, eid, position in rows
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
