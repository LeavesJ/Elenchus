"""The frame-generation spike (spec 2026-07-05-frame-generation-spike-design): a go/no-go
experiment measuring whether a model can generate lift-passing frames for novel problems (Arm 1)
while mush is rejected (Arm 2). Reuses run_lift_test unchanged; only the generator is new."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .content_loader import load_library, load_mush_frames
from .lift_test import run_lift_test
from .types import CandidateFrame, LiftScenario, PreferenceRating, Regime


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

    def rate_preference(self, scenario_prompt, output_a, output_b):
        # The model sometimes returns a non-tie preference with magnitude 0 ("difference is
        # minimal"), which passes the JSON schema but fails PreferenceRating's cross-field validator.
        # Retry once, then coerce to a CONSERVATIVE tie (no lift credited) so one bad rating can't
        # nuke the experiment.
        for _ in range(2):
            try:
                return self._m.rate_preference(scenario_prompt, output_a, output_b)
            except ValidationError:
                continue
        return PreferenceRating(
            distinguishability=0, preferred="tie", magnitude=0, key_difference="(coerced tie)"
        )

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


def _curated_frames() -> list[tuple[str, str]]:
    """The 5 curated frames as (frame_code, frame_detail) — the novelty gate's comparison set."""
    seen: dict[str, str] = {}
    for e in load_library():
        if e.regime is not Regime.open_ended or e.rubric is None:
            continue
        for f in e.rubric.frames:
            seen.setdefault(f.frame_code, f.frame_detail)
    return list(seen.items())


def _order(scenarios: list[LiftScenario]) -> dict[str, str]:
    # Fixed A/B randomization map (deterministic for the spike): alternate AB/BA by index.
    return {s.scenario_id: ("AB" if i % 2 == 0 else "BA") for i, s in enumerate(scenarios)}


def _categorize(result):
    """Both axes, manipulation-check applied (review fold): a frame is read on distinguishability
    AND signed preference over ONLY the scenarios where the injection was EXPRESSED. Errors/
    all-inconclusive are pulled out of the denominator; depreciation (dist+/pref-, the model already
    does the move) is separated from invisible (dist<theta) and from the mush-band boundary."""
    theta = result.theta_dist
    valid = [s for s in result.scenarios if s.injection_expressed]
    incon = result.inconclusive_count
    if not valid:
        return "INCONCLUSIVE(no valid injection)", 0, incon
    statuses = [s.status(theta) for s in valid]
    if all(x == "lift" for x in statuses):
        return (
            ("HARD-LIFT" if not result.below_floor else f"lift(below_floor n={len(valid)})"),
            len(valid),
            incon,
        )
    if result.mean_distinguishability < theta:
        return "INVISIBLE(null)", len(valid), incon
    if result.mean_preference < 0:
        return "DEPRECIATION(dist+/pref-)", len(valid), incon
    return "BOUNDARY(mush-band)", len(valid), incon


