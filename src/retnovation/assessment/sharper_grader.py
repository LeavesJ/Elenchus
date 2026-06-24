from __future__ import annotations

from ..model import Model
from ..types import Assessment, Experience, SharperAuditItem


def audit_sharper(exp: Experience, assessment: Assessment, model: Model) -> Assessment:
    """Blind 2-vote audit of the instructor's sharper calls: re-grade each closed frame; a
    disputed call is dropped from frames_closed_under_pressure and its delta reverted, so
    update_state cannot credit it. Records the full audit trail on sharper_audit."""
    closed = set(assessment.frames_closed_under_pressure)
    audit: list[SharperAuditItem] = []
    disputed: set[str] = set()
    seen: set[str] = set()
    for p in assessment.trajectory:
        if (
            p.kind != "frame"
            or p.target_code not in closed
            or p.response_classification != "closed"
            or p.target_code in seen
        ):
            continue
        seen.add(p.target_code)
        verdict = model.grade_sharper(exp, p.kind, p.target_code, p.text, p.response)
        audit.append(
            SharperAuditItem(
                code=p.target_code,
                kind=p.kind,
                instructor_sharper=True,
                grader_sharper=verdict.sharper,
                confirmed=verdict.sharper,
                grader_reason=verdict.reason,
            )
        )
        if not verdict.sharper:
            disputed.add(p.target_code)
    new_closed = [c for c in assessment.frames_closed_under_pressure if c not in disputed]
    new_deltas = [d for d in assessment.frame_deltas if d.code not in disputed]
    return assessment.model_copy(
        update={
            "frames_closed_under_pressure": new_closed,
            "frame_deltas": new_deltas,
            "sharper_audit": audit,
        }
    )
