from __future__ import annotations

import logging
import unicodedata
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from .content_loader import load_prompt, load_spike_prompt
from .prompt_text import LEARNER_INDENT, bulleted, indent_after_first, labelled
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

_log = logging.getLogger("elenchus.model")


class ModelError(RuntimeError):
    """Raised when the rented model refuses or returns no usable output."""


class IntakeClassification(BaseModel):
    frame_states: dict[str, FrameState]
    trap_states: dict[str, TrapState]


class ResponseClassification(BaseModel):
    outcome: Literal["closed", "unchanged", "regressed"]
    mechanism_supplied: bool
    hard_wrong: bool
    # T2 CHANGE 2 (evidence anchor): the verbatim span of `response` the grader claims states the
    # causal why. `classify_response` checks it against `response` itself immediately after
    # parsing and floors `mechanism_supplied` to False when the claim has no supporting span --
    # see that function's own comment. Empty by default: most replies never claim a mechanism.
    mechanism_span: str = ""


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


_TURN_RENDER_CAP = 40000  # characters, measured on the RENDERED turn (after indent_after_first),
# not the raw text handed in. judgment_loop._POSITION_CAP's own comment records that a cap
# measured before render does not bound what comes out: a newline-heavy raw text can render to
# several times its own length once every continuation line gets its own LEARNER_INDENT prefix.
# Capping the rendered string directly sidesteps that arithmetic: the bound holds regardless of
# how the raw turn is shaped -- one enormous line, thousands of empty ones, anything between.
#
# Raised from 6000 to 40000 (boundary-6 review): `screen_moves` (~150 lines below) reuses this
# same constant as a REFUSAL threshold, not a trim point -- it raises ModelError instead of
# composing when the rendered text it is asked to screen exceeds the cap (boundary-4 Fix 1). 6000
# was carried over from `_render_turns`' trim point, itself derived from `_ECHO_MAX_TOKENS = 1024`
# -- the budget for concierge_turn/close/open/land, the routine per-turn Vera author. But that is
# the WRONG producer for `screen_moves`: its widest callers are `voice.close`/`voice.sitting_close`
# screening `concierge_sitting_close`'s close and `forge.forge_experience` screening
# `forge_scenario`'s scenario, both under `_FORGE_MAX_TOKENS = 4096` (model.py:303), and
# `voice.converse` screening `concierge_converse`'s reply, under `_CLASSIFY_MAX_TOKENS = 4096`
# (model.py:290) -- but `concierge_converse` rides `_parse_required` (model.py:579-595), which
# doubles the budget to 8192 on a single truncation retry before it fails loud, so a real
# (non-raising) `reply` can legitimately reach that doubled ceiling. 8192 is therefore the largest
# token budget any producer that legitimately reaches `screen_moves` can spend: by the same ~4
# characters-per-output-token approximation this comment already uses (ASSUMED, falsified by any
# real rendered turn this repo observes exceeding it) -- 8192 * 4 = 32768 characters
# (`python3 -c "print(8192*4)"`). The old 6000 sat 26768 characters BELOW that ceiling, so it could
# refuse a real, doctrine-compliant completion the engine itself produced. The OTHER caller that
# reaches this same threshold carries real, unbounded learner text rather than a token-bounded
# completion: `voice.land`'s `_student_text(recent)` baseline, every student turn in the session
# joined -- see that function's own comment; an ordinary rigorous session can grow that join past
# any fixed cap, which is why `voice.land` must degrade to its static fallback on a genuine
# ModelError here rather than assume the cap alone is enough (boundary-6 Fix 1). 40000 sits above
# the 32768 producer ceiling with 7232 characters of headroom
# (`python3 -c "print(40000-32768)"`) for the render overhead (`labelled` adds a fixed 20
# characters plus 4 per line the text contains --
# `python3 -c "from elenchus.prompt_text import labelled; print(len(labelled('Text to screen:', '')))"`
# prints 20) and for ordinary paragraph structure -- the same style of margin the old 6000 kept
# over ITS OWN floor of 4096 (`_ECHO_MAX_TOKENS * 4`).
#
# This also closes a second gap the same review caught: `forge._MAX_LEN = 6000` gates the RAW
# scenario `forge_experience` will serve, but `screen_moves` measures the RENDERED one (always at
# least 20 characters longer, +4 per line) -- at the old 6000 cap a scenario forge would happily
# serve as servable could still get refused by the screen measuring a few characters more. A raw
# scenario at forge's own ceiling now renders to at most 6000 + 20 + 4*(its own line count)
# characters, nowhere near 40000, so every scenario forge can serve clears `screen_moves` with
# room to spare -- tests/test_anthropic_model.py pins this against both constants directly, not by
# proximity.
#
# `_ECHO_MAX_TOKENS = 1024` (model.py:282, `grep -n "_ECHO_MAX_TOKENS = " model.py`) still bounds
# concierge_turn/close/open/land at 1024 * 4 = 4096 characters (`python3 -c "print(1024*4)"`),
# comfortably inside the new cap too. Doctrine, not this constant, is what keeps every
# Vera-authored turn short -- 40000 is not a hard guarantee against any call's full token ceiling,
# but no cap short of the producers' own doubled ceiling would be, and the old 6000 was not one
# either (the mistake this raise fixes, one function over from the raise that fixed it for
# `_render_turns` the first time).
#
# Worst-case block size for the wind-down callers (limit=20: concierge_land, concierge_converse):
# 40000 * 20 = 800,000 characters (`python3 -c "print(40000*20)"`), plus the fixed "Recent
# exchange:" header and the role-prefix overhead. (See the GENERAL RULE below, at the site where
# `_LEARNER_TEXT_CAP` used to be defined -- this cap paid for the same lesson twice, 2000 -> 6000
# -> 40000, before that constant repeated the mistake a third time, one function over.)

