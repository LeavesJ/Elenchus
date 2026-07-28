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


def retention_due(state: LearnerState, code: str, now: datetime) -> float:
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
) -> list[tuple[NextExperienceSpec, SelectionReceipt]]:
    wU, wR, wT, wL = config["wU"], config["wR"], config["wT"], config["wL"]
    theta = config["theta_located"]
    gaps = _content_gaps(state, experiences, now, theta)

    scored = []  # each: dict with sort_key, frame, exp, drive, V, terms, penalty
    for e in experiences:
        penalty = max(
            (_uncertainty(state, g.frame_code, now) for g in e.rubric.frames), default=0.0
        )
        load = len(e.rubric.frames)
        for fr in e.rubric.frames:
            f = fr.frame_code
            terms = {
                "diagnose": wU * _uncertainty(state, f, now),
                "consolidate": wR * retention_due(state, f, now),
                "deploy": wT * _transfer(state, f, e.ledger_ref),
            }
            V = terms["diagnose"] + terms["consolidate"] + terms["deploy"] - wL * penalty
            drive = max(terms.items(), key=lambda kv: kv[1])[0]
            scored.append(
                {
                    "sort_key": (-V, load, f, e.ledger_ref, e.experience_id),
                    "frame": f,
                    "exp": e,
                    "drive": drive,
                    "V": V,
                    "terms": terms,
                    "penalty": penalty,
                }
            )

    if not scored:
        raise ValueError("no (frame, experience) candidates to score")
    scored.sort(key=lambda c: c["sort_key"])

    ranked: list[tuple[NextExperienceSpec, SelectionReceipt]] = []
    for c in scored:
        others = [o for o in scored if o["drive"] != c["drive"]]
        if others:
            best_other = max(others, key=lambda o: o["V"])
            runner_up_drive = best_other["drive"]
            margin = c["V"] - best_other["V"]
        else:
            runner_up_drive, margin = None, 0.0
        e, f, terms = c["exp"], c["frame"], c["terms"]
        spec = NextExperienceSpec(
            target_frames=[f],
            ledger_ref=e.ledger_ref,
            regime=Regime.open_ended,
            experience_id=e.experience_id,
        )
        receipt = SelectionReceipt(
            frame=f,
            problem=e.ledger_ref,
            experience_id=e.experience_id,
            drive=c["drive"],
            scores={
                "uncertainty": terms["diagnose"] / wU if wU else 0.0,
                "retention": terms["consolidate"] / wR if wR else 0.0,
                "transfer": terms["deploy"] / wT if wT else 0.0,
                "penalty": c["penalty"],
                "V": c["V"],
            },
            runner_up_drive=runner_up_drive,
            margin=margin,
            content_gaps=gaps,
            created_at=now,
        )
        ranked.append((spec, receipt))
    return ranked
