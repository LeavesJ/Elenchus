from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from .content_loader import load_prompt
from .types import (
    CheckableGrade,
    CheckableQuestion,
    EgressScreen,
    EntryClass,
    EntryClassification,
    Experience,
    FrameState,
    GeneratedOutput,
    InjectionExpressed,
    PreferenceRating,
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
    def generate_output(
        self, scenario_prompt: str, injection: str | None, *, max_tokens: int = 1024
    ) -> GeneratedOutput: ...
    def rate_preference(
        self, scenario_prompt: str, output_a: str, output_b: str
    ) -> PreferenceRating: ...
    def check_injection_expressed(
        self, injection: str, framed_output: str
    ) -> InjectionExpressed: ...
    def classify_entry(
        self, prompt: str, opening: str, recent: list[tuple[str, str]]
    ) -> "EntryClassification": ...
    def concierge_turn(
        self,
        problem: str,
        push: str,
        recent: list[tuple[str, str]],
        *,
        arc: tuple[int, int] | None = None,
        voice: str = "",
    ) -> str: ...
    def concierge_close(
        self, problem: str, recent: list[tuple[str, str]], *, voice: str = ""
    ) -> str: ...
    def concierge_open(self, problem: str, *, voice: str = "") -> str: ...
    def concierge_converse(
        self,
        problem: str,
        recent: list[tuple[str, str]],
        *,
        stop_reason: str = "converged",
        voice: str = "",
    ) -> str: ...
    def concierge_land(
        self,
        problem: str,
        recent: list[tuple[str, str]],
        stop_reason: str,
        *,
        steer: str = "",
        voice: str = "",
    ) -> str: ...
    def screen_moves(self, moves: list[str], text: str) -> "EgressScreen": ...


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

    def classify_entry(
        self, prompt: str, opening: str, recent: list[tuple[str, str]]
    ) -> EntryClassification:
        # Offline double: every opening is a real attempt (keeps the engine path unchanged).
        return EntryClassification(entry_class=EntryClass.substantive, reply="")

    def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
        return push or "take a real position"  # probe: echo the brief; reinvite: a safe invite

    def concierge_close(self, problem, recent, *, voice=""):
        return "[close synthesis]"

    def concierge_open(self, problem, *, voice=""):
        return "[open]"

    def concierge_converse(self, problem, recent, *, stop_reason="converged", voice=""):
        return "[converse winddown]"

    def concierge_land(self, problem, recent, stop_reason, *, steer="", voice=""):
        return f"[land:{stop_reason}]"

    def check_injection_expressed(self, injection: str, framed_output: str) -> InjectionExpressed:
        # Safe by default; voice tests that need a leak use FakeLeakModel (Task 2).
        return InjectionExpressed(expressed=False, evidence="(fake: no leak)")

    def screen_moves(self, moves: list[str], text: str) -> EgressScreen:
        # Safe by default; voice tests that need a leak override this (FakeLeakModel).
        return EgressScreen(performed=[], evidence="(fake: nothing screened)")


class FakeLiftModel:
    """Scripted model for blind-lift-harness tests. Outputs keyed by (prompt, is_framed);
    ratings by prompt; expression-checks by the framed output text."""

    def __init__(self, outputs, ratings, expressed):
        self._outputs = outputs
        self._ratings = ratings
        self._expressed = expressed

    def generate_output(self, scenario_prompt, injection, *, max_tokens=1024):
        return self._outputs[(scenario_prompt, injection is not None)]

    def rate_preference(self, scenario_prompt, output_a, output_b):
        return self._ratings[scenario_prompt]

    def check_injection_expressed(self, injection, framed_output):
        return self._expressed[framed_output]


# Shared Opus 4.8 request params (claude-api reference): adaptive thinking + high effort,
# no sampling parameters (temperature/top_p are removed on 4.8 and 400).
_PARAMS = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}

