from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.cli import build_store
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.orchestration import run_session
from retnovation.types import (
    EntryClass,
    EntryClassification,
    FrameState,
    Regime,
    TrapState,
    Work,
)
from retnovation.web.session_runner import SessionRegistry

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)
_ANCHOR = "veldra:embedded_anchor_lock_in"


def test_start_emits_error_on_worker_failure(tmp_path, make_fake):
    # tmp_path is a directory -> build_store's sqlite connect raises inside the worker
    # -> error emission (no hang); verifies the "exception inside worker → error, never hang" guarantee
    reg = SessionRegistry(str(tmp_path), model_factory=make_fake)
    tag, data = reg.start("s_err", now=NOW)
    assert tag == "error" and "message" in data


def test_menu_titles_are_clean_and_never_leak_the_veldra_ref(tmp_path, make_fake):
    """The picker must show human display titles, never the ledger_ref (veldra: slug)."""
    reg = SessionRegistry(str(tmp_path / "m.db"), model_factory=make_fake)
    tag, data = reg.start("sm", now=NOW)
    assert tag == "menu"
    assert data["problems"]  # non-empty
    assert all(
        "veldra:" not in p for p in data["problems"]
    )  # clean labels, no confidentiality leak


def test_runner_assessment_equals_direct_run_session(tmp_path, make_fake, steer):
    # direct run_session with synchronous scripted callbacks
    db1 = build_store(str(tmp_path / "a.db"))
    core = derive_core(aim())
    direct_state, direct_assess = run_session(
        db1,
        core,
        make_fake(),
        NOW,
        regime=Regime.open_ended,
        present=lambda exp: Work(
            opening="reasoning that already holds the move",
            respond=lambda push: "mechanism",
        ),
        decide=steer("irreversible_anchor"),
        decide_core=lambda c: [],
    )
    # same inputs via the runner's queue bridge (Concierge turns are display-only)
    reg = SessionRegistry(str(tmp_path / "b.db"), model_factory=make_fake)
    tag, _ = reg.start("s1", now=NOW)
    assert tag == "menu"
    menu_idx = reg.menu_index("s1", _ANCHOR)
    tag, _ = reg.step("s1", menu_idx)
    assert tag == "say"  # scenario + invite
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "say":  # each probe is a display-only "say"
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    # close moved to the user-owned /close path; the done payload still carries the assessment, and
    # bridge transparency (assessment byte-equality) is unchanged.
    runner_assess = data["assessment"]
    assert (
        runner_assess.model_dump() == direct_assess.model_dump()
    )  # byte-identical -> bridge transparent


def test_step_after_done_returns_error_and_does_not_hang(tmp_path, make_fake):
    """Terminal-state guard: step after 'done' must short-circuit, never put to the dead worker."""
    reg = SessionRegistry(str(tmp_path / "c.db"), model_factory=make_fake)
    tag, _ = reg.start("s_term", now=NOW)
    assert tag == "menu"
    menu_idx = reg.menu_index("s_term", _ANCHOR)
    tag, _ = reg.step("s_term", menu_idx)
    assert tag == "say"
    tag, data = reg.step("s_term", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("s_term", "mechanism")
    assert tag == "done"

    # Session is now terminal — further step must return error immediately, not hang.
    tag2, data2 = reg.step("s_term", "anything")
    assert tag2 == "error"
    assert "message" in data2


class _ConciergeFidelityModel(FakeModel):
    """Substantive entry; concierge_turn PREFIXES so the displayed turn differs from the canonical push."""

    def classify_entry(self, prompt, opening, recent):
        return EntryClassification(entry_class=EntryClass.substantive, reply="")

    def concierge_turn(self, problem, push, recent, *, arc=None, voice=""):
        return "SHOWN::" + push  # probe mode: re-voice the canonical push (display only)


def _fid_factory():
    intake = IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={
            "deferred_the_one_time_choice": TrapState.not_tripped,
            "assumed_the_happy_path": TrapState.not_tripped,
        },
    )
    closed = [
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        for _ in range(4)
    ]
    return _ConciergeFidelityModel(intake, {"choose_the_failure_default_deliberately": closed})


