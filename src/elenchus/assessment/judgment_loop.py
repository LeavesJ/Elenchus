from __future__ import annotations

from ..model import Model
from ..types import (
    Assessment,
    Experience,
    FrameDelta,
    FrameState,
    Mode,
    Positions,
    Push,
    StopReason,
    TrapState,
    Work,
)
from .sharper_grader import audit_sharper

MAX_PUSHES = 8  # >= the 8-angle depth floor; budget-only (loop still pushes frames/traps — Step 5 probes dims)

_POSITION_CAP = 1200  # characters per position, measured BEFORE render. This bounds what _cap
# hands to _bulleted, not what reaches the prompt: _bulleted indents every continuation line
# past the bullet, and a newline-heavy position can render up to ~5x larger than its capped
# length (measured against a pathological 1200-char, all-newline position: 5999 rendered chars,
# not 1200). 8 such positions render to roughly 48,000 characters of learner text, not the
# naive 8 x 1200 = 9600 this comment used to claim.

PUSH_LABEL_WITH_POSITIONS = "push_label_with_positions"  # a cost THIS change introduced
PUSH_LABEL_BLIND = "push_label_blind"  # the PRE-EXISTING unscreened-push condition


def _cap(text: str) -> str:
    """Truncate at the last sentence boundary under the cap, marking the elision.

    A mid-clause cut hands the push author a position that appears to end where the learner
    stopped talking, and the author then presses the trailing thought — an artifact of our cap
    rather than anything the learner argued. Deterministic; no model call."""
    if len(text) <= _POSITION_CAP:
        return text
    head = text[:_POSITION_CAP]
    stop = max(head.rfind("."), head.rfind("?"), head.rfind("!"))
    return (head[: stop + 1] if stop > 0 else head.rstrip()) + "…[trimmed]"


def _group_positions(trajectory: list[Push], kind: str, code: str) -> Positions:
    """The learner's own words, split by whether they were argued on the angle being pressed.

    Keyed on the FULL (kind, code) target. Codes are unique across kinds today by accident, not
    by enforcement, and the rubric bank grows by hand — a trap code matching a frame code would
    put a trap position in `on_angle` and tell the stress author it was the reasoned engagement
    with this angle. Silently.

    `response_classification` is deliberately NOT read: a push author that knows the grader
    called your last reply a deflection is one step from scolding you."""
    here, there = [], []
    for p in trajectory:
        if not p.response:
            continue
        (here if (p.kind, p.target_code) == (kind, code) else there).append(_cap(p.response))
    return Positions(on_angle=tuple(here), elsewhere=tuple(there))


def _push_label_leak(push: str, rubric) -> str | None:
    """The label bar, plus the push-specific category denylist: a named framework, a frame/trap
    code in snake or spaced form, or one of the seven category-cueing phrases in
    content/gate/push_category_denylist.yaml ('classic case of', 'use the framework', 'the right
    framework', 'which framework', 'this is an example of', 'think of this as a', 'treat this as
    a'). The label bar is checked first and wins any tie, because a leaked frame code is the more
    serious finding and the one the ledger most needs to distinguish. Returns the matched phrase
    (so a caller can put it in the ledger), or None.

    Still deliberately NOT `generator.validate_scene`'s full bar. That bar also carries the
    REMAINING two scaffold_denylist entries ('this is a', 'apply the') and WRAPPER_WORDS ('points',
    'timer', 'reward', ..., matched as bare substrings) -- all calibrated against AUTHORED SCENE
    prompts, where a type-hint cues the problem category and a wrapper word means cosmetic
    gamification. A push is a different distribution: ordinary instructor prose, where "at several
    points" or "this is a real account" are unremarkable English. Per Invariant 7 (a safety
    property is a property of gate times distribution), that calibration does not transfer, so
    those two scaffold entries and WRAPPER_WORDS as a whole stay off the push path. The seven
    category phrases DO travel with the push regardless of distribution: push.md's first hard rule
    forbids naming the frame or its category, and Invariant 6 makes the unlabeled problem the moat,
    so a phrase that states the angle's type is a real leak on either distribution.
    tests/test_judgment_loop.py::test_push_label_leak_catches_each_category_phrase pins that each
    of the seven phrases trips this bar. Measured against the twelve-push corpus in
    tests/test_judgment_loop.py::test_push_label_leak_clears_ordinary_pushes_on_real_content, run
    against the real rubric content/rubrics/license_continuity.yaml: the full validate_scene bar
    rejects 5 of 12 ordinary instructor pushes; this bar rejects 0 of 12 and still catches a named
    framework, a snake frame code, and a spaced frame code.

    Screens the OUTPUT rather than sanitising the input: stripping labels from the learner's
    positions would destroy signal, because a learner naming a frame is itself information the
    loop should be able to press."""
    from ..content_loader import load_denylist
    from ..generator import label_leak, phrase_leak

    hit = label_leak(push, rubric, load_denylist("framework_denylist"))
    if hit is not None:
        return hit
    return phrase_leak(push, load_denylist("push_category_denylist"))


