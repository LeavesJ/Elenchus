from __future__ import annotations

from .model import Model
from .types import Experience, ProbeResult, ProbeRun, Rubric

DEFAULT_TARGET = "embed_credentials_as_a_list"


def assert_intake_equivalence(rubric: Rubric | None, target_frame_code: str) -> None:
    """Refuse any rubric where intake `present_reasoned` is NOT provably equivalent to the
    target landing in `reasoned_unprompted`. Encodes the rubric half of the proof (the loop
    half is pinned by the fixtured guardian in tests/test_sp3_progression.py). See the spec's
    "Durability of the proof" section."""
    if rubric is None:
        raise ValueError("intake-only equivalence requires an open_ended rubric; got None")
    frame_codes = {f.frame_code for f in rubric.frames}
    if target_frame_code not in frame_codes:
        raise ValueError(
            f"target {target_frame_code!r} is not a frame in the rubric ({sorted(frame_codes)})"
        )
    if rubric.decision_frame is not None:
        raise ValueError(
            "intake-only equivalence requires decision_frame is None; "
            f"rubric has decision_frame={rubric.decision_frame!r} (it would be force-probed)"
        )
    if rubric.binding_constraint == target_frame_code:
        raise ValueError(
            "intake-only equivalence requires the target not be the binding_constraint; "
            f"target {target_frame_code!r} is the binding_constraint (it could be probed)"
        )


def assert_no_frame_code_leak(prompt: str, frame_codes: list[str]) -> None:
    """L-13 automated floor: the learner-facing prompt must not contain any frame code verbatim.
    (A plain-words paraphrase is caught by the human verbatim adjudication, not here.)"""
    leaked = [c for c in frame_codes if c in prompt]
    if leaked:
        raise ValueError(f"L-13 floor: frame code(s) {leaked} appear in the learner-facing prompt")


def run_elicitation_probe(
    experiences: list[Experience],
    model: Model,
    *,
    runs_by_id: dict[str, int],
    target_frame_code: str = DEFAULT_TARGET,
) -> ProbeResult:
    """Pure orchestration over the Model protocol. For each experience: assert the equivalence
    + L-13 preconditions once, then per run capture a bare frame-naive opening and its real
    intake classification. A refused opening is recorded and its intake skipped."""
    runs: list[ProbeRun] = []
    for exp in experiences:
        assert_intake_equivalence(exp.rubric, target_frame_code)
        assert_no_frame_code_leak(exp.prompt, [f.frame_code for f in exp.rubric.frames])
        for i in range(runs_by_id[exp.experience_id]):
            output = model.generate_output(exp.prompt, None)  # bare = no system = frame-naive
            if output.refused:
                runs.append(
                    ProbeRun(
                        experience_id=exp.experience_id,
                        run_index=i,
                        opening=output.text,
                        refused=True,
                    )
                )
                continue
            intake = model.classify_intake(exp, output.text)
            runs.append(
                ProbeRun(
                    experience_id=exp.experience_id,
                    run_index=i,
                    opening=output.text,
                    refused=False,
                    frame_states=dict(intake.frame_states),
                    trap_states=dict(intake.trap_states),
                )
            )
    return ProbeResult(target_frame_code=target_frame_code, runs=runs)
