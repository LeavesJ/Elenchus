from retnovation.content_loader import load_mush_frames, load_spike_prompt
from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import CandidateFrame


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
