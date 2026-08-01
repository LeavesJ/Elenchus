from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from .content_loader import load_prompt, load_spike_prompt
from .prompt_text import LEARNER_INDENT, indent_after_first, labelled
from .types import (
    CandidateFrame,
    CheckableGrade,
    CheckableQuestion,
    ConvergenceCheck,
    ConverseTurn,
    EgressScreen,
    EntryClass,
    EntryClassification,
    Experience,
    FitCheck,
    FrameState,
    GeneratedOutput,
    InjectionExpressed,
    Positions,
    PreferenceRating,
    SharperVerdict,
    TerritoryMap,
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
        self,
        exp: Experience,
        kind: str,
        code: str,
        *,
        stress: bool = False,
        positions: Positions = Positions(),
        steer: str = "",
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
    ) -> "ConverseTurn": ...
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
    def map_territories(
        self, situation: str, territories: list[tuple[str, str]]
    ) -> "TerritoryMap": ...
    def forge_scenario(self, brief: str, steer: str = "") -> str: ...
    def fit_check(self, scenario: str, requirements: str) -> "FitCheck": ...
    def concierge_sitting_close(
        self, situation: str, segments: list[list[tuple[str, str]]], voice: str = ""
    ) -> str: ...


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

    def generate_push(
        self,
        exp: Experience,
        kind: str,
        code: str,
        *,
        stress: bool = False,
        positions: Positions = Positions(),
        steer: str = "",
    ) -> str:
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
        return ConverseTurn(reply="[converse winddown]", next_pressure="")

    def concierge_land(self, problem, recent, stop_reason, *, steer="", voice=""):
        return f"[land:{stop_reason}]"

    # Living-sitting constants (scripted-pop pattern untouched — review M12); leak/reject test
    # fakes subclass-override these per the _ConciergeFidelityModel convention.
    def map_territories(self, situation, territories):
        return TerritoryMap(
            ranked=[eid for eid, _ in territories], confidence="high", reflection="[reflect]"
        )

    def generate_frames(self, problem, exemplars):
        return getattr(self, "_frames", [])

    def generate_scenarios(self, problem):
        return getattr(self, "_scenarios", [])

    def frame_convergence(self, frame_detail, curated):
        return getattr(
            self,
            "_convergence",
            ConvergenceCheck(
                nearest=(curated[0][0] if curated else "choose_the_failure_default_deliberately"),
                restates_nearest=False,
                confidence="low",
                rationale="(fake: no judgment)",
            ),
        )

    def forge_scenario(self, brief, steer=""):
        return "[forged scenario]"

    def fit_check(self, scenario, requirements):
        return FitCheck(fits=True, reason="")

    def concierge_sitting_close(self, situation, segments, voice=""):
        return "[sitting close]"

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


# Shared Opus 5 request params (claude-api reference): adaptive thinking + high effort, no
# sampling parameters (temperature/top_p are removed on Opus 4.7 onward and 400). Both stay
# valid verbatim on Opus 5 — its two breaking changes are that thinking is ON when the field is
# OMITTED (we set it explicitly, so nothing moves) and that `thinking: {"type": "disabled"}` is
# rejected above `high` effort. We never disable thinking and never exceed `high`, so neither
# bites. Do NOT raise either constant to `xhigh`/`max` without re-reading that second rule.
_PARAMS = {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}

# Medium effort for the batched egress screen only (claude-api: Opus 5 takes low|medium|high|xhigh|
# max, default high; adaptive thinking stays ON). MEASURED: with adaptive thinking, high is already fast on the
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

# Forge-surface headroom (living sitting L1): the forged scenario (the opening say, multi-paragraph)
# and the whole-sitting close are the two long-form authored surfaces — 4096 pinned by the plan so
# adaptive thinking plus the authored text never trips truncation (L-17: an explicit budget per
# caller; _ECHO_MAX_TOKENS was tuned for one-or-two-sentence turns and does not fit these).
_FORGE_MAX_TOKENS = 4096


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


