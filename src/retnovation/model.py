from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from .content_loader import load_prompt
from .types import (
    CheckableGrade,
    CheckableQuestion,
    Experience,
    FrameState,
    SharperVerdict,
    TrapState,
)


class ModelError(RuntimeError):
    """Raised when the rented model refuses or returns no usable output."""


class IntakeClassification(BaseModel):
    frame_states: dict[str, FrameState]
    trap_states: dict[str, TrapState]


class ResponseClassification(BaseModel):
    outcome: Literal["closed", "unchanged", "regressed"]
    mechanism_supplied: bool
    hard_wrong: bool


@runtime_checkable
class Model(Protocol):
    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification: ...
    def generate_push(
        self, exp: Experience, kind: str, code: str, *, stress: bool = False
    ) -> str: ...
    def classify_response(
        self,
        exp: Experience,
        kind: str,
        code: str,
        push: str,
        response: str,
        *,
        stress: bool = False,
    ) -> ResponseClassification: ...
    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade: ...
    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict: ...


class FakeModel:
    """Deterministic, scripted model for tests. Pops one response per (code) call."""

    def __init__(
        self,
        intake: IntakeClassification,
        responses: dict[str, list[ResponseClassification]],
        grades: dict[str, list[CheckableGrade]] | None = None,
        sharper_verdicts: dict[str, list[SharperVerdict]] | None = None,
    ):
        self._intake = intake
        self._responses = responses
        self._grades = grades or {}
        self._sharper_verdicts = sharper_verdicts or {}

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        return self._intake

    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str:
        return f"[push:{kind}]"

    def classify_response(
        self,
        exp: Experience,
        kind: str,
        code: str,
        push: str,
        response: str,
        *,
        stress: bool = False,
    ) -> ResponseClassification:
        return self._responses[code].pop(0)

    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade:
        return self._grades[question.question_id].pop(0)

    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict:
        scripted = self._sharper_verdicts.get(code)
        if scripted:
            return scripted.pop(0)
        return SharperVerdict(sharper=True, reason="(default agree)")


# Shared Opus 4.8 request params (claude-api reference): adaptive thinking + high effort,
# no sampling parameters (temperature/top_p are removed on 4.8 and 400).
_PARAMS = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}


class _FrameStateItem(BaseModel):
    code: str
    state: FrameState


class _TrapStateItem(BaseModel):
    code: str
    state: TrapState


class _IntakeWire(BaseModel):
    """List-of-pairs wire shape — strict structured outputs cannot express an open-keyed map."""

    frames: list[_FrameStateItem]
    traps: list[_TrapStateItem]


def _situation_block(exp) -> str:
    scene = getattr(exp, "scene", None)
    return f"\n\nSituation:\n{scene.situation}" if scene is not None else ""


def _render_rubric(rubric) -> str:
    lines = [
        f"Mode: {rubric.mode.value}",
        f"Binding constraint: {rubric.binding_constraint}",
        "Frames (classify each by its code):",
    ]
    for f in rubric.frames:
        paired = f" (paired trap: {f.paired_trap})" if f.paired_trap else ""
        lines.append(f"- {f.frame_code}: {f.frame_detail}{paired}")
    lines.append("Traps (classify each by its code):")
    for t in rubric.traps:
        lines.append(f"- {t.trap_code}: {t.trap_detail}")
    return "\n".join(lines)


def _target_detail(rubric, kind: str, code: str) -> str:
    if kind == "trap":
        for t in rubric.traps:
            if t.trap_code == code:
                return t.trap_detail
    else:
        for f in rubric.frames:
            if f.frame_code == code:
                return f.frame_detail
    raise ModelError(f"unknown {kind} code: {code}")


def _require(resp):
    """Doctrine-critical calls never silently default: raise on refusal / empty output."""
    if getattr(resp, "stop_reason", None) == "refusal" or resp.parsed_output is None:
        raise ModelError("model refused or returned no parsed output")
    return resp.parsed_output


class AnthropicModel:
    """Real adapter over Claude Opus 4.8. Doctrine lives in content/prompts/; this is plumbing.

    The doctrine prompts (loaded from content/) carry the disband rules: never name the frame,
    never hand the answer, never grade the conclusion; sharper = a gap closed with a supplied
    mechanism. This class only renders the rubric, calls the model, and parses the result.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-8", client=None):
        self._model = model
        self._api_key = api_key
        self._client = client

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy: tests never need the SDK or network

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        system = load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": opening}],
            output_format=_IntakeWire,
            **_PARAMS,
        )
        wire = _require(resp)
        frame_states = {f.frame_code: FrameState.absent for f in exp.rubric.frames}
        trap_states = {t.trap_code: TrapState.not_tripped for t in exp.rubric.traps}
        # Ignore codes the model invented that are not in the rubric — a hallucinated key
        # would corrupt the judgment loop's convergence and target-selection logic.
        for item in wire.frames:
            if item.code in frame_states:
                frame_states[item.code] = item.state
        for item in wire.traps:
            if item.code in trap_states:
                trap_states[item.code] = item.state
        return IntakeClassification(frame_states=frame_states, trap_states=trap_states)

    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str:
        detail = _target_detail(exp.rubric, kind, code)
        prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""
        user = f"{prefix}Experience:\n{exp.prompt}\n\nAngle to push on:\n{detail}"
        system = load_prompt("push")
        if stress:
            system += "\n\n" + load_prompt("push_stress")
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise ModelError("push generation refused")
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ModelError("no text block in push response")

    def classify_response(
        self,
        exp: Experience,
        kind: str,
        code: str,
        push: str,
        response: str,
        *,
        stress: bool = False,
    ) -> ResponseClassification:
        detail = _target_detail(exp.rubric, kind, code)
        system = (
            load_prompt("response")
            + (("\n\n" + load_prompt("response_stress")) if stress else "")
            + _situation_block(exp)
            + f"\n\nMode: {exp.rubric.mode.value}"
            + f"\nBinding constraint: {exp.rubric.binding_constraint}"
            + f"\nTarget angle: {detail}"
        )
        user = f"Push:\n{push}\n\nStudent reply:\n{response}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ResponseClassification,
            **_PARAMS,
        )
        return _require(resp)

    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade:
        system = (
            load_prompt("grade")
            + f"\n\nQuestion: {question.prompt}"
            + f"\nReference answer(s): {question.answer_key}"
            + f"\nCriteria: {question.criteria}"
        )
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"Student answer:\n{answer}"}],
            output_format=CheckableGrade,
            **_PARAMS,
        )
        return _require(resp)

    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict:
        detail = _target_detail(exp.rubric, kind, code)
        system = load_prompt("grade_sharper") + f"\n\nTarget angle: {detail}"
        user = f"Push:\n{push}\n\nStudent reply:\n{response}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=SharperVerdict,
            **_PARAMS,
        )
        return _require(resp)
