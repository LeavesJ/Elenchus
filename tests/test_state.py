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
    st = update_state(LearnerState(), a, _now(), "exp1", "veldra:p1")
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
    st = update_state(LearnerState(), a, _now(), "exp1", "veldra:p1")
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
    st = update_state(LearnerState(), a, _now(), "exp1", "veldra:p1")
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
        st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", "veldra:p1", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # initial
    st = update_state_checkable(
        st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", "veldra:p1", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 2  # grew by ease
    st = update_state_checkable(
        st, _casmt([("safety_vs_liveness", False)]), _now(), "cs", "veldra:p1", spacing=sp
    )
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # reset, not deleted
    assert "safety_vs_liveness" in st.declarative_seed


def test_checkable_concept_recalled_only_if_all_questions_correct():
    from retnovation.state import update_state_checkable
    from retnovation.types import LearnerState

    sp = {"initial_interval_days": 1, "ease_factor": 2.0, "min_interval_days": 1}
    a = _casmt([("c", True), ("c", False)])  # same concept, one miss
    st = update_state_checkable(LearnerState(), a, _now(), "cs", "veldra:p1", spacing=sp)
    assert st.declarative_seed["c"].interval_days == 1  # treated as missed


def test_state_updaters_registry_routes_by_regime():
    from retnovation.state import STATE_UPDATERS, update_state, update_state_checkable
    from retnovation.types import Regime

    assert STATE_UPDATERS[Regime.open_ended] is update_state
    assert STATE_UPDATERS[Regime.cs_technical] is update_state_checkable


def test_storage_tier_strong_needs_two_unprompted_problems():
    from datetime import datetime, timezone
    from retnovation.state import derive_strength
    from retnovation.types import Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # 1 unprompted problem → forming (not strong yet)
    assert derive_strength(1, {"veldra:a"}, t0, t0) is Strength.forming
    # 2 distinct unprompted problems → strong (reachable)
    assert derive_strength(2, {"veldra:a", "veldra:b"}, t0, t0) is Strength.strong
    # engaged but never unprompted (closed-under-pressure only) → forming
    assert derive_strength(2, set(), t0, t0) is Strength.forming
    # no engagement → weak
    assert derive_strength(0, set(), t0, t0) is Strength.weak


def test_derive_strength_decays_one_bucket_then_springs_back():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import derive_strength
    from retnovation.types import Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    strong_args = (2, {"veldra:a", "veldra:b"})  # storage tier = strong, interval 30d
    assert derive_strength(*strong_args, t0, t0) is Strength.strong  # fresh
    assert (
        derive_strength(*strong_args, t0, t0 + timedelta(days=40)) is Strength.forming
    )  # decayed one bucket
    # re-exposure: last_seen advances, storage unchanged → springs back
    assert (
        derive_strength(*strong_args, t0 + timedelta(days=40), t0 + timedelta(days=40))
        is Strength.strong
    )


def test_due_keys_to_storage_tier_not_the_decayed_bucket():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import derive_due

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    strong_due = derive_due(2, {"veldra:a", "veldra:b"}, t0)
    forming_due = derive_due(1, {"veldra:a"}, t0)
    # the well-earned (strong-storage) frame comes due LATER, i.e. is reviewed less, not more, as it decays
    assert strong_due == t0 + timedelta(days=30)
    assert forming_due == t0 + timedelta(days=7)
    assert strong_due > forming_due


def test_frame_uncertainty_monotone():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import frame_uncertainty

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # more evidence → less uncertain
    assert frame_uncertainty(1, {"a"}, set(), t0, t0) > frame_uncertainty(5, {"a"}, set(), t0, t0)
    # broader → less uncertain
    assert frame_uncertainty(2, {"a"}, set(), t0, t0) > frame_uncertainty(
        2, {"a", "b"}, set(), t0, t0
    )
    # staler → more uncertain
    assert frame_uncertainty(2, {"a", "b"}, {"a", "b"}, t0, t0) < frame_uncertainty(
        2, {"a", "b"}, {"a", "b"}, t0, t0 + timedelta(days=20)
    )
    # more unprompted breadth → higher storage tier → longer interval → lower staleness-driven uncertainty
    assert frame_uncertainty(2, {"a"}, {"x"}, t0, t0 + timedelta(days=20)) > frame_uncertainty(
        2, {"a"}, {"x", "y"}, t0, t0 + timedelta(days=20)
    )
    u = frame_uncertainty(1, {"a"}, set(), t0, t0)
    assert 0.0 <= u <= 1.0


def test_strong_reachable_across_two_problems():
    from datetime import datetime, timezone
    from retnovation.model import IntakeClassification, ResponseClassification  # noqa: F401
    from retnovation.state import update_state
    from retnovation.types import (
        Assessment,
        FrameDelta,
        FrameState,
        LearnerState,
        Push,
        StopReason,
        Strength,
    )

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)

    def _unprompted(code):
        # an unprompted present_reasoned: a delta to present_reasoned, NOT in frames_closed_under_pressure
        return Assessment(
            trajectory=[
                Push(
                    target_code=code,
                    kind="frame",
                    text="t",
                    response_classification="closed",
                    response="r",
                )
            ],
            frame_deltas=[
                FrameDelta(code=code, before=FrameState.absent, after=FrameState.present_reasoned)
            ],
            frames_closed_under_pressure=[],
            hard_wrong_flags=[],
            stop_reason=StopReason.converged,
        )

    st = LearnerState()
    st = update_state(st, _unprompted("f"), now, "exp1", "veldra:p1")
    assert st.frames["f"].strength is Strength.forming  # one problem only
    st = update_state(st, _unprompted("f"), now, "exp2", "veldra:p2")
    assert st.frames["f"].unprompted_breadth == {"veldra:p1", "veldra:p2"}
    assert st.frames["f"].strength is Strength.strong  # two distinct problems, unprompted


def test_closed_under_pressure_is_forming_not_strong():
    from datetime import datetime, timezone
    from retnovation.state import update_state
    from retnovation.types import (
        Assessment,
        FrameDelta,
        FrameState,
        LearnerState,
        Push,
        StopReason,
        Strength,
    )

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    a = Assessment(
        trajectory=[
            Push(
                target_code="f",
                kind="frame",
                text="t",
                response_classification="closed",
                response="r",
            )
        ],
        frame_deltas=[
            FrameDelta(code="f", before=FrameState.absent, after=FrameState.present_reasoned)
        ],
        frames_closed_under_pressure=["f"],  # needed the push
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )
    st = update_state(LearnerState(), a, now, "exp1", "veldra:p1")
    assert st.frames["f"].strength is Strength.forming
    assert st.frames["f"].breadth == {"veldra:p1"}
    assert (
        st.frames["f"].unprompted_breadth == set()
    )  # closed-under-pressure does NOT earn strong-grade