# Task 4 (graded/routing sites: classify_response, classify_entry, map_territories; task 6 added
# grade_sharper and concierge_sitting_close's situation blob -- NOT its per-turn text, which takes
# `_TURN_RENDER_CAP` like every other dialogue turn): text typed directly by a person, never
# something the model wrote back. Unlike `_TURN_RENDER_CAP`, none of this has a model max_tokens
# ceiling it has to clear -- the concern that forced `_TURN_RENDER_CAP` up from 2000 to 6000 was
# Vera's OWN turns being re-fed through `recent` and re-rendered (session_runner.py appends a
# probe/re-invite/converse reply, then passes it back through `_render_turns` on the next call);
# nothing re-feeds a model completion back through any of these sites.
#
# GENERAL RULE (boundary-6 Fix 3, the third time this exact shape has bitten on this branch --
# `_TURN_RENDER_CAP` above paid for it twice, 2000 -> 6000 -> 40000, before the single
# `_LEARNER_TEXT_CAP` this comment used to define repeated the mistake one function over, at a
# threshold roughly 350 words wide): a threshold that FAILS LOUD must clear the ORDINARY
# distribution of the text it gates, not merely the pathological one. A refusal is not a speed
# bump -- it is a dead segment for whoever typed the median-to-thorough input that tripped it, so
# size a raise against the realistic maximum a real producer emits, WITH headroom, and only THEN
# confirm it still refuses the pathological case. Sizing it against the pathological case first
# and calling the gap "margin" is the mistake, because the ordinary case was never checked against
# it at all. A threshold that only TRIMS is a different problem: trimming degrades the prompt's
# context, it does not end the session, so it may sit closer to the ordinary distribution than a
# raise ever safely can. When one constant is asked to do both jobs, as `_LEARNER_TEXT_CAP` used
# to, split it and size each half against what it actually costs to be wrong -- do not average the
# two costs into one number that is too small for the raise and unnecessarily tight for the trim.
#
# `_LEARNER_TEXT_REFUSAL_CAP` gates `classify_response` and `grade_answer`, which RAISE rather
# than trim (see each function's own comment: a silently clipped tail can turn a real
# closure/correct answer into a false negative, corrupting durable `FrameState`/`correct` --
# worse than a formatting nit). Measured, not guessed: `tests/test_anthropic_model.py`'s
# `_ORDINARY_REPLY` fixture is real prose reasoning through a licensing decision, not a synthetic
# filler string -- `PYTHONPATH=src .venv/bin/python3 -c "import sys; sys.path.insert(0, 'tests');
# from test_anthropic_model import _ORDINARY_REPLY as t; print(len(t), len(t.split()))"` prints
# `2476 422`: 422 words of ordinary, thorough reasoning render to 2476 characters, ~5.87
# characters per word (`python3 -c "print(2476/422)"`). ASSUMED (falsified by any real reply this
# repo observes exceeding it): a genuinely maximal single typed reply -- the kind of exhaustive,
# multi-paragraph answer an unusually thorough but real learner might compose in one sitting --
# runs to roughly 1500 words, which at the same measured ratio is ~8801 characters
# (`python3 -c "print(1500*2476/422)"`). `_LEARNER_TEXT_REFUSAL_CAP = 20000` sits 11199 characters
# above that assumed ceiling (`python3 -c "print(20000-1500*2476/422)"`) -- more than double it
# (`python3 -c "print(20000/(1500*2476/422))"` prints ~2.27) -- and tolerates a reply of ~3409
# words before refusing (`python3 -c "print(20000*422/2476)"`), eight times the length of the
# measured thorough fixture. The pathological fixtures this suite already exercises against these
# sites (`"\n" * 50_000`, `"x" * (cap * 2)`) sit far on the other side of that gap and still raise.
_LEARNER_TEXT_REFUSAL_CAP = 20000

