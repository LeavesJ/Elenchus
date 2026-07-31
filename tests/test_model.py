import inspect

from elenchus.model import (
    AnthropicModel,
    FakeModel,
    IntakeClassification,
    Model,
    ResponseClassification,
)
from elenchus.types import ConverseTurn, FrameState, TrapState


def test_converseturn_defaults_empty():
    t = ConverseTurn(reply="that's the edge of it")
    assert t.reply == "that's the edge of it"
    assert t.next_pressure == ""  # F1: empty-by-default is the confident default


def test_fakemodel_concierge_converse_returns_converseturn():
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})
    out = m.concierge_converse("problem", [("student", "hi")])
    assert isinstance(out, ConverseTurn)
    assert out.next_pressure == ""


def _exp():  # minimal stand-in; FakeModel ignores it
    return None


def test_fake_model_returns_scripted_intake_and_responses():
    intake = IntakeClassification(
        frame_states={"protect_the_core_lane": FrameState.absent},
        trap_states={"erode_core_for_one_customer": TrapState.not_tripped},
    )
    responses = {
        "protect_the_core_lane": [
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        ]
    }
    m = FakeModel(intake=intake, responses=responses)
    assert (
        m.classify_intake(_exp(), "opening").frame_states["protect_the_core_lane"]
        is FrameState.absent
    )
    assert isinstance(m.generate_push(_exp(), "frame", "protect_the_core_lane"), str)
    rc = m.classify_response(_exp(), "frame", "protect_the_core_lane", "push", "reply")
    assert rc.outcome == "closed" and rc.mechanism_supplied is True


def test_fake_model_raises_when_script_exhausted():
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={"f": []})
    try:
        m.classify_response(_exp(), "frame", "f", "p", "r")
        raise AssertionError("expected IndexError")
    except IndexError:
        pass


def test_fake_model_grade_answer_is_scripted():
    from elenchus.model import FakeModel, IntakeClassification
    from elenchus.types import CheckableGrade, CheckableQuestion, CheckType

    q = CheckableQuestion(
        question_id="q1",
        concept="c",
        prompt="p",
        check_type=CheckType.model_graded,
        answer_key=["ref"],
        criteria="be right",
    )
    m = FakeModel(
        IntakeClassification(frame_states={}, trap_states={}),
        responses={},
        grades={"q1": [CheckableGrade(correct=True)]},
    )
    assert m.grade_answer(None, q, "an answer").correct is True


def test_fake_model_grade_sharper_scripted_then_default_agree():
    from elenchus.model import FakeModel, IntakeClassification
    from elenchus.types import SharperVerdict

    m = FakeModel(
        IntakeClassification(frame_states={}, trap_states={}),
        responses={},
        sharper_verdicts={"f": [SharperVerdict(sharper=False, reason="assent only")]},
    )
    assert m.grade_sharper(None, "frame", "f", "push", "yeah you're right").sharper is False
    # an unscripted code -> the test double's grader agrees by default
    assert m.grade_sharper(None, "frame", "other", "push", "because mechanism X").sharper is True


# ---------------------------------------------------------------------------
# R3: generate_push gains a keyword-only steer on all three definitions
# ---------------------------------------------------------------------------


def test_generate_push_gains_a_keyword_only_steer_on_all_three_definitions():
    """3a. The Protocol, FakeModel, and AnthropicModel must all carry the same shape: `steer` is
    keyword-only with an empty default, mirroring `forge_scenario(brief, steer="")`."""
    for owner in (Model, FakeModel, AnthropicModel):
        sig = inspect.signature(owner.generate_push)
        assert "steer" in sig.parameters, owner
        assert sig.parameters["steer"].default == "", owner
        assert sig.parameters["steer"].kind == inspect.Parameter.KEYWORD_ONLY, owner


def test_fake_model_generate_push_accepts_a_steer_without_erroring():
    intake = IntakeClassification(frame_states={}, trap_states={})
    m = FakeModel(intake, responses={})
    assert isinstance(
        m.generate_push(_exp(), "frame", "protect_the_core_lane", steer="fix this"), str
    )
