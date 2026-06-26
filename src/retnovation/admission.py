from __future__ import annotations

import json
from pathlib import Path

from .lift_test import run_lift_test
from .types import LiftResult, MinedCandidate


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
