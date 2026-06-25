from datetime import datetime, timezone

from retnovation.scheduler import schedule_next
from retnovation.types import (
    LearnerState,
    LedgerEntry,
    Regime,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _cs_state(items):
    from retnovation.types import LearnerState, SpacedItem

    st = LearnerState()
    for concept, (due, interval) in items.items():
        st.declarative_seed[concept] = SpacedItem(concept=concept, due=due, interval_days=interval)
    return st


def test_open_ended_uses_the_value_function_over_real_content():
    st = LearnerState()
    led = [LedgerEntry(id="veldra:license_fork_risk", owned_problem="...")]
    spec, receipt = schedule_next(st, led, _now())
    assert spec.regime is Regime.open_ended
    assert spec.experience_id is not None and spec.experience_id == receipt.experience_id
    assert spec.target_frames == [receipt.frame] and receipt.scores["V"] >= 0.0


def test_cs_technical_targets_due_concepts_first():
    from datetime import timedelta

    now = _now()
    st = _cs_state(
        {
            "overdue": (now - timedelta(days=1), 1),
            "future": (now + timedelta(days=5), 4),
        }
    )
    spec, _ = schedule_next(st, [], now, regime=Regime.cs_technical)
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
    spec, _ = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["soon"]


def test_cs_technical_due_ties_break_by_concept_code():
    now = _now()
    st = _cs_state({"zebra": (now, 1), "alpha": (now, 1)})  # identical due
    spec, _ = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["alpha", "zebra"]  # deterministic, code-sorted
