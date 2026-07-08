import os

import pytest

from retnovation.content_loader import load_mush_frames, load_spike_prompt
from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import (
    CandidateFrame,
    ConvergenceCheck,
    GeneratedOutput,
    InjectionExpressed,
    PreferenceRating,
)


def _fake(**kw):
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})
    for k, v in kw.items():
        setattr(m, f"_{k}", v)
    return m


def test_mush_frames_load_and_validate():
    mush = load_mush_frames()
    assert len(mush) >= 6
    for f in mush:
        assert f["frame_code"] and f["frame_detail"] and f["injection"]
    codes = [f["frame_code"] for f in mush]
    assert len(codes) == len(set(codes))  # unique codes


def test_frame_gen_doctrine_forbids_mush():
    p = load_spike_prompt("frame_gen").lower()
    # the generator must demand non-obvious hidden moves and forbid generic advice (L-6)
    assert "hidden move" in p or "non-obvious" in p
    assert "generic advice" in p or "recognize the type" in p or "homework" in p


def test_frame_novelty_doctrine_judges_the_move_not_the_topic():
    p = load_spike_prompt("frame_novelty").lower()
    assert "move" in p and ("restate" in p or "same move" in p)


def test_frame_novelty_doctrine_is_symmetric_and_names_rationale():
    """M2 fold 1: the prompt must make confidence earnable in BOTH directions and require a
    rationale + a whole-list necessity bar — else the model keeps emitting the one-sided low (L-30)."""
    p = load_spike_prompt("frame_novelty").lower()
    # symmetric confidence — high reachable on a NON-restatement too
    assert "either direction" in p or "either way" in p
    assert "different is a high-confidence answer" in p
    # the directional rationale field
    assert "rationale" in p
    # the necessity bar + whole-list guard (founder decision 1)
    assert "necessary" in p and "whole" in p
    # the mandatory 3-field return contract + the uncertain branch
    assert "restates_nearest" in p and "nearest" in p


def test_fakemodel_frame_convergence_default_and_scripted():
    assert _fake().frame_convergence("d", [("c", "cd")]).maps_to_existing is False
    scripted = ConvergenceCheck(maps_to_existing=True, nearest="c", confidence="high")
    assert _fake(convergence=scripted).frame_convergence("d", [("c", "cd")]) == scripted


def test_fakemodel_generate_frames_returns_candidate_frames():
    scripted = [CandidateFrame(frame_code="c1", frame_detail="d", injection="inj")]
    m = _fake(frames=scripted)
    assert m.generate_frames("a problem", "exemplars") == scripted


def test_fakemodel_generate_frames_default_empty():
    assert _fake().generate_frames("p", "e") == []


def test_fakemodel_generate_scenarios_returns_prompts():
    m = _fake(scenarios=["scenario one", "scenario two"])
    assert m.generate_scenarios("p") == ["scenario one", "scenario two"]


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="no key")
def test_live_generate_scenarios_returns_prompts():
    from retnovation.model import AnthropicModel

    out = AnthropicModel().generate_scenarios(
        "You must set the subscription price for your software in a saturated market. Decide."
    )
    assert 2 <= len(out) <= 4 and all(isinstance(s, str) and s.strip() for s in out)


class FakeSpikeModel:
    """Scripts every call the harness makes: the framed output ('FRAMED') is preferred + distinct,
    so the offline test exercises a deterministic `lift` verdict with NO API (L-22)."""

    def __init__(self, frames):
        self._frames = frames

    def generate_frames(self, problem, exemplars):
        return self._frames

    def generate_scenarios(self, problem):
        return ["decision scenario A", "decision scenario B"]

    def generate_output(self, prompt, injection, *, max_tokens=1024):
        return GeneratedOutput(text=("FRAMED" if injection else "CONTROL"), refused=False)

    def check_injection_expressed(self, injection, framed_output):
        return InjectionExpressed(expressed=True, evidence="e")

    def rate_preference(self, prompt, output_a, output_b):
        framed_is_a = output_a == "FRAMED"
        return PreferenceRating(
            distinguishability=2,
            preferred="A" if framed_is_a else "B",
            magnitude=2,
            key_difference="k",
        )

    def frame_convergence(self, frame_detail, curated):
        return ConvergenceCheck(maps_to_existing=False, nearest="", confidence="low")


def test_curated_exemplars_renders_the_five():
    from retnovation.frame_gen_spike import curated_exemplars

    ex = curated_exemplars()
    assert len(ex.strip()) > 50  # non-empty exemplar text derived from the curated library


