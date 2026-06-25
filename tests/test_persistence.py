from datetime import datetime, timezone

from retnovation.persistence import Store
from retnovation.types import (
    FrameStrength,
    LearnerState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
    Strength,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def test_state_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    st = LearnerState()
    st.frames["protect_the_core_lane"] = FrameStrength(
        strength=Strength.forming,
        last_seen=_now(),
        due=_now(),
        last_evidence="closed under pressure",
        evidence_count=1,  # evidence_count=1 → storage tier forming; staleness 0 → derives forming
    )
    s.save_state(st)
    loaded = Store(tmp_path / "t.db").load_state(_now())
    assert loaded.frames["protect_the_core_lane"].strength is Strength.forming


def test_ledger_and_queue_fifo(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_ledger_entry(LedgerEntry(id="veldra:licensing_continuity", owned_problem="..."))
    assert s.load_ledger()[0].id == "veldra:licensing_continuity"
    s.queue_push(
        NextExperienceSpec(
            target_frames=["protect_the_core_lane"],
            ledger_ref="veldra:licensing_continuity",
            regime=Regime.open_ended,
        )
    )
    popped = s.queue_pop()
    assert popped.target_frames == ["protect_the_core_lane"]
    assert s.queue_pop() is None


def test_queue_len_is_non_consuming(tmp_path):
    s = Store(tmp_path / "q.db")
    assert s.queue_len() == 0
    s.queue_push(NextExperienceSpec(target_frames=["a"], ledger_ref="x", regime=Regime.open_ended))
    assert s.queue_len() == 1
    assert s.queue_len() == 1  # still there


def test_concepts_roundtrip_and_never_deleted(tmp_path):
    from retnovation.types import SpacedItem

    s = Store(tmp_path / "c.db")
    st = LearnerState()
    st.declarative_seed["safety_vs_liveness"] = SpacedItem(
        concept="safety_vs_liveness", due=_now(), interval_days=4
    )
    s.save_state(st)
    loaded = Store(tmp_path / "c.db").load_state(_now())
    assert loaded.declarative_seed["safety_vs_liveness"].interval_days == 4

    # demote (shorter interval) — row stays present
    st.declarative_seed["safety_vs_liveness"] = SpacedItem(
        concept="safety_vs_liveness", due=_now(), interval_days=1
    )
    s.save_state(st)
    re2 = Store(tmp_path / "c.db").load_state(_now())
    assert set(re2.declarative_seed) == {"safety_vs_liveness"}
    assert re2.declarative_seed["safety_vs_liveness"].interval_days == 1


def test_corpus_scene_roundtrip_and_none_default(tmp_path):
    from retnovation.types import CorpusEntry, Scene

    s = Store(tmp_path / "sc.db")
    s.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:a",
            domain="founder_ceo",
            why_owned="stakes",
            unlabeled="u",
            provenance="p",
            corpus_pointers=[],
            scene=Scene(prompt="concrete", situation="world"),
        )
    )
    s.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:b",
            domain="founder_ceo",
            why_owned="stakes",
            unlabeled="u",
            provenance="p",
            corpus_pointers=[],
        )
    )  # no scene
    loaded = Store(tmp_path / "sc.db")
    assert loaded.get_corpus("veldra:a").scene.prompt == "concrete"
    assert loaded.get_corpus("veldra:a").scene.situation == "world"
    assert loaded.get_corpus("veldra:b").scene is None


def test_corpus_scene_column_is_migrated_onto_an_old_table(tmp_path):
    import sqlite3

    from retnovation.types import CorpusEntry, Scene

    db = tmp_path / "old.db"
    # an OLD corpus table without scene_json
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE corpus (ledger_ref TEXT PRIMARY KEY, domain TEXT NOT NULL, "
        "why_owned TEXT NOT NULL, unlabeled TEXT NOT NULL, provenance TEXT NOT NULL, "
        "corpus_pointers_json TEXT NOT NULL)"
    )
    con.commit()
    con.close()
    # opening via Store migrates the table; a scene then round-trips
    s = Store(db)
    s.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:a",
            domain="founder_ceo",
            why_owned="s",
            unlabeled="u",
            provenance="p",
            corpus_pointers=[],
            scene=Scene(prompt="c", situation="w"),
        )
    )
    assert Store(db).get_corpus("veldra:a").scene.prompt == "c"


def test_storage_fields_round_trip_and_strength_derives(tmp_path):
    from datetime import datetime, timedelta, timezone
    from retnovation.persistence import Store
    from retnovation.types import FrameStrength, LearnerState, Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    s = Store(tmp_path / "p.db")
    st = LearnerState()
    st.frames["f"] = FrameStrength(
        strength=Strength.strong,
        last_seen=t0,
        due=t0 + timedelta(days=30),
        last_evidence="exp:reasoned",
        evidence_count=2,
        breadth={"veldra:a", "veldra:b"},
        unprompted_breadth={"veldra:a", "veldra:b"},
    )
    s.save_state(st)
    # fresh read at t0 → strong (staleness 0); read 40d later → decayed to forming, storage intact
    fresh = Store(tmp_path / "p.db").load_state(t0)
    assert fresh.frames["f"].strength is Strength.strong
    assert fresh.frames["f"].unprompted_breadth == {"veldra:a", "veldra:b"}
    decayed = Store(tmp_path / "p.db").load_state(t0 + timedelta(days=40))
    assert decayed.frames["f"].strength is Strength.forming
    assert decayed.frames["f"].evidence_count == 2  # storage never lost


