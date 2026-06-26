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


def test_adjudication_packet_shows_both_axes_and_outputs(tmp_path):
    from retnovation.admission import format_adjudication_packet

    result = screen_candidate(
        _candidate(),
        [
            LiftScenario(
                scenario_id="s1", prompt="p1", posture="founder_ceo", candidate="cap_effort"
            ),
            LiftScenario(
                scenario_id="s2", prompt="p2", posture="founder_ceo", candidate="cap_effort"
            ),
        ],
        _fake(),
        order={"s1": "AB", "s2": "AB"},
        config=CFG,
        out_dir=tmp_path,
    )
    packet = format_adjudication_packet(_candidate(), result)
    assert "mean_distinguishability" in packet and "mean_preference" in packet
    assert "below_floor" in packet  # advisory floor surfaced for the human (m3)
    assert "framed1" in packet and "control1" in packet  # verbatim outputs for the human
    assert "kd1" in packet  # rater's key_difference


def test_admission_record_yaml_round_trips():
    from retnovation.admission import format_admission_record
    from retnovation.types import AdmissionRecord, AdmittedAs, Gates, Provenance, ScreenSummary

    rec = AdmissionRecord(
        frame_code="cap_effort",
        posture="founder_ceo",
        provenance=Provenance(source_type="owned", pointer="BIZLOG 2026-05-28"),
        screen=ScreenSummary(
            verdict="lift",
            screen_action="surface",
            mean_distinguishability=2.0,
            mean_preference=1.0,
            framed_preferred_count=2,
            data_ref="data/lift/screen_cap_effort.json",
        ),
        gates=Gates(
            surface_independence="pass",
            atomicity="pass",
            orthogonality="pass",
            falsifiable_application="pass",
            trainable_cognition="pass",
        ),
        nearest_sibling="protect_the_core_lane",
        separating_artifact="a pre-committed stop rule",
        decision="admit_provisional",
        rationale="lifts on both; sales-persistence reflex inverted",
        admitted_as=AdmittedAs(
            experience_id="prospect_focus",
            ledger_ref="veldra:first_customer_proof_loop",
        ),
    )
    text = format_admission_record(rec)
    import yaml

    reloaded = AdmissionRecord(**yaml.safe_load(text))
    assert reloaded.model_dump() == rec.model_dump()
    assert "marginal_lift: pass" in text  # derived view rendered for humans
