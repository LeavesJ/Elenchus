from datetime import datetime, timezone

from retnovation.types import (
    LearnerState,
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


def test_propose_open_ended_returns_ranked_proposal():
    from retnovation.scheduler import propose_open_ended
    from retnovation.content_loader import load_library, load_progression

    exps = [e for e in load_library() if e.regime.value == "open_ended"]
    prop = propose_open_ended(LearnerState(), exps, load_progression(), _now())
    assert len(prop.candidates) >= 1
    assert prop.top[0].regime is Regime.open_ended
    assert prop.top[0].experience_id == prop.top[1].experience_id


def test_schedule_cs_targets_due_concepts_first():
    from datetime import timedelta
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state(
        {"overdue": (now - timedelta(days=1), 1), "future": (now + timedelta(days=5), 4)}
    )
    spec = schedule_cs(st, [], now)
    assert spec.target_frames == ["overdue"] and spec.regime is Regime.cs_technical


def test_schedule_cs_with_nothing_due_targets_soonest():
    from datetime import timedelta
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state({"soon": (now + timedelta(days=1), 1), "later": (now + timedelta(days=9), 8)})
    assert schedule_cs(st, [], now).target_frames == ["soon"]


def test_schedule_cs_due_ties_break_by_concept_code():
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state({"zebra": (now, 1), "alpha": (now, 1)})
    assert schedule_cs(st, [], now).target_frames == ["alpha", "zebra"]
