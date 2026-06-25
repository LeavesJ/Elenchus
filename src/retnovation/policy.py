from __future__ import annotations

from datetime import datetime

from .state import frame_interval_days, frame_uncertainty
from .types import Experience, LearnerState, NextExperienceSpec, Regime, SelectionReceipt, Strength


def _uncertainty(state: LearnerState, code: str, now: datetime) -> float:
    fs = state.frames.get(code)
    if fs is None:
        return 1.0  # never seen -> maximally uncertain (cold start)
    return frame_uncertainty(
        fs.evidence_count, fs.breadth, fs.unprompted_breadth, fs.last_seen, now
    )


def _retention_due(state: LearnerState, code: str, now: datetime) -> float:
    fs = state.frames.get(code)
    if fs is None or fs.evidence_count == 0:
        return 0.0
    interval = frame_interval_days(fs.evidence_count, fs.unprompted_breadth)
    staleness = max(0.0, (now - fs.last_seen).total_seconds() / 86400.0)
    return max(0.0, min(1.0, (staleness - interval) / interval))


def _transfer(state: LearnerState, code: str, problem: str) -> float:
    fs = state.frames.get(code)
    if fs is None or fs.strength is not Strength.forming:
        return 0.0
    return 1.0 if problem not in fs.breadth else 0.0


def _located(state: LearnerState, code: str, now: datetime, theta: float) -> bool:
    return _uncertainty(state, code, now) <= theta


def _content_gaps(
    state: LearnerState, experiences: list[Experience], now: datetime, theta: float
) -> list[str]:
    all_frames = set()
    for e in experiences:
        all_frames.update(f.frame_code for f in e.rubric.frames)
    gaps = []
    for f in sorted(all_frames):
        homed = False
        for e in experiences:
            codes = [x.frame_code for x in e.rubric.frames]
            if f not in codes:
                continue
            if all(_located(state, c, now, theta) for c in codes if c != f):
                homed = True
                break
        if not homed:
            gaps.append(f)
    return gaps


def select_next(
    state: LearnerState, experiences: list[Experience], config: dict, now: datetime
) -> tuple[NextExperienceSpec, SelectionReceipt]:
    wU, wR, wT, wL = config["wU"], config["wR"], config["wT"], config["wL"]
    theta = config["theta_located"]

    best = None  # (sort_key, frame, exp, terms, V, penalty)
    for e in experiences:
        penalty = max(
            (_uncertainty(state, g.frame_code, now) for g in e.rubric.frames), default=0.0
        )
        load = len(e.rubric.frames)
        for fr in e.rubric.frames:
            f = fr.frame_code
            terms = {
                "diagnose": wU * _uncertainty(state, f, now),
                "consolidate": wR * _retention_due(state, f, now),
                "deploy": wT * _transfer(state, f, e.ledger_ref),
            }
            V = terms["diagnose"] + terms["consolidate"] + terms["deploy"] - wL * penalty
            sort_key = (-V, load, f, e.ledger_ref, e.experience_id)
            if best is None or sort_key < best[0]:
                best = (sort_key, f, e, terms, V, penalty)

    if best is None:
        raise ValueError("no (frame, experience) candidates to score")
    _, frame, exp, terms, V, penalty = best
    ranked = sorted(terms.items(), key=lambda kv: -kv[1])
    drive = ranked[0][0]
    runner_up_drive = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else None
    margin = ranked[0][1] - ranked[1][1] if runner_up_drive is not None else 0.0

    spec = NextExperienceSpec(
        target_frames=[frame],
        ledger_ref=exp.ledger_ref,
        regime=Regime.open_ended,
        experience_id=exp.experience_id,
    )
    receipt = SelectionReceipt(
        frame=frame,
        problem=exp.ledger_ref,
        experience_id=exp.experience_id,
        drive=drive,
        scores={
            "uncertainty": terms["diagnose"] / wU if wU else 0.0,
            "retention": terms["consolidate"] / wR if wR else 0.0,
            "transfer": terms["deploy"] / wT if wT else 0.0,
            "penalty": penalty,
            "V": V,
        },
        runner_up_drive=runner_up_drive,
        margin=margin,
        content_gaps=_content_gaps(state, experiences, now, theta),
        created_at=now,
    )
    return spec, receipt
