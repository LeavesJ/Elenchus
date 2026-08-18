import itertools
from datetime import datetime, timezone

from elenchus.assessment import judgment_loop
from elenchus.assessment.sharper_grader import audit_sharper
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
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
    TrapState,
    Work,
)

# A two-frame, two-trap rubric for the real-path sweep below. `_exp()` carries a single frame,
# which cannot exercise the case where one code is credited while another is not.
_LOOP_FRAMES = ["protect_the_core_lane", "lead_with_what_you_refuse_to_do"]
_LOOP_TRAPS = ["erode_core_for_one_customer", "scope_creep_to_please"]


def _loop_exp(mode):
    return Experience(
        experience_id="x",
        prompt="p",
        ledger_ref="r",
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[
                Frame(
                    frame_code=_LOOP_FRAMES[0],
                    frame_detail="keep core",
                    paired_trap=_LOOP_TRAPS[0],
                ),
                Frame(
                    frame_code=_LOOP_FRAMES[1],
                    frame_detail="boundary first",
                    paired_trap=_LOOP_TRAPS[1],
                ),
            ],
            traps=[
                Trap(trap_code=_LOOP_TRAPS[0], trap_detail="special-case"),
                Trap(trap_code=_LOOP_TRAPS[1], trap_detail="bend to please"),
            ],
            mode=mode,
        ),
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


def test_audit_selects_on_the_loops_credit_decision_not_the_raw_outcome():
    """The predicate switch itself, on a cell THE LOOP CANNOT EMIT. Read the second paragraph
    before trusting this test for anything.

    `audit_sharper` selects on `not p.gap_closed`. It used to select on
    `p.response_classification != "closed"`. A mutation battery found that reverting the line --
    or deleting the clause outright -- left the whole suite at its exact baseline, because the
    only Push fixture in this file carries `response_classification="closed"` AND
    `gap_closed=True`, so both predicates agree on it.

    THE CELL BELOW IS UNREACHABLE, and an earlier version of this docstring called it "the cell
    where they disagree" without saying so. It contradicted the fixture comment 40 lines above,
    which already states that a code only reaches `frames_closed_under_pressure` through the
    loop's credit branch -- and this test then sets `gap_closed=False` while LEAVING the code in
    that list, which is exactly the state that comment says cannot exist. Measured: 589,824 real
    `judgment_loop.assess` runs over every combination of intake frame state, trap state, mode,
    binding constraint, decision frame and response classification produced 176,308 pushes
    classified `closed` and denied credit, and ZERO where such a push's code was in
    `frames_closed_under_pressure`. `test_frames_closed_under_pressure_implies_a_credited_push`
    below is the real-path pin and carries the reproduction.

    So `sharper_grader.py`'s `p.target_code not in closed` already excludes every Push this
    clause would, and the switch is NOT measurable on any state the engine currently produces.
    What this test actually pins is the hand-built cell only: it is defense in depth against a
    FUTURE writer of `frames_closed_under_pressure` that does not go through the credit branch.
    Keep it for that, and do not read a green run here as evidence about production behaviour."""
    a = _closed_assessment()
    a.trajectory[0].gap_closed = False  # loop refused the credit; the grader still said "closed"
    audited = audit_sharper(_exp(), a, _model())
    assert audited.sharper_audit == []  # the old predicate audited it; this one must not


def test_frames_closed_under_pressure_implies_a_credited_push():
    """The real-path complement to the hand-built test above: drive the actual loop and assert
    the invariant the test above depends on but cannot exercise.

    `frames_closed_under_pressure` has exactly two writers -- `judgment_loop.py`, fed from the
    credit branch where the `Push` necessarily carries `gap_closed=True`, and `audit_sharper`'s
    own removal-only rewrite -- so membership must imply credit. An uncredited push adds its code
    to `exhausted` and `_select_target` skips exhausted codes at every branch, so it can never
    return later to earn credit; both early breaks end the loop outright.

    This is what would go red if someone added a third writer that bypasses the credit branch,
    which is the only way `audit_sharper`'s `not p.gap_closed` clause could ever start mattering.
    The full sweep behind the number in the docstring above is this same loop widened to 589,824
    runs; the bounded version here is what the suite can afford."""
    rcs = [
        ResponseClassification(
            outcome=o, mechanism_supplied=m, hard_wrong=h, mechanism_span="reply"
        )
        for o in ("closed", "unchanged", "regressed")
        for m in (True, False)
        for h in (True, False)
    ]
    inflated = 0
    credited = 0
    runs = 0
    for r0, r1 in itertools.product(rcs, repeat=2):
        for mode in (Mode.genuinely_open, Mode.bounded_error):
            runs += 1
            intake = IntakeClassification(
                frame_states={c: FrameState.absent for c in _LOOP_FRAMES},
                trap_states={c: TrapState.tripped for c in _LOOP_TRAPS},
            )
            script = {
                _LOOP_FRAMES[0]: [r0.model_copy() for _ in range(8)],
                _LOOP_FRAMES[1]: [r1.model_copy() for _ in range(8)],
                _LOOP_TRAPS[0]: [r0.model_copy() for _ in range(8)],
                _LOOP_TRAPS[1]: [r1.model_copy() for _ in range(8)],
            }
            a = judgment_loop.assess(
                _loop_exp(mode),
                Work(opening="here is my reasoning", respond=lambda push: "reply"),
                FakeModel(intake, script),
            )
            closed = set(a.frames_closed_under_pressure)
            for p in a.trajectory:
                if p.kind != "frame":
                    continue
                if p.response_classification == "closed" and not p.gap_closed:
                    inflated += 1
                if p.target_code in closed:
                    credited += 1
                    assert p.gap_closed, (
                        f"{p.target_code} is in frames_closed_under_pressure but its Push carries "
                        "gap_closed=False. A writer of that list now bypasses the loop's credit "
                        "branch, and audit_sharper's `target_code not in closed` no longer implies "
                        "`gap_closed`."
                    )
    # Not vacuous: the interesting state really occurs, and so does its credited counterpart.
    assert runs == 288
    assert inflated > 0, "swept nothing with a closed-but-uncredited push; the sweep went stale"
    assert credited > 0, "swept nothing that reached frames_closed_under_pressure"


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
