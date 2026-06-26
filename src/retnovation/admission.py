from __future__ import annotations

import json
from pathlib import Path

import yaml

from .lift_test import run_lift_test
from .types import AdmissionRecord, Experience, LiftResult, MinedCandidate


def screen_candidate(
    candidate: MinedCandidate,
    scenarios,
    model,
    order: dict[str, str],
    config: dict,
    *,
    out_dir: str | Path,
) -> LiftResult:
    """Run the blind-lift screen for one candidate and persist the raw result.

    Filters the flat scenario bank to this candidate (by the `candidate` tag), runs the
    SP1 harness, and writes the LiftResult JSON to out_dir/screen_{frame_code}.json so an
    expensive @live run is never lost. Returns the LiftResult.
    """
    cand_scenarios = [s for s in scenarios if s.candidate == candidate.frame_code]
    result = run_lift_test(candidate.to_candidate_frame(), cand_scenarios, model, order, config)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"screen_{candidate.frame_code}.json").write_text(
        json.dumps(result.model_dump(), indent=2)
    )
    return result


def format_adjudication_packet(candidate: MinedCandidate, result: LiftResult) -> str:
    """Human-readable markdown for adjudicating one screened candidate.

    Surfaces BOTH screen axes plus, per scenario, the verbatim framed/control outputs and the
    rater's key-difference — so the surface_independence call is made with the evidence, not blind.
    """
    lines = [
        f"# Adjudication — {candidate.frame_code}",
        f"hypothesis: {candidate.hypothesis}",
        f"nearest_sibling: {candidate.nearest_sibling}",
        f"separating_artifact: {candidate.separating_artifact}",
        "",
        f"verdict: {result.verdict}    screen_action: {result.screen_action}",
        f"mean_distinguishability: {result.mean_distinguishability:.2f}    "
        f"mean_preference: {result.mean_preference:.2f}    "
        f"framed_preferred_count: {result.framed_preferred_count}    "
        f"below_floor: {result.below_floor}",  # advisory: fewer valid scenarios than min_scenarios
        "",
        "## Per-scenario",
    ]
    for s in result.scenarios:
        lines += [
            f"### {s.scenario_id} — status={s.status(result.theta_dist)} "
            f"dist={s.distinguishability} pref={s.preference}",
            f"key_difference: {s.key_difference}",
            f"framed_refused={s.framed_refused}  control_refused={s.control_refused}",
            "FRAMED:",
            s.framed_output,
            "CONTROL:",
            s.control_output,
            "",
        ]
    return "\n".join(lines)


def format_admission_record(record: AdmissionRecord) -> str:
    """Serialize an AdmissionRecord to committable YAML (derived marginal_lift included)."""
    return yaml.safe_dump(record.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


def check_content_graph_integrity(
    experiences: list[Experience],
    process_frames: list[str],
    valid_ledger_refs: set[str],
    records: list[AdmissionRecord],
) -> None:
    """Assert the three-file admit edit is referentially intact BEFORE the gated path runs.

    A ledger_ref typo or duplicate experience_id surfaces here as a named assertion, not as an
    opaque failure deep in select/assess (spec §8, seam 3).
    """
    ids = [e.experience_id for e in experiences]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate experience_id: {dupes}")
    by_id = {e.experience_id: e for e in experiences}
    for e in experiences:
        if e.ledger_ref not in valid_ledger_refs:
            raise ValueError(
                f"experience {e.experience_id!r} ledger_ref {e.ledger_ref!r} does not resolve"
            )
    pf = set(process_frames)
    for r in records:
        if r.decision != "admit_provisional" or r.admitted_as is None:
            continue
        aa = r.admitted_as
        if aa.experience_id not in by_id:
            raise ValueError(
                f"admission {r.frame_code!r}: admitted_as.experience_id does not resolve"
            )
        exp = by_id[aa.experience_id]
        if aa.ledger_ref != exp.ledger_ref:
            raise ValueError(f"admission {r.frame_code!r}: admitted_as.ledger_ref mismatch")
        if r.frame_code not in pf:
            raise ValueError(f"admitted frame {r.frame_code!r} not in process_frames")
        rubric_frames = {f.frame_code for f in (exp.rubric.frames if exp.rubric else [])}
        if r.frame_code not in rubric_frames:
            raise ValueError(
                f"admitted frame {r.frame_code!r} not in rubric of {exp.experience_id!r}"
            )
