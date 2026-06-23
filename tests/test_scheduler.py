from datetime import datetime, timezone

from retnovation.scheduler import schedule_next
from retnovation.types import (
    FrameStrength,
    LearnerState,
    LedgerEntry,
    Regime,
    Strength,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _state(frames):
    st = LearnerState()
    for code, strg in frames.items():
        st.frames[code] = FrameStrength(
            strength=strg, last_seen=_now(), due=_now(), last_evidence=""
        )
    return st


def test_weak_frames_are_targeted_first():
    st = _state({"a": Strength.weak, "b": Strength.forming})
    led = [LedgerEntry(id="veldra:licensing_continuity", owned_problem="...")]
    spec = schedule_next(st, led, _now())
    assert spec.target_frames == ["a"]
    assert spec.ledger_ref == "veldra:licensing_continuity"
    assert spec.regime is Regime.open_ended


def test_all_strong_targets_soonest_due():
    st = _state({"a": Strength.strong, "b": Strength.strong})
    led = [LedgerEntry(id="veldra:licensing_continuity", owned_problem="...")]
    spec = schedule_next(st, led, _now())
    assert len(spec.target_frames) == 1