def _lift_rows(prob_id, prob, frames, scenarios, model, config, out_dir):
    rows = []
    order = _order(scenarios)
    for cand in frames:
        try:  # a single frame's failure (529, an odd parse) must not kill the whole experiment
            result = run_lift_test(cand, scenarios, model, order, config)
        except Exception as exc:  # noqa: BLE001 — experiment resilience; the row records the class
            rows.append(
                {
                    "problem": prob_id,
                    "frame_code": cand.frame_code,
                    "frame_detail": cand.frame_detail,
                    "category": f"INCONCLUSIVE(errored: {type(exc).__name__})",
                    "mean_pref": None,
                    "mean_dist": None,
                    "valid": 0,
                    "inconclusive": None,
                    "verdict": None,  # 3-way; filled by the novelty GATE for HARD-LIFT frames
                    "nearest": None,  # curated anchor (a novel row's nearest is NOT a partial match)
                    "restates_nearest": None,
                    "rationale": None,
                    "scenarios": [],
                }
            )
            continue
        (Path(out_dir) / f"screen_{cand.frame_code}.json").write_text(
            json.dumps(result.model_dump(), indent=2)
        )
        category, valid, incon = _categorize(result)
        rows.append(
            {
                "problem": prob_id,
                "frame_code": cand.frame_code,
                "frame_detail": cand.frame_detail,
                "category": category,
                "mean_pref": round(result.mean_preference, 2),  # SIGNED — carried as its own axis
                "mean_dist": round(result.mean_distinguishability, 2),
                "valid": valid,
                "inconclusive": incon,
                "verdict": None,  # 3-way; filled by the novelty GATE for HARD-LIFT frames
                "nearest": None,  # curated anchor (a novel row's nearest is NOT a partial match)
                "restates_nearest": None,
                "rationale": None,
                "scenarios": [
                    {
                        "expressed": s.injection_expressed,  # per-scenario manipulation check
                        "dist": s.distinguishability if s.injection_expressed else None,
                        "pref": s.preference if s.injection_expressed else None,
                        "framed": s.framed_output,
                        "control": s.control_output,
                        "key_difference": s.key_difference,
                    }
                    for s in result.scenarios
                ],
            }
        )
    return rows


def _apply_novelty_gate(rows, model):
    """The novelty GATE (M2 honest 3-way): for HARD-LIFT frames, get the directional restates_nearest
    call at SYMMETRIC confidence and DERIVE the verdict HERE — never returned by the model (L-1 seam).
    Uncertainty AND ungated/error rows both HOLD; the ONLY path to 'novel' is
    restates_nearest=false & confidence=high (fail-safe, L-13/L-30)."""
    curated = _curated_frames()
    for r in rows:
        if r["category"] != "HARD-LIFT":
            continue  # errored/inconclusive/boundary rows keep verdict=None -> never 'novel'
        c = model.frame_convergence(r["frame_detail"], curated)
        r["nearest"] = c.nearest
        r["restates_nearest"] = c.restates_nearest
        r["rationale"] = c.rationale
        if c.confidence == "high" and c.restates_nearest:
            r["verdict"] = "convergent"
        elif c.confidence == "high" and not c.restates_nearest:
            r["verdict"] = "novel"  # confidently distinct — the new positive signal
        else:  # confidence == "low" (either direction) -> HOLD for the human adjudicator
            r["verdict"] = "uncertain"
    # L-28/L-1: every gated hard-lift row is scored with exactly one 3-way verdict
    for r in rows:
        if r["category"] == "HARD-LIFT":
            assert r.get("verdict") in ("convergent", "novel", "uncertain"), (
                "novelty gate left a hard-lift row unscored"
            )
    return rows


def run_arm(problems, model, config, *, out_dir):
    """Arm 1: per problem, generate frames + scenarios, lift-test each frame, novelty-gate the
    hard-lift survivors."""
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
    return _apply_novelty_gate(rows, model)


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


def _is_hard_lift(row) -> bool:
    return row["category"] == "HARD-LIFT"


def _is_inconclusive(row) -> bool:
    return row["category"].startswith("INCONCLUSIVE")


def _summary(rows) -> dict:
    """The corrected numbers: the denominator EXCLUDES inconclusive/errored (they measured nothing);
    the operative go count is HARD-LIFT ∧ CONFIDENTLY-NOVEL; convergent and uncertain are their own
    buckets (L-28). Ungated rows (the mush arm never runs the gate) carry verdict=None: the mush arm
    is intentionally ungated, so `hard_lift_unscored` is the L-28 no-hidden-bucket guard — in a GATED
    arm it is 0 (the per-row assert in `_apply_novelty_gate` guarantees it), and any nonzero value in
    Arm 1 would surface a gating drift instead of hiding it."""
    valid = [r for r in rows if not _is_inconclusive(r)]
    hard = [r for r in valid if _is_hard_lift(r)]
    return {
        "total": len(rows),
        "denominator": len(valid),
        "inconclusive": len(rows) - len(valid),
        "hard_lift": len(hard),
        "hard_lift_novel": sum(1 for r in hard if r.get("verdict") == "novel"),
        "hard_lift_convergent": sum(1 for r in hard if r.get("verdict") == "convergent"),
        "hard_lift_uncertain": sum(1 for r in hard if r.get("verdict") == "uncertain"),
        "hard_lift_unscored": sum(
            1 for r in hard if r.get("verdict") not in ("novel", "convergent", "uncertain")
        ),
        "depreciation": sum(1 for r in valid if r["category"].startswith("DEPRECIATION")),
        "boundary": sum(1 for r in valid if r["category"].startswith("BOUNDARY")),
    }


