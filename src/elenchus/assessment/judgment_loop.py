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

_POSITION_CAP = 1200  # characters per position; worst case 8 x 1200 = 9600 of learner text

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
    """The label bar ALONE: a named framework, or a frame/trap code in snake or spaced form.
    Returns the matched phrase (so a caller can put it in the ledger), or None.

    Deliberately NOT `generator.validate_scene`'s full bar. That bar adds the scaffold denylist
    ('this is a', 'classic case of', ...) and WRAPPER_WORDS ('points', 'timer', 'reward', ...,
    matched as bare substrings) on top of the label check -- both calibrated against AUTHORED
    SCENE prompts, where a type-hint cues the problem category and a wrapper word means cosmetic
    gamification. A push is a different distribution: ordinary instructor prose, where "at several
    points" or "this is a real account" are unremarkable English. Per Invariant 7 (a safety
    property is a property of gate times distribution), that calibration does not transfer. Measured
    by the controller against a real rubric: the full bar rejects 9 of 12 ordinary instructor
    pushes; the label bar alone rejects 0 of 12 and still catches a named framework, a snake frame
    code, and a spaced frame code.

    Screens the OUTPUT rather than sanitising the input: stripping labels from the learner's
    positions would destroy signal, because a learner naming a frame is itself information the
    loop should be able to press."""
    from ..content_loader import load_denylist
    from ..generator import label_leak

    return label_leak(push, rubric, load_denylist("framework_denylist"))


def _label_steer(hit: str, rubric) -> str:
    """R3. The one-shot retry steer for a leak `_push_label_leak` just caught -- never the code
    itself (`test_the_target_code_never_reaches_the_prompt` exists because a code in the prompt
    RAISES the leak rate). Two branches, decided by testing `hit` against the loaded framework
    denylist `_push_label_leak` matched against:

    - a framework hit names the term: there is nothing secret about a named method, and naming
      it tells the author exactly what to drop.
    - a frame/trap code hit gets a FIXED generic string that names no code. `label_leak` lowers
      both the denylist and the code phrases it matches against before comparing, so `hit` is
      always already lowercase here."""
    from ..content_loader import load_denylist

    if hit in load_denylist("framework_denylist"):
        return f'Do not use the term "{hit}" or name any framework.'
    return "Your previous attempt echoed an internal label. Press the reasoning, never the name."


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
        blind = not (pos.on_angle or pos.elsewhere)
        hit = _push_label_leak(push_text, exp.rubric)
        if hit is not None:
            # The code is derived from what THIS call actually received, never from the attempt
            # index. A first push has an empty trajectory, so it is blind in substance, and filing
            # it as "caused by positions" is the exact conflation the two codes exist to prevent.
            rejections_here.append(
                (1, PUSH_LABEL_BLIND if blind else PUSH_LABEL_WITH_POSITIONS, hit)
            )
            if not blind:
                # A blind first call would be re-authored from a byte-identical prompt, so the
                # retry would be pure resampling at a paid call -- skipped. Only a call that HAD
                # positions can be meaningfully steered, so the retry keeps them and adds the
                # steer derived from what leaked. New safety claim (the old "blind fallback"
                # claim no longer holds): a served push has been screened at least once and at
                # most twice, and is never served without being counted. That is still no worse
                # than the pre-branch code, which screened the push zero times.
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