def _label_steer(hit: str, rubric) -> str:
    """R3. The one-shot retry steer for a leak `_push_label_leak` just caught -- never the code
    itself (`test_the_target_code_never_reaches_the_prompt` exists because a code in the prompt
    RAISES the leak rate). Two branches, decided by testing `hit` against THIS RUBRIC's own frame
    and trap phrases (`generator.frame_trap_phrases`, snake and spaced form) -- not against the
    framework denylist `_push_label_leak` also draws from, which cannot tell a rubric code apart
    from a framework name or a category cue:

    - `hit` is one of this rubric's frame/trap phrases: a FIXED generic string that names no
      code, because re-injecting the code that just leaked would raise the leak rate on the very
      retry meant to fix it. This is also what closes a latent collision: if a framework denylist
      entry ever equalled a rubric code's spaced form, `_push_label_leak` would surface that
      spaced form as `hit`, and testing membership in the framework denylist alone would have
      named it -- writing the target code straight into the retry prompt, the one thing this
      function exists to prevent.
    - anything else -- a named framework, or one of the seven category-cueing phrases in
      content/gate/push_category_denylist.yaml -- names the term: neither is secret, and naming
      it tells the author exactly what to drop.

    `generator.frame_trap_phrases` lowercases both the codes and their spaced form before
    comparing, and `content_loader.load_denylist` lowercases every entry at load time, so `hit`
    -- which always comes from one of those two sources via `_push_label_leak` -- is always
    already lowercase here."""
    from ..generator import frame_trap_phrases

    if hit in frame_trap_phrases(rubric):
        return (
            "Your previous attempt echoed an internal label. Press the reasoning, never the name."
        )
    return (
        f'Do not use the term "{hit}" -- it names a framework or the category of this '
        "angle, not the reasoning."
    )


_LOWER = {
    FrameState.present_reasoned: FrameState.present_asserted,
    FrameState.present_asserted: FrameState.absent,
    FrameState.absent: FrameState.absent,
}


def _lower(state: FrameState) -> FrameState:
    return _LOWER[state]


def _select_target(exp: Experience, frame_states, trap_states, exhausted, probed):
    """Forced decision frame first (once), then tripped traps, binding-adjacent absent frames,
    then remaining absent frames. Skips codes already exhausted (a non-moving push)."""
    df = exp.rubric.decision_frame
    if df is not None and df not in probed and df not in exhausted:
        return ("frame", df)
    for t in exp.rubric.traps:
        if t.trap_code in exhausted:
            continue
        if trap_states.get(t.trap_code) is TrapState.tripped:
            return ("trap", t.trap_code)
    binding = exp.rubric.binding_constraint
    if (
        binding
        and binding not in exhausted
        and frame_states.get(binding) is not None
        and frame_states[binding] is not FrameState.present_reasoned
    ):
        return ("frame", binding)
    for f in exp.rubric.frames:
        if f.frame_code in exhausted:
            continue
        if frame_states.get(f.frame_code) is not FrameState.present_reasoned:
            return ("frame", f.frame_code)
    return None


def _converged(frame_states, trap_states, exp, probed) -> bool:
    # A rubric that declares a decision_frame may not converge until that frame has been
    # stressed once — even if intake rated it present_reasoned (the silence-when-strong fix).
    df = exp.rubric.decision_frame
    if df is not None and df not in probed:
        return False
    frames_ok = all(s is FrameState.present_reasoned for s in frame_states.values())
    traps_ok = all(s is not TrapState.tripped for s in trap_states.values())
    return frames_ok and traps_ok