def format_report(arm1, mush) -> str:
    a1, m2 = _summary(arm1), _summary(mush)
    lines = [
        "# Frame-Generation Spike — results (both axes; manipulation-check applied)",
        "",
        "## Summary",
        f"- Arm 1 (generated): denominator {a1['denominator']} "
        f"(excl {a1['inconclusive']} inconclusive/errored)",
        f"    HARD-LIFT (robust, all valid scenarios lift): {a1['hard_lift']}",
        f"    HARD-LIFT ∧ CONFIDENTLY-NOVEL (auto-go candidate): {a1['hard_lift_novel']}",
        f"    HARD-LIFT ∧ CONVERGENT (adds no doctrine): {a1['hard_lift_convergent']}",
        f"    HARD-LIFT ∧ UNCERTAIN (HELD for human adjudication — never auto-admitted): "
        f"{a1['hard_lift_uncertain']}",
        f"    DEPRECIATION (dist+/pref-, Opus already does it): {a1['depreciation']}  |  "
        f"BOUNDARY (mush-band): {a1['boundary']}",
        f"- Arm 2 (mush): HARD-LIFT {m2['hard_lift']}/{m2['denominator']} (teeth: 0 = clean); "
        f"BOUNDARY {m2['boundary']} + DEPRECIATION {m2['depreciation']} — the SAME bands as Arm 1's "
        "non-hard-lift, i.e. the gate only separates at the hard-lift cluster.",
    ]
    if a1["hard_lift_unscored"]:
        lines.append(
            f"    HARD-LIFT ∧ UNSCORED (not gated — a gating drift for Arm 1): {a1['hard_lift_unscored']}"
        )
    lines += [
        "",
        "## Arm 1 — generated frames",
    ]
    for r in arm1 + [{"_hdr": "## Arm 2 — mush control"}] + mush:
        if "_hdr" in r:
            lines += ["", r["_hdr"]]
            continue
        vrd = f" verdict={r['verdict']}" if r.get("verdict") else ""
        lines += [
            "",
            f"### [{r['problem']}] {r['frame_code']} — {r['category']}"
            f" pref={r['mean_pref']} dist={r['mean_dist']} valid={r['valid']}"
            f" inconclusive={r['inconclusive']}{vrd}",
            f"move: {r['frame_detail']}",
        ]
        if r.get("verdict"):
            lines.append(
                f"novelty: {r['verdict']} (nearest ~{r.get('nearest')}) — {r.get('rationale')}"
            )
        for s in r["scenarios"]:
            exp = "expressed" if s["expressed"] else "NOT-EXPRESSED(inconclusive)"
            axes = f"dist={s['dist']} pref={s['pref']}" if s["expressed"] else ""
            lines += [
                f"  - [{exp}] {axes}  key_difference: {s['key_difference']}",
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
    a1, m2 = _summary(arm1), _summary(mush)
    print(
        f"Arm 1: HARD-LIFT {a1['hard_lift']}, HARD-LIFT∧NOVEL {a1['hard_lift_novel']} "
        f"(denominator {a1['denominator']}) | Arm 2 mush HARD-LIFT {m2['hard_lift']}/{m2['denominator']}"
    )
    print(f"report -> {out_path}")


if __name__ == "__main__":  # pragma: no cover
    main()
