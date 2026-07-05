"""The frame-generation spike (spec 2026-07-05-frame-generation-spike-design): a go/no-go
experiment measuring whether a model can generate lift-passing frames for novel problems (Arm 1)
while mush is rejected (Arm 2). Reuses run_lift_test unchanged; only the generator is new."""

from __future__ import annotations

import json
from pathlib import Path

from .content_loader import load_library
from .lift_test import run_lift_test
from .types import CandidateFrame, LiftScenario, Regime


def curated_exemplars() -> str:
    """Render the 5 curated rubrics' frames as exemplar text for the generator (the STANDARD)."""
    lines: list[str] = []
    for e in load_library():
        if e.regime is not Regime.open_ended or e.rubric is None:
            continue
        for f in e.rubric.frames:
            lines.append(f"- {f.frame_code}: {f.frame_detail}")
    return "\n".join(lines)


def _order(scenarios: list[LiftScenario]) -> dict[str, str]:
    # Fixed A/B randomization map (deterministic for the spike): alternate AB/BA by index.
    return {s.scenario_id: ("AB" if i % 2 == 0 else "BA") for i, s in enumerate(scenarios)}


def _lift_rows(prob_id, prob, frames, scenarios, model, config, out_dir):
    rows = []
    order = _order(scenarios)
    for cand in frames:
        result = run_lift_test(cand, scenarios, model, order, config)
        (Path(out_dir) / f"screen_{cand.frame_code}.json").write_text(
            json.dumps(result.model_dump(), indent=2)
        )
        rows.append(
            {
                "problem": prob_id,
                "frame_code": cand.frame_code,
                "frame_detail": cand.frame_detail,
                "verdict": result.verdict,
                "mean_pref": round(result.mean_preference, 2),
                "mean_dist": round(result.mean_distinguishability, 2),
                "framed_preferred": result.framed_preferred_count,
                "below_floor": result.below_floor,
                "scenarios": [
                    {
                        "framed": s.framed_output,
                        "control": s.control_output,
                        "key_difference": s.key_difference,
                    }
                    for s in result.scenarios
                ],
            }
        )
    return rows


def run_arm(problems, model, config, *, out_dir):
    """Arm 1: per problem, generate frames + scenarios, lift-test each frame."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    exemplars = curated_exemplars()
    rows = []
    for i, prob in enumerate(problems):
        frames = model.generate_frames(prob, exemplars)
        prompts = model.generate_scenarios(prob)
        scenarios = [
            LiftScenario(scenario_id=f"p{i}_s{j}", prompt=p, posture="spike")
            for j, p in enumerate(prompts)
        ]
        rows += _lift_rows(f"p{i}", prob, frames, scenarios, model, config, out_dir)
    return rows


def run_mush_arm(mush, scenarios_prompts, model, config, *, out_dir):
    """Arm 2: run each mush frame against a FIXED real problem's scenarios (teeth test)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    frames = [CandidateFrame(**m) for m in mush]
    scenarios = [
        LiftScenario(scenario_id=f"mush_s{j}", prompt=p, posture="spike")
        for j, p in enumerate(scenarios_prompts)
    ]
    return _lift_rows("mush", "(mush control)", frames, scenarios, model, config, out_dir)


def _pass(row) -> bool:
    return row["verdict"] == "lift"


def format_report(arm1, mush) -> str:
    a1_pass = sum(_pass(r) for r in arm1)
    mush_pass = sum(_pass(r) for r in mush)
    lines = [
        "# Frame-Generation Spike — results",
        "",
        "## Summary",
        f"- Arm 1 (generated): {a1_pass}/{len(arm1)} frames passed (verdict==lift)",
        f"- Arm 2 (mush): {mush_pass}/{len(mush)} frames passed  <-- must be MUCH lower (teeth)",
        "- Novel vs convergent-on-the-5: (founder fills, per passing frame below)",
        "",
        "## Arm 1 — generated frames",
    ]
    for r in arm1 + [{"_hdr": "## Arm 2 — mush control"}] + mush:
        if "_hdr" in r:
            lines += ["", r["_hdr"]]
            continue
        lines += [
            "",
            f"### [{r['problem']}] {r['frame_code']} — verdict={r['verdict']} "
            f"pref={r['mean_pref']} dist={r['mean_dist']} framed_preferred={r['framed_preferred']}"
            f"{' (below_floor)' if r['below_floor'] else ''}",
            f"move: {r['frame_detail']}",
        ]
        for s in r["scenarios"]:
            lines += [
                f"  - key_difference: {s['key_difference']}",
                f"    FRAMED: {s['framed'][:400]}",
                f"    CONTROL: {s['control'][:400]}",
            ]
    return "\n".join(lines)
