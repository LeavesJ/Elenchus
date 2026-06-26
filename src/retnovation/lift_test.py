from __future__ import annotations

from typing import Literal

from .types import CandidateFrame, LiftResult, LiftScenario, ScenarioVerdict


def randomize(framed: str, control: str, order: Literal["AB", "BA"]) -> tuple[str, str]:
    return (framed, control) if order == "AB" else (control, framed)


def un_randomize(
    preferred: Literal["A", "B", "tie"], magnitude: int, order: Literal["AB", "BA"]
) -> int:
    """Map the rater's preference (toward shown A/B) back to a signed value toward FRAMED."""
    if preferred == "tie":
        return 0
    framed_letter = "A" if order == "AB" else "B"
    return magnitude if preferred == framed_letter else -magnitude


def run_lift_test(
    candidate: CandidateFrame,
    scenarios: list[LiftScenario],
    model,
    order: dict[str, str],
    config: dict,
) -> LiftResult:
    verdicts: list[ScenarioVerdict] = []
    for sc in scenarios:
        control = model.generate_output(sc.prompt, None)
        framed = model.generate_output(sc.prompt, candidate.injection)
        ie = model.check_injection_expressed(candidate.injection, framed.text)
        if not ie.expressed:  # gate: un-expressed -> inconclusive, excluded from aggregation
            verdicts.append(
                ScenarioVerdict(
                    scenario_id=sc.scenario_id,
                    injection_expressed=False,
                    framed_output=framed.text,
                    control_output=control.text,
                    framed_refused=framed.refused,
                    control_refused=control.refused,
                )
            )
            continue
        a, b = randomize(framed.text, control.text, order[sc.scenario_id])
        pr = model.rate_preference(sc.prompt, a, b)
        preference = un_randomize(pr.preferred, pr.magnitude, order[sc.scenario_id])
        verdicts.append(
            ScenarioVerdict(
                scenario_id=sc.scenario_id,
                injection_expressed=True,
                distinguishability=pr.distinguishability,
                preference=preference,
                key_difference=pr.key_difference,
                framed_output=framed.text,
                control_output=control.text,
                framed_refused=framed.refused,
                control_refused=control.refused,
            )
        )
    return LiftResult(
        frame_code=candidate.frame_code,
        scenarios=verdicts,
        theta_dist=config["theta_dist"],
        min_scenarios=config["min_scenarios"],
    )
