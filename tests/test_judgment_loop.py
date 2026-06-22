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
        prompt="...", rubric=rub, ledger_ref="veldra:licensing_continuity", regime=Regime.open_ended
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