def assess(exp: Experience, work: Work, model: Model) -> Assessment:
    intake = model.classify_intake(exp, work.opening)
    frame_states = dict(intake.frame_states)
    trap_states = dict(intake.trap_states)

    trajectory: list[Push] = []
    deltas: list[FrameDelta] = []
    closed: list[str] = []
    hard_wrong: list[str] = []
    push_rejections: list[tuple[int, str, str]] = []
    exhausted: set[str] = set()
    probed: set[str] = set()
    recent: list[tuple[str, bool]] = []  # (code, moved) for the last pushes
    stop_reason: StopReason | None = None

    while True:
        if _converged(frame_states, trap_states, exp, probed):
            stop_reason = StopReason.converged
            break
        if len(trajectory) >= MAX_PUSHES:
            stop_reason = StopReason.budget
            break
        if (
            len(recent) >= 2
            and recent[-1][0] != recent[-2][0]
            and not recent[-1][1]
            and not recent[-2][1]
        ):
            stop_reason = StopReason.plateau
            break

        target = _select_target(exp, frame_states, trap_states, exhausted, probed)
        if target is None:
            stop_reason = StopReason.plateau
            break
        kind, code = target

        stress = kind == "frame" and frame_states.get(code) is FrameState.present_reasoned
        probed.add(code)
        rejections_here: list[tuple[int, str, str]] = []
        pos = _group_positions(trajectory, kind, code)
        push_text = model.generate_push(exp, kind, code, stress=stress, positions=pos)
        # `blind` no longer picks a control-flow branch below -- it exists solely to choose which
        # rejection code attempt 1 is filed under, just below.
        blind = not (pos.on_angle or pos.elsewhere)
        hit = _push_label_leak(push_text, exp.rubric)
        if hit is not None:
            # The code is derived from what THIS call actually received, never from the attempt
            # index. A first push has an empty trajectory, so it is blind in substance, and filing
            # it as "caused by positions" is the exact conflation the two codes exist to prevent.
            rejections_here.append(
                (1, PUSH_LABEL_BLIND if blind else PUSH_LABEL_WITH_POSITIONS, hit)
            )
            # The retry runs unconditionally, blind or not: `_label_steer` derives the steer from
            # what leaked, never from `positions` -- whether that steer names the leaked term or
            # (for a rubric code hit) returns a fixed generic string that names nothing is a
            # separate branch inside `_label_steer` itself, deliberate and pinned by its own
            # tests. Either way attempt 1's steer is always "" and the retry's is not, so even a
            # blind call's re-authored prompt is materially different from the one that just
            # leaked -- never a resample. `positions=pos` is already empty when blind, so nothing
            # else changes. A served push has been screened at least once and at most twice, and
            # is never served without being counted.
            push_text = model.generate_push(
                exp,
                kind,
                code,
                stress=stress,
                positions=pos,
                steer=_label_steer(hit, exp.rubric),
            )
            hit = _push_label_leak(push_text, exp.rubric)
            if hit is not None:
                # Stays PUSH_LABEL_BLIND: it now means "a leak that survived a steer", the
                # same pre-existing unscreened condition showing through.
                rejections_here.append((2, PUSH_LABEL_BLIND, hit))
        push_rejections.extend(rejections_here)
        response = work.respond(push_text)
        rc = model.classify_response(exp, kind, code, push_text, response, stress=stress)

        moved = False
        if rc.hard_wrong and exp.rubric.mode is Mode.bounded_error:
            hard_wrong.append(code)
            trajectory.append(
                Push(
                    target_code=code,
                    kind=kind,
                    text=push_text,
                    response_classification=rc.outcome,
                    response=response,
                )
            )
            stop_reason = StopReason.bounded_error_violation
            break

        if rc.outcome == "regressed":
            if kind == "frame":
                before = frame_states.get(code, FrameState.absent)
                after = _lower(before)
                frame_states[code] = after
                if after is not before:
                    deltas.append(FrameDelta(code=code, before=before, after=after))
            trajectory.append(
                Push(
                    target_code=code,
                    kind=kind,
                    text=push_text,
                    response_classification=rc.outcome,
                    response=response,
                )
            )
            stop_reason = StopReason.regression
            break

        if rc.outcome == "closed" and rc.mechanism_supplied:
            if kind == "frame":
                before = frame_states.get(code, FrameState.absent)
                frame_states[code] = FrameState.present_reasoned
                if before is not FrameState.present_reasoned:
                    deltas.append(
                        FrameDelta(code=code, before=before, after=FrameState.present_reasoned)
                    )
                closed.append(code)
            else:
                trap_states[code] = TrapState.repaired
            moved = True
        else:
            exhausted.add(code)

        trajectory.append(
            Push(
                target_code=code,
                kind=kind,
                text=push_text,
                response_classification=rc.outcome,
                response=response,
            )
        )
        recent.append((code, moved))

    reasoned_unprompted = [
        code
        for code, s0 in intake.frame_states.items()
        if s0 is FrameState.present_reasoned
        and frame_states.get(code) is FrameState.present_reasoned
        and code not in probed
    ]
    assessment = Assessment(
        trajectory=trajectory,
        frame_deltas=deltas,
        frames_closed_under_pressure=closed,
        hard_wrong_flags=hard_wrong,
        stop_reason=stop_reason or StopReason.budget,
        reasoned_unprompted=reasoned_unprompted,
        push_rejections=tuple(push_rejections),
    )
    return audit_sharper(exp, assessment, model)