class _FramesWire(BaseModel):
    frames: list[CandidateFrame]


class _ScenariosWire(BaseModel):
    scenarios: list[str]  # decision-scenario prompts (the harness wraps them in LiftScenario)


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


_TURN_RENDER_CAP = 6000  # characters, measured on the RENDERED turn (after indent_after_first),
# not the raw text handed in. judgment_loop._POSITION_CAP's own comment records that a cap
# measured before render does not bound what comes out: a newline-heavy raw text can render to
# several times its own length once every continuation line gets its own LEARNER_INDENT prefix.
# Capping the rendered string directly sidesteps that arithmetic: the bound holds regardless of
# how the raw turn is shaped -- one enormous line, thousands of empty ones, anything between.
#
# Raised from 2000 (review, 2026-07-31): 2000 sat BELOW the model's own output ceiling, so it
# could trim a turn the engine itself produced -- not just pathological learner input -- because
# Vera's own turns are fed back into `recent` and re-rendered on every later call
# (web/session_runner.py:1225 appends a probe/re-invite turn; :2302 appends a concierge_converse
# reply). `_ECHO_MAX_TOKENS = 1024` (model.py:282, `grep -n "_ECHO_MAX_TOKENS = " model.py`) bounds
# concierge_turn/close/land, the routine per-turn Vera author. Assuming ~4 characters per output
# token -- a standard order-of-magnitude approximation for English text; this repo has no offline
# tokenizer to measure it exactly, and calling the live count_tokens endpoint is out of scope for
# a code comment, so this ratio is ASSUMED, falsified by any real rendered turn this repo observes
# exceeding the cap -- 1024 * 4 = 4096 characters (`python3 -c "print(1024*4)"`). 6000 sits above
# that with headroom.
#
# concierge_converse's reply is a second, larger source, also fed back into `recent`
# (session_runner.py:2302) and re-rendered later: it runs under `_CLASSIFY_MAX_TOKENS = 4096`
# (model.py:290), doubled to 8192 on one retry (_parse_required, model.py:474-475). That budget
# buys adaptive-thinking headroom, not proportionally longer visible text -- the same relationship
# this file's own comments on `_CLASSIFY_MAX_TOKENS` and `_SCREEN_MAX_TOKENS` already document
# (lines 284-297): a larger cap only buys thinking room, and cost does not rise unless the call
# genuinely thinks or writes more. Doctrine, not this constant, is what keeps a converse reply
# short, the same as every other Vera-authored turn -- 6000 is not a hard guarantee against that
# call's full token ceiling, but no cap short of tens of thousands of characters would be, and the
# old 2000 was not one either.
#
# Worst-case block size for the wind-down callers (limit=20: concierge_land, concierge_converse):
# 6000 * 20 = 120,000 characters (`python3 -c "print(6000*20)"`), plus the fixed "Recent
# exchange:" header and the role-prefix overhead.

# Task 4 (graded/routing sites: classify_response, classify_entry, map_territories; task 6 added
# grade_sharper and concierge_sitting_close's situation blob -- NOT its per-turn text, which takes
# `_TURN_RENDER_CAP` like every other dialogue turn): a SMALLER cap for text that
# is typed directly by a person, never something the model wrote back. `grade_answer` uses this
# number too but as a REFUSAL threshold rather than a trim point, because its result IS a grade --
# see its own comment. Unlike
# `_TURN_RENDER_CAP`, this number has no model max_tokens ceiling it has to clear -- the concern
# that forced `_TURN_RENDER_CAP` up from 2000 to 6000 was Vera's OWN turns being re-fed through
# `recent` and re-rendered (session_runner.py appends a probe/re-invite/converse reply, then
# passes it back through `_render_turns` on the next call); nothing re-feeds a model
# completion back through any of these sites. This mirrors `forge.build_brief`'s `_BRIEF_BLOB_CAP`
# (forge.py:101) exactly, restated here for a sibling site over the identical KIND of text -- and
# for `map_territories` and `concierge_sitting_close`, over the identical DATA: both are handed
# the same `situation` string session_runner.py already threads into `build_brief`, so capping it
# at the same number here is matching an existing precedent for this data, not inventing a new
# one. (map_territories' other caller, `_capture_steer`, passes `next_pressure` instead -- a
# model-DISTILLED value, per its own field doc in types.ConverseTurn "a distilled fresh decision"
# whose "label echoes her raw words" -- i.e. a short phrase, not a full authored reply, so it
# carries none of the re-fed-turn concern either; ASSUMED short based on that doc, not measured,
# since no offline path produces one.) 2000 stays generous against a real typed message on its
# own terms.
_LEARNER_TEXT_CAP = 2000