def test_old_db_without_new_columns_migrates(tmp_path):
    import sqlite3
    from datetime import datetime, timezone
    from retnovation.persistence import Store

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # simulate a pre-migration frames table (no evidence_count/breadth columns)
    db = tmp_path / "old.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE frames (frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL, "
        "last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL)"
    )
    con.execute(
        "INSERT INTO frames VALUES ('f','forming',?,?,'old')",
        (t0.isoformat(), t0.isoformat()),
    )
    con.commit()
    con.close()
    loaded = Store(db).load_state(t0)  # __init__ migrates, load derives
    assert loaded.frames["f"].evidence_count == 0  # old row → no storage evidence
    assert loaded.frames["f"].breadth == set()
    from retnovation.types import Strength

    assert loaded.frames["f"].strength is Strength.weak  # derived from zero evidence


def test_decay_frame_is_gone(tmp_path):
    from retnovation.persistence import Store

    assert not hasattr(Store(tmp_path / "x.db"), "decay_frame")


def test_trap_gallery_round_trips_and_is_idempotent(tmp_path):
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import LearnerState, TrapOccurrence

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    s = Store(tmp_path / "tg.db")
    st = LearnerState()
    st.trap_gallery["scope_creep_to_please"] = [
        TrapOccurrence(experience_id="exp1", occurred_at=t0, detail="unchanged"),
        TrapOccurrence(experience_id="exp2", occurred_at=t0, detail="regressed"),
    ]
    s.save_state(st)
    s.save_state(st)  # second save must not duplicate
    loaded = Store(tmp_path / "tg.db").load_state(t0)
    occ = loaded.trap_gallery["scope_creep_to_please"]
    assert len(occ) == 2
    assert {o.experience_id for o in occ} == {"exp1", "exp2"}
    assert {o.detail for o in occ} == {"unchanged", "regressed"}
    assert {o.occurred_at for o in occ} == {t0}


def test_queue_round_trips_experience_id(tmp_path):
    from retnovation.persistence import Store
    from retnovation.types import NextExperienceSpec, Regime

    s = Store(tmp_path / "q.db")
    s.queue_push(
        NextExperienceSpec(
            target_frames=["f"],
            ledger_ref="veldra:x",
            regime=Regime.open_ended,
            experience_id="license_continuity",
        )
    )
    assert s.queue_pop().experience_id == "license_continuity"


def test_selection_log_decision_columns_fresh_and_old_db(tmp_path):
    import sqlite3
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import (
        NextExperienceSpec,
        Outcome,
        Regime,
        SelectionReceipt,
        Selection,
    )

    # old DB: selection_log WITHOUT the new columns
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.executescript(
        "CREATE TABLE selection_log (created_at TEXT NOT NULL, frame TEXT NOT NULL, "
        "problem TEXT NOT NULL, experience_id TEXT NOT NULL, drive TEXT NOT NULL, "
        "scores_json TEXT NOT NULL, runner_up_drive TEXT, margin REAL NOT NULL, "
        "content_gaps_json TEXT NOT NULL);"
    )
    con.commit()
    con.close()

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    for path in (old, tmp_path / "fresh.db"):
        store = Store(path)  # migration must not raise
        cols = {r["name"] for r in store._db.execute("PRAGMA table_info(selection_log)")}
        assert {"outcome", "chosen_frame", "chosen_problem", "chosen_experience_id"} <= cols

        def rc(frame, ref, eid):
            return SelectionReceipt(
                frame=frame,
                problem=ref,
                experience_id=eid,
                drive="deploy",
                scores={"V": 0.7},
                runner_up_drive="diagnose",
                margin=0.2,
                content_gaps=[],
                created_at=now,
            )

        sel = Selection(
            proposed_receipt=rc("lead", "veldra:p1", "e1"),
            chosen_spec=NextExperienceSpec(
                target_frames=["lead"],
                ledger_ref="veldra:p2",
                regime=Regime.open_ended,
                experience_id="e2",
            ),
            chosen_receipt=rc("lead", "veldra:p2", "e2"),
            outcome=Outcome.redirected,
        )
        store.log_decision(sel)
        row = store._db.execute("SELECT * FROM selection_log").fetchone()
        assert row["frame"] == "lead" and row["experience_id"] == "e1"  # proposed
        assert row["outcome"] == "redirected"
        assert row["chosen_problem"] == "veldra:p2" and row["chosen_experience_id"] == "e2"
        store.close()


def test_core_decision_log_roundtrip(tmp_path):
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import CoreCandidate, CoreKind, CoreVerdict

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    store = Store(tmp_path / "c.db")
    v = CoreVerdict(
        candidate=CoreCandidate(
            kind=CoreKind.promote, target="protect", rationale="decayed, broad"
        ),
        outcome="accepted",
    )
    store.log_core_decision(v, now)
    row = store._db.execute("SELECT * FROM core_decision_log").fetchone()
    assert row["kind"] == "promote" and row["target"] == "protect" and row["outcome"] == "accepted"
    store.close()
