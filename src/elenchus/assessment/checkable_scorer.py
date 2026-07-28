from __future__ import annotations

import re

from ..model import Model
from ..types import (
    CheckableAssessment,
    CheckableQuestion,
    CheckType,
    ConceptResult,
    Experience,
    Work,
)


def _normalize(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    return s.strip(".,;:!?\"'")


def _render(q: CheckableQuestion) -> str:
    if q.choices:
        opts = "\n".join(f"  - {c}" for c in q.choices)
        return f"{q.prompt}\n{opts}"
    return q.prompt


def score_question(exp: Experience, q: CheckableQuestion, answer: str, model: Model) -> bool:
    if q.check_type is CheckType.deterministic:
        if not q.answer_key:
            raise ValueError(f"deterministic question {q.question_id} has no answer_key")
        return _normalize(answer) in {_normalize(k) for k in q.answer_key}
    return model.grade_answer(exp, q, answer).correct


def assess(exp: Experience, work: Work, model: Model) -> CheckableAssessment:
    if exp.checkable is None:
        raise ValueError("cs_technical experience has no checkable set")
    results: list[ConceptResult] = []
    for q in exp.checkable.questions:
        answer = work.respond(_render(q))
        results.append(
            ConceptResult(
                concept=q.concept,
                question_id=q.question_id,
                correct=score_question(exp, q, answer, model),
                check_type=q.check_type,
            )
        )
    return CheckableAssessment(results=results)
