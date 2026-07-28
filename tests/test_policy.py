from datetime import datetime, timedelta, timezone

from elenchus.policy import select_next
from elenchus.types import (
    Experience,
    Frame,
    FrameStrength,
    LearnerState,
    Mode,
    Regime,
    Rubric,
    Strength,
)

NOW = datetime(2026, 6, 24, tzinfo=timezone.utc)
CFG = {"wU": 1.0, "wR": 1.0, "wT": 1.5, "wL": 0.5, "theta_located": 0.5}


def _exp(eid, ref, frames):
    rub = Rubric(
        frames=[Frame(frame_code=c, frame_detail="d") for c in frames],
        traps=[],
        mode=Mode.genuinely_open,
    )
    return Experience(
        experience_id=eid, prompt="p", rubric=rub, ledger_ref=ref, regime=Regime.open_ended
    )


def _forming(ref, now=NOW):
    return FrameStrength(
        strength=Strength.forming,
        last_seen=now,
        due=now,
        last_evidence="x",
        evidence_count=1,
        breadth={ref},
        unprompted_breadth={ref},
    )


def test_cold_start_serves_lowest_load_experience_first():
    exps = [_exp("cap", "veldra:p1", ["a", "b", "c"]), _exp("iso", "veldra:p2", ["z"])]
    spec, receipt = select_next(LearnerState(), exps, CFG, NOW)[0]
    assert receipt.experience_id == "iso"
    assert (
        spec.experience_id == "iso"
        and spec.ledger_ref == "veldra:p2"
        and spec.target_frames == ["z"]
    )


def test_transfer_fires_for_forming_frame_on_a_new_problem():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1")
    exps = [
        _exp("e1", "veldra:p1", ["lead", "other1"]),
        _exp("e2", "veldra:p2", ["lead", "other2"]),
    ]
    spec, receipt = select_next(st, exps, CFG, NOW)[0]
    assert receipt.frame == "lead" and receipt.problem == "veldra:p2" and receipt.drive == "deploy"


def test_retention_fires_only_when_overdue_on_the_storage_clock():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1", now=NOW - timedelta(days=10))
    spec, receipt = select_next(st, [_exp("e1", "veldra:p1", ["lead"])], CFG, NOW)[0]
    assert receipt.scores["retention"] > 0.0


def test_content_gap_logged_for_frame_with_no_isolated_home():
    spec, receipt = select_next(LearnerState(), [_exp("e1", "veldra:p1", ["a", "b"])], CFG, NOW)[0]
    assert "a" in receipt.content_gaps and "b" in receipt.content_gaps


def test_two_experiences_sharing_a_pair_pick_lower_load():
    e_iso = _exp("e_iso", "veldra:p1", ["lead"])
    e_cap = _exp("e_cap", "veldra:p1", ["lead", "x", "y"])
    ranked = select_next(LearnerState(), [e_cap, e_iso], CFG, NOW)
    assert ranked[0][1].experience_id == "e_iso"


def test_select_next_returns_full_ranking():
    exps = [_exp("cap", "veldra:p1", ["a", "b", "c"]), _exp("iso", "veldra:p2", ["z"])]
    ranked = select_next(LearnerState(), exps, CFG, NOW)
    assert len(ranked) == 4  # (a,cap),(b,cap),(c,cap),(z,iso)
    assert ranked[0][1].experience_id == "iso"  # best first


def test_runner_up_is_best_candidate_of_a_different_drive():
    # 'lead' forming on p1 -> deploy candidate on p2; a fresh frame -> diagnose candidate.
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1")
    exps = [_exp("e2", "veldra:p2", ["lead"]), _exp("e3", "veldra:p3", ["fresh"])]
    spec, receipt = select_next(st, exps, CFG, NOW)[0]
    assert receipt.drive == "deploy"
    assert receipt.runner_up_drive == "diagnose"  # a DIFFERENT drive, not 'deploy' again
    assert receipt.margin > 0.0


def test_runner_up_none_at_uniform_cold_start():
    # all candidates are 'diagnose' (cold start) -> no different-drive runner-up
    exps = [_exp("a", "veldra:p1", ["x"]), _exp("b", "veldra:p2", ["y"])]
    spec, receipt = select_next(LearnerState(), exps, CFG, NOW)[0]
    assert receipt.drive == "diagnose"
    assert receipt.runner_up_drive is None and receipt.margin == 0.0


def test_select_next_raises_on_empty_experiences():
    import pytest

    with pytest.raises(ValueError):
        select_next(LearnerState(), [], CFG, NOW)
