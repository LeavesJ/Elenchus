from retnovation.types import FrameState, ProbeResult, ProbeRun, TrapState


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
