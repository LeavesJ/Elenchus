import os

import pytest

from retnovation.content_loader import load_mush_frames, load_spike_prompt
from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import (
    CandidateFrame,
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
    assert rows[0]["verdict"] == "lift"  # framed preferred + distinguishable across scenarios
    assert (tmp_path / "screen_good.json").exists()  # persisted (L-24 resume)


def test_format_report_has_both_arms(tmp_path):
    from retnovation.frame_gen_spike import format_report, run_arm

    frames = [CandidateFrame(frame_code="good", frame_detail="d", injection="inj")]
    arm1 = run_arm(
        ["p"], FakeSpikeModel(frames), {"theta_dist": 1, "min_scenarios": 2}, out_dir=str(tmp_path)
    )
    report = format_report(arm1, arm1)  # reuse arm1 as a stand-in mush arm for the shape test
    assert "Arm 1" in report and "Arm 2" in report and "lift" in report
