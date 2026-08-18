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
    # TODAY, but by TWO mechanisms, not the one an earlier version of this comment named. A T2
    # review ran the loop and falsified the single-invariant story, so both are stated here:
    #
    # * On the fall-through, a push that fails the credit branch is added to `exhausted`, and
    #   `judgment_loop._select_target` skips exhausted codes, so that code is never pushed again.
    # * On the `hard_wrong` and `regressed` early breaks, THIS code is never added to
    #   `exhausted` -- `exhausted.add(code)` sits only on the fall-through -- and the conclusion
    #   survives for a different reason: both paths `break`, ending the loop, so no later
    #   credited push for that code can exist.
    #
    #   An earlier version of this bullet closed with `Measured: exhausted is empty after either
    #   break`, which is false and was itself caught by a review that ran it. `exhausted` is a
    #   loop-scoped accumulator over ALL codes, and neither break clears it, so any earlier push
    #   that fell through uncredited leaves its own code in the set: executed, a sitting whose
    #   first push falls through and whose second breaks reaches the break with `exhausted ==
    #   {first_code}`. The measurement generalized a single-iteration run, and `Measured:` is
    #   this repo's strongest confidence label, so a false one is worse than no label at all --
    #   a later reader has no reason to re-run it. Only THIS code's absence is claimed, and the
    #   break, not exhaustion, is what carries the argument.
    #
    # AND NEITHER BULLET IS THE BINDING CONSTRAINT, which an earlier version of this comment did
    # not say. `p.target_code not in closed`, on the line below, already excludes every Push this
    # clause would, on every state the loop can emit. `frames_closed_under_pressure` has exactly
    # two writers: `judgment_loop.py`, fed from the credit branch where the `Push` necessarily
    # carries `gap_closed=True`, and this function's own removal-only rewrite below. Membership
    # therefore implies credit. Measured over 589,824 real `assess` runs spanning every
    # combination of intake frame state, trap state, mode, binding constraint, decision frame and
    # response classification: 176,308 pushes classified `closed` and denied credit, and ZERO
    # whose code was in `frames_closed_under_pressure`.
    #
    # So this clause is defense in depth against a FUTURE third writer of that list, never a live
    # behaviour change, and it CANNOT be measured on anything the engine currently produces. Both
    # halves are pinned in `tests/test_sharper_grader.py`:
    # `test_frames_closed_under_pressure_implies_a_credited_push` drives the real loop and fails
    # the moment a writer bypasses the credit branch, and the hand-built cell next to it now says
    # in its own docstring that it is hand-built and why.
    #
    # Either way it is a proxy standing in for the real predicate, and that same proxy is what
    # let an inflated `closed` delete a trap's gallery row in `state.update_state` (see
    # `types.Push.gap_closed`). The authority is the loop's credit decision, and
    # `instructor_sharper=True` below is hardcoded on the strength of it -- an uncredited push is
    # not an instructor closure to audit. Note this reads `gap_closed` strictly BEFORE this
    # function revokes anything, which is why the pre-audit value is the correct one here.
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
