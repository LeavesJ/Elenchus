import json

from retnovation.admission import screen_candidate
from retnovation.model import FakeLiftModel
from retnovation.types import (
    GeneratedOutput,
    InjectionExpressed,
    LiftResult,
    LiftScenario,
    MinedCandidate,
    PreferenceRating,
    Provenance,
)

CFG = {"theta_dist": 1, "min_scenarios": 2}


def _candidate():
    return MinedCandidate(
        frame_code="cap_effort",
        frame_detail="d",
        injection="INJ",
        posture="founder_ceo",
        hypothesis="model over-persists",
        nearest_sibling=None,
        separating_artifact="stop rule",
        provenance=Provenance(pointer="BIZLOG 2026-05-28"),
    )


def _fake():
    outputs = {
        ("p1", False): GeneratedOutput(text="control1"),
        ("p1", True): GeneratedOutput(text="framed1"),
        ("p2", False): GeneratedOutput(text="control2"),
        ("p2", True): GeneratedOutput(text="framed2"),
    }
    ratings = {
        "p1": PreferenceRating(
            distinguishability=2, preferred="A", magnitude=1, key_difference="kd1"
        ),
        "p2": PreferenceRating(
            distinguishability=2, preferred="A", magnitude=1, key_difference="kd2"
        ),
    }
    expressed = {
        "framed1": InjectionExpressed(expressed=True, evidence="e"),
        "framed2": InjectionExpressed(expressed=True, evidence="e"),
    }
    return FakeLiftModel(outputs=outputs, ratings=ratings, expressed=expressed)


def test_screen_candidate_filters_persists_and_returns(tmp_path):
    scenarios = [
        LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo", candidate="cap_effort"),
        LiftScenario(scenario_id="s2", prompt="p2", posture="founder_ceo", candidate="cap_effort"),
        LiftScenario(
            scenario_id="s3", prompt="other", posture="founder_ceo", candidate="someone_else"
        ),
    ]
    result = screen_candidate(
        _candidate(),
        scenarios,
        _fake(),
        order={"s1": "AB", "s2": "AB"},
        config=CFG,
        out_dir=tmp_path,
    )
    assert result.verdict == "lift" and len(result.scenarios) == 2  # s3 filtered out
    path = tmp_path / "screen_cap_effort.json"
    assert path.exists()
    reloaded = LiftResult(**json.loads(path.read_text()))
    assert reloaded.verdict == "lift"
