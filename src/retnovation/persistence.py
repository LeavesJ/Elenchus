from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .types import (
    CorpusEntry,
    FrameStrength,
    LearnerState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
    Strength,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
  frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL,
  last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
  id TEXT PRIMARY KEY, owned_problem TEXT NOT NULL, links_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS queue (
  position INTEGER PRIMARY KEY AUTOINCREMENT,
  target_frames_json TEXT NOT NULL, ledger_ref TEXT NOT NULL, regime TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corpus (
  ledger_ref TEXT PRIMARY KEY, domain TEXT NOT NULL, why_owned TEXT NOT NULL,
  unlabeled TEXT NOT NULL, provenance TEXT NOT NULL, corpus_pointers_json TEXT NOT NULL);
"""


class Store:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def load_state(self) -> LearnerState:
        st = LearnerState()
        for r in self._db.execute("SELECT * FROM frames"):
            st.frames[r["frame_code"]] = FrameStrength(
                strength=Strength(r["strength"]),
                last_seen=datetime.fromisoformat(r["last_seen"]),
                due=datetime.fromisoformat(r["due"]),
                last_evidence=r["last_evidence"],
            )
        return st

    def save_state(self, state: LearnerState) -> None:
        for code, fs in state.frames.items():
            self._db.execute(
                "INSERT INTO frames(frame_code,strength,last_seen,due,last_evidence) "
                "VALUES(?,?,?,?,?) ON CONFLICT(frame_code) DO UPDATE SET "
                "strength=excluded.strength,last_seen=excluded.last_seen,"
                "due=excluded.due,last_evidence=excluded.last_evidence",
                (
                    code,
                    fs.strength.value,
                    fs.last_seen.isoformat(),
                    fs.due.isoformat(),
                    fs.last_evidence,
                ),
            )
        self._db.commit()

    def decay_frame(self, frame_code: str, new_strength: Strength, new_due: datetime) -> None:
        self._db.execute(
            "UPDATE frames SET strength=?, due=? WHERE frame_code=?",
            (new_strength.value, new_due.isoformat(), frame_code),
        )
        self._db.commit()

    def add_ledger_entry(self, entry: LedgerEntry) -> None:
        self._db.execute(
            # Preserve links_json on conflict: links accrue downstream and the entry/seed is not
            # their authority, so a re-add (e.g. re-ingest) must not clobber accumulated links.
            "INSERT INTO ledger(id,owned_problem,links_json) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET owned_problem=excluded.owned_problem",
            (entry.id, entry.owned_problem, json.dumps(entry.links_to_experiences)),
        )
        self._db.commit()

    def load_ledger(self) -> list[LedgerEntry]:
        rows = self._db.execute("SELECT * FROM ledger ORDER BY id")
        return [
            LedgerEntry(
                id=r["id"],
                owned_problem=r["owned_problem"],
                links_to_experiences=json.loads(r["links_json"]),
            )
            for r in rows
        ]

    def upsert_corpus(self, entry: CorpusEntry) -> None:
        self._db.execute(
            "INSERT INTO corpus(ledger_ref,domain,why_owned,unlabeled,provenance,"
            "corpus_pointers_json) VALUES(?,?,?,?,?,?) ON CONFLICT(ledger_ref) DO UPDATE SET "
            "domain=excluded.domain,why_owned=excluded.why_owned,unlabeled=excluded.unlabeled,"
            "provenance=excluded.provenance,corpus_pointers_json=excluded.corpus_pointers_json",
            (
                entry.ledger_ref,
                entry.domain,
                entry.why_owned,
                entry.unlabeled,
                entry.provenance,
                json.dumps(entry.corpus_pointers),
            ),
        )
        self._db.commit()

    @staticmethod
    def _corpus_row(r: sqlite3.Row) -> CorpusEntry:
        return CorpusEntry(
            ledger_ref=r["ledger_ref"],
            domain=r["domain"],
            why_owned=r["why_owned"],
            unlabeled=r["unlabeled"],
            provenance=r["provenance"],
            corpus_pointers=json.loads(r["corpus_pointers_json"]),
        )

    def load_corpus(self) -> list[CorpusEntry]:
        return [
            self._corpus_row(r)
            for r in self._db.execute("SELECT * FROM corpus ORDER BY ledger_ref")
        ]

    def get_corpus(self, ledger_ref: str) -> CorpusEntry | None:
        r = self._db.execute("SELECT * FROM corpus WHERE ledger_ref=?", (ledger_ref,)).fetchone()
        return self._corpus_row(r) if r is not None else None

    def queue_push(self, spec: NextExperienceSpec) -> None:
        self._db.execute(
            "INSERT INTO queue(target_frames_json,ledger_ref,regime) VALUES(?,?,?)",
            (json.dumps(spec.target_frames), spec.ledger_ref, spec.regime.value),
        )
        self._db.commit()

    def queue_pop(self) -> NextExperienceSpec | None:
        row = self._db.execute("SELECT * FROM queue ORDER BY position LIMIT 1").fetchone()
        if row is None:
            return None
        self._db.execute("DELETE FROM queue WHERE position=?", (row["position"],))
        self._db.commit()
        return NextExperienceSpec(
            target_frames=json.loads(row["target_frames_json"]),
            ledger_ref=row["ledger_ref"],
            regime=Regime(row["regime"]),
        )

    def queue_len(self) -> int:
        return self._db.execute("SELECT COUNT(*) AS n FROM queue").fetchone()["n"]
