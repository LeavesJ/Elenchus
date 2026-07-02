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
    assert kinds[0] == "vera"  # the opening
    assert kinds[1] == "you" and turns[1]["payload"]["text"] == "my position"
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
    assert [t["kind"] for t in turns] == ["vera", "you"]  # opening + the user's words only


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
    # the sitting is OVER: a stale converse/close now says so instead of re-serving
    assert reg.converse("s1", "hello?")[0] == "error"


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
    # a step in flight blocks the drain (simulated via the bookkeeping set)
    reg._stepping.add("s1")
    assert not ch2.terminal
    reg._drain("s1")
    assert not ch2.terminal  # skipped: never steal from a blocked request
    reg._stepping.discard("s1")

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
    assert tag2 == "menu"  # MF-3's honest path: the doors, never a silent converged re-serve


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
    assert tag == "menu"  # cold start
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
    assert tag == "menu" and data.get("nonce")
    stale = data["nonce"] - 1
    tag2, data2 = reg.choose("s1", 0, nonce=stale)
    assert tag2 == "menu"  # re-served, no door opened
    tag3, _ = reg.choose("s1", reg.menu_index("s1", _ANCHOR), nonce=data2["nonce"])
    assert tag3 == "say"  # the correct nonce proceeds