# Medium effort for the batched egress screen only (claude-api: effort is low|medium|high, default
# high; adaptive thinking stays ON). MEASURED: with adaptive thinking, high is already fast on the
# simple calls (classify_entry ~1.3s, concierge_turn ~1.5s) — lowering them buys nothing and slightly
# hurts, so they keep _PARAMS. The real latency win was BATCHING the egress (4 serial per-move
# checks ~11s -> one screen ~2.5s, §screen_moves), not effort. Medium shaves the screen 3.6->2.5s
# and the @live no-op + leak-catch confirm it stays accurate. Judgment calls all keep _PARAMS.
_MED_PARAMS = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}

_ECHO_MAX_TOKENS = 1024  # a push is a sentence or two; explicit per L-17 (adaptive thinking budget)

# Graded-classifier headroom (L-17 third strike, founder dogfood 2026-07-01): classify_intake
# MEASURED 1052-1828 output tokens (thinking included) on a real founder opening against the old
# 2048 cap — one longer adaptive-thinking excursion crossed it, parsed_output=None, and _require
# bricked the session terminally. Same rationale as _SCREEN_MAX_TOKENS: a larger cap only buys
# thinking room; cost does not rise unless the model genuinely thinks more. classify_entry stays
# at 2048 (measured ~19 output tokens — nowhere near the cap).
_CLASSIFY_MAX_TOKENS = 4096

# Egress screen headroom: the structured output (performed + evidence) is tiny, but medium-effort
# adaptive thinking on a nuanced screen can exceed 1024 and trip the truncation guard — which raises
# and would brick the turn in production. A larger cap only buys thinking room (adaptive spends what
# it needs), so cost does not rise unless the screen genuinely thinks more. (L-17: budget a shared
# helper for its hardest caller; surfaced @live by the comprehension gear's longer turns.)
_SCREEN_MAX_TOKENS = 4096


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


