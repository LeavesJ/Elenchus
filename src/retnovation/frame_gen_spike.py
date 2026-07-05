"""The frame-generation spike (spec 2026-07-05-frame-generation-spike-design): a go/no-go
experiment measuring whether a model can generate lift-passing frames for novel problems (Arm 1)
while mush is rejected (Arm 2). Reuses run_lift_test unchanged; only the generator is new."""

from __future__ import annotations

import json
from pathlib import Path

from .content_loader import load_library, load_mush_frames
from .lift_test import run_lift_test
from .types import CandidateFrame, LiftScenario, Regime


class _SpikeModel:
    """Wrap the real model so the lift test's `generate_output` gets a DECISION-sized token budget
    (L-17: the lift helper's 1024 default was tuned for SP1's short pitch outputs; decision-reasoning
    scenarios plus adaptive thinking overrun it and return no text block). Everything else delegates
    to the wrapped model unchanged."""

    def __init__(self, model, max_tokens: int = 4096):
        self._m = model
        self._max = max_tokens

    def generate_output(self, prompt, injection, *, max_tokens=None):
        return self._m.generate_output(prompt, injection, max_tokens=self._max)

    def __getattr__(self, name):
        return getattr(self._m, name)


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
    model = _SpikeModel(model)  # decision-sized generate_output budget (L-17)
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
    model = _SpikeModel(model)  # decision-sized generate_output budget (L-17)
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


PROBLEMS = [
    "I set the subscription tiers for our AI-agent software in a saturated market. What pricing "
    "move pulls the most customers without starving revenue — and doesn't just get matched and "
    "erased by a bigger incumbent?",
    "My technical co-founder wants to hand our biggest customer's integration support to a junior "
    "engineer so the seniors can ship the launch. I don't trust the junior on it, but I can't have "
    "my best people babysitting one account. Do I overrule my co-founder?",
    "We connect indie designers with small brands; neither side shows up without the other. "
    "Subsidize the designers, subsidize the brands, or fake liquidity on one side first — which?",
    "A larger company wants to integrate our tech into their platform — huge distribution, but it "
    "hands them the data and know-how that is our actual advantage; they could build their own "
    "version in a year. Take the deal?",
    "We can ship a clearly-valuable feature that sits in a regulatory gray area; the rules will "
    "probably tighten in 12-18 months. Move now and grab the market before it closes, or wait for "
    "clarity and cede first-mover advantage?",
]


def main(out_path: str = "/tmp/frame_gen_spike_report.md") -> None:  # pragma: no cover (@live)
    from .model import AnthropicModel

    model = AnthropicModel()
    config = {"theta_dist": 1, "min_scenarios": 2}
    art = "/tmp/frame_gen_spike_artifacts"
    arm1 = run_arm(PROBLEMS, model, config, out_dir=art)
    mush_scenarios = model.generate_scenarios(PROBLEMS[0])  # a real decision for the teeth test
    mush = run_mush_arm(load_mush_frames(), mush_scenarios, model, config, out_dir=art)
    report = format_report(arm1, mush)
    Path(out_path).write_text(report)
    a1 = sum(_pass(r) for r in arm1)
    print(f"Arm 1: {a1}/{len(arm1)} passed | Arm 2 mush: {sum(_pass(r) for r in mush)}/{len(mush)}")
    print(f"report -> {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