def test_run_arm_produces_lift_verdicts(tmp_path):
    from retnovation.frame_gen_spike import run_arm

    frames = [CandidateFrame(frame_code="good", frame_detail="d", injection="inj")]
    rows = run_arm(
        ["a problem"],
        FakeSpikeModel(frames),
        {"theta_dist": 1, "min_scenarios": 2},
        out_dir=str(tmp_path),
    )
    assert len(rows) == 1
    assert rows[0]["frame_code"] == "good"
    assert rows[0]["category"] == "HARD-LIFT"  # all valid scenarios lift, >= min_scenarios
    assert rows[0]["novelty"] == "novel"  # the novelty gate ran (fake maps low-confidence)
    assert rows[0]["scenarios"][0]["expressed"] is True  # per-scenario manipulation check surfaced
    assert (tmp_path / "screen_good.json").exists()  # persisted (L-24 resume)


def test_format_report_has_both_arms(tmp_path):
    from retnovation.frame_gen_spike import format_report, run_arm

    frames = [CandidateFrame(frame_code="good", frame_detail="d", injection="inj")]
    arm1 = run_arm(
        ["p"], FakeSpikeModel(frames), {"theta_dist": 1, "min_scenarios": 2}, out_dir=str(tmp_path)
    )
    report = format_report(arm1, arm1)  # reuse arm1 as a stand-in mush arm for the shape test
    assert "Arm 1" in report and "Arm 2" in report and "HARD-LIFT" in report
    assert "HARD-LIFT ∧ NOVEL" in report  # the corrected go count is surfaced


def test_summary_excludes_errors_and_counts_hard_lift_novel():
    """The corrected numbers (review fold): errored/inconclusive out of the denominator; the go
    count is HARD-LIFT ∧ NOVEL, not a lift bool."""
    from retnovation.frame_gen_spike import _summary

    rows = [
        {"category": "HARD-LIFT", "novelty": "novel"},
        {"category": "HARD-LIFT", "novelty": "convergent(~x)"},
        {"category": "DEPRECIATION(dist+/pref-)", "novelty": None},
        {"category": "BOUNDARY(mush-band)", "novelty": None},
        {"category": "INCONCLUSIVE(errored: ModelError)", "novelty": None},
    ]
    s = _summary(rows)
    assert s["denominator"] == 4  # the errored row is out of the denominator
    assert s["hard_lift"] == 2 and s["hard_lift_novel"] == 1  # only the NOVEL hard-lift counts
    assert s["depreciation"] == 1 and s["boundary"] == 1


def test_spike_problem_set_is_wellformed():
    from retnovation.frame_gen_spike import PROBLEMS

    assert 4 <= len(PROBLEMS) <= 6
    assert all(isinstance(p, str) and len(p.strip()) > 40 for p in PROBLEMS)


def test_spikemodel_wrapper_enlarges_budget_and_delegates():
    """L-17: the wrapper hands generate_output a decision-sized budget; everything else delegates."""
    from retnovation.frame_gen_spike import _SpikeModel

    seen = {}

    class M:
        def generate_output(self, prompt, injection, *, max_tokens=1024):
            seen["mt"] = max_tokens
            return GeneratedOutput(text="x")

        def other(self):
            return "delegated"

    w = _SpikeModel(M(), max_tokens=4096)
    w.generate_output("p", "inj")
    assert seen["mt"] == 4096  # enlarged budget passed through
    assert w.other() == "delegated"  # everything else delegates


def test_spikemodel_rate_preference_coerces_invalid_to_tie():
    """The model sometimes emits a non-tie preference with magnitude 0 (fails the cross-field
    validator); the wrapper retries then coerces to a conservative tie rather than crashing."""
    from retnovation.frame_gen_spike import _SpikeModel

    class M:
        def rate_preference(self, prompt, a, b):
            # constructing this raises ValidationError (magnitude 0 with a non-tie preference)
            return PreferenceRating(
                distinguishability=1, preferred="A", magnitude=0, key_difference="x"
            )

    out = _SpikeModel(M()).rate_preference("p", "a", "b")
    assert out.preferred == "tie" and out.magnitude == 0


def test_run_arm_records_error_row_on_frame_failure(tmp_path):
    """A single frame's failure records an error row and does not kill the run (experiment resilience)."""
    from retnovation.frame_gen_spike import run_arm

    class Boom:
        def generate_frames(self, p, e):
            return [CandidateFrame(frame_code="boom", frame_detail="d", injection="i")]

        def generate_scenarios(self, p):
            return ["s1", "s2"]

        def generate_output(self, prompt, injection, *, max_tokens=1024):
            raise RuntimeError("boom")

    rows = run_arm(["p"], Boom(), {"theta_dist": 1, "min_scenarios": 2}, out_dir=str(tmp_path))
    assert len(rows) == 1 and rows[0]["category"].startswith("INCONCLUSIVE(errored")
