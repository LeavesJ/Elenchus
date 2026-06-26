import json

import pytest

from retnovation.admission import check_content_graph_integrity, screen_candidate
from retnovation.model import FakeLiftModel
from retnovation.types import (
    AdmissionRecord,
    AdmittedAs,
    Experience,
    Frame,
    Gates,
    GeneratedOutput,
    InjectionExpressed,
    LiftResult,
    LiftScenario,
    MinedCandidate,
    Mode,
    PreferenceRating,
    Provenance,
    Regime,
    Rubric,
    ScreenSummary,
    Trap,
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
    assert "mean_distinguishability: 2.00" in packet  # pin axis value (not just label)
    assert "mean_preference: 1.00" in packet  # pin axis value (not just label)
    assert "below_floor" in packet  # advisory floor surfaced for the human (m3)
    assert "framed1" in packet and "control1" in packet  # verbatim outputs for the human
    assert "kd1" in packet  # rater's key_difference


def test_admission_record_yaml_round_trips():
    from retnovation.admission import format_admission_record

    import yaml

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
    reloaded = AdmissionRecord(**yaml.safe_load(text))
    assert reloaded.model_dump() == rec.model_dump()
    assert "marginal_lift: pass" in text  # derived view rendered for humans


# ---------------------------------------------------------------------------
# check_content_graph_integrity tests
# ---------------------------------------------------------------------------


def _exp(eid, ledger_ref, frame_code):
    return Experience(
        experience_id=eid,
        prompt="p",
        ledger_ref=ledger_ref,
        regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code=frame_code, frame_detail="d", paired_trap="t")],
            traps=[Trap(trap_code="t", trap_detail="td")],
            mode=Mode.genuinely_open,
        ),
    )


def _admit_record(frame_code, eid, ledger_ref):
    return AdmissionRecord(
        frame_code=frame_code,
        posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=ScreenSummary(
            verdict="lift",
            screen_action="surface",
            mean_distinguishability=2.0,
            mean_preference=1.0,
            framed_preferred_count=2,
            data_ref="x",
        ),
        gates=Gates(
            surface_independence="pass",
            atomicity="pass",
            orthogonality="pass",
            falsifiable_application="pass",
            trainable_cognition="pass",
        ),
        nearest_sibling="protect_the_core_lane",
        separating_artifact="a",
        decision="admit_provisional",
        rationale="lifts",
        admitted_as=AdmittedAs(experience_id=eid, ledger_ref=ledger_ref),
    )


def test_integrity_passes_on_consistent_graph():
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    check_content_graph_integrity(
        exps, ["frame_x"], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
    )  # no raise


def test_integrity_catches_dangling_ledger_ref():
    exps = [_exp("e1", "veldra:TYPO", "frame_x")]
    with pytest.raises(ValueError, match="does not resolve"):
        check_content_graph_integrity(exps, ["frame_x"], {"veldra:slug_a"}, [])


def test_integrity_catches_duplicate_experience_id():
    exps = [_exp("e1", "veldra:slug_a", "frame_x"), _exp("e1", "veldra:slug_a", "frame_y")]
    with pytest.raises(ValueError, match="duplicate experience_id"):
        check_content_graph_integrity(exps, ["frame_x", "frame_y"], {"veldra:slug_a"}, [])


def test_integrity_catches_frame_not_in_process_frames():
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    with pytest.raises(ValueError, match="not in process_frames"):
        check_content_graph_integrity(
            exps, [], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
        )


def test_integrity_catches_frame_not_in_rubric():
    exps = [_exp("e1", "veldra:slug_a", "other_frame")]
    with pytest.raises(ValueError, match="not in rubric"):
        check_content_graph_integrity(
            exps, ["frame_x"], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
        )


def test_integrity_catches_missing_admitted_experience():
    """admitted_as.experience_id points to an id that doesn't exist — must raise."""
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    # record claims admitted_as experience_id="e_missing" which is not in experiences
    record = _admit_record("frame_x", "e_missing", "veldra:slug_a")
    with pytest.raises(ValueError, match="admitted_as.experience_id"):
        check_content_graph_integrity(exps, ["frame_x"], {"veldra:slug_a"}, [record])


def test_integrity_catches_ledger_ref_mismatch():
    """admitted_as.ledger_ref disagrees with the experience's ledger_ref — must raise."""
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    # experience e1 has ledger_ref="veldra:slug_a" but record claims "veldra:slug_b"
    record = _admit_record("frame_x", "e1", "veldra:slug_b")
    with pytest.raises(ValueError, match="mismatch"):
        check_content_graph_integrity(exps, ["frame_x"], {"veldra:slug_a"}, [record])


def test_screen_candidate_raises_on_missing_order(tmp_path):
    """order dict missing a scenario_id from the filtered set → named ValueError at the boundary."""
    scenarios = [
        LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo", candidate="cap_effort"),
        LiftScenario(scenario_id="s2", prompt="p2", posture="founder_ceo", candidate="cap_effort"),
    ]
    # order only contains s1 — s2 is absent
    with pytest.raises(ValueError, match="order is missing"):
        screen_candidate(
            _candidate(),
            scenarios,
            _fake(),
            order={"s1": "AB"},
            config=CFG,
            out_dir=tmp_path,
        )
