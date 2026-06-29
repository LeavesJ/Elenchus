import json
from datetime import datetime, timezone

import pytest

from retnovation.content_loader import load_experience
from retnovation.elicitation import (
    DEFAULT_TARGET,
    assert_intake_equivalence,
    assert_no_frame_code_leak,
    run_elicitation_probe,
)
from retnovation.model import IntakeClassification
from retnovation.types import (
    Frame,
    FrameState,
    GeneratedOutput,
    Mode,
    ProbeResult,
    ProbeRun,
    Rubric,
    Trap,
    TrapState,
)


def _run(eid, i, target_state, trips=(), refused=False):
    return ProbeRun(
        experience_id=eid,
        run_index=i,
        opening="" if refused else f"opening-{eid}-{i}",
        refused=refused,
        frame_states={} if refused else {"embed_credentials_as_a_list": target_state},
        trap_states={} if refused else {t: TrapState.tripped for t in trips},
    )


def test_summarize_counts_states_trips_and_refusals():
    result = ProbeResult(
        target_frame_code="embed_credentials_as_a_list",
        runs=[
            _run("irreversible_anchor", 0, FrameState.present_reasoned, trips=()),
            _run(
                "irreversible_anchor", 1, FrameState.absent, trips=("deferred_the_one_time_choice",)
            ),
            _run("irreversible_anchor", 2, FrameState.absent, refused=True),
        ],
    )
    (s,) = result.summarize()
    assert s.experience_id == "irreversible_anchor"
    assert (s.total_runs, s.usable_runs, s.refused_runs) == (3, 2, 1)
    assert (s.target_present_reasoned, s.target_present_asserted, s.target_absent) == (1, 0, 1)
    assert s.trap_trips == {"deferred_the_one_time_choice": 1}


TARGET = "embed_credentials_as_a_list"


def _rubric(*, decision_frame=None, binding_constraint=None, frames=(TARGET,)):
    return Rubric(
        frames=[Frame(frame_code=c, frame_detail="d", paired_trap=None) for c in frames],
        traps=[Trap(trap_code="t", trap_detail="d")],
        mode=Mode.genuinely_open,
        binding_constraint=binding_constraint,
        decision_frame=decision_frame,
    )


def test_guard_passes_the_two_real_rubrics():
    for eid in ("irreversible_anchor", "continuity_lock_in"):
        assert_intake_equivalence(load_experience(eid).rubric, DEFAULT_TARGET)  # no raise


def test_guard_refuses_decision_frame():
    with pytest.raises(ValueError, match="decision_frame"):
        assert_intake_equivalence(_rubric(decision_frame=TARGET), TARGET)


def test_guard_refuses_target_as_binding_constraint():
    with pytest.raises(ValueError, match="binding_constraint"):
        assert_intake_equivalence(_rubric(binding_constraint=TARGET), TARGET)


def test_guard_refuses_target_not_in_rubric():
    with pytest.raises(ValueError, match="not a frame"):
        assert_intake_equivalence(_rubric(frames=("some_other_frame",)), TARGET)


def test_guard_refuses_none_rubric():
    with pytest.raises(ValueError, match="rubric"):
        assert_intake_equivalence(None, TARGET)


def test_no_frame_code_leak_passes_real_prompts():
    for eid in ("irreversible_anchor", "continuity_lock_in"):
        exp = load_experience(eid)
        assert_no_frame_code_leak(exp.prompt, [f.frame_code for f in exp.rubric.frames])


def test_no_frame_code_leak_raises_on_a_planted_code():
    with pytest.raises(ValueError, match="frame code"):
        assert_no_frame_code_leak("decide using embed_credentials_as_a_list now", [TARGET])


class _FakeProbeModel:
    """generate_output pops scripted outputs in order; classify_intake returns a fixed intake
    keyed by the opening text. Raises if classify_intake is called on a refused (empty) opening."""

    def __init__(self, outputs, intake_by_text):
        self._outputs = list(outputs)
        self._intake_by_text = intake_by_text
        self.classify_calls = 0

    def generate_output(self, scenario_prompt, injection):
        assert injection is None  # frame-naive by construction (bare = the SP2 control call)
        return self._outputs.pop(0)

    def classify_intake(self, exp, opening):
        self.classify_calls += 1
        return self._intake_by_text[opening]


def _intake(target_state, traps):
    return IntakeClassification(
        frame_states={"embed_credentials_as_a_list": target_state},
        trap_states=traps,
    )


def test_probe_records_states_and_verbatim_per_run():
    exp = load_experience("continuity_lock_in")
    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="op-0"), GeneratedOutput(text="op-1")],
        intake_by_text={
            "op-0": _intake(
                FrameState.present_reasoned, {"shipped_the_one_shot_term": TrapState.not_tripped}
            ),
            "op-1": _intake(FrameState.absent, {"shipped_the_one_shot_term": TrapState.tripped}),
        },
    )
    result = run_elicitation_probe([exp], model, runs_by_id={"continuity_lock_in": 2})
    assert isinstance(result, ProbeResult) and len(result.runs) == 2
    assert [r.opening for r in result.runs] == ["op-0", "op-1"]
    assert result.runs[0].frame_states["embed_credentials_as_a_list"] is FrameState.present_reasoned
    assert result.runs[1].trap_states["shipped_the_one_shot_term"] is TrapState.tripped


def test_probe_records_refusal_and_skips_intake():
    exp = load_experience("continuity_lock_in")
    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="", refused=True)],
        intake_by_text={},  # classify_intake would KeyError if called — proves it is skipped
    )
    result = run_elicitation_probe([exp], model, runs_by_id={"continuity_lock_in": 1})
    assert result.runs[0].refused is True
    assert result.runs[0].frame_states == {}
    assert model.classify_calls == 0


def test_probe_enforces_the_equivalence_guard():
    # a cs_technical experience has rubric=None -> guard refuses before any model call
    from retnovation.content_loader import load_checkable_experience

    exp = load_checkable_experience("consensus_safety_liveness")  # checkable -> rubric is None
    with pytest.raises(ValueError):
        run_elicitation_probe([exp], _FakeProbeModel([], {}), runs_by_id={exp.experience_id: 1})


def test_run_writes_artifact_and_returns_result(tmp_path):
    from retnovation import run_elicitation

    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="op-x")],
        intake_by_text={"op-x": _intake(FrameState.present_reasoned, {})},
    )
    path, result = run_elicitation.run(
        model,
        runs_by_id={"continuity_lock_in": 1},
        data_dir=tmp_path,
        now=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert path == tmp_path / "20260627T120000Z.json"
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk["runs"][0]["opening"] == "op-x"
    assert isinstance(result, ProbeResult)
