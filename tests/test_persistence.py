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
