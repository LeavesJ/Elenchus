from __future__ import annotations

from datetime import datetime

from .types import (
    Assessment,
    FrameState,
    FrameStrength,
    LearnerState,
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
            strength = Strength.strong  # reasoned without needing the closing push
        else:
            strength = Strength.weak
        state.frames[code] = FrameStrength(
            strength=strength,
            last_seen=now,
            due=now,
            last_evidence=f"{experience_id}:{final_state.get(code, 'unmoved')}",
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
