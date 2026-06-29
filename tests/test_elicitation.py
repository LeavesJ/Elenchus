import pytest

from retnovation.content_loader import load_experience
from retnovation.elicitation import (
    DEFAULT_TARGET,
    assert_intake_equivalence,
    assert_no_frame_code_leak,
)
from retnovation.types import (
    Frame,
    FrameState,
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
