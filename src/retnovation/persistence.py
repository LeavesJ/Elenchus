from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .types import (
    CoreVerdict,
    CorpusEntry,
    FrameStrength,
    LearnerState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
    Scene,
    Selection,
    SelectionReceipt,
    SpacedItem,
    TrapOccurrence,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
  frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL,
  last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL,
  evidence_count INTEGER NOT NULL DEFAULT 0, breadth_json TEXT, unprompted_breadth_json TEXT);
CREATE TABLE IF NOT EXISTS ledger (
  id TEXT PRIMARY KEY, owned_problem TEXT NOT NULL, links_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS queue (
  position INTEGER PRIMARY KEY AUTOINCREMENT,
  target_frames_json TEXT NOT NULL, ledger_ref TEXT NOT NULL, regime TEXT NOT NULL,
  experience_id TEXT);
CREATE TABLE IF NOT EXISTS selection_log (
  created_at TEXT NOT NULL, frame TEXT NOT NULL, problem TEXT NOT NULL, experience_id TEXT NOT NULL,
  drive TEXT NOT NULL, scores_json TEXT NOT NULL, runner_up_drive TEXT, margin REAL NOT NULL,
  content_gaps_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corpus (
  ledger_ref TEXT PRIMARY KEY, domain TEXT NOT NULL, why_owned TEXT NOT NULL,
  unlabeled TEXT NOT NULL, provenance TEXT NOT NULL, corpus_pointers_json TEXT NOT NULL,
  scene_json TEXT);
CREATE TABLE IF NOT EXISTS concepts (
  concept TEXT PRIMARY KEY, due TEXT NOT NULL, interval_days INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS trap_gallery (
  trap_code TEXT NOT NULL, experience_id TEXT NOT NULL, occurred_at TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS core_decision_log (
  created_at TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL,
  rationale TEXT NOT NULL, outcome TEXT NOT NULL);
"""


class Store:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._db.commit()
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(corpus)")}
        if "scene_json" not in cols:
            self._db.execute("ALTER TABLE corpus ADD COLUMN scene_json TEXT")
            self._db.commit()
        fcols = {r["name"] for r in self._db.execute("PRAGMA table_info(frames)")}
        for col, decl in (
            ("evidence_count", "INTEGER NOT NULL DEFAULT 0"),
            ("breadth_json", "TEXT"),
            ("unprompted_breadth_json", "TEXT"),
        ):
            if col not in fcols:
                self._db.execute(f"ALTER TABLE frames ADD COLUMN {col} {decl}")
        self._db.commit()
        qcols = {r["name"] for r in self._db.execute("PRAGMA table_info(queue)")}
        if "experience_id" not in qcols:
            self._db.execute("ALTER TABLE queue ADD COLUMN experience_id TEXT")
        self._db.commit()
        scols = {r["name"] for r in self._db.execute("PRAGMA table_info(selection_log)")}
        for col in ("outcome", "chosen_frame", "chosen_problem", "chosen_experience_id"):
            if col not in scols:
                self._db.execute(f"ALTER TABLE selection_log ADD COLUMN {col} TEXT")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def load_state(self, now: datetime) -> LearnerState:
        from .state import derive_due, derive_strength

        st = LearnerState()
        for r in self._db.execute("SELECT * FROM frames"):
            breadth = set(json.loads(r["breadth_json"])) if r["breadth_json"] else set()
            unprompted = (
                set(json.loads(r["unprompted_breadth_json"]))
                if r["unprompted_breadth_json"]
                else set()
            )
            evidence_count = r["evidence_count"] or 0
            last_seen = datetime.fromisoformat(r["last_seen"])
            st.frames[r["frame_code"]] = FrameStrength(
                strength=derive_strength(evidence_count, unprompted, last_seen, now),
                last_seen=last_seen,
                due=derive_due(evidence_count, unprompted, last_seen),
                last_evidence=r["last_evidence"],
                evidence_count=evidence_count,
                breadth=breadth,
                unprompted_breadth=unprompted,
            )
        for r in self._db.execute("SELECT * FROM concepts"):
            st.declarative_seed[r["concept"]] = SpacedItem(
                concept=r["concept"],
                due=datetime.fromisoformat(r["due"]),
                interval_days=r["interval_days"],
            )
        for r in self._db.execute("SELECT * FROM trap_gallery ORDER BY occurred_at, experience_id"):
            st.trap_gallery.setdefault(r["trap_code"], []).append(
                TrapOccurrence(
                    experience_id=r["experience_id"],
                    occurred_at=datetime.fromisoformat(r["occurred_at"]),
                    detail=r["detail"],
                )
            )
        return st

    def save_state(self, state: LearnerState) -> None:
        for code, fs in state.frames.items():
            self._db.execute(
                "INSERT INTO frames(frame_code,strength,last_seen,due,last_evidence,"
                "evidence_count,breadth_json,unprompted_breadth_json) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(frame_code) DO UPDATE SET strength=excluded.strength,"
                "last_seen=excluded.last_seen,due=excluded.due,last_evidence=excluded.last_evidence,"
                "evidence_count=excluded.evidence_count,breadth_json=excluded.breadth_json,"
                "unprompted_breadth_json=excluded.unprompted_breadth_json",
                (
                    code,
                    fs.strength.value,  # snapshot only — load_state re-derives; never read back as authority
                    fs.last_seen.isoformat(),
                    fs.due.isoformat(),
                    fs.last_evidence,
                    fs.evidence_count,
                    json.dumps(sorted(fs.breadth)),
                    json.dumps(sorted(fs.unprompted_breadth)),
                ),
            )
        for concept, si in state.declarative_seed.items():
            self._db.execute(
                "INSERT INTO concepts(concept,due,interval_days) VALUES(?,?,?) "
                "ON CONFLICT(concept) DO UPDATE SET due=excluded.due, "
                "interval_days=excluded.interval_days",
                (concept, si.due.isoformat(), si.interval_days),
            )
        self._db.execute("DELETE FROM trap_gallery")
        for trap_code, occurrences in state.trap_gallery.items():
            for o in occurrences:
                self._db.execute(
                    "INSERT INTO trap_gallery(trap_code,experience_id,occurred_at,detail) "
                    "VALUES(?,?,?,?)",
                    (trap_code, o.experience_id, o.occurred_at.isoformat(), o.detail),
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
            "corpus_pointers_json,scene_json) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(ledger_ref) DO UPDATE SET "
            "domain=excluded.domain,why_owned=excluded.why_owned,unlabeled=excluded.unlabeled,"
            "provenance=excluded.provenance,corpus_pointers_json=excluded.corpus_pointers_json,"
            "scene_json=excluded.scene_json",
            (
                entry.ledger_ref,
                entry.domain,
                entry.why_owned,
                entry.unlabeled,
                entry.provenance,
                json.dumps(entry.corpus_pointers),
                entry.scene.model_dump_json() if entry.scene else None,
            ),
        )
        self._db.commit()

    @staticmethod
    def _corpus_row(r: sqlite3.Row) -> CorpusEntry:
        scene_json = r["scene_json"]
        return CorpusEntry(
            ledger_ref=r["ledger_ref"],
            domain=r["domain"],
            why_owned=r["why_owned"],
            unlabeled=r["unlabeled"],
            provenance=r["provenance"],
            corpus_pointers=json.loads(r["corpus_pointers_json"]),
            scene=Scene.model_validate_json(scene_json) if scene_json else None,
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
            "INSERT INTO queue(target_frames_json,ledger_ref,regime,experience_id) VALUES(?,?,?,?)",
            (
                json.dumps(spec.target_frames),
                spec.ledger_ref,
                spec.regime.value,
                spec.experience_id,
            ),
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
            experience_id=row["experience_id"],
        )

    def log_selection(self, receipt: SelectionReceipt) -> None:
        self._db.execute(
            "INSERT INTO selection_log(created_at,frame,problem,experience_id,drive,scores_json,"
            "runner_up_drive,margin,content_gaps_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                receipt.created_at.isoformat(),
                receipt.frame,
                receipt.problem,
                receipt.experience_id,
                receipt.drive,
                json.dumps(receipt.scores),
                receipt.runner_up_drive,
                receipt.margin,
                json.dumps(receipt.content_gaps),
            ),
        )
        self._db.commit()

    def log_decision(self, selection: Selection) -> None:
        p = selection.proposed_receipt
        c = selection.chosen_receipt
        self._db.execute(
            "INSERT INTO selection_log(created_at,frame,problem,experience_id,drive,scores_json,"
            "runner_up_drive,margin,content_gaps_json,outcome,chosen_frame,chosen_problem,"
            "chosen_experience_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p.created_at.isoformat(),
                p.frame,
                p.problem,
                p.experience_id,
                p.drive,
                json.dumps(p.scores),
                p.runner_up_drive,
                p.margin,
                json.dumps(p.content_gaps),
                selection.outcome.value,
                c.frame,
                c.problem,
                c.experience_id,
            ),
        )
        self._db.commit()

    def log_core_decision(self, verdict: CoreVerdict, now: datetime) -> None:
        self._db.execute(
            "INSERT INTO core_decision_log(created_at,kind,target,rationale,outcome) "
            "VALUES(?,?,?,?,?)",
            (
                now.isoformat(),
                verdict.candidate.kind.value,
                verdict.candidate.target,
                verdict.candidate.rationale,
                verdict.outcome,
            ),
        )
        self._db.commit()

    def queue_len(self) -> int:
        return self._db.execute("SELECT COUNT(*) AS n FROM queue").fetchone()["n"]
