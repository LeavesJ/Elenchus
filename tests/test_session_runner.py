from datetime import datetime, timedelta, timezone

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
    """The doors must show human display titles, never the ledger_ref (veldra: slug)."""
    reg = SessionRegistry(str(tmp_path / "m.db"), model_factory=make_fake)
    tag, data = reg.start("sm", now=NOW)
    assert tag == "say" and data.get("frontdoor")  # the cold beat is the front door now
    assert data["menu"]["problems"]  # non-empty small doors
    assert all(
        "veldra:" not in p for p in data["menu"]["problems"]
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
    assert tag == "say"  # the front door (doors embedded; menu_index reads the cached refs)
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
    assert tag == "say"  # front door
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
    assert tag == "say"  # front door
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
    assert tag == "say"  # front door
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


def _agnostic(make_fake, outcome):
    """Problem-agnostic fake: intake from the actual rubric; every push -> `outcome`."""
    m = make_fake()
    m.classify_intake = lambda exp, opening: IntakeClassification(
        frame_states={f.frame_code: FrameState.absent for f in exp.rubric.frames},
        trap_states={t.trap_code: TrapState.not_tripped for t in exp.rubric.traps},
    )
    m.classify_response = lambda exp, kind, code, push, response, stress=False: (
        ResponseClassification(
            outcome=outcome, mechanism_supplied=(outcome == "closed"), hard_wrong=False
        )
    )
    return m


def _drive(reg, sid, opening="an opening"):
    tag, data = reg.step(sid, opening)
    while tag == "say":
        tag, data = reg.step(sid, "again")
    return tag, data


def test_plateaued_segment_is_not_banked_and_can_be_reoffered(tmp_path, make_fake):
    """F1: the sitting dedupe is by CONVERGED refs ONLY — a plateaued segment's problem may
    legitimately be re-offered (it was not banked as a house)."""
    reg = SessionRegistry(
        str(tmp_path / "f1.db"), model_factory=lambda: _agnostic(make_fake, "unchanged")
    )
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = _drive(reg, "s1")
    assert tag == "done"
    rec = reg._last_record["s1"]
    assert rec["stop_reason"] != "converged"  # the always-unchanged fake cannot converge
    assert _ANCHOR not in reg._sitting_done.get("s1", set())  # NOT banked (F1)
    # and the guarded pick may legitimately re-offer it
    assert data["next_title"]  # a door is still offered


def test_error_segment_does_not_strand_continuation(tmp_path, make_fake):
    """F2: a chained segment that ERRORS must not leave continued=True stuck on the last converged
    record — the user must be able to continue again after a transient failure."""

    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        if calls["n"] == 1:
            return _agnostic(make_fake, "closed")  # segment 1 converges
        m = _agnostic(make_fake, "closed")

        def boom(exp, opening):
            raise RuntimeError("transient model failure")

        m.classify_intake = boom  # segment 2 errors at intake
        return m

    reg = SessionRegistry(str(tmp_path / "f2.db"), model_factory=factory)
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = _drive(reg, "s1", "reasoning that already holds the move")
    assert tag == "done"
    tag2, _ = reg.continue_session("s1")
    assert tag2 == "say"  # segment 2 opened
    tag3, _ = reg.step("s1", "an opening")  # intake raises -> error, terminal
    assert tag3 == "error"
    # the continuation flow is NOT stranded: a fresh continue is accepted
    tag4, data4 = reg.continue_session("s1")
    assert tag4 in ("say", "menu"), f"stranded: {tag4} {data4}"


# ---- Durable sittings: write-through (spec 2026-07-01-durable-sittings-design §2b) ----------


def test_write_through_persists_projected_transcript_and_state(tmp_path, make_fake):
    """The store mirrors the PROJECTED wire: vera/you/landing turns in order, NO menus, NO refs
    (L-13); the landed record + next pick + converged row are persisted; inflight clears at done."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "wt.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    tag, _ = reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    assert tag == "say"
    tag, data = _drive(reg, "s1", opening="my position")
    assert tag == "done"

    store = SittingStore(db)
    sit = store.live_sitting()
    assert sit is not None
    turns = store.turns(sit["id"])
    kinds = [t["kind"] for t in turns]
    assert "menu" not in kinds and "error" not in kinds  # menus/errors never persist
    assert kinds[:2] == ["vera", "vera"]  # the front-door ask, then the opening
    assert kinds[2] == "you" and turns[2]["payload"]["text"] == "my position"
    assert kinds[-1] == "landing" and turns[-1]["payload"]["text"] == data["landing"]
    import json as _json

    blob = _json.dumps([t["payload"] for t in turns])
    assert "veldra:" not in blob  # L-13 on the durable mirror

    state = store.read_state(sit["id"])
    assert state["record"]["stop_reason"] == "converged"
    assert state["record"]["experience_id"]  # rebuildable identity, not the object
    assert state["inflight"] is None  # cleared at done
    assert state["next_pick"] is not None and state["next_pick"][0] != _ANCHOR
    # the converged log stamps wall-clock time (the registry's own now), so read with wall-clock
    assert _ANCHOR in store.converged_within(datetime.now(timezone.utc))


def test_write_through_continue_seam_marker_and_converse_record(tmp_path, make_fake):
    """Continue persists marker+seam+opening (never the swallowed internal menu) and the response
    carries the seam; converse persists the pair AND rewrites record_json.recent."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "seam.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    _drive(reg, "s1")

    tag, data = reg.continue_session("s1")
    assert tag == "say"
    assert data.get("seam") == "Same sitting — next door."

    store = SittingStore(db)
    sit = store.live_sitting()
    turns = store.turns(sit["id"])
    kinds = [t["kind"] for t in turns]
    i = kinds.index("seam")
    assert turns[i - 1]["kind"] == "muted"  # Continue → {title} marker precedes the seam
    assert turns[i - 1]["payload"]["text"].startswith("Continue → ")
    assert turns[i + 1]["kind"] == "vera"  # the new segment's opening follows
    assert "menu" not in kinds

    # converse (over the landed record, mid-segment-2 is fine: registry-level record)
    tag_c, data_c = reg.converse("s1", "but what about the long run?")
    assert tag_c == "say"
    turns = store.turns(sit["id"])
    assert turns[-2]["kind"] == "you" and turns[-1]["kind"] == "vera"
    rec = store.read_state(sit["id"])["record"]
    assert ["student", "but what about the long run?"] in rec["recent"]  # same-transaction rewrite


def test_write_through_plateau_banks_no_converged_row(tmp_path, make_fake):
    """F1 on the durable log: a plateaued segment persists its record (honest stop_reason) but
    NEVER a converged row — it may legitimately re-offer."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "plateau.db")
    reg = SessionRegistry(db, model_factory=lambda: _agnostic(make_fake, "unchanged"))
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, _ = _drive(reg, "s1")
    assert tag == "done"
    store = SittingStore(db)
    sit = store.live_sitting()
    rec = store.read_state(sit["id"])["record"]
    assert rec["stop_reason"] != "converged"
    assert store.converged_within(NOW) == set()


def test_error_emissions_never_reach_the_durable_transcript(tmp_path, make_fake):
    """L-14: exception text can carry frame codes — a worker error emission must not persist."""
    from retnovation.web.sitting_store import SittingStore

    def factory():
        m = make_fake()

        def boom(exp, opening):
            raise RuntimeError("Boom: choose_the_failure_default_deliberately leaked")

        m.classify_intake = boom
        return m

    db = str(tmp_path / "err.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, _ = reg.step("s1", "a real opening")
    assert tag == "error"
    store = SittingStore(db)
    sit = store.live_sitting()
    turns = store.turns(sit["id"])
    import json as _json

    blob = _json.dumps(turns)
    assert "Boom" not in blob and "choose_the_failure" not in blob
    # ask + opening + the user's words only — never the error emission
    assert [t["kind"] for t in turns] == ["vera", "vera", "you"]


def test_close_marks_sitting_closed_and_clears_it(tmp_path, make_fake):
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "cl.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    _drive(reg, "s1")
    tag, data = reg.close("s1")
    assert tag == "close"
    store = SittingStore(db)
    assert store.live_sitting() is None  # closed, retained
    # the sitting is OVER (channel popped, C1/C14): stale requests get the refresh nudge — never
    # a hang on a reaped worker's queue, never a false "has not converged"
    assert reg.converse("s1", "hello?")[0] == "nudge"
    assert reg.step("s1", "hello again")[0] == "nudge"


def test_drain_consumes_an_orphan_done_but_never_steals_from_a_stepper(tmp_path, make_fake):
    """Defensive drain: an undequeued done (handshake drift) is consumed by close/continue and
    banked via _on_done; but the drain is skipped while a step is in flight for the sid."""
    from retnovation.content_loader import load_library

    db = str(tmp_path / "drain.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    _drive(reg, "s1")
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 open, worker parked at the gate

    ch2 = reg._ch["s1"]
    exp = next(e for e in load_library() if e.ledger_ref == _ANCHOR)
    ch2.record = {
        "model": make_fake(),
        "posture": None,
        "exp": exp,
        "recent": [("student", "x")],
        "stop_reason": "converged",
        "terrain": [],
    }
    ch2.from_worker.put(("done", {"landing": ""}))  # fabricated proactive emission (drift)
    # a step in flight blocks the drain (simulated via the bookkeeping counter)
    reg._stepping["s1"] = 1
    assert not ch2.terminal
    reg._drain("s1")
    assert not ch2.terminal  # skipped: never steal from a blocked request
    reg._stepping.pop("s1", None)

    tag_cl, data_cl = reg.close("s1")  # close drains first -> _on_done banks segment 2
    assert tag_cl == "close"
    # close() then ENDS the sitting (clears the in-memory maps) — the durable evidence is the
    # converged log the drain's _on_done wrote before the close branched.
    from retnovation.web.sitting_store import SittingStore

    assert _ANCHOR in SittingStore(db).converged_within(datetime.now(timezone.utc))


# ---- Durable sittings: resume, rebuild, guards (spec §2c/§2e) --------------------------------


def _converge_one(db, make_fake, sid="s1"):
    """Fresh registry over db; drive one full segment to done. Returns (reg, done_data)."""
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start(sid, now=NOW)
    reg.step(sid, reg.menu_index(sid, _ANCHOR))
    tag, data = _drive(reg, sid, opening="my position")
    assert tag == "done"
    return reg, data


def test_restart_resume_returns_transcript_and_working_record(tmp_path, make_fake):
    """The crown: a NEW registry over the same db (== process restart) resumes the sitting —
    verbatim turns, End/Continue state, converse over the REBUILT record — and a converse
    exchange survives a SECOND restart (record_json write-through)."""
    db = str(tmp_path / "resume.db")
    _converge_one(db, make_fake)

    reg2 = SessionRegistry(db, model_factory=make_fake)  # restart #1
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    assert data["mode"] == "converse" and data["end_visible"] is True
    kinds = [t["kind"] for t in data["turns"]]
    assert kinds[0] == "vera" and "landing" in kinds
    assert any(t["text"] == "my position" for t in data["turns"])
    assert data["next_title"] and "veldra:" not in str(data)
    assert "frame" not in str(data.get("theme", {}))

    tag_c, data_c = reg2.converse("s1", "so what did that cost me?")
    assert tag_c == "say" and data_c["text"]

    reg3 = SessionRegistry(db, model_factory=make_fake)  # restart #2
    tag, data = reg3.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    texts = [t["text"] for t in data["turns"]]
    assert "so what did that cost me?" in texts  # the converse pair survived the second restart
    # and the rebuilt record REMEMBERS it (Vera must not contradict her own on-screen memory)
    rec = reg3._rebuild("s1")
    assert ["student", "so what did that cost me?"] in [list(t) for t in rec["recent"]]


def test_restart_continue_works_and_flag_cleared(tmp_path, make_fake):
    """A persisted continued-flag would brick Continue forever after a restart — the rebuild must
    clear it (in-memory only), while double-continue within a process still refuses."""
    db = str(tmp_path / "cflag.db")
    reg, _ = _converge_one(db, make_fake)
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # continued flag now set on the record, segment 2 in flight

    reg2 = SessionRegistry(db, model_factory=make_fake)  # restart mid-continued-segment
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    tag2, data2 = reg2.continue_session("s1")
    assert tag2 in ("say", "menu")  # NOT "continuation already in flight"
    if tag2 == "say":
        # and within-process idempotency still holds
        assert reg2.continue_session("s1")[0] == "error"


def test_restart_mid_segment_honesty_and_static_close(tmp_path, make_fake):
    """A lost in-flight segment resumes with the branch-accurate honesty line; close() over the
    interrupted tail returns the STATIC variant, never a mirrored close of the previous problem
    (MF-5 across restart)."""
    db = str(tmp_path / "mid.db")
    reg, _ = _converge_one(db, make_fake)
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 open; now the "process dies" (drop the registry)

    reg2 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    assert "restarted mid-problem" in data["honesty"]
    assert data["mode"] == "converse"  # a landed record exists beneath the lost segment
    tag_cl, data_cl = reg2.close("s1")
    assert tag_cl == "close"
    assert "closed unfinished" in data_cl["close"]  # static variant, not authored
    assert isinstance(data_cl["terrain"], list)


def test_restart_mid_first_segment_offers_fresh_menu(tmp_path, make_fake):
    """Restart mid-FIRST segment: nothing landed — honesty line + an embedded fresh menu; the
    composer never dead-ends."""
    db = str(tmp_path / "midfirst.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))  # opening served; segment in flight

    reg2 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    assert "restarted mid-problem" in data["honesty"]
    assert data["mode"] == "engine" and data["end_visible"] is False
    assert data["menu"] and data["menu"]["problems"]  # a fresh way forward
    assert "refs" not in data["menu"]  # L-13: the embedded menu is title-only
    assert "eids" not in data["menu"]  # L-13: the F1 territory keys stay server-side too


def test_rolling_window_dedupe_across_processes(tmp_path, make_fake):
    """Refs converged in a PRIOR process within 24h are excluded from the auto-pick even across a
    UTC date boundary; a stale persisted next_pick into a since-converged ref drops to the menu."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "window.db")
    reg, data = _converge_one(db, make_fake)
    # process 1 converged _ANCHOR; simulate a prior sitting having converged the offered pick
    offered_ref = reg._next_pick["s1"]
    assert offered_ref is not None
    store = SittingStore(db)
    store.log_converged("someprior", offered_ref, datetime.now(timezone.utc))

    reg2 = SessionRegistry(db, model_factory=make_fake)  # restart
    tag, rdata = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    # the stale pick was re-validated against the window and dropped or replaced
    assert rdata["next_title"] == "" or rdata["next_title"] != reg._next_pick_title.get("s1")
    tag2, data2 = reg2.continue_session("s1")
    # MF-3's honest path: the doors (now the front door), never a silent converged re-serve
    assert tag2 == "say" and data2.get("frontdoor")


def test_rebuild_failure_degrades_to_statics(tmp_path, make_fake):
    """A record whose experience_id no longer resolves (L-1 content drift across a restart) must
    never author unscreened or 500 — converse and close degrade to statics + persisted terrain."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "degraded.db")
    _converge_one(db, make_fake)
    store = SittingStore(db)
    sit = store.live_sitting()
    rec = store.read_state(sit["id"])["record"]
    rec["experience_id"] = "retired_experience_that_no_longer_exists"
    store.write_state(sit["id"], record=rec)

    reg2 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    tag_c, data_c = reg2.converse("s1", "hello again")
    assert tag_c == "say" and data_c["text"]  # the safe static, not an unscreened author
    tag_cl, data_cl = reg2.close("s1")
    assert tag_cl == "close" and isinstance(data_cl["terrain"], list)


def test_stale_sitting_older_than_18h_cold_starts(tmp_path, make_fake):
    """A sitting is an evening, not an undying thread: >18h idle -> closed (retained), cold menu."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "stale.db")
    _converge_one(db, make_fake)

    reg2 = SessionRegistry(db, model_factory=make_fake)
    later = datetime.now(timezone.utc) + timedelta(hours=19)
    tag, data = reg2.resume_or_start("s1", now=later)
    assert tag == "say" and data.get("frontdoor")  # cold start = the front door
    store = SittingStore(db)
    assert store.live_sitting() is not None  # the NEW sitting
    # exactly one closed + one live sitting exist; nothing deleted


def test_stale_tab_requests_fail_soft(tmp_path, make_fake):
    """/say against a missing channel (post-restart tab) nudges instead of KeyError-500ing."""
    db = str(tmp_path / "staletab.db")
    _converge_one(db, make_fake)
    reg2 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg2.step("s1", "hello?")  # no channel in this process
    assert tag == "nudge" and "refresh" in data["message"]


def test_stale_menu_nonce_reserves_the_menu(tmp_path, make_fake):
    """A choose carrying a stale nonce re-serves the current menu instead of silently opening a
    door the user never picked (selection semantics preserved)."""
    db = str(tmp_path / "nonce.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data["menu"].get("nonce")
    stale = data["menu"]["nonce"] - 1
    tag2, data2 = reg.choose("s1", 0, nonce=stale)
    assert tag2 == "menu"  # re-served, no door opened
    tag3, _ = reg.choose("s1", reg.menu_index("s1", _ANCHOR), nonce=data2["nonce"])
    assert tag3 == "say"  # the correct nonce proceeds


# ---- Batch-review folds (2026-07-01 late): the confirmed findings, pinned ---------------------


def test_stale_start_reaps_the_replaced_parked_worker(tmp_path, make_fake):
    """C2/C8/C15: replacing a live non-terminal channel (18h-abandonment path) poison-pills the
    parked worker so its store closes and the thread exits — never a silent leak."""
    db = str(tmp_path / "reap18.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))  # opening served; worker parked at the gate
    old_ch = reg._ch["s1"]
    assert old_ch.thread.is_alive()

    later = datetime.now(timezone.utc) + timedelta(hours=19)
    tag, _ = reg.resume_or_start("s1", now=later)  # stale -> close + cold start over the channel
    assert tag == "say"  # the fresh front door
    old_ch.thread.join(timeout=5)
    assert not old_ch.thread.is_alive()  # reaped: finally ran, store closed


def test_same_process_errored_tail_gets_static_close_not_mirrored(tmp_path, make_fake):
    """C3: converge -> continue -> the new segment ERRORS -> End (no reload). The close must be
    the static interrupted variant read from the PERSISTED inflight discriminator — never an
    authored close mirroring the previous problem beneath the errored problem's turns."""
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        m = make_fake()
        if calls["n"] >= 2:  # segment 2's model: brick at intake

            def boom(exp, opening):
                raise RuntimeError("segment two dies")

            m.classify_intake = boom
        return m

    db = str(tmp_path / "mf5same.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    _drive(reg, "s1")
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 opening
    tag, _ = reg.step("s1", "a real position")  # gate passes; intake bricks -> error
    assert tag == "error"
    tag_cl, data_cl = reg.close("s1")
    assert tag_cl == "close"
    assert "closed unfinished" in data_cl["close"]  # static, cause-neutral
    assert "[close" not in data_cl["close"]  # never the authored mirror of the previous problem


def test_errored_segment_clears_the_pending_seam(tmp_path, make_fake):
    """C5: a seam pending on an errored segment must die with it — a stale (re)open line must not
    render or persist on an unrelated later door."""
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        m = make_fake()
        if calls["n"] == 2:

            def boom(exp, opening):
                raise RuntimeError("boot fails")

            m.classify_intake = boom
        return m

    db = str(tmp_path / "seamclear.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    _drive(reg, "s1")
    tag, _ = reg.continue_session("s1")  # seam set; segment 2 opens fine (error comes at intake)
    assert tag == "say"
    tag, _ = reg.step("s1", "a position")  # error emission
    assert tag == "error"
    assert "s1" not in reg._seam_pending  # cleared with the errored segment


def test_choose_is_refused_when_no_menu_is_pending(tmp_path, make_fake):
    """C10/C11: a replayed choose (same nonce, menu already consumed) is nudged — it must not
    inject an int into the gate loop nor fabricate 'door chosen' turns."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "replay.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg.start("s1", now=NOW)
    nonce = data["menu"]["nonce"]
    idx = reg.menu_index("s1", _ANCHOR)
    tag, _ = reg.choose("s1", idx, nonce=nonce)
    assert tag == "say"  # accepted; menu consumed
    store = SittingStore(db)
    sit = store.live_sitting()
    turns_before = len(store.turns(sit["id"]))
    tag2, data2 = reg.choose("s1", idx, nonce=nonce)  # the second tab's identical click
    assert tag2 == "nudge"
    assert len(store.turns(sit["id"])) == turns_before  # no fabricated turns


def test_union_screen_fails_closed_and_catches_lost_exp_moves(tmp_path, make_fake):
    """C9/C12: after a restart-lost segment, converse screens the UNION — a reply performing the
    LOST problem's move serves the safe static; an unresolvable lost exp also fails closed."""
    from retnovation.content_loader import load_library
    from retnovation.model import EgressScreen
    from retnovation.web import voice as voice_mod
    from retnovation.web.sitting_store import SittingStore

    anchor_exp = next(e for e in load_library() if e.ledger_ref == _ANCHOR)
    # the screen receives RENDERED move details (frame/trap details, 1-based indices) — the exact
    # move SET identifies the caller: A's own screen passes, the LOST exp's screen flags
    a_details = set(voice_mod._moves(anchor_exp))

    def leak_factory():
        m = make_fake()

        def screen(moves, text):
            if set(moves) != a_details:
                return EgressScreen(performed=[1], evidence="(fake: lost-exp leak)")
            return EgressScreen(performed=[], evidence="(fake: clean)")

        m.screen_moves = screen
        return m

    db = str(tmp_path / "union.db")
    reg, _ = _converge_one(db, make_fake)
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 (a NON-anchor door) in flight; now the process "dies"

    reg2 = SessionRegistry(db, model_factory=leak_factory)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume" and data["mode"] == "converse"
    tag_c, data_c = reg2.converse("s1", "so about that other problem…")
    assert tag_c == "say"
    assert data_c["text"] == voice_mod.SAFE_CONTRACT  # union screen caught the lost-exp move

    # and an UNRESOLVABLE lost exp fails closed too (never unscreened)
    store = SittingStore(db)
    sit = store.live_sitting()
    store.write_state(
        sit["id"], inflight={"experience_id": "retired_exp", "ledger_ref": "veldra:gone"}
    )
    reg3 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg3.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    tag_c3, data_c3 = reg3.converse("s1", "hello again")
    assert tag_c3 == "say" and data_c3["text"] == voice_mod.SAFE_CONTRACT


def test_reopen_seam_on_reentering_the_interrupted_door(tmp_path, make_fake):
    """C12: continuing back into the restart-interrupted door carries the reopen seam, not the
    generic one — mechanical honesty about the visible prior words."""
    db = str(tmp_path / "reopen.db")
    reg, _ = _converge_one(db, make_fake)
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 in flight (its ref == the persisted next_pick)

    reg2 = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    tag2, data2 = reg2.continue_session("s1")
    assert tag2 == "say"
    assert data2.get("seam") == (
        "Starting this one over — restate your position, or build on what you wrote above."
    )


# ---- The living sitting (plan L4): worker front door, same-world continue, rebuild fidelity,
# ---- bounded difficulty, sitting close (spec §2a/§2c/§2e/§2f/§2g) ---------------------------

from retnovation.content_loader import load_territory_text  # noqa: E402
from retnovation.web import voice as _voice  # noqa: E402
from retnovation.web.session_runner import (  # noqa: E402
    _FRONTDOOR_ASK,
    _HONEST_FIT,
    _RESERVE_COPY,
    _STATIC_BRIDGE,
    _territory_subtitle,
)
from retnovation.web.sitting_store import SittingStore  # noqa: E402

_SITUATION = "Signing a delivery commitment Thursday; the penalty clause is the fight."

# Clears the forge's code gates against EVERY rubric (structural + validate_scene — verified in
# dev against all five), so the same fake serves whatever territory the flow targets next.
_SCENARIO = (
    "You signed the delivery agreement on Thursday, and this morning your second-largest "
    "customer asked for the same penalty terms before Fridays board review. The account team "
    "wants an answer before the standup, and whatever you give one customer the others will "
    "hear about. What do you do?"
)

# Library (glob-sorted) order — FakeModel.map_territories ranks in given order, so the mapped
# territory is the first and Continue walks this order minus the window.
_T1, _T2, _T3 = "continuity_lock_in", "decision_under_stakes", "irreversible_anchor"


def _world_factory(make_fake, briefs=None, outcome=None, screens=None):
    """Problem-agnostic fake whose forge_scenario clears the gates. `briefs` collects
    (brief, steer) across segments (the level spy reads the Level: line); `outcome` is a mutable
    {'v': ...} so a test can flip converge/plateau mid-sitting; `screens` counts screen_moves
    calls (the ONE-union-call assertion)."""
    outcome = outcome if outcome is not None else {"v": "closed"}

    def factory():
        m = make_fake()
        m.classify_intake = lambda exp, opening: IntakeClassification(
            frame_states={f.frame_code: FrameState.absent for f in exp.rubric.frames},
            trap_states={t.trap_code: TrapState.not_tripped for t in exp.rubric.traps},
        )
        m.classify_response = lambda exp, kind, code, push, response, stress=False: (
            ResponseClassification(
                outcome=outcome["v"],
                mechanism_supplied=(outcome["v"] == "closed"),
                hard_wrong=False,
            )
        )

        def fs(brief, steer=""):
            if briefs is not None:
                briefs.append((brief, steer))
            return _SCENARIO

        m.forge_scenario = fs
        if screens is not None:
            orig_screen = m.screen_moves

            def counting(moves, text):
                screens.append(list(moves))
                return orig_screen(moves, text)

            m.screen_moves = counting
        return m

    return factory


def _open_world(reg, sid="s1", situation=_SITUATION, now=NOW):
    """Cold start through the front door with free text; returns the forged opening say data."""
    tag, data = reg.start(sid, now=now)
    assert tag == "say" and data.get("frontdoor"), (tag, data)
    tag, data = reg.step(sid, situation)
    assert tag == "say", (tag, data)
    return data


def test_front_door_free_text_forges_the_world_end_to_end(tmp_path, make_fake):
    """The battery's spine (spec §2a/§2g): static ask + small doors → free text → heard-you
    bridge riding the forged opening (the scenario IS the opening) → engine grades → landing.
    The world/instance rows persist; the transcript persists ask/text/bridge; no gen: on any
    wire payload or persisted turn."""
    db = str(tmp_path / "fd.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data.get("frontdoor") is True
    assert data["text"] == _FRONTDOOR_ASK  # STATIC — the coldest beat pays zero model calls
    assert data["menu"]["problems"] and data["menu"].get("nonce")  # the small doors + nonce
    assert data.get("theme")  # phase-1 persona theme rides the cold beat

    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say" and data["text"] == _SCENARIO  # the forged scenario IS the opening (M6)
    assert data.get("bridge") == "[reflect]"  # the screened heard-you reflection (D9)

    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_world(sit) == _SITUATION  # written BEFORE forging (P1 no-poisoning)
    row = store.read_generated_problem(f"gen:{sit}:1")
    assert row == {"experience_id": _T1, "scenario": _SCENARIO}

    tag, data = _drive(reg, "s1", opening="my position on the penalty")
    assert tag == "done" and data["landing"]
    # Continue is subtitled with the NEXT territory's description (P4), never the worked one
    assert data["next_title"] == _territory_subtitle(_T2)
    log = store.converged_log()
    assert [(r["ref"], r["experience_id"]) for r in log] == [(f"gen:{sit}:1", _T1)]

    turns = store.turns(sit)
    kinds = [t["kind"] for t in turns]
    assert kinds[:4] == ["vera", "you", "bridge", "vera"]  # ask, her text, bridge, opening
    assert turns[0]["payload"]["text"] == _FRONTDOOR_ASK
    assert turns[1]["payload"]["text"] == _SITUATION
    assert turns[2]["payload"]["text"] == "[reflect]"
    assert turns[3]["payload"]["text"] == _SCENARIO
    import json as _json

    assert "gen:" not in _json.dumps([t["payload"] for t in turns])  # L-13 on the durable mirror


def test_front_door_menu_click_still_opens_a_curated_door(tmp_path, make_fake):
    """Doors-path unchanged: an int through the front door is today's curated menu path — no
    world row, no forge, the authored curated opening."""
    db = str(tmp_path / "fd-doors.db")
    reg = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data.get("frontdoor")
    tag, data = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    assert tag == "say" and data["text"] == "[open]"  # voice.opening via concierge_open
    assert "bridge" not in data
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) is None  # no world was opened


def test_front_door_low_confidence_honest_fit_then_text_proceeds(tmp_path, make_fake):
    """§2a honest fit: low mapper confidence serves the user-centric copy VERBATIM (territory
    description inlined) and collects again — any text proceeds with the mapped territory."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories

        def low(situation, territories):
            out = orig(situation, territories)
            return out.model_copy(update={"confidence": "low"})

        m.map_territories = low
        return m

    db = str(tmp_path / "fd-low.db")
    reg = SessionRegistry(db, model_factory=factory)
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data.get("frontdoor")
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say"
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _HONEST_FIT.format(desc=desc)  # the pinned copy, verbatim
    tag, data = reg.step("s1", "yes — start there")
    assert tag == "say" and data["text"] == _SCENARIO  # proceeds with the MAPPED territory
    assert data.get("bridge") == "[reflect]"
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) == _SITUATION  # her ORIGINAL situation


def test_front_door_low_confidence_int_takes_a_door(tmp_path, make_fake):
    """The honest-fit round-trip's other exit: an int goes to today's menu path."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    reg = SessionRegistry(str(tmp_path / "fd-low2.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say" and "other doors" in data["text"]
    tag, data = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    assert tag == "say" and data["text"] == "[open]"  # curated door, no forge


def test_leaking_reflection_serves_the_static_bridge(tmp_path, make_fake):
    """L4 review F2 (D9 teeth): a reflection that PERFORMS a move of the mapped territory must
    not ride the opening — the static bridge serves instead. The leak fake flags ONLY the exact
    reflection text, so the forge's union screen (the scenario) and every other authored
    surface stay clean — this test discriminates the reflection gate specifically."""
    from retnovation.model import EgressScreen

    def factory():
        m = _world_factory(make_fake)()

        def screen(moves, text):
            if text == "[reflect]":
                return EgressScreen(performed=[1], evidence="(fake: reflection leaks)")
            return EgressScreen(performed=[], evidence="(fake: clean)")

        m.screen_moves = screen
        return m

    reg = SessionRegistry(str(tmp_path / "fd-leak.db"), model_factory=factory)
    data = _open_world(reg)  # cold start -> free text -> forged opening
    assert data["text"] == _SCENARIO  # the forge still serves (its union screen stayed clean)
    assert data.get("bridge") == _STATIC_BRIDGE  # the leaked reflection never rides


def test_resume_mid_front_door_same_process_reserves_the_ask(tmp_path, make_fake):
    """New resume state (§2g): a session parked in the front-door loop (live worker) resumes
    with the ask re-served over the same live queues — same nonce, composer alive."""
    reg = SessionRegistry(str(tmp_path / "fd-park.db"), model_factory=_world_factory(make_fake))
    tag, data = reg.start("s1", now=NOW)
    nonce = data["menu"]["nonce"]
    tag, rdata = reg.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume" and rdata["mode"] == "engine"
    assert rdata["frontdoor"]["text"] == _FRONTDOOR_ASK
    assert rdata["frontdoor"]["menu"]["problems"]
    assert rdata["frontdoor"]["menu"]["nonce"] == nonce  # the SAME pending menu answers it
    # the live loop is intact: her text still forges the world
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say" and data["text"] == _SCENARIO


def test_restart_mid_front_door_resumes_honestly_with_the_world(tmp_path, make_fake):
    """Cross-restart mid-front-door (§2g): her text + world row persisted, worker died before
    the opening — the resume re-serves the static ask over her visible words; no false honesty
    line (nothing graded was lost)."""

    def factory():
        m = _world_factory(make_fake)()

        def boom(situation, territories):
            raise RuntimeError("mapper down")

        m.map_territories = boom
        return m

    db = str(tmp_path / "fd-mid.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    tag, _ = reg.step("s1", _SITUATION)  # world written, then the mapper dies -> error
    assert tag == "error"
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_world(sit) == _SITUATION  # the world survived the failed forge

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    assert data["frontdoor"]["text"] == _FRONTDOOR_ASK
    assert data["honesty"] == ""  # no segment was lost — the ask is simply re-served
    assert any(t["text"] == _SITUATION for t in data["turns"])  # her words, visible
    tag, data = reg2.step("s1", _SITUATION)  # the live loop works after the restart
    assert tag == "say" and data["text"] == _SCENARIO


def test_restart_after_forged_convergence_rebuilds_the_generated_prompt(tmp_path, make_fake):
    """Review M2 (must-fix): post-restart converse/close must author over the GENERATED
    scenario, never the curated prompt beneath her generated conversation."""
    problems = []

    def spy_factory():
        m = _world_factory(make_fake)()
        orig = m.concierge_converse

        def rec(problem, recent, *, stop_reason="converged", voice=""):
            problems.append(problem)
            return orig(problem, recent, stop_reason=stop_reason, voice=voice)

        m.concierge_converse = rec
        return m

    db = str(tmp_path / "fd-rebuild.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="my position")
    assert tag == "done"
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    ser = store.read_state(sit)["record"]
    assert ser["ledger_ref"] == f"gen:{sit}:1"  # instance-grain identity persisted (M2)

    reg2 = SessionRegistry(db, model_factory=spy_factory)
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume" and data["mode"] == "converse"
    tag, data = reg2.converse("s1", "so what did that cost me?")
    assert tag == "say" and data["text"]
    assert problems == [_SCENARIO]  # the author saw the GENERATED prompt, not the curated one


def test_missing_generated_row_degrades_to_statics(tmp_path, make_fake):
    """M2's failure branch: a gen: record whose instance row is gone serves statics — never an
    unscreened author, never a 500."""
    db = str(tmp_path / "fd-gone.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="my position")
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    ser = store.read_state(sit)["record"]
    ser["ledger_ref"] = "gen:someother:9"  # a row no store has
    store.write_state(sit, record=ser)

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    tag, data = reg2.converse("s1", "hello again")
    assert tag == "say" and data["text"] == _voice.SAFE_CONTRACT
    tag, data = reg2.close("s1")
    assert tag == "close" and isinstance(data["terrain"], list)


def test_continue_forges_the_next_territory_and_windows_the_worked_one(tmp_path, make_fake):
    """§2c: Continue targets the next territory (mapper rank minus the 24h territory window) on
    the SAME world; the generic seam rides the forged opening; a new instance row lands."""
    db = str(tmp_path / "fd-cont.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, data = _drive(reg, "s1", opening="my position")
    assert tag == "done"
    tag, data = reg.continue_session("s1")
    assert tag == "say" and data["text"] == _SCENARIO  # the next forged opening, one request
    assert data.get("seam") == "Same sitting — next door."
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    row = store.read_generated_problem(f"gen:{sit}:2")
    assert row is not None and row["experience_id"] == _T2  # T1 windowed -> T2 targeted
    turns = store.turns(sit)
    marker = next(t for t in turns if t["kind"] == "muted")
    assert _territory_subtitle(_T2) in marker["payload"]["text"]  # Continue → {subtitle}


def test_all_windowed_serves_informed_reserve_and_work_anyway_forges_least_recent(
    tmp_path, make_fake
):
    """§2c review P3: every territory inside the window is a DEFINED state — the informed
    re-serve copy (verbatim), never a false fresh door; work-anyway forges the least-recent
    territory; 'tomorrow' costs nothing (the continuation was not consumed)."""
    db = str(tmp_path / "fd-window.db")
    store = SittingStore(db)
    wall = datetime.now(timezone.utc)
    aged = ["irreversible_anchor", "license_continuity", "proof_before_promise", _T2]
    for i, eid in enumerate(aged):  # oldest first: irreversible_anchor
        store.log_converged("prior", f"gen:prior:{i}", wall - timedelta(hours=4 - i), eid)

    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, data = _drive(reg, "s1", opening="my position")
    assert tag == "done" and data["next_title"] == ""  # nothing honest to subtitle

    tag, data = reg.continue_session("s1")
    assert tag == "reserve"
    assert data["copy"] == _RESERVE_COPY
    assert data["choices"] == ["Work it anyway", "Come back tomorrow"]

    tag, data = reg.continue_session("s1", work_anyway=True)  # not consumed by the question
    assert tag == "say" and data["text"] == _SCENARIO
    sit = store.live_sitting()["id"]
    row = store.read_generated_problem(f"gen:{sit}:2")
    assert row is not None and row["experience_id"] == "irreversible_anchor"  # least recent


def test_fallback_rides_the_bridge_and_continue_retries_the_forge(tmp_path, make_fake):
    """Review P1: a failed forge serves the CURATED base with the bridge line riding the
    opening payload; the world persists and the NEXT continue runs the forge again — a
    fallback never poisons the sitting."""
    calls = {"n": 0}

    def factory():
        m = _world_factory(make_fake)()

        def degenerate(brief, steer=""):
            calls["n"] += 1
            return "[forged scenario]"  # fails the structural gate both attempts

        m.forge_scenario = degenerate
        return m

    db = str(tmp_path / "fd-fall.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say" and data["text"] == "[open]"  # the curated base's authored opening
    assert data.get("bridge") == (
        "I'll hold your situation — first, work this one; "
        "it's the same pressure you're standing in."
    )
    assert calls["n"] == 2  # one generation + ONE steered regen, then the honest fallback
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_world(sit) == _SITUATION  # the world row persists through the fallback
    assert store.read_generated_problem(f"gen:{sit}:1") is None  # no instance row on fallback

    tag, data = _drive(reg, "s1", opening="my position")
    assert tag == "done"
    tag, data = reg.continue_session("s1")
    assert tag == "say" and data["text"] == "[open]"  # fallback again, honestly
    assert calls["n"] == 4  # the forge RAN again on the next continue (no poisoning)


def test_level_steps_one_per_move_and_snaps_back(tmp_path, make_fake):
    """§2e: the brief's Level line walks base → firm → tight one step per converged move and
    snaps back one step on any non-converged stop; never a prose delta."""
    briefs: list[tuple[str, str]] = []
    outcome = {"v": "closed"}
    reg = SessionRegistry(
        str(tmp_path / "lvl.db"),
        model_factory=_world_factory(make_fake, briefs=briefs, outcome=outcome),
    )
    _open_world(reg, "s1")
    assert "Level: base" in briefs[-1][0].splitlines()  # a new world opens at base
    _drive(reg, "s1", opening="p1")
    assert reg.continue_session("s1")[0] == "say"
    assert "Level: firm" in briefs[-1][0].splitlines()  # one step up after a convergence
    _drive(reg, "s1", opening="p2")
    assert reg.continue_session("s1")[0] == "say"
    assert "Level: tight" in briefs[-1][0].splitlines()  # capped top of the enum
    outcome["v"] = "unchanged"  # this segment plateaus
    tag, _ = _drive(reg, "s1", opening="p3")
    assert tag == "done"
    outcome["v"] = "closed"
    assert reg.continue_session("s1")[0] == "say"
    assert "Level: firm" in briefs[-1][0].splitlines()  # snap back ONE step, immediately


def test_level_derives_from_durable_history_after_restart(tmp_path, make_fake):
    """§2e across a restart: the level re-derives deterministically from the converged log +
    the persisted record's stop_reason (converge once, then plateau -> back to base)."""
    briefs: list[tuple[str, str]] = []
    outcome = {"v": "closed"}
    db = str(tmp_path / "lvl-r.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake, outcome=outcome))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="p1")  # converged: level idx 1
    outcome["v"] = "unchanged"
    assert reg.continue_session("s1")[0] == "say"
    tag, _ = _drive(reg, "s1", opening="p2")  # plateau: snap back to 0
    assert tag == "done"

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake, briefs=briefs))
    tag, _ = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume"
    assert reg2.continue_session("s1")[0] == "say"
    assert "Level: base" in briefs[-1][0].splitlines()  # derived: 1 convergence − 1 snap-back


def test_reopen_seam_keys_on_experience_id_after_restart(tmp_path, make_fake):
    """Review M8: a forged lost segment's gen: ref never equals a menu ref — the reopen
    comparison keys on the TERRITORY (experience_id) and survives a restart."""
    db = str(tmp_path / "fd-reopen.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="p1")
    tag, _ = reg.continue_session("s1")
    assert tag == "say"  # segment 2 forged over _T2, opening served; now the process "dies"

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume" and "restarted mid-problem" in data["honesty"]
    tag, data = reg2.continue_session("s1")
    assert tag == "say" and data["text"] == _SCENARIO
    assert data.get("seam") == _REOPEN_SEAM_TEXT  # re-entering the interrupted TERRITORY


_REOPEN_SEAM_TEXT = (
    "Starting this one over — restate your position, or build on what you wrote above."
)


def test_return_visit_line_rides_the_cold_front_door(tmp_path, make_fake):
    """Review P10: a cold start with closed worlds is not amnesiac — one muted line above the
    ask, counted from the converged log. L4 review F4: both nouns pluralize correctly
    ("1 house" / "2 houses"; the region count stays singular when both rows share a territory)."""
    db = str(tmp_path / "fd-return.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="p1")
    reg.close("s1")  # the sitting ends; the log survives (L-3)

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "say" and data.get("frontdoor")
    assert data["returning"] == "Your world so far: 1 house, 1 region alight."

    # A second sitting converges the SAME territory (the free-text map ignores the window):
    # two houses, one region — the mixed case pins both plural branches at once.
    tag, data = reg2.step("s1", _SITUATION)
    assert tag == "say"
    tag, _ = _drive(reg2, "s1", opening="p2")
    assert tag == "done"
    reg2.close("s1")

    reg3 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg3.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "say" and data.get("frontdoor")
    assert data["returning"] == "Your world so far: 2 houses, 1 region alight."


def test_menu_marks_a_forge_converged_territory_as_just_worked(tmp_path, make_fake):
    """L4 review F1: a forged convergence logs a gen: ref that never matches a curated menu
    ref — the ' · just worked' marker keys on the TERRITORY too, so re-entering the doors
    within the window is an informed choice, never a silent re-serve."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"ranked": [_T2, _T1, _T3]})
        return m

    db = str(tmp_path / "fd-mark.db")
    reg = SessionRegistry(db, model_factory=factory)
    _open_world(reg, "s1")  # forges over _T2 (the fake ranks it first)
    tag, _ = _drive(reg, "s1", opening="p1")
    assert tag == "done"  # converged: the log holds (gen:{sit}:1, _T2)

    tag, data = reg.continue_session("s1", menu=True)  # back through the front door
    assert tag == "say" and data.get("frontdoor")
    problems = data["menu"]["problems"]
    title = _voice.display_titles()["veldra:concentrated_market_pricing_power"]
    assert title + " · just worked" in problems  # territory-keyed (the gen: ref matches no door)
    marked = [p for p in problems if p.endswith(" · just worked")]
    assert len(marked) == 1  # the unworked doors stay clean


def test_sitting_close_receives_all_segments_and_screens_once(tmp_path, make_fake):
    """§2f: the close author receives the whole sitting (kind-filtered you/vera turns per
    segment + the situation) and its output crosses ONE union egress screen (M13)."""
    closes = []
    screens: list[list[str]] = []

    def factory():
        m = _world_factory(make_fake, screens=screens)()
        orig = m.concierge_sitting_close

        def rec(situation, segments, voice=""):
            closes.append((situation, segments))
            return orig(situation, segments, voice)

        m.concierge_sitting_close = rec
        return m

    db = str(tmp_path / "fd-close.db")
    reg = SessionRegistry(db, model_factory=factory)
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="position one")
    assert reg.continue_session("s1")[0] == "say"
    _drive(reg, "s1", opening="position two")

    n_before = len(screens)
    tag, data = reg.close("s1")
    assert tag == "close" and data["close"] == "[sitting close]"
    assert len(closes) == 1
    situation, segments = closes[0]
    assert situation == _SITUATION
    assert len(segments) == 2  # one per landed segment, split on landing turns
    assert all(role in ("you", "vera") for seg in segments for role, _ in seg)
    assert any(text == "position one" for role, text in segments[0] if role == "you")
    assert any(text == "position two" for role, text in segments[1] if role == "you")
    assert len(screens) - n_before == 1  # ONE union screen call over the sitting's moves
    union = screens[-1]
    assert len(union) == len(set(union))  # deduped
    # L4 review F6 (discriminating): the union must COVER every converged territory — a
    # regression to a single-territory union would silently shrink it otherwise.
    from retnovation.content_loader import load_library
    from retnovation.web import voice as _v2

    eids = {r["experience_id"] for r in SittingStore(db).converged_log()}
    assert len(eids) == 2
    by_eid = {e.experience_id: e for e in load_library()}
    for eid in eids:
        assert set(_v2._moves(by_eid[eid])) & set(union), f"union misses territory {eid}"
    assert isinstance(data["terrain"], list)


def test_sitting_close_falls_back_static_on_screen_failure(tmp_path, make_fake):
    """The union screen flags the authored sitting close -> the safe static serves."""
    from retnovation.model import EgressScreen

    def factory():
        m = _world_factory(make_fake)()

        def screen(moves, text):
            if text == "[sitting close]":
                return EgressScreen(performed=[1], evidence="(fake: close leaks)")
            return EgressScreen(performed=[], evidence="(fake: clean)")

        m.screen_moves = screen
        return m

    reg = SessionRegistry(str(tmp_path / "fd-close2.db"), model_factory=factory)
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="p1")
    tag, data = reg.close("s1")
    assert tag == "close"
    assert data["close"] == _voice._STATIC_CLOSE  # never an unscreened sitting story


def test_front_door_park_is_reaped_on_stale_cold_start(tmp_path, make_fake):
    """The front-door collect honors the poison pill: an 18h-stale cold start over a
    front-door-parked worker reaps it (store closes, thread exits)."""
    reg = SessionRegistry(str(tmp_path / "fd-reap.db"), model_factory=_world_factory(make_fake))
    tag, _ = reg.start("s1", now=NOW)
    assert tag == "say"
    old_ch = reg._ch["s1"]
    assert old_ch.thread.is_alive()
    later = datetime.now(timezone.utc) + timedelta(hours=19)
    tag, data = reg.resume_or_start("s1", now=later)
    assert tag == "say" and data.get("frontdoor")  # a fresh cold front door
    old_ch.thread.join(timeout=5)
    assert not old_ch.thread.is_alive()


def test_forged_flow_never_leaks_gen_refs_on_the_wire(tmp_path, make_fake):
    """L-13 extension: no gen: ref in ANY payload across the whole forged flow (front door,
    opening, done, resume, close)."""
    import json as _json

    db = str(tmp_path / "fd-l13.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    blobs = []
    tag, data = reg.start("s1", now=NOW)
    blobs.append({"text": data["text"], "menu": {"problems": data["menu"]["problems"]}})
    tag, data = reg.step("s1", _SITUATION)
    blobs.append(data)
    tag, data = _drive(reg, "s1", opening="my position")
    blobs.append({"landing": data.get("landing", ""), "next_title": data.get("next_title", "")})
    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    blobs.append(data)
    tag, data = reg2.close("s1")
    blobs.append(data)
    assert "gen:" not in _json.dumps(blobs, default=str)


def test_errored_segment_reply_nudges_refresh_not_dead_end(tmp_path, make_fake):
    """Founder live dogfood 2026-07-02: after a mid-press model error killed the worker, every
    reply dead-ended in 'session already ended'. An errored (record-less) terminal channel must
    point at the honest way forward — refresh resumes the durable sitting."""

    def factory():
        m = make_fake()

        def boom(exp, opening):
            raise RuntimeError("truncated mid-press")

        m.classify_intake = boom
        return m

    reg = SessionRegistry(str(tmp_path / "doorfail.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, _ = reg.step("s1", "a real position")
    assert tag == "error"  # the worker died loudly
    tag2, data2 = reg.step("s1", "hello? are you still there?")
    assert tag2 == "nudge"
    assert "refresh" in data2["message"]  # actionable, not 'session already ended'


def test_resume_at_the_front_door_shows_one_ask(tmp_path, make_fake):
    """Founder live dogfood 2026-07-02: the doubled intro. A reload parked at the front door must
    render the ask ONCE — the replayed transcript turn and the re-served block dedupe, and
    repeated cross-restart resumes never accumulate ask turns durably."""
    from retnovation.web.sitting_store import SittingStore

    db = str(tmp_path / "oneask.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data.get("frontdoor")

    # same-process reload parked at the ask
    tag, data = reg.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "resume" and data.get("frontdoor")
    ask = data["frontdoor"]["text"]
    replayed_asks = [t for t in data["turns"] if t["kind"] == "vera" and t["text"] == ask]
    assert replayed_asks == []  # the block re-serves it; the replay must not double it

    # cross-restart resumes never accumulate duplicate ask turns in the durable mirror
    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    reg3 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg3.resume_or_start("s1", now=datetime.now(timezone.utc))
    store = SittingStore(db)
    sit = store.live_sitting()
    asks = [
        t for t in store.turns(sit["id"]) if t["kind"] == "vera" and t["payload"].get("text") == ask
    ]
    assert len(asks) == 1
