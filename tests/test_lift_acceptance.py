import os

import pytest

from elenchus.lift_test import run_lift_test
from elenchus.model import FakeLiftModel
from elenchus.types import (
    CandidateFrame,
    GeneratedOutput,
    InjectionExpressed,
    LiftScenario,
    PreferenceRating,
)

CFG = {"theta_dist": 1, "min_scenarios": 2}  # EXP ran at n=2; min is advisory, not a reject


def _scn(n):
    return [
        LiftScenario(scenario_id=f"s{i}", prompt=f"p{i}", posture="founder_ceo")
        for i in range(1, n + 1)
    ]


def _fake(per_scenario):
    """per_scenario: {prompt: (control_text, framed_text, PreferenceRating, expressed_bool)}"""
    outputs, ratings, expressed = {}, {}, {}
    for prompt, (c, f, pr, exp) in per_scenario.items():
        outputs[(prompt, False)] = GeneratedOutput(text=c, refused=(c == "<refusal>"))
        outputs[(prompt, True)] = GeneratedOutput(text=f, refused=(f == "<refusal>"))
        ratings[prompt] = pr
        expressed[f] = InjectionExpressed(expressed=exp, evidence="e")
    return FakeLiftModel(outputs=outputs, ratings=ratings, expressed=expressed)


def _cand(code):
    return CandidateFrame(frame_code=code, frame_detail="d", injection="INJ")


def test_exp002_lead_reproduces_lift_with_a_control_refusal():
    # A2 pitch: framed wins; B2 announcement: control REFUSES, framed converts -> framed wins.
    fake = _fake(
        {
            "p1": (
                "control pitch",
                "framed pitch",
                PreferenceRating(
                    distinguishability=2,
                    preferred="A",
                    magnitude=1,
                    key_difference="concrete boundary",
                ),
                True,
            ),
            "p2": (
                "<refusal>",
                "privacy-first announcement",
                PreferenceRating(
                    distinguishability=3,
                    preferred="A",
                    magnitude=2,
                    key_difference="control refused",
                ),
                True,
            ),
        }
    )
    res = run_lift_test(
        _cand("lead_with_what_you_refuse_to_do"),
        _scn(2),
        fake,
        order={"s1": "AB", "s2": "AB"},
        config=CFG,
    )
    assert res.verdict == "lift" and res.framed_preferred_count == 2
    assert res.scenarios[1].control_refused is True  # the refusal was captured, not raised


def test_exp001_choose_reproduces_negative_lift_not_null():
    # EXP-001: distinguishable (dist 1) but dispreferred in both -> negative_lift (NOT the dist-0 null cell).
    fake = _fake(
        {
            "p1": (
                "control",
                "framed",
                PreferenceRating(
                    distinguishability=1,
                    preferred="B",
                    magnitude=1,
                    key_difference="control broader",
                ),
                True,
            ),
            "p2": (
                "control",
                "framed",
                PreferenceRating(
                    distinguishability=1,
                    preferred="B",
                    magnitude=1,
                    key_difference="control broader",
                ),
                True,
            ),
        }
    )
    res = run_lift_test(
        _cand("choose_the_failure_default_deliberately"),
        _scn(2),
        fake,
        order={"s1": "AB", "s2": "AB"},
        config=CFG,
    )
    # order "AB" => framed is A; the rater prefers the CONTROL (B) in both -> preference < 0 -> negative.
    assert res.verdict == "negative_lift" and res.screen_action == "auto_kill"


def test_exp003_partial_is_mixed_and_surfaces():
    # 1 lift + 1 tie -> mixed, surfaced (never auto-killed).
    fake = _fake(
        {
            "p1": (
                "control",
                "framed",
                PreferenceRating(
                    distinguishability=2, preferred="A", magnitude=1, key_difference="sharper"
                ),
                True,
            ),
            "p2": (
                "control",
                "framed",
                PreferenceRating(
                    distinguishability=2,
                    preferred="tie",
                    magnitude=0,
                    key_difference="false precision distrusted",
                ),
                True,
            ),
        }
    )
    res = run_lift_test(
        _cand("ledger_context"), _scn(2), fake, order={"s1": "AB", "s2": "AB"}, config=CFG
    )
    assert res.verdict == "mixed" and res.screen_action == "surface"


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")),
    reason="no Anthropic credential",
)
def test_live_lift_smoke():
    from elenchus.model import AnthropicModel

    cand = CandidateFrame(
        frame_code="lead_with_what_you_refuse_to_do",
        frame_detail="lead with the boundary you will not cross",
        injection="Lead with the capability you deliberately do not have or the boundary you will not cross.",
    )
    scn = [
        LiftScenario(
            scenario_id="s1",
            prompt="Write a 120-word pitch to a skeptical security buyer.",
            posture="founder_ceo",
        )
    ]
    res = run_lift_test(cand, scn, AnthropicModel(), order={"s1": "AB"}, config=CFG)
    assert res.verdict in ("lift", "mixed", "neutral", "null", "negative_lift", "inconclusive")