# `_LEARNER_TEXT_TRIM_CAP` gates the sites where a clipped tail costs only degraded context, never
# a dead segment, so it may sit closer to the ordinary distribution than a raise safely could:
# `classify_entry`'s door opening, and `map_territories`/`concierge_sitting_close`'s `situation`
# blob, which mirrors `forge.build_brief`'s `_BRIEF_BLOB_CAP` (forge.py:101) over the identical
# KIND of text -- and for `map_territories`/`concierge_sitting_close`, the identical DATA: both
# are handed the same `situation` string session_runner.py already threads into `build_brief`, so
# capping it at the same number here matches an existing precedent for this data, not inventing a
# new one. (map_territories' other caller, `_capture_steer`, passes `next_pressure` instead -- a
# model-DISTILLED value, per its own field doc in types.ConverseTurn "a distilled fresh decision"
# whose "label echoes her raw words" -- i.e. a short phrase, not a full authored reply, so it
# carries none of the re-fed-turn concern either; ASSUMED short based on that doc, not measured,
# since no offline path produces one.) 2000 stays generous against a real typed message on its own
# terms and is UNCHANGED by this split -- the problem the split above fixes was never these sites;
# a trimmed opening or situation blob degrades context, it does not corrupt a grade or kill a
# sitting.
#
# `grade_sharper` is the one exception that looks like a trim site but is NOT governed by this
# constant: it re-grades the SAME string `classify_response` already routed through the raise gate
# above (assessment/sharper_grader.py:24 passes `p.response`, the trajectory point
# `classify_response` produced), so it takes `_LEARNER_TEXT_REFUSAL_CAP` instead, even though it
# only trims (see its own comment). If it used this smaller trim cap, a reply between 2000 and
# 20000 characters -- one `classify_response` composed in FULL because it cleared the raise gate --
# would arrive at the blind sharper audit silently shortened, so the instructor and the auditor
# would grade different bytes of the same reply, breaking the audit property `grade_answer`'s own
# comment (~230 lines below) names explicitly. Matching the cap makes the trim a no-op for every
# reply `classify_response` ever admits: identical compose over identical data needs an identical
# bound, not merely an identical-looking one.
_LEARNER_TEXT_TRIM_CAP = 2000


def _cap_rendered_turn(rendered: str, cap: int = _TURN_RENDER_CAP) -> str:
    """Truncate an already-rendered blob at `cap` characters (default `_TURN_RENDER_CAP`),
    marking the elision.

    Applied AFTER `indent_after_first`/`labelled`, never before -- the fix for the mistake
    `judgment_loop._POSITION_CAP` documents in its own comment, where the cap bounded the text
    handed TO the renderer rather than the string that came OUT of it. Slicing the rendered
    string can only shorten an existing line or drop a trailing one; it can never introduce a new
    line, so it cannot undo the indent discipline that keeps a learner byte off column 0.

    Originally turn-specific (`_render_turns`' per-turn cap, the only caller until task 4); the
    `cap` parameter generalises it for the graded/routing sites, some of which pass
    `_LEARNER_TEXT_TRIM_CAP` or `_LEARNER_TEXT_REFUSAL_CAP` instead of the default -- see each
    constant's own comment for which site uses which and why."""
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


# T2 REVIEW FIX: the confusable-punctuation classes `_normalize_for_span_match` folds before the
# evidence-anchor substring check in `classify_response` and `grade_sharper` below. None of these
# decompose under Unicode NFKC (they are canonical codepoints in their own right, not compatibility
# forms of their ASCII look-alikes), which is why NFKC alone does not close this gap and an
# explicit translate table is required on top of it.
_CONFUSABLE_PUNCTUATION = str.maketrans(
    {
        "‘": "'",  # LEFT SINGLE QUOTATION MARK
        "’": "'",  # RIGHT SINGLE QUOTATION MARK -- the one an iOS keyboard emits for "can't"
        "ʼ": "'",  # MODIFIER LETTER APOSTROPHE
        "“": '"',  # LEFT DOUBLE QUOTATION MARK
        "”": '"',  # RIGHT DOUBLE QUOTATION MARK
        "‐": "-",  # HYPHEN
        "‑": "-",  # NON-BREAKING HYPHEN
        "‒": "-",  # FIGURE DASH
        "–": "-",  # EN DASH
        "—": "-",  # EM DASH
        "―": "-",  # HORIZONTAL BAR
        "…": "...",  # HORIZONTAL ELLIPSIS
    }
)


