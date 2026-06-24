from datetime import datetime, timezone

from retnovation.state import update_state
from retnovation.types import (
    Assessment,
    FrameDelta,
    FrameState,
    LearnerState,
    Push,
    Strength,
    StopReason,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _asmt(deltas, closed, traps_pushes=None):
    return Assessment(
        trajectory=traps_pushes or [],
        frame_deltas=deltas,
        frames_closed_under_pressure=closed,
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )


def test_closed_under_pressure_becomes_forming():
    a = _asmt(
        [
            FrameDelta(
                code="protect_the_core_lane",
                before=FrameState.absent,
                after=FrameState.present_reasoned,
            )
        ],
        closed=["protect_the_core_lane"],
    )
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert st.frames["protect_the_core_lane"].strength is Strength.forming


def test_unmoved_absent_frame_becomes_weak():
    a = _asmt([], closed=[])
    # frame present in rubric but never closed -> mark weak via trajectory target
    a.trajectory.append(
        Push(
            target_code="lead_with_what_you_refuse_to_do",
            kind="frame",
            text="p",
            response_classification="unchanged",
        )
    )
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert st.frames["lead_with_what_you_refuse_to_do"].strength is Strength.weak


def test_tripped_trap_recorded_in_gallery():
    a = _asmt([], closed=[])
    a.trajectory.append(
        Push(
            target_code="erode_core_for_one_customer",
            kind="trap",
            text="p",
            response_classification="unchanged",
        )
    )
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert "erode_core_for_one_customer" in st.trap_gallery
    assert st.trap_gallery["erode_core_for_one_customer"][0].experience_id == "exp1"


def _casmt(pairs):
    from retnovation.types import CheckableAssessment, ConceptResult, CheckType

    return CheckableAssessment(
        results=[
            ConceptResult(
                concept=c, question_id=f"{c}_q", correct=ok, check_type=CheckType.deterministic
            )
            for c, ok in pairs
        ]
    )


def test_checkable_recall_grows_interval_miss_resets():
    from retnovation.state import update_state_checkable
    from retnovation.types import LearnerState

    sp = {"initial_interval_days": 1, "ease_factor": 2.0, "min_interval_days": 1}
    st = LearnerState()
    st = update_state_checkable(
        st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # initial
    st = update_state_checkable(
        st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 2  # grew by ease
    st = update_state_checkable(
        st, _casmt([("safety_vs_liveness", False)]), _now(), "cs", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # reset, not deleted
    assert "safety_vs_liveness" in st.declarative_seed


def test_checkable_concept_recalled_only_if_all_questions_correct():
    from retnovation.state import update_state_checkable
    from retnovation.types import LearnerState

    sp = {"initial_interval_days": 1, "ease_factor": 2.0, "min_interval_days": 1}
    a = _casmt([("c", True), ("c", False)])  # same concept, one miss
    st = update_state_checkable(LearnerState(), a, _now(), "cs", spacing=sp)
    assert st.declarative_seed["c"].interval_days == 1  # treated as missed


def test_state_updaters_registry_routes_by_regime():
    from retnovation.state import STATE_UPDATERS, update_state, update_state_checkable
    from retnovation.types import Regime

    assert STATE_UPDATERS[Regime.open_ended] is update_state
    assert STATE_UPDATERS[Regime.cs_technical] is update_state_checkable