def _cap_rendered_turn(rendered: str, cap: int = _TURN_RENDER_CAP) -> str:
    """Truncate an already-rendered blob at `cap` characters (default `_TURN_RENDER_CAP`),
    marking the elision.

    Applied AFTER `indent_after_first`/`labelled`, never before -- the fix for the mistake
    `judgment_loop._POSITION_CAP` documents in its own comment, where the cap bounded the text
    handed TO the renderer rather than the string that came OUT of it. Slicing the rendered
    string can only shorten an existing line or drop a trailing one; it can never introduce a new
    line, so it cannot undo the indent discipline that keeps a learner byte off column 0.

    Originally turn-specific (`_render_turns`' per-turn cap, the only caller until task 4); the
    `cap` parameter generalises it for the four graded/routing sites, some of which pass
    `_LEARNER_TEXT_CAP` instead of the default -- see that constant's comment for which site uses
    which and why."""
    if len(rendered) <= cap:
        return rendered
    return rendered[:cap] + "…[trimmed]"


def _render_turns(recent: list[tuple[str, str]], limit: int = 6) -> str:
    """Render the trailing window of dialogue turns for a composed prompt.

    Every continuation line of a turn is indented past its `"{role}: "` prefix -- the same
    discipline `prompt_text.bulleted` applies to a position: the first line carries the prefix,
    every later line gets `prompt_text.LEARNER_INDENT`, so a newline in a learner's reply can
    never open a line at column 0, where the composed prompt's own headings live. A turn
    containing no line break -- the ordinary case, almost all real input -- renders byte-identically
    to the old bare `f"{role}: {text}"`: the indent machinery is a no-op when a turn has no second
    line to indent. This does NOT extend to a turn that merely LOOKS single-line under `splitlines()`
    but carries a trailing line break (e.g. `"hello\n"`): `splitlines()` drops the terminator, so
    that turn renders one byte shorter than the bare form -- inherited from `indent_after_first`,
    not introduced here (see `prompt_text.bulleted`'s docstring for the same caveat).

    Each turn is then capped at `_TURN_RENDER_CAP` characters, measured on its RENDERED text, not
    the raw text handed in (see `_cap_rendered_turn`). The cap is applied per turn, not once
    across the whole block: the number of turns is already bounded by `limit`, a code constant
    (6, or 20 for the wind-down callers) that no learner input ever touches, so a per-turn cap
    already fixes the worst-case size of the whole block at `limit * _TURN_RENDER_CAP`, plus the
    fixed "Recent exchange:" header and the role-prefix overhead. A second cap spanning the block
    would only bound a quantity the per-turn cap has already determined.
    """
    if not recent:
        return ""
    lines = [
        _cap_rendered_turn(indent_after_first(text, f"{role}: ", LEARNER_INDENT))
        for role, text in recent[-limit:]
    ]
    return "Recent exchange:\n" + "\n".join(lines) + "\n\n"


