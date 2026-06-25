from __future__ import annotations

from datetime import datetime

from .policy import retention_due
from .types import CoreCandidate, CoreKind, Core, Experience, LearnerState, LedgerEntry


def _active_problem_frames(
    ledger: list[LedgerEntry], experiences: list[Experience]
) -> dict[str, set[str]]:
    """frame_code -> set of active owned problems whose experiences carry it (exogenous signal:
    Experience.ledger_ref into the ledger, NOT LedgerEntry.links_to_experiences which is empty in
    production, NOT breadth which is endogenous)."""
    active = {entry.id for entry in ledger}
    out: dict[str, set[str]] = {}
    for e in experiences:
        if e.ledger_ref not in active or e.rubric is None:
            continue
        for fr in e.rubric.frames:
            out.setdefault(fr.frame_code, set()).add(e.ledger_ref)
    return out


def crystallization_candidates(
    state: LearnerState,
    core: Core,
    ledger: list[LedgerEntry],
    experiences: list[Experience],
    now: datetime,
    config: dict,
) -> list[CoreCandidate]:
    theta = config["theta_ledger_refs"]
    refs = _active_problem_frames(ledger, experiences)
    out: list[CoreCandidate] = []

    # Demote: core process frame, no evidence, not referenced by any active problem.
    for f in core.process_frames:
        fs = state.frames.get(f)
        untouched = fs is None or fs.evidence_count == 0
        if untouched and f not in refs:
            out.append(
                CoreCandidate(
                    kind=CoreKind.demote,
                    target=f,
                    rationale="no evidence and unreferenced by the active ledger",
                )
            )

    # Promote: a frame that has decayed AND keeps surfacing across active problems.
    for f, fs in state.frames.items():
        ref_count = len(refs.get(f, set()))
        if retention_due(state, f, now) > 0.0 and ref_count >= theta:
            out.append(
                CoreCandidate(
                    kind=CoreKind.promote,
                    target=f,
                    rationale=f"decayed and referenced across {ref_count} active problems",
                )
            )
    return out