def _render_turns(recent: list[tuple[str, str]], limit: int = 6) -> str:
    if not recent:
        return ""
    lines = [f"{role}: {text}" for role, text in recent[-limit:]]
    return "Recent exchange:\n" + "\n".join(lines) + "\n\n"


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
    """Doctrine-critical calls never silently default: raise on refusal / empty output. Truncation
    gets its OWN message (L-17 third strike): adaptive thinking eating the budget must never
    masquerade as a refusal — it cost a live diagnosis to attribute the 2026-07-01 session brick."""
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise ModelError(
            "structured output truncated at max_tokens — raise this call's budget (L-17)"
        )
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
            max_tokens=_CLASSIFY_MAX_TOKENS,
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
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ResponseClassification,
            **_PARAMS,
        )
        return _require(resp)

    def classify_entry(
        self, prompt: str, opening: str, recent: list[tuple[str, str]]
    ) -> EntryClassification:
        system = load_prompt("entry")  # frame-blind: doctrine only, never the rubric
        user = f"Problem:\n{prompt}\n\n{_render_turns(recent)}Student's latest message:\n{opening}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=EntryClassification,
            **_PARAMS,  # measured ~1.3s at high; lowering effort here is slower, not faster
        )
        return _require(resp)

    def concierge_turn(
        self,
        problem: str,
        push: str,
        recent: list[tuple[str, str]],
        *,
        arc: tuple[int, int] | None = None,
        voice: str = "",
    ) -> str:
        # Frame-blind: problem + dialogue + the SAFE push only. `voice` = composed persona+role+craft.
        # arc=(n, cap) is the frame-blind position hint — two integers, PROBE briefs only (the
        # re-invite is pre-engine and never carries it); the doctrine in concierge.md holds the bands.
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge")
        brief = (
            f"Next angle to pursue (turn it into a question; never state it):\n{push}"
            if push
            else "The student has not taken a real position yet — acknowledge what they said and invite one."
        )
        if push and arc:
            n, cap = arc
            brief += (
                f"\nArc: this is push {n}; the diagnostic never runs past {cap} pushes "
                "and usually resolves well before that."
            )
        user = f"Problem:\n{problem}\n\n{_render_turns(recent)}{brief}"
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""  # never block the loop; voice falls back to the push or a safe contract
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def concierge_close(
        self, problem: str, recent: list[tuple[str, str]], *, voice: str = ""
    ) -> str:
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_close")
        user = f"Problem:\n{problem}\n\n{_render_turns(recent)}Write the closing synthesis."
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def concierge_open(self, problem: str, *, voice: str = "") -> str:
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_open")
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": f"Problem:\n{problem}"}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def concierge_converse(
        self,
        problem: str,
        recent: list[tuple[str, str]],
        *,
        stop_reason: str = "converged",
        voice: str = "",
    ) -> str:
        # Post-stop wind-down: no engine push, no re-invite. Wider window (limit=20) so a committed
        # position can't age out of view and get re-demanded. Honest by stop_reason (a process signal,
        # never a grade — L-4): on a non-converged stop the author must NOT assume the student
        # committed (dogfood 2026-07-01). Frame-blind.
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_converse")
        user = (
            f"Problem:\n{problem}\n\nStop reason: {stop_reason}\n\n"
            f"{_render_turns(recent, limit=20)}Respond to the student's latest."
        )
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def concierge_land(
        self,
        problem: str,
        recent: list[tuple[str, str]],
        stop_reason: str,
        *,
        steer: str = "",
        voice: str = "",
    ) -> str:
        # The felt landing at convergence/stop. `stop_reason` is the assessment's StopReason value —
        # the author lands honestly by it. Frame-blind; correctness is deliberately NOT supplied (L-4:
        # the landing rewards the reckoning, never the answer). Wider window (limit=20) so it references
        # the real arc, not a 6-turn tail. NOTE: `resp.stop_reason` below is the API's finish reason,
        # distinct from the `stop_reason` argument (the diagnostic outcome).
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_land")
        user = (
            f"Problem:\n{problem}\n\nStop reason: {stop_reason}\n\n"
            f"{_render_turns(recent, limit=20)}Write the landing."
        )
        if steer:  # the one-shot retry steer (voice.land): re-land without restating the mechanism
            user += "\n" + steer
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_ECHO_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

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

    def generate_output(
        self, scenario_prompt: str, injection: str | None, *, max_tokens: int = 1024
    ) -> GeneratedOutput:
        kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": scenario_prompt}],
            **_PARAMS,
        )
        if (
            injection is not None
        ):  # framed: the frame is the system guidance; control is frame-naive
            kwargs["system"] = injection
        resp = self._get_client().messages.create(**kwargs)
        refused = getattr(resp, "stop_reason", None) == "refusal"
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        if not text and not refused:  # a truly empty non-refusal is an error; a refusal is signal
            raise ModelError("no text in generate_output response")
        return GeneratedOutput(text=text, refused=refused)

    def rate_preference(
        self, scenario_prompt: str, output_a: str, output_b: str
    ) -> PreferenceRating:
        system = load_prompt("lift_rate")
        user = f"Task:\n{scenario_prompt}\n\nOutput A:\n{output_a}\n\nOutput B:\n{output_b}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=PreferenceRating,
            **_PARAMS,
        )
        return _require(resp)

    def check_injection_expressed(self, injection: str, framed_output: str) -> InjectionExpressed:
        system = load_prompt("lift_manipulation") + f"\n\nThe move to check for:\n{injection}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"Output:\n{framed_output}"}],
            output_format=InjectionExpressed,
            **_PARAMS,
        )
        return _require(resp)

    def screen_moves(self, moves: list[str], text: str) -> EgressScreen:
        # Batched egress (the L-13 backstop): which of the hidden moves does `text` PERFORM, in ONE
        # call over the whole list, instead of one check_injection_expressed per move. The lift
        # harness keeps check_injection_expressed (high effort); this auditor runs at medium.
        numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(moves))
        system = load_prompt("egress")
        user = f"Hidden moves:\n{numbered}\n\nText to screen:\n{text}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=_SCREEN_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=EgressScreen,
            **_MED_PARAMS,
        )
        # Fail LOUD on truncation: a cut-off parse could drop performed indices -> silent
        # false-negative (a leak passes), the one direction the backstop must never fail quietly.
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise ModelError("screen_moves truncated at max_tokens — egress screen unreliable")
        return _require(resp)