def _bulleted(items: tuple[str, ...]) -> str:
    """Render positions as a list no learner line can escape.

    Exists because both position groups (on_angle and elsewhere) in generate_push need it.
    Continuation lines are indented past the bullet, so a newline in a learner's reply cannot
    place text at column 0 where the composed prompt's own headings live."""
    out: list[str] = []
    for item in items:
        lines = item.splitlines() or [""]
        out.append(f"  - {lines[0]}")
        out.extend(f"    {line}" for line in lines[1:])
    return "\n".join(out)


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
    """Real adapter over Claude Opus 5. Doctrine lives in content/prompts/; this is plumbing.

    The doctrine prompts (loaded from content/) carry the disband rules: never name the frame,
    never hand the answer, never grade the conclusion; sharper = a gap closed with a supplied
    mechanism. This class only renders the rubric, calls the model, and parses the result.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-5", client=None):
        self._model = model
        self._api_key = api_key
        self._client = client

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy: tests never need the SDK or network

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def _parse_required(self, *, max_tokens: int, **kwargs):
        """One structured parse, output REQUIRED — with a SINGLE retry: budget-doubled on
        truncation, plain on refusal/empty parse. L-17 keeps failing loud as the backstop, but
        one adaptive-thinking excursion past the base budget must cost a RETRY, not the segment
        (founder live dogfood 2026-07-02: a truncated structured call mid-press killed the
        worker on a door he was working well). A STOCHASTIC refusal costs a retry for the same
        reason (founder live dogfood 2026-07-03: classify_response refused mid-press on an
        ethically pointed reply — 'I'll read high … nobody can pinpoint it to me' — and killed
        the door; the instrumented live replay named the class: same dialogue, 2 clean runs,
        1 refusal). A deterministic refusal still fails loud on the second strike."""
        client = self._get_client()
        resp = client.messages.parse(model=self._model, max_tokens=max_tokens, **kwargs)
        if getattr(resp, "stop_reason", None) == "max_tokens":
            resp = client.messages.parse(model=self._model, max_tokens=max_tokens * 2, **kwargs)
        elif getattr(resp, "stop_reason", None) == "refusal" or resp.parsed_output is None:
            resp = client.messages.parse(model=self._model, max_tokens=max_tokens, **kwargs)
        return _require(resp)  # the single retry is spent; both classes now fail LOUD

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        system = load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": opening}],
            output_format=_IntakeWire,
            **_PARAMS,
        )
        wire = resp
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

    def generate_push(
        self,
        exp: Experience,
        kind: str,
        code: str,
        *,
        stress: bool = False,
        positions: Positions = Positions(),
        steer: str = "",
    ) -> str:
        detail = _target_detail(exp.rubric, kind, code)
        prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""
        # The learner's own words (spec 2026-07-30). Each group is omitted when empty, so a
        # default Positions() composes a byte-identical prompt to before this existed. The
        # target CODE is never emitted — only the grouping derived from it.
        blocks = ""
        if positions.on_angle:
            said = _bulleted(positions.on_angle)
            blocks += f"What the student has already argued on THIS angle:\n{said}\n\n"
        if positions.elsewhere:
            said = _bulleted(positions.elsewhere)
            blocks += f"Positions taken elsewhere in this sitting:\n{said}\n\n"
        user = f"{prefix}Experience:\n{exp.prompt}\n\n{blocks}Angle to push on:\n{detail}"
        # The steered retry (R3): composed exactly like forge_scenario's, so an empty steer is
        # byte-identical to no steer at all (every existing caller keeps passing none).
        if steer:
            user += f"\n\nSteer (fix exactly this): {steer}"
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
        # Task 4: `response` is the learner's own reply -- the boundary seam, `_LEARNER_TEXT_CAP`
        # (see its comment). `push` is the engine's own generated angle, never learner text, and
        # stays outside the seam.
        user = f"Push:\n{push}\n\n" + _cap_rendered_turn(
            labelled("Student reply:", response), cap=_LEARNER_TEXT_CAP
        )
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ResponseClassification,
            **_PARAMS,
        )
        return resp

    def classify_entry(
        self, prompt: str, opening: str, recent: list[tuple[str, str]]
    ) -> EntryClassification:
        system = load_prompt("entry")  # frame-blind: doctrine only, never the rubric
        # Task 4: `opening` is the learner's own latest message -- the boundary seam,
        # `_LEARNER_TEXT_CAP` (see its comment). `_render_turns(recent)` already caps its own
        # dialogue turns at `_TURN_RENDER_CAP` (untouched here).
        user = f"Problem:\n{prompt}\n\n{_render_turns(recent)}" + _cap_rendered_turn(
            labelled("Student's latest message:", opening), cap=_LEARNER_TEXT_CAP
        )
        resp = self._parse_required(
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=EntryClassification,
            **_PARAMS,  # measured ~1.3s at high; lowering effort here is slower, not faster
        )
        return resp

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
    ) -> ConverseTurn:
        # Post-stop wind-down: no engine push, no re-invite. Wider window (limit=20) so a committed
        # position can't age out of view and get re-demanded. Honest by stop_reason (a process signal,
        # never a grade — L-4): on a non-converged stop the author must NOT assume the student
        # committed (dogfood 2026-07-01). Frame-blind. STRUCTURED (§2a): reply + next_pressure
        # (empty-by-default, F1); the distilled next_pressure is server-side only (L-13/F2). Rides
        # _parse_required (L-17: one budget-doubled retry on truncation, then loud). _CLASSIFY budget:
        # the subtle F1 judgment can spend adaptive-thinking tokens, and a larger cap only buys
        # thinking room (adaptive spends what it needs).
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_converse")
        user = (
            f"Problem:\n{problem}\n\nStop reason: {stop_reason}\n\n"
            f"{_render_turns(recent, limit=20)}Respond to the student's latest."
        )
        return self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ConverseTurn,
            **_PARAMS,
        )

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
        # Task 6: `answer` is the student's own submission -- the boundary seam,
        # `_LEARNER_TEXT_CAP` (see its comment). Both `Work.respond` implementations return text a
        # person typed, never a model completion (orchestration.py:34 `input("> ")`;
        # web/session_runner.py:1226 the raw student reply off the worker channel), so this carries
        # none of the re-fed-turn concern that forced `_TURN_RENDER_CAP` higher. The question, key,
        # and criteria are curated content and stay in `system`, outside the seam.
        #
        # The cap is a REFUSAL threshold here, never a trim point, and unlike its three sibling
        # sites this one does not call `_cap_rendered_turn` at all (T2 review Fix 1). Reason:
        # `assessment/checkable_scorer.py:33` returns `grade_answer(...).correct` straight through
        # as the concept result, so a silently clipped tail that carried what `criteria` asks for
        # turns a correct answer into `correct=False` -- a wrong grade wearing a checkmark. That is
        # exactly the trade `screen_moves` refuses ~90 lines below, for the same reason: where the
        # cut makes the judgment unreliable, fail loud instead of trimming quietly. `grade_sharper`
        # keeps the silent trim deliberately: it re-grades the SAME string `classify_response`
        # already capped identically, so trimming there keeps instructor and blind auditor reading
        # byte-identical text, which is the property that audit depends on.
        rendered = labelled("Student answer:", answer)
        if len(rendered) > _LEARNER_TEXT_CAP:
            raise ModelError("grade_answer input exceeds _LEARNER_TEXT_CAP — grade unreliable")
        resp = self._parse_required(
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": rendered}],
            output_format=CheckableGrade,
            **_PARAMS,
        )
        return resp

    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict:
        detail = _target_detail(exp.rubric, kind, code)
        system = load_prompt("grade_sharper") + f"\n\nTarget angle: {detail}"
        # Task 6: `response` is the learner's own stress-probe reply -- literally the string
        # `classify_response` already routes through the seam, re-graded blind
        # (assessment/sharper_grader.py:24 passes `p.response`, the trajectory point
        # classify_response produced). Identical compose over identical data, so identical cap.
        # `push` is the engine's own generated angle, never learner text, and stays outside.
        user = f"Push:\n{push}\n\n" + _cap_rendered_turn(
            labelled("Student reply:", response), cap=_LEARNER_TEXT_CAP
        )
        resp = self._parse_required(
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=SharperVerdict,
            **_PARAMS,
        )
        return resp

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
        resp = self._parse_required(
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=PreferenceRating,
            **_PARAMS,
        )
        return resp

    def check_injection_expressed(self, injection: str, framed_output: str) -> InjectionExpressed:
        system = load_prompt("lift_manipulation") + f"\n\nThe move to check for:\n{injection}"
        resp = self._parse_required(
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"Output:\n{framed_output}"}],
            output_format=InjectionExpressed,
            **_PARAMS,
        )
        return resp

    def screen_moves(self, moves: list[str], text: str) -> EgressScreen:
        # Batched egress (the L-13 backstop): which of the hidden moves does `text` PERFORM, in ONE
        # call over the whole list, instead of one check_injection_expressed per move. The lift
        # harness keeps check_injection_expressed (high effort); this auditor runs at medium.
        #
        # Task 4 audit (web/voice.py): `text` is NOT exclusively learner text. Most callers pass a
        # Vera-AUTHORED reply -- concierge_turn/close/open/land/converse's `reply`, forge_scenario's
        # scenario (forge.py:369), concierge_sitting_close's close -- content already governed by a
        # model max_tokens budget, the same shape `_render_turns`' re-fed dialogue turns are. One
        # caller, voice.land's baseline check, DOES pass real learner text: `_student_text(recent)`,
        # every student turn in the session joined. Both need this L-13 backstop to see the text in
        # FULL or refuse outright, so `_TURN_RENDER_CAP` (the default, not the smaller
        # `_LEARNER_TEXT_CAP`) is a REFUSAL threshold here, never a trim point (boundary-4 Fix 1):
        # a move performed in a silently clipped tail can never land in `performed`, so
        # `egress_safe_reply` (`not _performed(...)`) returns True for text that leaks -- the exact
        # failure the truncation guard ten lines below already refuses on the output side.
        numbered = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(moves))
        rendered = labelled("Text to screen:", text)
        if len(rendered) > _TURN_RENDER_CAP:
            raise ModelError(
                "screen_moves input exceeds _TURN_RENDER_CAP — egress screen unreliable"
            )
        system = load_prompt("egress")
        user = f"Hidden moves:\n{numbered}\n\n{rendered}"
        resp = self._parse_required(
            max_tokens=_SCREEN_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=EgressScreen,
            **_MED_PARAMS,
        )
        # Fail LOUD on truncation: a cut-off parse could drop performed indices -> silent
        # false-negative (a leak passes), the one direction the backstop must never fail quietly.
        # The guarantee lives one layer up, not here: `_parse_required` returns `_require(resp)`,
        # which already raises ModelError on `stop_reason == "max_tokens"` before this method ever
        # sees a result. `resp` above is that parsed EgressScreen (only `performed`/`evidence`), not
        # the raw API response, so it carries no `stop_reason` attribute to check.
        return resp

    def map_territories(self, situation: str, territories: list[tuple[str, str]]) -> TerritoryMap:
        # The front-door mapper (living sitting §2a): ONE batched parse over every territory
        # candidate (L-20 — never one call per candidate), in screen_moves' shape. Server-side —
        # the reflection is learner-facing only AFTER the caller screens it (§2a's gated
        # reflection). The curated content is the territory DESCRIPTIONS (content/territories/,
        # L-1); this system text is structural task instruction only.
        numbered = "\n".join(
            f"{i + 1}. [{eid}] {desc}" for i, (eid, desc) in enumerate(territories)
        )
        system = (
            "You map a person's real situation onto the numbered territories below — each names "
            "a kind of decision. Return: `ranked` — every territory id, best fit first, ids "
            'exactly as given in brackets; `confidence` — "high" if the best territory\'s kind '
            'of decision is plainly the kind she is facing, else "low"; `verdict` — "decision" '
            "if she describes a decision, a dilemma, or a situation she must act in; "
            '"topic" if she instead asks a question, seeks advice, or names a subject of '
            "curiosity; `reflection` — ONE line reflecting what she is facing, in her own words "
            'wherever possible (on "topic", reflect the subject she raised). The reflection '
            "describes her situation only: never advice, never analysis vocabulary, never the "
            'territory text. `conversion` — empty unless verdict is "topic"; then ONE sentence '
            "that engages her subject in her own words, plus ONE question asking for the "
            "concrete call she faces inside that subject. The conversion never answers her "
            "question, never recommends, never names a territory, never judges the question, "
            "and never declares anything out of scope. "
            "`fit` — ALWAYS fill it: ONE noun phrase naming the sharpest decision the best-fit "
            'territory can press INSIDE her own situation, in her own words (e.g. "how you set '
            'your pricing tiers against a competitor already saturating your market"). It is the '
            "EDGE of HER subject, phrased as the thing she must decide — never the generic kind of "
            "decision, never the territory text, never advice, never analysis vocabulary, never a "
            'question. It reads naturally after "the sharpest pressure I can put on it: ".'
        )
        # Task 4: `situation` is her own words at this call's primary site (session_runner.py's
        # front door, the same string threaded into forge.build_brief -- see `_LEARNER_TEXT_CAP`'s
        # comment for why this reuses that cap). The second caller (`_capture_steer`) passes a
        # model-distilled `next_pressure` instead; the territories are curated content, never hers.
        user = (
            _cap_rendered_turn(labelled("Her situation:", situation), cap=_LEARNER_TEXT_CAP)
            + f"\n\nTerritories:\n{numbered}"
        )
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=TerritoryMap,
            **_MED_PARAMS,
        )
        return resp  # fails LOUD on truncation (L-17) and refusal

    def generate_frames(self, problem: str, exemplars: str) -> list[CandidateFrame]:
        # The frame-gen spike's one new call (L-1 doctrine in content/spike/frame_gen.md): candidate
        # decision-frames for a novel problem, seeded with curated exemplars. Structured, L-17.
        system = load_spike_prompt("frame_gen").replace("{exemplars}", exemplars)
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": f"The decision:\n{problem}"}],
            output_format=_FramesWire,
            **_PARAMS,
        )
        return list(resp.frames)

    def generate_scenarios(self, problem: str) -> list[str]:
        # Decision-scenario variants for the lift test (frame-gen spike). Structured, L-17.
        system = load_spike_prompt("frame_gen_scenarios")
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": f"The decision:\n{problem}"}],
            output_format=_ScenariosWire,
            **_PARAMS,
        )
        return list(resp.scenarios)

    def frame_convergence(
        self, frame_detail: str, curated: list[tuple[str, str]]
    ) -> ConvergenceCheck:
        # The novelty GATE (frame-gen spike): does this move restate a curated move? Move-to-move,
        # NOT situation-to-territory (map_territories' job) — the frame's detail against the curated
        # frames. Structured; a defined gate that sharpens as problems get more novel.
        numbered = "\n".join(f"{i + 1}. [{c}] {d}" for i, (c, d) in enumerate(curated))
        system = load_spike_prompt("frame_novelty")
        user = f"Candidate move:\n{frame_detail}\n\nExisting moves:\n{numbered}"
        return self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ConvergenceCheck,
            **_PARAMS,  # HIGH effort — the symmetric call is harder than the classifiers (spec §3C)
        )

    def forge_scenario(self, brief: str, steer: str = "") -> str:
        # Authors the scenario IN OPENING VOICE — it IS the opening say (§2b/M6: one generation,
        # one screen; no separate concierge_open pass on generated content). Doctrine lives in
        # content/prompts/forge_scenario.md (L-1); the brief arrives frame-blind and Vera-free
        # from the forge. `steer` is the one-shot regen reason (precondition / situation-structure
        # language only).
        system = load_prompt("forge_scenario")
        user = brief
        if steer:
            user += f"\n\nSteer (fix exactly this): {steer}"
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_FORGE_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""  # the forge's gates treat an empty scenario as a failed generation
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def fit_check(self, scenario: str, requirements: str) -> FitCheck:
        # The forge's reject-only fit gate (living sitting §2b): does the scenario give natural
        # occasion for the preconditions the rubric's meaning presumes? `requirements` is
        # precondition text assembled by the forge (frame-aware, SERVER-side — never learner-
        # facing). The reason must speak precondition/situation-structure language only — the
        # stimulus, never the move — because it becomes the regen steer.
        system = (
            "You check whether a scenario gives natural occasion for the requirements below — "
            "each names a precondition the situation itself must establish. Return `fits`, and "
            "when it does not fit, a `reason` naming which precondition the scenario fails to "
            "establish, in situation-structure language only (what the scenario lacks: a "
            "deadline, an undemonstrated capability, a live decision). Never describe how a "
            "person should respond; describe only what the situation must contain."
        )
        user = f"Scenario:\n{scenario}\n\nRequirements:\n{requirements}"
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=FitCheck,
            **_MED_PARAMS,
        )
        return resp  # fails LOUD on truncation (L-17) and refusal

    def concierge_sitting_close(
        self, situation: str, segments: list[list[tuple[str, str]]], voice: str = ""
    ) -> str:
        # The whole-sitting close (§2f): tells the world's story over every segment —
        # retrospective, no verdicts (L-4: correctness is deliberately NOT supplied). The caller
        # kind-filters the turns per segment and egress-screens the result against the union of
        # the sitting's territories' moves (static fallback on failure; the union scale is
        # measured per L-17/L-20 before trusting).
        system = (voice + "\n\n" if voice else "") + load_prompt("concierge_sitting_close")
        blocks = []
        for i, seg in enumerate(segments):
            # Task 6: a segment turn is the shape `_render_turns` guards -- the role prefix carries
            # the first line, `LEARNER_INDENT` every later one, then the RENDERED turn is capped.
            # Written out rather than calling `_render_turns`, which emits its own "Recent
            # exchange:" header and keeps only the trailing `limit` turns; the close tells the
            # story over EVERY landed turn (web/voice.py:106). Two copies of this expression, not
            # three -- extract on the third.
            lines = "\n".join(
                _cap_rendered_turn(indent_after_first(text, f"{role}: ", LEARNER_INDENT))
                for role, text in seg
            )
            blocks.append(f"Segment {i + 1}:\n{lines}")
        # `situation` is her own words: the same string `map_territories` caps, arriving by the same
        # route (web/voice.py:119 is handed the sitting's situation, which session_runner also
        # threads into forge.build_brief), so it takes the same `_LEARNER_TEXT_CAP`. The per-turn
        # cap above is the larger `_TURN_RENDER_CAP` for `_render_turns`' reason: a segment turn can
        # be one of Vera's own completions fed back in. Neither cap bounds the NUMBER of turns --
        # no code constant limits it here, unlike `_render_turns`' `limit`; it is bounded by how
        # long the sitting ran, which no single learner message can inflate.
        user = (
            _cap_rendered_turn(labelled("Her situation:", situation), cap=_LEARNER_TEXT_CAP)
            + "\n\n"
            + "\n\n".join(blocks)
            + "\n\nTell the sitting's story."
        )
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=_FORGE_MAX_TOKENS,
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
