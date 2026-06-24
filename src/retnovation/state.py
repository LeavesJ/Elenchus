from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from .content_loader import load_spacing
from .types import (
    Assessment,
    CheckableAssessment,
    FrameState,
    FrameStrength,
    LearnerState,
    Regime,
    SpacedItem,
    Strength,
    TrapOccurrence,
)


def update_state(
    state: LearnerState, assessment: Assessment, now: datetime, experience_id: str
) -> LearnerState:
    closed = set(assessment.frames_closed_under_pressure)

    # Frame strengths move on rigor/trajectory evidence only (never correctness).
    final_state: dict[str, FrameState] = {}
    for d in assessment.frame_deltas:
        final_state[d.code] = d.after

    seen_frame_targets = {p.target_code for p in assessment.trajectory if p.kind == "frame"}
    for code in seen_frame_targets | set(final_state):
        if code in closed and final_state.get(code) is FrameState.present_reasoned:
            strength = Strength.forming
        elif final_state.get(code) is FrameState.present_reasoned:
            # NOTE: currently unreachable from the judgment loop — the loop co-populates deltas and
            # frames_closed_under_pressure, so a loop-driven present_reasoned is always "forming".
            # "strong" is the documented, not-yet-calibrated sharp edge from spec section 7.
            strength = Strength.strong  # reasoned without needing the closing push
        else:
            strength = Strength.weak
        fstate = final_state.get(code)
        evidence = fstate.value if fstate is not None else "unmoved"
        state.frames[code] = FrameStrength(
            strength=strength,
            last_seen=now,
            due=now,
            last_evidence=f"{experience_id}:{evidence}",
        )

    # Trap gallery: any trap target that was pushed and not repaired is logged.
    for p in assessment.trajectory:
        if p.kind == "trap" and p.response_classification != "closed":
            state.trap_gallery.setdefault(p.target_code, []).append(
                TrapOccurrence(
                    experience_id=experience_id, occurred_at=now, detail=p.response_classification
                )
            )
    return state


def update_state_checkable(
    state: LearnerState,
    assessment: CheckableAssessment,
    now: datetime,
    experience_id: str,
    spacing: dict | None = None,
) -> LearnerState:
    if spacing is None:
        spacing = load_spacing()
    initial = spacing["initial_interval_days"]
    ease = spacing["ease_factor"]
    floor = spacing["min_interval_days"]

    by_concept: dict[str, list[bool]] = {}
    for r in assessment.results:
        by_concept.setdefault(r.concept, []).append(r.correct)

    for concept, corrects in by_concept.items():
        recalled = all(corrects)
        prev = state.declarative_seed.get(concept)
        if prev is None:
            interval = initial if recalled else floor
        elif recalled:
            interval = max(floor, round(prev.interval_days * ease))
        else:
            interval = floor  # reversible demotion — row is updated, never deleted (L-3)
        state.declarative_seed[concept] = SpacedItem(
            concept=concept, due=now + timedelta(days=interval), interval_days=interval
        )
    return state


STATE_UPDATERS: dict[Regime, Callable] = {
    Regime.open_ended: update_state,
    Regime.cs_technical: update_state_checkable,
}
