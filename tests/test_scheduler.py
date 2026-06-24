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


def _cs_state(items):
    from retnovation.types import LearnerState, SpacedItem

    st = LearnerState()
    for concept, (due, interval) in items.items():
        st.declarative_seed[concept] = SpacedItem(concept=concept, due=due, interval_days=interval)
    return st


def test_cs_technical_targets_due_concepts_first():
    from datetime import timedelta

    now = _now()
    st = _cs_state(
        {
            "overdue": (now - timedelta(days=1), 1),
            "future": (now + timedelta(days=5), 4),
        }
    )
    spec = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["overdue"]
    assert spec.regime is Regime.cs_technical


def test_cs_technical_with_nothing_due_targets_soonest():
    from datetime import timedelta

    now = _now()
    st = _cs_state(
        {
            "soon": (now + timedelta(days=1), 1),
            "later": (now + timedelta(days=9), 8),
        }
    )
    spec = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["soon"]


def test_cs_technical_due_ties_break_by_concept_code():
    now = _now()
    st = _cs_state({"zebra": (now, 1), "alpha": (now, 1)})  # identical due
    spec = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["alpha", "zebra"]  # deterministic, code-sorted
