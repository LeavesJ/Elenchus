from retnovation.lift_test import run_lift_test, un_randomize
from retnovation.model import FakeLiftModel
from retnovation.types import (
    CandidateFrame,
    GeneratedOutput,
    InjectionExpressed,
    LiftScenario,
    PreferenceRating,
)

CFG = {"theta_dist": 1, "min_scenarios": 3}


def test_un_randomize_round_trip_catches_sign_flip():
    # framed is clearly stronger and was placed as B (order "BA"); rater prefers B with magnitude 2.
    # un_randomize must attribute that to FRAMED (positive), not control.
    assert un_randomize("B", 2, "BA") == 2  # framed (B under BA) preferred -> +2
    assert un_randomize("A", 2, "BA") == -2  # control (A under BA) preferred -> -2
    assert un_randomize("A", 1, "AB") == 1  # framed (A under AB) preferred -> +1
    assert un_randomize("tie", 0, "AB") == 0  # tie -> 0, order-independent


def _cand():
    return CandidateFrame(frame_code="f", frame_detail="d", injection="INJ")


def test_run_lift_test_builds_verdict_per_scenario():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo")
    fake = FakeLiftModel(
        outputs={
            ("p1", False): GeneratedOutput(text="C1"),
            ("p1", True): GeneratedOutput(text="F1"),
        },
        ratings={
            "p1": PreferenceRating(
                distinguishability=2, preferred="A", magnitude=2, key_difference="k"
            )
        },
        expressed={"F1": InjectionExpressed(expressed=True, evidence="e")},
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    sv = res.scenarios[0]
    assert sv.injection_expressed is True and sv.preference == 2  # A=framed under AB, mag 2
    assert sv.framed_output == "F1" and sv.control_output == "C1"
    assert res.verdict == "lift"


def test_manipulation_gate_makes_scenario_inconclusive_not_no_lift():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="x")
    fake = FakeLiftModel(
        outputs={
            ("p1", False): GeneratedOutput(text="C1"),
            ("p1", True): GeneratedOutput(text="F1"),
        },
        ratings={
            "p1": PreferenceRating(
                distinguishability=3, preferred="A", magnitude=2, key_difference="k"
            )
        },
        expressed={"F1": InjectionExpressed(expressed=False, evidence="frame not present")},
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    assert res.scenarios[0].injection_expressed is False
    assert res.verdict == "inconclusive"  # not null / negative_lift
    assert res.screen_action == "surface"  # all-inconclusive never auto-kills


def test_control_refusal_is_captured_on_the_verdict():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="x")
    fake = FakeLiftModel(
        outputs={
            ("p1", False): GeneratedOutput(text="I can't.", refused=True),
            ("p1", True): GeneratedOutput(text="A privacy-first announcement."),
        },
        ratings={
            "p1": PreferenceRating(
                distinguishability=3, preferred="B", magnitude=2, key_difference="k"
            )
        },
        expressed={
            "A privacy-first announcement.": InjectionExpressed(expressed=True, evidence="e")
        },
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    sv = res.scenarios[0]
    assert sv.control_refused is True and sv.framed_refused is False
    assert sv.preference == -2  # order "AB": framed=A, control=B; rater preferred B (control) -> -2
