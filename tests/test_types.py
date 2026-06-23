from datetime import datetime, timezone
from retnovation.types import (
    Strength,
    Regime,
    Mode,
    FrameState,
    StopReason,
    Frame,
    Trap,
    Rubric,
    Experience,
    Assessment,
    Push,
    FrameDelta,
    LearnerState,
    FrameStrength,
    Work,
)


def test_experience_roundtrips_through_json():
    rub = Rubric(
        frames=[Frame(frame_code="protect_the_core_lane", frame_detail="keep the core promise")],
        traps=[
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case one account")
        ],
        mode=Mode.genuinely_open,
    )
    exp = Experience(
        experience_id="veldra:licensing_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:licensing_continuity",
        regime=Regime.open_ended,
    )
    again = Experience.model_validate_json(exp.model_dump_json())
    assert again.regime is Regime.open_ended
    assert again.rubric.frames[0].frame_code == "protect_the_core_lane"


def test_learner_state_defaults_are_independent():
    a, b = LearnerState(), LearnerState()
    now = datetime.now(timezone.utc)
    a.frames["x"] = FrameStrength(strength=Strength.weak, last_seen=now, due=now, last_evidence="")
    assert b.frames == {}  # no shared mutable default


def test_assessment_holds_stop_reason_and_work_is_callable():
    asmt = Assessment(
        trajectory=[
            Push(target_code="f", kind="frame", text="t", response_classification="closed")
        ],
        frame_deltas=[
            FrameDelta(code="f", before=FrameState.absent, after=FrameState.present_reasoned)
        ],
        frames_closed_under_pressure=["f"],
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )
    assert asmt.stop_reason is StopReason.converged
    w = Work(opening="hi", respond=lambda push: "ok")
    assert w.respond("anything") == "ok"


def test_gatecode_and_gateresult_and_experience_id():
    from retnovation.types import GateCode, GateResult, Experience, Rubric, Mode, Regime

    assert GateCode.recoverable_label.value == "recoverable_label"
    assert len(list(GateCode)) == 8

    res = GateResult(
        passed=False, rejects=[GateCode.recoverable_label], downgrades=[], angle_count=4
    )
    assert res.passed is False
    assert res.angle_count == 4

    exp = Experience(
        experience_id="x",
        prompt="p",
        rubric=Rubric(frames=[], traps=[], mode=Mode.genuinely_open, binding_constraint=None),
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
    )
    assert exp.experience_id == "x"
