from __future__ import annotations

from ..model import Model
from ..types import (
    Assessment,
    Experience,
    FrameDelta,
    FrameState,
    Mode,
    Push,
    StopReason,
    TrapState,
    Work,
)
from .sharper_grader import audit_sharper

MAX_PUSHES = 8  # >= the 8-angle depth floor; budget-only (loop still pushes frames/traps — Step 5 probes dims)

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
        push_text = model.generate_push(exp, kind, code, stress=stress)
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

    assessment = Assessment(
        trajectory=trajectory,
        frame_deltas=deltas,
        frames_closed_under_pressure=closed,
        hard_wrong_flags=hard_wrong,
        stop_reason=stop_reason or StopReason.budget,
    )
    return audit_sharper(exp, assessment, model)
