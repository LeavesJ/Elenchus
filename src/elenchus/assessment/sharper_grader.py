from __future__ import annotations

from ..model import Model
from ..types import Assessment, Experience, SharperAuditItem


def audit_sharper(exp: Experience, assessment: Assessment, model: Model) -> Assessment:
    """Blind 2-vote audit of the instructor's sharper calls: re-grade each closed frame; a
    disputed call is dropped from frames_closed_under_pressure and its delta reverted, so
    update_state cannot credit it. Records the full audit trail on sharper_audit.

    T2 REVIEW FIX: `verdict.sharper` is the auditor's real, unfloored judgment -- `grade_sharper`
    (model.py) no longer floors it on a failed evidence-anchor span match (see that method's own
    comment for why reverting an already-credited closure over a typographic mismatch is a
    strictly worse failure than missing a fabricated span). `verdict.span_unverified` carries the
    span-check outcome separately and is copied straight onto `SharperAuditItem` below; a span-only
    failure is NEVER added to `disputed` here, because `verdict.sharper` already reflects the
    auditor's actual call regardless of whether the span matched."""
    closed = set(assessment.frames_closed_under_pressure)
    audit: list[SharperAuditItem] = []
    disputed: set[str] = set()
    seen: set[str] = set()
    # `not p.gap_closed`, not `p.response_classification != "closed"`. The two are equivalent
    # TODAY, and only by an invariant that lives in another module: `judgment_loop._select_target`
    # skips exhausted codes, and a code is exhausted the instant a push fails the credit branch,
    # so a code reaching `frames_closed_under_pressure` has only credited points behind it. That
    # is a proxy standing in for the real predicate, and the same proxy is what let an inflated
    # `closed` delete a trap's gallery row in `state.update_state` (see `types.Push.gap_closed`).
    # The authority is the loop's credit decision, and `instructor_sharper=True` below is
    # hardcoded on the strength of it -- an uncredited push is not an instructor closure to audit.
    for p in assessment.trajectory:
        if (
            p.kind != "frame"
            or p.target_code not in closed
            or not p.gap_closed
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
                span_unverified=verdict.span_unverified,
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
