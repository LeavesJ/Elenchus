from retnovation.assessment import judgment_loop
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import (
    Experience,
    Frame,
    FrameState,
    Mode,
    Rubric,
    Regime,
    StopReason,
    Trap,
    TrapState,
    Work,
)


def _exp(mode=Mode.genuinely_open, binding=None):
    rub = Rubric(
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="boundary first",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="keep core",
                paired_trap="erode_core_for_one_customer",
            ),
        ],
        traps=[
            Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case"),
        ],
        mode=mode,
        binding_constraint=binding,
    )
    return Experience(
        experience_id="veldra:licensing_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:licensing_continuity",
        regime=Regime.open_ended,
    )


def _work():
    return Work(opening="here is my reasoning", respond=lambda push: "reply")


def test_cooperative_student_converges():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake, {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()}
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert set(a.frames_closed_under_pressure) == {
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
    }
    # disband rule: no push text contains a literal frame_code
    assert all("protect_the_core_lane" not in p.text for p in a.trajectory)
    # disband: the loop relays generate_push output verbatim — it never wraps the
    # frame_code into student-facing text. (A regression like
    # f"Think about {code}: {push}" would change p.text and fail this.)
    assert all(p.text == f"[push:{p.kind}]" for p in a.trajectory)
    # the independent grader ran and confirmed both sharper calls (default-agree FakeModel)
    assert len(a.sharper_audit) == 2
    assert all(item.confirmed for item in a.sharper_audit)


def test_bounded_error_violation_stops_immediately():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.tripped,
        },
    )
    m = FakeModel(
        intake,
        {
            "erode_core_for_one_customer": [
                ResponseClassification(
                    outcome="unchanged", mechanism_supplied=False, hard_wrong=True
                )
            ]
        },
    )
    a = judgment_loop.assess(
        _exp(mode=Mode.bounded_error, binding="erode_core_for_one_customer"), _work(), m
    )
    assert a.stop_reason is StopReason.bounded_error_violation
    assert a.hard_wrong_flags == ["erode_core_for_one_customer"]


def test_budget_caps_unproductive_loop():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    stuck = [
        ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
        for _ in range(judgment_loop.MAX_PUSHES + 2)
    ]
    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": list(stuck), "protect_the_core_lane": list(stuck)},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason in (StopReason.plateau, StopReason.budget)


def test_regression_stops_when_student_backslides():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_asserted,  # unmet; will be targeted
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    m = FakeModel(
        intake,
        {
            "protect_the_core_lane": [
                ResponseClassification(
                    outcome="regressed", mechanism_supplied=False, hard_wrong=False
                )
            ]
        },
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.regression
    # backslide recorded: present_asserted -> absent, and not credited as closed
    assert any(
        d.code == "protect_the_core_lane" and d.after is FrameState.absent for d in a.frame_deltas
    )
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    # the raw student response is captured on the push
    assert a.trajectory[-1].response == "reply"


def test_plateau_stops_on_two_distinct_unmoved_targets():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def unchanged():
        return [
            ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
        ]

    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": unchanged(), "protect_the_core_lane": unchanged()},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.plateau
    # rotation happened: the two pushes were on DISTINCT targets
    pushed = [p.target_code for p in a.trajectory]
    assert len(pushed) == 2 and pushed[0] != pushed[1]


def test_grader_dispute_demotes_a_sharper_call_in_the_full_loop():
    from retnovation.types import SharperVerdict

    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()},
        sharper_verdicts={
            "protect_the_core_lane": [SharperVerdict(sharper=False, reason="assent only")]
        },
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    # instructor closed both; the blind grader disputes protect_the_core_lane -> demoted
    assert "lead_with_what_you_refuse_to_do" in a.frames_closed_under_pressure
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    assert any(i.code == "protect_the_core_lane" and not i.confirmed for i in a.sharper_audit)


# ---------------------------------------------------------------------------
# Decision-frame / probe-gated convergence tests (Task 3)
# ---------------------------------------------------------------------------


def _exp_decision():
    rub = Rubric(
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="boundary first",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="keep core",
                paired_trap="erode_core_for_one_customer",
            ),
            Frame(
                frame_code="commit_under_the_deadline",
                frame_detail="commit, own the trade, name the reversal",
                paired_trap="commit_without_a_tripwire",
            ),
        ],
        traps=[
            Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case"),
            Trap(trap_code="commit_without_a_tripwire", trap_detail="no reversal line"),
        ],
        mode=Mode.genuinely_open,
        binding_constraint=None,
        decision_frame="commit_under_the_deadline",
    )
    return Experience(
        experience_id="veldra:license_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:license_continuity",
        regime=Regime.open_ended,
    )


def _all_reasoned_intake():
    return IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
            "commit_under_the_deadline": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )


def test_decision_frame_forces_one_stress_probe_before_converging():
    # The dogfood repro: a strong answer rated all-present_reasoned at intake must NOT converge
    # silently — the decision frame is stressed exactly once, then the loop converges.
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(
                    outcome="unchanged", mechanism_supplied=False, hard_wrong=False
                )
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert len(a.trajectory) == 1
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_decision_frame_stress_probe_can_be_credited_sharper():
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert "commit_under_the_deadline" in a.frames_closed_under_pressure
    assert len(a.trajectory) == 1


def test_decision_frame_absent_is_targeted_first():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
            "commit_under_the_deadline": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {
            "commit_under_the_deadline": closed(),
            "lead_with_what_you_refuse_to_do": closed(),
            "protect_the_core_lane": closed(),
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    # without the force, rubric order would target lead_with_what_you_refuse_to_do first
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_no_decision_frame_all_reasoned_still_converges_at_intake():
    # Byte-stability lock: a rubric with no decision_frame keeps today's behavior —
    # an all-present_reasoned opening converges immediately with an empty trajectory.
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    a = judgment_loop.assess(_exp(), _work(), FakeModel(intake, {}))
    assert a.stop_reason is StopReason.converged
    assert a.trajectory == []