def test_engine_records_canonical_push_not_the_concierge_turn(tmp_path):
    """The Concierge turn is display-only: the trajectory the engine records (and grades / reads for
    the unprompted signal) must be the canonical generate_push output, never the engaged re-voice."""
    reg = SessionRegistry(str(tmp_path / "f.db"), model_factory=_fid_factory)
    tag, _ = reg.start("sf", now=NOW)
    menu_idx = reg.menu_index("sf", _ANCHOR)
    reg.step("sf", menu_idx)  # say (scenario + invite)
    tag, data = reg.step("sf", "reasoning that already holds the move")
    while tag == "say":
        assert data["text"].startswith("SHOWN::")  # the user SEES the engaged re-voice
        tag, data = reg.step("sf", "mechanism")
    assert tag == "done"
    for push in data["assessment"].trajectory:
        assert not push.text.startswith("SHOWN::")  # the engine RECORDS the canonical push
        assert push.text == "[push:frame]"  # FakeModel.generate_push canonical output


def _irreversible_anchor_intake() -> IntakeClassification:
    return IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={
            "deferred_the_one_time_choice": TrapState.not_tripped,
            "assumed_the_happy_path": TrapState.not_tripped,
        },
    )


def _four_closed() -> dict[str, list[ResponseClassification]]:
    return {
        "choose_the_failure_default_deliberately": [
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            for _ in range(4)
        ]
    }


class _AlwaysGreetingModel(FakeModel):
    """Never enters the engine at the gate — every turn classifies as a (non-substantive) greeting."""

    def classify_entry(self, prompt, opening, recent):
        return EntryClassification(
            entry_class=EntryClass.greeting, reply="Take a real position to begin."
        )


def _greeting_factory() -> FakeModel:
    return _AlwaysGreetingModel(_irreversible_anchor_intake(), _four_closed())


def test_gate_loop_is_bounded_after_repeated_nonsubstantive_turns(tmp_path):
    """Liveness: a user (or a mis-classifying model) who never gives a substantive opening must not
    pin the session in the gate loop forever. After a small cap the loop stops re-collecting, treats
    the latest text as the RAW opening, and enters the engine (bridge stays transparent). Re-invites
    show the FakeModel reinvite text; the cap-entry shows the first engine probe."""
    reg = SessionRegistry(str(tmp_path / "d.db"), model_factory=_greeting_factory)
    tag, _ = reg.start("sd", now=NOW)
    assert tag == "menu"
    menu_idx = reg.menu_index("sd", _ANCHOR)
    tag, _ = reg.step("sd", menu_idx)
    assert tag == "say"  # scenario + invite
    # non-substantive turns are re-invited (push="" -> FakeModel reinvite text)
    tag, data = reg.step("sd", "hi")
    assert tag == "say" and data["text"] == "take a real position"
    tag, data = reg.step("sd", "hello again")
    assert tag == "say" and data["text"] == "take a real position"
    # the cap turn stops re-collecting and falls into the engine: the first probe, not a 3rd re-invite
    tag, data = reg.step("sd", "still just chatting")
    assert tag == "say" and data["text"] == "[push:frame]"  # entered the engine (bounded)


