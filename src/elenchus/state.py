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


# Storage-keyed staleness clock. The interval is a function of the persistent STORAGE tier
# (evidence_count / unprompted_breadth), never the displayed/decayed bucket — acyclic and §5-faithful.
# Moves to content/cadence/progression.yaml in Project 2.
_INTERVAL_DAYS: dict[Strength, int] = {Strength.weak: 1, Strength.forming: 7, Strength.strong: 30}
_STEP_DOWN: dict[Strength, Strength] = {
    Strength.strong: Strength.forming,
    Strength.forming: Strength.weak,
    Strength.weak: Strength.weak,
}


def _storage_tier(evidence_count: int, unprompted_breadth: set[str]) -> Strength:
    if len(unprompted_breadth) >= 2:
        return Strength.strong  # unprompted on >=2 distinct problems: repeated AND cross-context
    if evidence_count >= 1:
        return (
            Strength.forming
        )  # engaged with a mechanism at least once (incl. closed-under-pressure)
    return Strength.weak


def frame_interval_days(evidence_count: int, unprompted_breadth: set[str]) -> int:
    return _INTERVAL_DAYS[_storage_tier(evidence_count, unprompted_breadth)]


def _staleness_days(last_seen: datetime, now: datetime) -> float:
    return max(0.0, (now - last_seen).total_seconds() / 86400.0)


def derive_strength(
    evidence_count: int, unprompted_breadth: set[str], last_seen: datetime, now: datetime
) -> Strength:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    if _staleness_days(last_seen, now) <= _INTERVAL_DAYS[tier]:
        return tier
    return _STEP_DOWN[
        tier
    ]  # decayed one bucket; the interval below stays keyed to `tier` (storage)


def derive_due(evidence_count: int, unprompted_breadth: set[str], last_seen: datetime) -> datetime:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    return last_seen + timedelta(days=_INTERVAL_DAYS[tier])


def frame_uncertainty(
    evidence_count: int,
    breadth: set[str],
    unprompted_breadth: set[str],
    last_seen: datetime,
    now: datetime,
) -> float:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    evidence_term = 1.0 / (1.0 + evidence_count)
    breadth_term = 0.0 if len(breadth) >= 2 else 1.0
    staleness_term = min(1.0, _staleness_days(last_seen, now) / _INTERVAL_DAYS[tier])
    return max(0.0, min(1.0, (evidence_term + breadth_term + staleness_term) / 3.0))


def update_state(
    state: LearnerState, assessment: Assessment, now: datetime, experience_id: str, ledger_ref: str
) -> LearnerState:
    closed = set(assessment.frames_closed_under_pressure)
    unprompted = set(assessment.reasoned_unprompted)
    engaged = closed | unprompted
    final_state: dict[str, FrameState] = {d.code: d.after for d in assessment.frame_deltas}
    seen_frame_targets = {p.target_code for p in assessment.trajectory if p.kind == "frame"}

    for code in seen_frame_targets | set(final_state) | unprompted:
        prev = state.frames.get(code)
        evidence_count = prev.evidence_count if prev else 0
        breadth = set(prev.breadth) if prev else set()
        unprompted_breadth = set(prev.unprompted_breadth) if prev else set()
        if code in engaged:
            evidence_count += 1
            breadth.add(ledger_ref)
            if code in unprompted:
                unprompted_breadth.add(ledger_ref)
        if code in unprompted:
            evidence = "reasoned_unprompted"
        else:
            fstate = final_state.get(code)
            evidence = fstate.value if fstate is not None else "unmoved"
        state.frames[code] = FrameStrength(
            strength=derive_strength(evidence_count, unprompted_breadth, now, now),
            last_seen=now,
            due=derive_due(evidence_count, unprompted_breadth, now),
            last_evidence=f"{experience_id}:{evidence}",
            evidence_count=evidence_count,
            breadth=breadth,
            unprompted_breadth=unprompted_breadth,
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
    ledger_ref: str,
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
