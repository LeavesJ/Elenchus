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