class _RecordingGateModel(FakeModel):
    """Records the (opening, recent) passed to classify_entry; always substantive (enters at once)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_calls: list[tuple[str, list[tuple[str, str]]]] = []

    def classify_entry(self, prompt, opening, recent):
        self.entry_calls.append((opening, list(recent)))
        return EntryClassification(entry_class=EntryClass.substantive, reply="")


def test_gate_does_not_duplicate_current_message_in_recent(tmp_path):
    """The current turn must reach classify_entry exactly once — as `opening`, not also as the last
    item of `recent`. present() appends ('student', text) AFTER calling gate(), so the latest
    message is not rendered twice in the classifier prompt."""
    model = _RecordingGateModel(_irreversible_anchor_intake(), _four_closed())
    reg = SessionRegistry(str(tmp_path / "e.db"), model_factory=lambda: model)
    reg.start("se", now=NOW)
    menu_idx = reg.menu_index("se", _ANCHOR)
    reg.step("se", menu_idx)
    reg.step("se", "my opening position")
    opening, recent = model.entry_calls[-1]
    assert opening == "my opening position"
    flat = [opening] + [t for _, t in recent]
    assert flat.count("my opening position") == 1  # appears once, not duplicated into recent


def test_converse_and_close_work_after_done_without_the_worker(tmp_path, make_fake):
    """Post-convergence is engine-free: the worker is terminal (step errors), yet converse — served
    from the persisted record — succeeds, and close returns the honest close + the frozen terrain."""
    reg = SessionRegistry(str(tmp_path / "cv.db"), model_factory=make_fake)
    tag, _ = reg.start("scv", now=NOW)
    menu_idx = reg.menu_index("scv", _ANCHOR)
    tag, _ = reg.step("scv", menu_idx)
    tag, data = reg.step("scv", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("scv", "mechanism")
    assert tag == "done"

    # the worker is terminal: step errors, but converse (engine-free, from the record) succeeds
    assert reg.step("scv", "more")[0] == "error"
    tag_c, data_c = reg.converse("scv", "but what about the long run?")
    assert tag_c == "say" and isinstance(data_c["text"], str) and data_c["text"]

    # the user-owned close returns the honest close + the frozen, frame-blind terrain
    tag_cl, data_cl = reg.close("scv")
    assert tag_cl == "close" and "close" in data_cl and isinstance(data_cl["terrain"], list)
    for blob in (data_c["text"], data_cl["close"], str(data_cl["terrain"])):
        assert "embed_credentials_as_a_list" not in blob
        assert "choose_the_failure_default_deliberately" not in blob


def test_probe_displays_carry_an_incrementing_arc(tmp_path):
    """Woven stance: every PROBE display call carries arc=(n, MAX_PUSHES), n starting at 1
    (pre-incremented at the top of respond — never push 0). The door re-invite path carries none.
    TWO absent frames + never-closing responses force MULTIPLE probes, so the increment itself is
    exercised — a counter stuck at 1 would fail (batch-review Minor #1)."""
    from retnovation.assessment.judgment_loop import MAX_PUSHES

    arcs = []

    def factory():
        intake = IntakeClassification(
            frame_states={
                "embed_credentials_as_a_list": FrameState.absent,
                "choose_the_failure_default_deliberately": FrameState.absent,
            },
            trap_states={
                "deferred_the_one_time_choice": TrapState.not_tripped,
                "assumed_the_happy_path": TrapState.not_tripped,
            },
        )
        m = FakeModel(intake, {})
        orig = m.concierge_turn

        def rec(problem, push, recent, *, arc=None, voice=""):
            if push:
                arcs.append(arc)
            return orig(problem, push, recent, arc=arc, voice=voice)

        m.concierge_turn = rec
        m.classify_response = lambda exp, kind, code, push, response, stress=False: (
            ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "arc.db"), model_factory=factory)
    tag, _ = reg.start("s1", now=NOW)
    assert tag == "menu"
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    assert tag == "say"  # opening
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    assert len(arcs) >= 2  # multiple probes: the increment itself is exercised, not just push 1
    assert arcs == [(i + 1, MAX_PUSHES) for i in range(len(arcs))]  # 1-based, pre-incremented


def test_continue_reaps_the_parked_worker_and_restarts_arc(tmp_path, make_fake):
    """MF-4: closing/continuing over a live mid-segment worker unblocks it via the poison pill so
    its finally runs (store closes, thread exits). Also: the arc counter restarts at push 1 in the
    chained segment (spy across both segments)."""
    arcs = []

    def factory():
        m = make_fake()
        orig = m.concierge_turn

        def rec(problem, push, recent, *, arc=None, voice=""):
            if push:
                arcs.append(arc)
            return orig(problem, push, recent, arc=arc, voice=voice)

        m.concierge_turn = rec
        # problem-AGNOSTIC doubles: the chained segment is a DIFFERENT problem, whose frame codes
        # make_fake's scripted dicts don't know (a KeyError would error the worker and skip the
        # static-close path). Intake derives from the actual rubric; every push closes -> converges.
        m.classify_intake = lambda exp, opening: IntakeClassification(
            frame_states={f.frame_code: FrameState.absent for f in exp.rubric.frames},
            trap_states={t.trap_code: TrapState.not_tripped for t in exp.rubric.traps},
        )
        m.classify_response = lambda exp, kind, code, push, response, stress=False: (
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "reap.db"), model_factory=factory)
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    n_first = len(arcs)
    assert n_first >= 1
    tag, data = reg.continue_session("s1")
    assert tag == "say"  # the new segment's opening arrived in-thread
    # drive one probe into segment 2 to observe the arc restart at push 1
    tag, data = reg.step("s1", "an opening without the move")
    if tag == "say" and len(arcs) > n_first:
        assert arcs[n_first][0] == 1  # fresh segment: the counter restarted
    # End over the LIVE mid-segment worker: honest static close + the worker is reaped
    ch2 = reg._ch["s1"]
    tag2, data2 = reg.close("s1")
    assert tag2 == "close" and "stepped away mid-problem" in data2["close"]
    ch2.thread.join(timeout=5)
    assert not ch2.thread.is_alive()  # finally ran -> store closed, thread exited
