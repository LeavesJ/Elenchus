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
    )
    s.save_state(st)
    loaded = Store(tmp_path / "t.db").load_state()
    assert loaded.frames["protect_the_core_lane"].strength is Strength.forming


def test_decay_updates_never_deletes(tmp_path):
    s = Store(tmp_path / "t.db")
    st = LearnerState()
    st.frames["f"] = FrameStrength(
        strength=Strength.strong, last_seen=_now(), due=_now(), last_evidence="x"
    )
    s.save_state(st)
    s.decay_frame("f", Strength.forming, _now())
    loaded = s.load_state()
    assert set(loaded.frames) == {"f"}  # row still present
    assert loaded.frames["f"].strength is Strength.forming


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
    loaded = Store(tmp_path / "c.db").load_state()
    assert loaded.declarative_seed["safety_vs_liveness"].interval_days == 4

    # demote (shorter interval) — row stays present
    st.declarative_seed["safety_vs_liveness"] = SpacedItem(
        concept="safety_vs_liveness", due=_now(), interval_days=1
    )
    s.save_state(st)
    re2 = Store(tmp_path / "c.db").load_state()
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