def _normalize_for_span_match(text: str) -> str:
    """Fold cosmetic differences a learner's own keyboard/OS, or a model's own JSON encoder,
    introduces before testing a claimed span as a substring of the reply it is supposed to quote
    (`classify_response`'s and `grade_sharper`'s evidence-anchor checks, both below share this).

    In order: Unicode NFKC (compatibility forms -- full-width variants, ligatures, and the like);
    then `_CONFUSABLE_PUNCTUATION` (curly quotes/apostrophes, the non-ASCII dash forms, the
    ellipsis glyph -- see that table's own comment for why NFKC does not already cover these);
    then whitespace runs collapsed to one space and both sides stripped; then casefolded.

    Casefolding is safe here specifically because this backs a SUBSTRING test, never an equality
    test on arbitrary content: two spans differing only in case are the same words, and casefolding
    two DIFFERENT words can never make them match -- it only ever merges case-variants of one
    identical word. (T2 REVIEW FIX: an earlier version of the comment at both call sites below
    claimed casefolding was unsafe here and left it out; that claim was wrong and is corrected at
    each site.)

    T2 REVIEW FIX: before this function existed, both call sites only collapsed whitespace, which
    floors a genuine, verbatim closure on ordinary punctuation a learner does not choose the
    encoding of -- an iOS contraction's curly apostrophe against a model-authored ASCII one (a
    model emitting JSON writes ASCII), a typed em dash against a hyphen, curly quotes against
    straight ones, or a model requoting a mid-sentence span with a capitalized first letter. That
    fires on ordinary typing, not on an attacker; see each call site's own comment for what a
    failed match costs there -- the two sites now differ."""
    folded = unicodedata.normalize("NFKC", text).translate(_CONFUSABLE_PUNCTUATION)
    return " ".join(folded.split()).casefold()


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
        1 refusal). A deterministic refusal still fails loud on the second strike.

        A truncation does not always surface as a clean `resp` with `stop_reason == "max_tokens"`:
        the SDK parses the structured output INSIDE `client.messages.parse` itself
        (`TypeAdapter.validate_json` in anthropic's `lib/_parse/_response.py`), so a completion
        that truncates mid-JSON — the common shape, not the rare one — raises
        `pydantic.ValidationError` out of that call before this method ever gets a `resp` object
        to inspect. Live (prompt_shift_probe arm C, `_parse_required` reached directly):

            pydantic_core._pydantic_core.ValidationError: 1 validation error for TerritoryMap
              Invalid JSON: EOF while parsing a string at line 1 column 8036
              input_value='{"ranked":["decision_und...he.The.The.The.The.The.'

        a repetition-loop truncation that hit the cap mid-string. Caught here as the SAME signal
        `stop_reason == "max_tokens"` already is, and spends the SAME single budget-doubled retry
        — never a second one — because a completion that breaks JSON syntax on the way out is a
        truncation whether or not the API also flags it. Caught narrowly: only
        `pydantic.ValidationError` (identically `pydantic_core.ValidationError` — pydantic
        re-exports the same class), never a bare `Exception`, so a transport failure, an auth
        error, or a rate limit still propagates unchanged instead of being mistaken for a
        truncation. If the doubled-budget retry ALSO fails to parse, that raises its own
        `ModelError` naming the budget it failed at — distinguishable from both a refusal and a
        clean (parseable-but-flagged) truncation, the two `_require` already names below."""
        client = self._get_client()
        try:
            resp = client.messages.parse(model=self._model, max_tokens=max_tokens, **kwargs)
        except ValidationError:
            resp = None  # parse-time truncation: the same signal as stop_reason == "max_tokens"
        if resp is None or getattr(resp, "stop_reason", None) == "max_tokens":
            doubled_budget = max_tokens * 2
            try:
                resp = client.messages.parse(model=self._model, max_tokens=doubled_budget, **kwargs)
            except ValidationError as exc:
                raise ModelError(
                    "structured output could not be parsed even at the doubled budget "
                    f"({doubled_budget}) — distinct from a refusal and from a clean truncation "
                    "(L-17)"
                ) from exc
        elif getattr(resp, "stop_reason", None) == "refusal" or resp.parsed_output is None:
            resp = client.messages.parse(model=self._model, max_tokens=max_tokens, **kwargs)
        return _require(resp)  # the single retry is spent; both classes now fail LOUD

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        system = load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)
        # boundary-7 Fix 1: `opening` is the learner's own text -- the boundary seam -- and used to
        # reach here byte-identical, unindented, and unbounded (a 100,000-character opening reached
        # the wire at full length). Routed through `labelled`/`_cap_rendered_turn` like every other
        # sealed site, taking `_LEARNER_TEXT_TRIM_CAP` rather than `_LEARNER_TEXT_REFUSAL_CAP`.
        #
        # This result seeds `frame_states`/`trap_states` for the WHOLE judgment loop
        # (assessment/judgment_loop.py:186-188) -- durable-looking output, the same class as
        # `classify_response`'s `ResponseClassification`, which argues for the REFUSAL cap. But the
        # two are not equivalent, and the difference is structural, not just timing: `assess`
        # initialises both dicts to the FLOOR (`FrameState.absent`/`TrapState.not_tripped`,
        # judgment_loop.py:187-188) BEFORE this call ever runs, so a trimmed opening can only
        # UNDER-report a frame the learner did engage -- evidence trimmed off the tail never reaches
        # the model, so at worst a present frame reads as absent. It can never REGRESS an
        # already-`present_reasoned` state the way a trimmed `classify_response` reply can
        # (classify_response's own comment, ~90 lines below), because at this point in the loop
        # there is nothing yet to regress. An under-reported frame is not a lost verdict either:
        # `_select_target`/`_converged` (judgment_loop.py:147-182) simply probe it again during the
        # loop's ordinary operation, spending a push, not corrupting a grade -- the same self-healing
        # `classify_entry`'s own trim on its "opening" field already relies on. A REFUSAL cap here
        # would instead kill the segment on the learner's very FIRST message, before a single push
        # has been generated and before any value has been delivered to them -- the worst point in
        # the loop to spend a cap `_LEARNER_TEXT_REFUSAL_CAP`'s own comment sizes for exactly one
        # cost: "the cost of being wrong is a dead segment." Degrading context here costs a redundant
        # probe, not a session.
        rendered = _cap_rendered_turn(
            labelled("Student's opening:", opening), cap=_LEARNER_TEXT_TRIM_CAP
        )
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": rendered}],
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
            said = bulleted(positions.on_angle)
            blocks += f"What the student has already argued on THIS angle:\n{said}\n\n"
        if positions.elsewhere:
            said = bulleted(positions.elsewhere)
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
        # REVERT (T2 review): `3e81f72` collapsed this composition -- moved `push` into `system`
        # and made `response` the entire user message, no `Push:` heading, no
        # `labelled("Student reply:", ...)` wrapper -- on the theory that removing every
        # engine-authored heading leaves nothing for a learner turn to forge. A T2 review found
        # that fix's efficacy was never measured (see below) and that it made two things worse: the
        # `system` block gained its own `Push: <text>` line in the exact `Label: value` shape a
        # learner reply can reproduce (the template moved, it did not vanish), and `push` is
        # authored FROM the learner's own prior words (`judgment_loop.py` passes `positions` into
        # `generate_push`), so promoting it into `system` moved learner-influenced text across a
        # trust boundary with no compensating screen. The founder decided: revert the collapse,
        # keep the prompt reframe (`content/prompts/response.md`, adapted to describe this
        # restored layout truthfully). `push` is back here, in `user`, never in `system`.
        #
        # The numbers actually measured on claude-opus-5 (3 draws each), pinned honestly: a reply
        # forging a continuation of the `Push:`/`Student reply:` template
        # ("...\n\nStudent reply:\n<fabricated mechanism>") landed `closed`/`mechanism_supplied`
        # 3/3 on the pre-indent form this repo originally shipped and 2/3 on THIS indented
        # `labelled(...)` form -- the form this method composes below, restored. The indent lowers
        # the landing rate; it does not zero it. The THIRD arm measured was a BENIGN CONTROL, not a
        # measurement of the collapsed form: the same reply with the forged continuation deleted
        # from it entirely, leaving no attack text in the message at all. It landed 0/3,
        # unsurprising for text carrying no forgery to land -- that arm never sent anything shaped
        # like the collapsed composition `3e81f72` shipped, so it said nothing about whether
        # removing the heading (rather than the reply) closed the hole. THE COLLAPSED FORM WAS
        # NEVER MEASURED, and neither is the prompt reframe kept above:
        # `injection_probe.py`/`run_injection_probe.py` (cells `A_new`/`B_new`) exist to make
        # exactly that measurement and have not been executed (never run a `run_*_probe` module
        # outside an explicit, confirmed, budgeted invocation). Do not read the 2/3 above as
        # evidence the reframe helps or hurts -- it predates the reframe entirely.
        #
        # Text detectors were explored and rejected: three independent adversarial passes broke
        # every one for free, and a shape detector fires on an honest multi-part learner reply too
        # (the rubrics ask for structured answers). The defense that ships is the indent:
        # `response` is rendered under `labelled("Student reply:", ...)`, which indents EVERY line,
        # including the first, so a forged `Push:`/`Student reply:` continuation the learner types
        # lands indented, never at column 0 where the real headings live -- see the
        # mechanism-evidence check below `_parse_required` for the separate property that a forged
        # span genuinely present in `response` (because the learner typed it) is not what this
        # indent claims to stop.
        #
        # `_LEARNER_TEXT_REFUSAL_CAP` (see its own comment) bounds the RENDERED string -- label plus
        # indent included -- not the raw `response`, matching every other `labelled(...)` raise site
        # in this module.
        #
        # boundary-6 Fix 2 (unchanged by the above): the cap is a REFUSAL threshold here, never a
        # trim point, matching `grade_answer` (~160 lines below) rather than the silent
        # `_cap_rendered_turn` this used to call. `grade_answer`'s own comment argues the raise is
        # required because a silently clipped tail that carried what `criteria` asks for turns a
        # correct answer into `correct=False` -- a wrong grade wearing a checkmark. That argument
        # applies verbatim here: `outcome`/`mechanism_supplied` are read in
        # `assessment/judgment_loop.py` (line ~317) to set `FrameState.present_reasoned`, lower a
        # frame state on regression, and decide whether the loop stops -- durable learner state,
        # exactly like a grade. A reply silently clipped past the mechanism the target angle asks
        # for could turn a real closure into a false "not closed" (or worse, a false "regressed"),
        # corrupting `FrameState` the same way a clipped answer corrupts a checkable grade. Fail
        # loud instead: raise before composing, never trim. The raise propagates out of
        # `judgment_loop.assess` uncaught (nothing there is persisted mid-loop --
        # `orchestration.run_session`'s `store.save_state` runs only AFTER `assess` returns), so no
        # state is banked for this experience; it surfaces at the same worker-level catch
        # `web/session_runner.py`'s `except Exception:` already uses for every other critical-call
        # failure (`classify_intake`, `generate_push`, and -- via `checkable_scorer.score_question`
        # -- this exact `grade_answer` raise on the cs_technical side), which logs the traceback
        # server-side and emits the honest, actionable `_DOOR_FAILED_NUDGE` ("refresh to pick up
        # where you left off") rather than crashing or silently corrupting the ledger. Degrades,
        # does not dead-end.
        rendered = labelled("Student reply:", response)
        if len(rendered) > _LEARNER_TEXT_REFUSAL_CAP:
            raise ModelError(
                "classify_response input exceeds _LEARNER_TEXT_REFUSAL_CAP — classification "
                "unreliable"
            )
        user = f"Push:\n{push}\n\n{rendered}"
        resp = self._parse_required(
            max_tokens=_CLASSIFY_MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ResponseClassification,
            **_PARAMS,
        )
        # T2 CHANGE 2 (evidence anchor): a DIFFERENT hole than CHANGE 1 above closes. CHANGE 1
        # removes the forgeable template; it does NOT stop a forged span that is genuinely a
        # substring of `response`, because the learner typed it. This closes a grader asserting
        # `mechanism_supplied=True` with no supporting span in the reply AT ALL -- the model
        # claiming a mechanism where none exists in the text. Normalized via
        # `_normalize_for_span_match` (its own docstring has the fold rules) before the substring
        # test, on BOTH sides.
        #
        # T2 REVIEW FIX: the check used to only collapse whitespace, which floors an honest
        # closure on ordinary punctuation a learner never controls the encoding of -- an iOS
        # contraction's curly apostrophe against a model's ASCII one, a typed em dash against a
        # hyphen, curly quotes against straight ones, a requoted span with a capitalized first
        # letter. That is ordinary typing, not an attacker, and it fired on it. `casefold()` IS
        # correct here (an earlier version of this comment claimed the opposite and was wrong):
        # this backs a SUBSTRING test, never an equality test on arbitrary content, so two spans
        # differing only in case are the same words -- casefolding two DIFFERENT words can never
        # make them match, it only ever merges case-variants of one identical word.
        #
        # FLOOR, never raise. `assessment/judgment_loop.py` raises the frame state and repairs a
        # trap only on `outcome == "closed" AND mechanism_supplied`, so the floor withholds both,
        # and `outcome` is left untouched -- the reply lands in the same shape the loop already
        # handles for an honest "no mechanism" classification.
        #
        # CORRECTION: an earlier version of this comment concluded from that one call site that
        # "flooring `mechanism_supplied` alone is sufficient". It was not, and the tree
        # contradicted it. `state.update_state` re-derived "this trap was repaired" from
        # `response_classification` -- which is this untouched `outcome` -- so a floored
        # `mechanism_supplied` still left `"closed"` on the trajectory point and deleted the
        # trap's durable gallery row. The floor is sufficient now because the loop's own credit
        # decision rides out on `types.Push.gap_closed` and `state.update_state` reads that
        # instead; it was never sufficient by itself. Anything downstream that keys off a bare
        # `outcome == "closed"` reopens this hole -- grep `gap_closed` before adding one.
        # Raising instead would
        # kill the door mid-sitting over a field-level evidence gap: state is already banked by
        # the time this runs (nothing in `judgment_loop.assess` persists mid-loop --
        # `orchestration.run_session`'s `store.save_state` runs only after `assess` returns), so
        # unwinding here would split the commit between the engine state and the sitting record --
        # the same split-commit failure `web/voice.py`'s `_STATIC_LAND` reasoning already fails
        # closed against rather than raises through. This floor is UNCHANGED by the T2 review fix
        # (only the normalization feeding it improved): it only withholds a state RAISE, which
        # stays conservative -- unlike `grade_sharper`'s analogous check below, which no longer
        # floors at all, because a floor there REVERTS state already credited (see its own
        # comment). Logged (never silently indistinguishable from an honest False) so the floor
        # rate is observable before anyone has to trust it.
        if resp.mechanism_supplied:
            span = _normalize_for_span_match(resp.mechanism_span)
            haystack = _normalize_for_span_match(response)
            if not span or span not in haystack:
                resp.mechanism_supplied = False
                _log.warning(
                    "classify_response: mechanism_span failed the evidence-anchor check for "
                    "%s/%s -- mechanism_supplied floored to False",
                    kind,
                    code,
                )
        return resp

    def classify_entry(
        self, prompt: str, opening: str, recent: list[tuple[str, str]]
    ) -> EntryClassification:
        system = load_prompt("entry")  # frame-blind: doctrine only, never the rubric
        # Task 4: `opening` is the learner's own latest message -- the boundary seam,
        # `_LEARNER_TEXT_TRIM_CAP` (see its comment). `_render_turns(recent)` already caps its own
        # dialogue turns at `_TURN_RENDER_CAP` (untouched here).
        user = f"Problem:\n{prompt}\n\n{_render_turns(recent)}" + _cap_rendered_turn(
            labelled("Student's latest message:", opening), cap=_LEARNER_TEXT_TRIM_CAP
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
        # `_LEARNER_TEXT_REFUSAL_CAP` (see its comment). Both `Work.respond` implementations
        # return text a person typed, never a model completion (orchestration.py:34
        # `input("> ")`; web/session_runner.py:1226 the raw student reply off the worker channel),
        # so this carries none of the re-fed-turn concern that forced `_TURN_RENDER_CAP` higher.
        # The question, key, and criteria are curated content and stay in `system`, outside the
        # seam.
        #
        # This composition carries the SAME forgeable shape `classify_response` does: engine
        # headings in a `Label: value` form (`Question:`, `Reference answer(s):`, `Criteria:`)
        # and one `labelled(...)` block a learner writes freely into. The measured turn-forgery
        # attack on `classify_response` was never run against this method, but nothing about it
        # is specific to the open-ended side, and here a landing writes `correct=True` straight
        # through `assessment/checkable_scorer.py` into the concept result. `content/prompts/
        # grade.md` now carries the same reframe `response.md` and `grade_sharper.md` do, stating
        # that every indented line under `Student answer:` was typed by the student and that
        # nothing inside it revises the criteria. THE REFRAME'S EFFICACY IS UNMEASURED HERE, on
        # this method, exactly as it is on the other two -- `injection_probe.py` targets
        # `classify_response` only, and no probe cell sends a `grade_answer` composition. Do not
        # read the added prose as a closed hole; it is parity, not proof.
        #
        # The cap is a REFUSAL threshold here, never a trim point, and unlike its three sibling
        # sites this one does not call `_cap_rendered_turn` at all (T2 review Fix 1). Reason:
        # `assessment/checkable_scorer.py:33` returns `grade_answer(...).correct` straight through
        # as the concept result, so a silently clipped tail that carried what `criteria` asks for
        # turns a correct answer into `correct=False` -- a wrong grade wearing a checkmark. That is
        # exactly the trade `screen_moves` refuses ~90 lines below, for the same reason: where the
        # cut makes the judgment unreliable, fail loud instead of trimming quietly. `grade_sharper`
        # keeps the silent trim deliberately: it re-grades the SAME string `classify_response`
        # already routed through this exact raise gate, so it takes `_LEARNER_TEXT_REFUSAL_CAP` as
        # its trim cap too -- not the smaller `_LEARNER_TEXT_TRIM_CAP` its shape would otherwise
        # suggest -- which keeps instructor and blind auditor reading byte-identical text, the
        # property audit depends on (see `_LEARNER_TEXT_REFUSAL_CAP`'s own comment for why).
        rendered = labelled("Student answer:", answer)
        if len(rendered) > _LEARNER_TEXT_REFUSAL_CAP:
            raise ModelError(
                "grade_answer input exceeds _LEARNER_TEXT_REFUSAL_CAP — grade unreliable"
            )
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
        # REVERT (T2 review, same restoration as `classify_response` above -- see its own comment
        # for the measured numbers, why a text detector was rejected, and why the founder chose to
        # revert `3e81f72`'s collapse rather than keep it): `push` is back in `user`, never in
        # `system`. `response` is the learner's own stress-probe reply -- literally the string
        # `classify_response` already routes through the seam, re-graded blind
        # (assessment/sharper_grader.py:24 passes `p.response`, the trajectory point
        # `classify_response` produced). Identical compose over identical data, so identical cap:
        # `_LEARNER_TEXT_REFUSAL_CAP`, not `_LEARNER_TEXT_TRIM_CAP` -- see that constant's own
        # comment for why this trim site is the one exception. `push` is the engine's own generated
        # angle, never learner text, and stays outside the seam.
        user = f"Push:\n{push}\n\n" + _cap_rendered_turn(
            labelled("Student reply:", response), cap=_LEARNER_TEXT_REFUSAL_CAP
        )
        resp = self._parse_required(
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=SharperVerdict,
            **_PARAMS,
        )
        # T2 CHANGE 2 (evidence anchor): the blind audit's analog of `classify_response`'s check
        # above -- SAME normalization (`_normalize_for_span_match`), DIFFERENT consequence on
        # failure, corrected by the T2 review fix. `assessment/sharper_grader.audit_sharper` reads
        # `sharper` to decide whether an INSTRUCTOR'S ALREADY-CREDITED closure survives the blind
        # audit: `sharper=False` drops the code from `frames_closed_under_pressure` and reverts its
        # `FrameDelta` (sharper_grader.py:35-38). Flooring `sharper` here on a span-match failure
        # alone used to do exactly that over an ordinary punctuation difference -- a learner's
        # curly apostrophe, a typed em dash, a requoted capital -- REVERTING credit the instructor
        # already gave for typing, not for an attack. That is a strictly worse failure than missing
        # a fabricated span: this repo's own rule (`web/voice.py:49-53`, boundary-6 Fix 1) is that
        # a check which cannot run means "not safe," routing to an existing fallback, never "kill
        # the segment" -- and the existing fallback here is the instructor's own credited verdict,
        # already banked before this audit ever runs. So `sharper` is left EXACTLY as the
        # model returned it (the auditor's actual judgment, never floored by this check), and the
        # span failure is recorded separately on `span_unverified` -- purely for observability;
        # `sharper_grader.audit_sharper` copies it onto `SharperAuditItem` and never treats a
        # span-only failure as a dispute. `classify_response`'s analogous floor above is UNCHANGED:
        # it only withholds a state RAISE (conservative), never reverts one already banked, so it
        # keeps flooring on the same failure this method now refuses to.
        if resp.sharper:
            span = _normalize_for_span_match(resp.mechanism_span)
            haystack = _normalize_for_span_match(response)
            if not span or span not in haystack:
                resp.span_unverified = True
                _log.warning(
                    "grade_sharper: mechanism_span failed the evidence-anchor check for %s/%s -- "
                    "sharper left at %s, span_unverified set (not disputed)",
                    kind,
                    code,
                    resp.sharper,
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
        # `_LEARNER_TEXT_REFUSAL_CAP`/`_LEARNER_TEXT_TRIM_CAP`) is a REFUSAL threshold here, never
        # a trim point (boundary-4 Fix 1):
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
        # front door, the same string threaded into forge.build_brief -- see
        # `_LEARNER_TEXT_TRIM_CAP`'s comment for why this reuses that cap). The second caller
        # (`_capture_steer`) passes a model-distilled `next_pressure` instead; the territories are
        # curated content, never hers.
        user = (
            _cap_rendered_turn(labelled("Her situation:", situation), cap=_LEARNER_TEXT_TRIM_CAP)
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
        # threads into forge.build_brief), so it takes the same `_LEARNER_TEXT_TRIM_CAP`. The
        # per-turn cap above is the larger `_TURN_RENDER_CAP` for `_render_turns`' reason: a
        # segment turn can be one of Vera's own completions fed back in. Neither cap bounds the
        # NUMBER of turns -- no code constant limits it here, unlike `_render_turns`' `limit`; it
        # is bounded by how long the sitting ran, which no single learner message can inflate.
        user = (
            _cap_rendered_turn(labelled("Her situation:", situation), cap=_LEARNER_TEXT_TRIM_CAP)
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
