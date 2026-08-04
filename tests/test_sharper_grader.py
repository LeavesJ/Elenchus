from datetime import datetime, timezone

from elenchus.assessment.sharper_grader import audit_sharper
from elenchus.model import FakeModel, IntakeClassification
from elenchus.state import update_state
from elenchus.types import (
    Assessment,
    Experience,
    Frame,
    FrameDelta,
    FrameState,
    LearnerState,
    Mode,
    Push,
    Regime,
    Rubric,
    SharperVerdict,
    StopReason,
    Strength,
    Trap,
)


def _exp():
    return Experience(
        experience_id="x",
        prompt="p",
        ledger_ref="r",
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[
                Frame(frame_code="protect_the_core_lane", frame_detail="keep core", paired_trap="t")
            ],
            traps=[Trap(trap_code="t", trap_detail="d")],
            mode=Mode.genuinely_open,
        ),
    )


def _closed_assessment():
    return Assessment(
        trajectory=[
            Push(
                target_code="protect_the_core_lane",
                kind="frame",
                text="push",
                response_classification="closed",
                response="because mechanism X",
                # A code only reaches `frames_closed_under_pressure` (below) through the loop's
                # credit branch, so this fixture was always modelling a CREDITED closure -- it
                # just could not say so before `Push.gap_closed` existed, and stated the proxy
                # instead.
                gap_closed=True,
            )
        ],
        frame_deltas=[
            FrameDelta(
                code="protect_the_core_lane",
                before=FrameState.absent,
                after=FrameState.present_reasoned,
            )
        ],
        frames_closed_under_pressure=["protect_the_core_lane"],
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )


def _model(verdicts=None):
    return FakeModel(
        IntakeClassification(frame_states={}, trap_states={}),
        responses={},
        sharper_verdicts=verdicts,
    )


def test_grader_confirms_keeps_the_closed_call():
    audited = audit_sharper(_exp(), _closed_assessment(), _model())  # default agree
    assert audited.frames_closed_under_pressure == ["protect_the_core_lane"]
    assert len(audited.frame_deltas) == 1
    assert len(audited.sharper_audit) == 1 and audited.sharper_audit[0].confirmed is True


def test_grader_dispute_demotes_reverts_then_state_is_weak():
    disputed = {"protect_the_core_lane": [SharperVerdict(sharper=False, reason="bare assent")]}
    audited = audit_sharper(_exp(), _closed_assessment(), _model(disputed))
    assert audited.frames_closed_under_pressure == []  # demoted out of closed
    assert audited.frame_deltas == []  # delta reverted
    assert audited.sharper_audit[0].confirmed is False
    # and update_state then scores it weak — guards the strong-misclassification trap
    st = update_state(
        LearnerState(), audited, datetime(2026, 6, 23, tzinfo=timezone.utc), "x", "veldra:p"
    )
    assert st.frames["protect_the_core_lane"].strength is Strength.weak


def test_grader_span_unverified_does_not_dispute_or_revert_credited_state():
    """T2 REVIEW FIX: `AnthropicModel.grade_sharper` (model.py) no longer floors `sharper` to False
    on a failed evidence-anchor span match -- it sets `span_unverified` instead, leaving `sharper`
    as the auditor's real judgment. A `sharper=True, span_unverified=True` verdict must NOT be
    treated as a dispute here: `frames_closed_under_pressure` and `frame_deltas` stay exactly as
    the instructor credited them, while the audit record still surfaces the span failure so its
    rate can be seen."""
    verdicts = {
        "protect_the_core_lane": [
            SharperVerdict(sharper=True, reason="agrees; span unverified", span_unverified=True)
        ]
    }
    audited = audit_sharper(_exp(), _closed_assessment(), _model(verdicts))
    assert audited.frames_closed_under_pressure == ["protect_the_core_lane"]  # NOT reverted
    assert len(audited.frame_deltas) == 1  # NOT reverted
    assert audited.sharper_audit[0].confirmed is True
    assert audited.sharper_audit[0].grader_sharper is True
    assert audited.sharper_audit[0].span_unverified is True
