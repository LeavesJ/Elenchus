import os

import pytest

from retnovation.aim import aim, derive_core
from retnovation.experience import select_experience
from retnovation.model import AnthropicModel, IntakeClassification
from retnovation.types import FrameState, LearnerState, Regime, TrapState

_HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_intake_on_fixed_experience():
    """Smoke: a real Opus 4.8 call classifies every rubric code on the fixed experience."""
    core = derive_core(aim())
    exp = select_experience(core, LearnerState(), ledger=[], spec=None)
    result = AnthropicModel().classify_intake(
        exp, "I would honor the customer's reading because the relationship matters most."
    )
    assert isinstance(result, IntakeClassification)
    assert set(result.frame_states) == {f.frame_code for f in exp.rubric.frames}
    assert set(result.trap_states) == {t.trap_code for t in exp.rubric.traps}
    assert all(isinstance(v, FrameState) for v in result.frame_states.values())
    assert all(isinstance(v, TrapState) for v in result.trap_states.values())


@pytest.mark.live
def test_live_grade_answer_smoke():
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY")
    from retnovation.model import AnthropicModel
    from retnovation.types import CheckableQuestion, CheckType, Experience, CheckableSet

    q = CheckableQuestion(
        question_id="q1",
        concept="idempotency_under_retry",
        prompt="One word: a handler safe to apply twice is ____.",
        check_type=CheckType.model_graded,
        answer_key=["idempotent"],
        criteria="correct iff the answer means idempotent",
    )
    exp = Experience(
        experience_id="live",
        prompt="p",
        ledger_ref="veldra:x",
        regime=Regime.cs_technical,
        checkable=CheckableSet(questions=[q]),
    )
    grade = AnthropicModel().grade_answer(exp, q, "idempotent")
    assert isinstance(grade.correct, bool)


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_grade_sharper_smoke():
    from retnovation.model import AnthropicModel
    from retnovation.types import (
        Experience,
        Frame,
        Mode,
        Regime,
        Rubric,
        Trap,
    )

    exp = Experience(
        experience_id="live",
        prompt="p",
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[
                Frame(
                    frame_code="protect_the_core_lane",
                    frame_detail="Keep the promise the core product makes to everyone.",
                    paired_trap="t",
                )
            ],
            traps=[Trap(trap_code="t", trap_detail="d")],
            mode=Mode.genuinely_open,
        ),
    )
    v = AnthropicModel().grade_sharper(
        exp,
        "frame",
        "protect_the_core_lane",
        "What do you give up by holding that line?",
        "you're right",
    )
    assert isinstance(v.sharper, bool)
