import pytest

from retnovation.assessment import checkable_scorer
from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import (
    CheckableGrade,
    CheckableQuestion,
    CheckableSet,
    CheckType,
    Experience,
    Regime,
    Work,
)


def _exp(questions):
    return Experience(
        experience_id="cs",
        prompt="answer",
        ledger_ref="veldra:consensus_correctness",
        regime=Regime.cs_technical,
        checkable=CheckableSet(questions=questions),
    )


def _det(qid, concept, key):
    return CheckableQuestion(
        question_id=qid,
        concept=concept,
        prompt="p",
        check_type=CheckType.deterministic,
        answer_key=key,
    )


def _work(answers):
    it = iter(answers)
    return Work(opening="", respond=lambda push: next(it, ""))


def _no_model():
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})


def test_deterministic_scoring_is_normalized_and_model_free():
    exp = _exp(
        [
            _det("q1", "safety_vs_liveness", ["safety"]),
            _det("q2", "idempotency_under_retry", ["idempotent", "idempotency"]),
        ]
    )
    work = _work(["  Safety. ", "IDEMPOTENT"])
    asmt = checkable_scorer.assess(exp, work, _no_model())
    assert [r.correct for r in asmt.results] == [True, True]
    assert [r.concept for r in asmt.results] == ["safety_vs_liveness", "idempotency_under_retry"]


def test_deterministic_wrong_answer_scores_false():
    exp = _exp([_det("q1", "safety_vs_liveness", ["safety"])])
    asmt = checkable_scorer.assess(exp, _work(["liveness"]), _no_model())
    assert asmt.results[0].correct is False


def test_model_graded_question_uses_the_grader():
    q = CheckableQuestion(
        question_id="q1", concept="c", prompt="p", check_type=CheckType.model_graded, criteria="x"
    )
    model = FakeModel(
        IntakeClassification(frame_states={}, trap_states={}),
        responses={},
        grades={"q1": [CheckableGrade(correct=True)]},
    )
    asmt = checkable_scorer.assess(_exp([q]), _work(["some prose"]), model)
    assert asmt.results[0].correct is True
    assert asmt.results[0].check_type is CheckType.model_graded


def test_deterministic_without_answer_key_raises():
    bad = CheckableQuestion(
        question_id="q1", concept="c", prompt="p", check_type=CheckType.deterministic, answer_key=[]
    )
    with pytest.raises(ValueError):
        checkable_scorer.assess(_exp([bad]), _work(["x"]), _no_model())


def test_assess_raises_when_checkable_is_none():
    exp = Experience.model_construct(
        experience_id="x",
        prompt="p",
        ledger_ref="r",
        regime=Regime.cs_technical,
        rubric=None,
        checkable=None,
    )
    with pytest.raises(ValueError):
        checkable_scorer.assess(exp, _work([]), _no_model())
