from datetime import datetime, timedelta, timezone

import pytest

from elenchus.aim import aim, derive_core
from elenchus.cli import build_store
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
from elenchus.orchestration import run_session
from elenchus.types import (
    ConverseTurn,
    EntryClass,
    EntryClassification,
    FrameState,
    Regime,
    TerritoryMap,
    TrapState,
    Work,
)
from elenchus.web.session_runner import SessionRegistry

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)
_ANCHOR = "veldra:embedded_anchor_lock_in"


def test_start_emits_error_on_worker_failure(tmp_path, make_fake):
    # tmp_path is a directory -> build_store's sqlite connect raises inside the worker
    # -> error emission (no hang); verifies the "exception inside worker → error, never hang" guarantee
    reg = SessionRegistry(str(tmp_path), model_factory=make_fake)
    tag, data = reg.start("s_err", now=NOW)
    assert tag == "error" and "message" in data


def test_worker_failure_logs_the_traceback_and_keeps_the_wire_generic(tmp_path, make_fake, caplog):
    """Founder live dogfood 2026-07-03: the wire's repr(e) was the failure's ONLY copy, and the
    refresh the recovery path itself recommends destroyed it — the error class was unrecoverable.
    The traceback must land in the SERVER log; the wire carries only the generic nudge (exception
    text can name frames/refs — the L-14 class applies to the transient wire too)."""

    def factory():
        m = make_fake()

        def boom(exp, opening):
            raise RuntimeError("frame-naming-detail")

        m.classify_intake = boom
        return m

    reg = SessionRegistry(str(tmp_path / "log.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", reg.menu_index("s1", _ANCHOR))
    tag, data = reg.step("s1", "a real position")
    assert tag == "error"
    assert "frame-naming-detail" not in data["message"]  # the wire never carries the exception
    assert "refresh" in data["message"]  # actionable copy, same as the dead-channel nudge
    rec = next(r for r in caplog.records if "segment worker died" in r.getMessage())
    assert rec.exc_info is not None and rec.exc_info[0] is RuntimeError


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
    from elenchus.assessment.judgment_loop import MAX_PUSHES

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


def _arm_steer(
    reg, sid, *, next_pressure, ranked_first=None, confidence="high", verdict="decision"
):
    """Override the converged record's model so the NEXT converse raises `next_pressure` and the
    capture mapper ranks `ranked_first` (default: a territory OTHER than the one just worked, so it
    is non-windowed → servable) with the given verdict/confidence. Returns the target eid. Mirrors
    how the record's own model authors the wind-down (converse uses rec['model'])."""
    from elenchus.content_loader import load_library

    worked = reg._last_record[sid]["exp"].experience_id
    open_eids = [e.experience_id for e in load_library() if e.regime is Regime.open_ended]
    target = ranked_first or next(e for e in open_eids if e != worked)
    m = reg._last_record[sid]["model"]
    m.concierge_converse = lambda problem, recent, *, stop_reason="converged", voice="": (
        ConverseTurn(reply="that's the edge of this one", next_pressure=next_pressure)
    )
    m.map_territories = lambda situation, territories: TerritoryMap(
        ranked=[target] + [e for e, _ in territories if e != target],
        confidence=confidence,
        reflection="[r]",
        verdict=verdict,
        conversion="",
    )
    return target


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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.content_loader import load_library

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
    from elenchus.web.sitting_store import SittingStore

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
    # Cause-neutral lost-segment honesty (C7/C16): an honesty line is served, but it does not
    # assert a specific cause — a genuine restart and a re-entry reload share this branch.
    assert data["honesty"] == _HONESTY_LOST_LANDED
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
    assert data["honesty"] == _HONESTY_LOST_FIRST  # cause-neutral; nothing landed (C7/C16)
    assert data["mode"] == "engine" and data["end_visible"] is False
    assert data["menu"] and data["menu"]["problems"]  # a fresh way forward
    assert "refs" not in data["menu"]  # L-13: the embedded menu is title-only
    assert "eids" not in data["menu"]  # L-13: the F1 territory keys stay server-side too


def test_rolling_window_dedupe_across_processes(tmp_path, make_fake):
    """Refs converged in a PRIOR process within 24h are excluded from the auto-pick even across a
    UTC date boundary; a stale persisted next_pick into a since-converged ref drops to the menu."""
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.web.sitting_store import SittingStore

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
    from elenchus.content_loader import load_library
    from elenchus.model import EgressScreen
    from elenchus.web import voice as voice_mod
    from elenchus.web.sitting_store import SittingStore

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
    # union screen caught the lost-exp move → fail closed to the HONEST static, never the
    # SAFE_CONTRACT "I'll push" lie (spec §2c consistency fold, 2026-07-05)
    assert data_c["text"] == voice_mod._CONVERSE_DONE_FRESH
    assert data_c["text"] != voice_mod.SAFE_CONTRACT

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
    assert tag_c3 == "say" and data_c3["text"] == voice_mod._CONVERSE_DONE_FRESH


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

from elenchus.content_loader import load_territory_text  # noqa: E402
from elenchus.web import session_runner  # noqa: E402
from elenchus.web import voice as _voice  # noqa: E402
from elenchus.web.session_runner import (  # noqa: E402
    _CONFIRM_COPY,
    _FRONTDOOR_ASK,
    _HONEST_FIT,
    _HONESTY_LOST_FIRST,
    _HONESTY_LOST_LANDED,
    _RESERVE_COPY,
    _STATIC_BRIDGE,
    _territory_subtitle,
)
from elenchus.web.sitting_store import SittingStore  # noqa: E402

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


def _world_factory(make_fake, briefs=None, outcome=None, screens=None, maps=None):
    """Problem-agnostic fake whose forge_scenario clears the gates. `briefs` collects
    (brief, steer) across segments (the level spy reads the Level: line); `outcome` is a mutable
    {'v': ...} so a test can flip converge/plateau mid-sitting; `screens` counts screen_moves
    calls (the ONE-union-call assertion); `maps` counts map_territories calls (the deterministic-
    consume assertion — a steered Continue makes NO second map call)."""
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
        if maps is not None:
            orig_map = m.map_territories

            def counting_map(situation, territories):
                maps.append(situation)
                return orig_map(situation, territories)

            m.map_territories = counting_map
        return m

    return factory


def _open_world(reg, sid="s1", situation=_SITUATION, now=NOW):
    """Cold start through the front door with free text; returns the forged opening say data.
    The default fake maps high-confidence/decision, so the honest-fit beat never intervenes and
    the very next beat is THE CONFIRM BEAT (Spec-3 P1 §4a) — answer it affirmatively so this
    helper still returns the forged opening, not the confirm ask."""
    tag, data = reg.start(sid, now=now)
    assert tag == "say" and data.get("frontdoor"), (tag, data)
    tag, data = reg.step(sid, situation)
    assert tag == "say", (tag, data)
    tag, data = reg.step(sid, "yes")  # she agrees this is the decision — nothing forged before this
    assert tag == "say", (tag, data)
    return data


def _mapper_factory(make_fake, script):
    """World factory whose map_territories pops one update-dict per call from `script`
    (merged over the base fake's TerritoryMap); an empty/exhausted script = base output."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories

        def mapper(situation, territories):
            out = orig(situation, territories)
            return out.model_copy(update=script.pop(0)) if script else out

        m.map_territories = mapper
        return m

    return factory


def test_topic_intake_gets_the_conversion_beat_then_a_decision_proceeds(tmp_path, make_fake):
    """Spec §2a: a question is answered with a CONVERSION (their subject + the call inside
    it), and the reply is a fresh intake — a decision reply proceeds to the forge. The world
    row follows the latest fed text; the wire stays kind+text."""
    script = [
        {
            "verdict": "topic",
            "conversion": "You're asking about onboarding — inside that build, what's the next call you have to make?",
        },
        {},  # the reply re-maps as a decision (base defaults: decision / high)
    ]
    db = str(tmp_path / "conv.db")
    reg = SessionRegistry(db, model_factory=_mapper_factory(make_fake, script))
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "what should optimal onboarding look like?")
    assert tag == "say"
    assert "what's the next call" in data["text"]  # the authored conversion served
    tag, data = reg.step("s1", "I must decide whether to gate signup behind SSO by Friday")
    assert tag == "say" and data["text"] != _SCENARIO  # the confirm beat rides first, not yet
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees this is the decision
    assert tag == "say" and data["text"] == _SCENARIO  # re-mapped as decision -> forged
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]).startswith("I must decide")
    _, rdata = reg.resume_or_start("s1")
    assert all(set(t) == {"kind", "text"} for t in rdata["turns"])  # wire purity


def test_second_topic_falls_through_to_the_honest_fit_beat(tmp_path, make_fake):
    """Spec §2a: exactly ONE conversion per pass — a second topic reply takes the honest-fit
    beat on the re-map's best stretch (doors escape lives there); consent semantics then
    proceed as today."""
    script = [
        {"verdict": "topic", "conversion": "First conversion question?"},
        {"verdict": "topic", "conversion": "Second conversion would be an interrogation"},
    ]
    reg = SessionRegistry(
        str(tmp_path / "conv2.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a question about strategy")
    assert data["text"] == "First conversion question?"
    tag, data = reg.step("s1", "another question, still not a decision")
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _HONEST_FIT.format(desc=desc)  # fit beat, NOT a second conversion
    tag, data = reg.step("s1", "fine, start there")  # proceeds with the mapped territory
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert tag == "say" and data["text"] == _SCENARIO  # consent proceeds as today


def test_a_correction_that_maps_to_a_topic_gets_the_conversion_beat(tmp_path, make_fake):
    """THE 2026-07-26 NAMED RESIDUAL, and the founder's own live path. His correction ("no no
    like how to get my first client") re-maps as a TOPIC, and the confirm loop re-served the
    CONFIRM beat — which ASSERTS "here's the decision I'd put to you" about a subject that names
    no decision at all. For a topic the conversion beat ASKS. Nothing false was written before
    this fix, but the wrong beat was serving his most common correction."""
    conversion = "Getting your first client — what's the call you have to make in that?"
    script = [
        {},  # the intake maps as a decision (base defaults) -> the confirm beat asserts it
        {"verdict": "topic", "confidence": "low", "conversion": conversion},  # his correction
        {},  # his answer to the conversion re-maps as a decision -> confirm, then forge
    ]
    db = str(tmp_path / "conv-correct.db")
    reg = SessionRegistry(db, model_factory=_mapper_factory(make_fake, script))
    reg.start("s1", now=NOW)
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    tag, data = reg.step("s1", "startup getting first client")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)  # the confirm beat asserts a decision
    tag, data = reg.step("s1", "no no like how to get my first client")
    assert data["text"] == conversion  # the conversion ASKS — not a second assertion
    decision = "whether to promise a full rebuild to win the first one"
    tag, data = reg.step("s1", decision)
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)  # confirming again, on the NEW mapping
    tag, data = reg.step("s1", "yes")
    assert tag == "say" and data["text"] == _SCENARIO  # forged only after he agreed
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) == decision  # the latest fed text


def test_the_conversion_budget_is_spent_once_across_both_loops(tmp_path, make_fake):
    """Spec §2a's ONE-conversion-per-pass rule spans the front door AND the confirm loop: a topic
    intake that already had its conversion must not get a second one when a later correction maps
    to a topic too. Pressing the conversion twice is an interrogation, and `converted` is the one
    budget both loops spend from.

    Residual 5 (2026-07-28) is what happens INSTEAD, and it used to be the confirm beat: that
    asserts a decision at full confidence on material the mapper has just called a topic, with no
    hedge — the one thing the honest-fit beat exists to prevent. A spent budget is a reason to
    hedge, never a reason to assert."""
    script = [
        {"verdict": "topic", "conversion": "First conversion question?"},
        {},  # her answer maps as a decision -> the confirm beat
        {"verdict": "topic", "conversion": "A second conversion would be an interrogation"},
    ]
    reg = SessionRegistry(
        str(tmp_path / "conv-budget.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a question about strategy")
    assert data["text"] == "First conversion question?"
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    tag, data = reg.step("s1", "I must decide whether to gate signup behind SSO by Friday")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)
    tag, data = reg.step("s1", "no, it's really about pricing")
    assert "interrogation" not in data["text"]  # NOT a second conversion
    assert data["text"] == _HONEST_FIT.format(desc=desc)  # hedged, with the doors escape


def test_click_at_the_confirm_loop_conversion_park_forges_the_clicked_territory(
    tmp_path, make_fake
):
    """The new park is a park like any other (§2b): a door click there is its own consent and
    forges the CLICKED territory around her corrected words — never the naked curated prompt."""
    briefs = []

    def factory():
        m = _world_factory(make_fake, briefs=briefs)()
        orig = m.map_territories
        script = [{}, {"verdict": "topic", "conversion": "What call do you face in that?"}]
        m.map_territories = lambda s, t: (
            orig(s, t).model_copy(update=script.pop(0)) if script else orig(s, t)
        )
        return m

    db = str(tmp_path / "conv-correct-click.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)  # the confirm beat
    correction = "no, it's really about getting the first client at all"
    tag, data = reg.step("s1", correction)
    assert data["text"] == "What call do you face in that?"  # parked at the conversion
    idx = reg._ch["s1"].last_menu_eids.index(_T2)
    tag, data = reg.step("s1", idx)  # the click
    assert tag == "say" and data["text"] == _SCENARIO  # forged, not curated
    assert correction in briefs[-1][0]  # her CORRECTED words are the brief's situation
    store = SittingStore(db)
    row = store.read_generated_problem(f"gen:{store.live_sitting()['id']}:1")
    assert row is not None and row["experience_id"] == _T2  # the CLICKED territory


def test_an_agreement_at_the_confirm_loop_conversion_never_becomes_the_world(tmp_path, make_fake):
    """THE 2026-07-27 EMERGENCY, one beat later — caught by the T2 review of the beat that
    introduced it. The confirm beat's last sentence is "Say yes, or tell me what it actually is",
    so the very next park inherits an invitation to agree. That park asks an OPEN question, and a
    fresh-intake branch there swallowed 'Yes, this is the decision I want to make.' — the literal
    string from his live db — straight into `web_world`, destroying his situation exactly as the
    emergency did. An agreement is not an intake: his correction stands and the beat that NAMES a
    decision asks again."""
    for reply in ["Yes, this is the decision I want to make.", "yes", "correct", "that's it"]:
        briefs = []
        script = [{}, {"verdict": "topic", "confidence": "low", "conversion": "What call?"}]

        def factory(_s=script, _b=briefs):
            m = _world_factory(make_fake, briefs=_b)()
            orig = m.map_territories
            m.map_territories = lambda s, t: (
                orig(s, t).model_copy(update=_s.pop(0)) if _s else orig(s, t)
            )
            return m

        db = str(tmp_path / f"agree-{abs(hash(reply))}.db")
        reg = SessionRegistry(db, model_factory=factory)
        reg.start("s1", now=NOW)
        reg.step("s1", "startup getting first client")
        correction = "no no like how to get my first client"
        tag, data = reg.step("s1", correction)
        assert data["text"] == "What call?"  # parked at the conversion
        tag, data = reg.step("s1", reply)
        store = SittingStore(db)
        assert store.read_world(store.live_sitting()["id"]) == correction, reply
        desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
        assert data["text"] == _HONEST_FIT.format(desc=desc), reply  # asked, never forged blind
        tag, data = reg.step("s1", "yes — start there")  # consent to the named stretch forges
        assert tag == "say" and data["text"] == _SCENARIO
        # The DURABLE world is not the only thing an agreement must not become. Assigning
        # `situation` above the guard leaves the db clean and still hands the forge a sentence
        # naming no situation (T2 review, M25) — so pin what the forge actually received.
        assert correction in briefs[-1][0], reply
        assert reply not in briefs[-1][0], reply


def test_the_reserve_after_an_agreement_is_hedged_never_the_rejected_sentence(tmp_path, make_fake):
    """Residuals 2 and 3 (SESSION_HANDOFF 2026-07-28), one site and one fix. Her correction did
    not move the rank head — the common case — so the confirm beat came back BYTE-IDENTICAL to
    the sentence she had just rejected, which reads as the machine ignoring her. Worse, it came
    back ASSERTING a decision on a `topic`/`low` map with no hedge, which is precisely what the
    honest-fit beat exists to prevent. The re-serve is that beat now: it hedges, names the
    stretch in her words, carries the doors escape, and cannot be the sentence she declined."""
    script = [{}, {"verdict": "topic", "confidence": "low", "conversion": "What call?"}]

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: (
            orig(s, t).model_copy(update=script.pop(0)) if script else orig(s, t)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "agree-hedge.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", "startup getting first client")
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    tag, first = reg.step("s1", "no no like how to get my first client")
    assert first["text"] == "What call?"  # the conversion park

    tag, data = reg.step("s1", "yes")
    assert data["text"] != _CONFIRM_COPY.format(desc=desc), "the sentence she just rejected"
    assert data["text"] == _HONEST_FIT.format(desc=desc)  # hedged, and it names the stretch
    assert "other doors first?" in data["text"]  # the escape the assert-y re-serve never carried


def _fit_screen_spy(monkeypatch):
    """Records every text `voice.egress_safe_reply` was asked to screen. It is ONE MODEL CALL per
    invocation (its own docstring says so), which is the whole point of counting them."""
    seen = []
    real = _voice.egress_safe_reply

    def spy(model, exp, text):
        seen.append(text)
        return real(model, exp, text)

    monkeypatch.setattr(_voice, "egress_safe_reply", spy)
    return seen


def test_the_screened_fit_costs_one_model_call_per_map(tmp_path, make_fake, monkeypatch):
    """Residual 3's cost half. Every beat that serves the mapper's `fit` screens it first, and
    the screen is a model call — so the honest-fit beat screened the string and the confirm beat
    immediately screened the SAME string off the SAME map. One screen per map now."""
    fit = "whether to sign the penalty clause Thursday"
    seen = _fit_screen_spy(monkeypatch)
    reg = SessionRegistry(
        str(tmp_path / "screen-once-fit.db"),
        model_factory=_mapper_factory(make_fake, [{"confidence": "low", "fit": fit}]),
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert data["text"] == _HONEST_FIT.format(desc=fit)  # the fit beat served it
    tag, data = reg.step("s1", "start there")
    assert data["text"] == _CONFIRM_COPY.format(desc=fit)  # the confirm beat served it again
    assert seen.count(fit) == 1, "the same map's fit must not be screened once per serve"


def test_a_bare_rejections_reask_does_not_buy_the_screen_again(tmp_path, make_fake, monkeypatch):
    """The other re-serve off an unchanged map: a bare rejection costs no re-map by design, so
    the re-ask is the same sentence off the same `tmap` — and it was paying for the screen a
    second time to produce a string already in hand."""
    fit = "whether to sign the penalty clause Thursday"
    seen = _fit_screen_spy(monkeypatch)
    reg = SessionRegistry(
        str(tmp_path / "screen-once-bare.db"),
        model_factory=_mapper_factory(make_fake, [{"fit": fit}]),
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert data["text"] == _CONFIRM_COPY.format(desc=fit)
    tag, data = reg.step("s1", "no")  # a bare rejection: no re-map, so the map is unchanged
    assert data["text"] == _CONFIRM_COPY.format(desc=fit)
    assert seen.count(fit) == 1


def test_a_correction_serves_the_new_maps_fit_never_the_cached_one(tmp_path, make_fake):
    """The hazard the per-map cache introduces, pinned in its own right. A correction re-maps, so
    the screened desc is stale the instant `remap` returns — serving it would put the PREVIOUS
    map's decision to her under the rubric chosen for her new words. Only `remap` may clear it,
    and it must, every time."""
    first, second = "whether to sign Thursday", "whether to renew at all"
    reg = SessionRegistry(
        str(tmp_path / "desc-not-stale.db"),
        model_factory=_mapper_factory(make_fake, [{"fit": first}, {"fit": second}]),
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert data["text"] == _CONFIRM_COPY.format(desc=first)
    tag, data = reg.step("s1", "it's really about the renewal terms in March")
    assert data["text"] == _CONFIRM_COPY.format(desc=second), "the re-map's fit, not the cache"


def test_the_conversion_budget_survives_a_raised_correction_cap(tmp_path, make_fake, monkeypatch):
    """Residual 5's other half, the DEAD STORE itself. `converted = True` inside the confirm
    loop's topic branch guards nothing at `_MAX_CONFIRM_CORRECTIONS = 2` — the cap ends the loop
    before a second topic correction can reach it — so both mutations survived and the handoff
    said so out loud rather than claiming it pinned. Raise the cap and the flag is load-bearing:
    it is what stops the composer pressing the conversion twice, which is an interrogation."""
    monkeypatch.setattr(session_runner, "_MAX_CONFIRM_CORRECTIONS", 3)
    script = [
        {},  # the confirm beat
        {"verdict": "topic", "conversion": "What call?"},  # correction 1 is a topic: convert
        {},  # her answer at the park maps to a decision — the confirm beat again
        {"verdict": "topic", "conversion": "A SECOND CONVERSION"},  # correction 2 is a topic too
    ]
    reg = SessionRegistry(
        str(tmp_path / "budget-raised-cap.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    tag, data = reg.step("s1", "no it's really about finding anyone to sell to")
    assert data["text"] == "What call?"
    tag, data = reg.step("s1", "whether to keep chasing enterprise or go self-serve")
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)

    tag, data = reg.step("s1", "actually the call is whether to fire the first sales hire")
    assert data["text"] != "A SECOND CONVERSION", "the conversion is one per pass, cap or no cap"
    assert "other doors first?" in data["text"]


def test_a_bare_rejection_at_the_confirm_beat_never_becomes_the_world(tmp_path, make_fake):
    """THE 2026-07-27 CLASS AGAIN, on the likeliest reply of all (found by the T2 review of the
    fix above). The beat ends "Say yes, or tell me what it actually is", and the canonical short
    answer to that question is "no" — which took the correction branch, wrote `no` into
    `web_world` as the learner's situation, and re-mapped territories on a string naming nothing.
    A rejection that carries no situation cannot replace one. It still counts as a correction, so
    the cap bounds a learner who only ever says no."""
    for reply in ["no", "nope", "that's not it", "none of these", "stop", "no, not that one"]:
        db = str(tmp_path / f"nope-{abs(hash(reply))}.db")
        reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
        reg.start("s1", now=NOW)
        desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
        tag, data = reg.step("s1", _SITUATION)
        assert data["text"] == _CONFIRM_COPY.format(desc=desc)
        tag, data = reg.step("s1", reply)
        store = SittingStore(db)
        assert store.read_world(store.live_sitting()["id"]) == _SITUATION, reply
        tag, data = reg.step("s1", "yes")  # and the door still works afterwards
        assert tag == "say" and data["text"] == _SCENARIO, reply


def test_a_bare_rejection_does_not_spend_one_of_her_two_corrections(tmp_path, make_fake):
    """Found by driving the real HTTP surface, not by a unit test. Counting a bare "no" as a
    correction made a plain no burn half her budget, so the correction that actually NAMED her
    situation hit the cap's honest-fit fall-through instead of the conversion beat built for it.
    A reply that carries nothing to map costs no model call and must cost no correction."""
    conversion = "Getting your first client — what's the call in that?"
    script = [{}, {"verdict": "topic", "confidence": "low", "conversion": conversion}]
    db = str(tmp_path / "bare-budget.db")
    reg = SessionRegistry(db, model_factory=_mapper_factory(make_fake, script))
    reg.start("s1", now=NOW)
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    reg.step("s1", "startup getting first client")
    tag, data = reg.step("s1", "no")  # spends a BARE allowance, not a correction
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)
    tag, data = reg.step("s1", "no no like how to get my first client")
    assert data["text"] == conversion  # the beat built for it, NOT the cap fall-through


def test_two_bare_rejections_still_terminate_at_the_honest_fit_beat(tmp_path, make_fake):
    """The other half: a learner who only ever says no must not loop. The second bare rejection
    takes the same fall-through the correction cap uses — the stretch named, the doors offered."""
    db = str(tmp_path / "bare-cap.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    reg.step("s1", "no")
    tag, data = reg.step("s1", "nope")
    assert "doors first?" in data["text"] or "other doors" in data["text"]
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) == _SITUATION  # never overwritten
    tag, data = reg.step("s1", "start there")
    assert tag == "say" and data["text"] == _SCENARIO  # never dead-ends


def test_a_rejection_that_carries_words_is_still_a_correction(tmp_path, make_fake):
    """The other direction, and it is the founder's own live path: "no no like how to get my
    first client" LEADS with rejection and carries a whole situation. That must re-map on his
    words — treating it as contentless would throw away the correction the door exists for."""
    db = str(tmp_path / "real-correction.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg.start("s1", now=NOW)
    reg.step("s1", "startup getting first client")
    correction = "no no like how to get my first client"
    reg.step("s1", correction)
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) == correction
    for other in ["not quite, it's about pricing", "no, the co-founder equity split"]:
        db2 = str(tmp_path / f"rc-{abs(hash(other))}.db")
        reg2 = SessionRegistry(db2, model_factory=_world_factory(make_fake))
        reg2.start("s1", now=NOW)
        reg2.step("s1", _SITUATION)
        reg2.step("s1", other)
        s2 = SittingStore(db2)
        assert s2.read_world(s2.live_sitting()["id"]) == other, other


def test_an_agreement_at_the_intake_conversion_park_never_becomes_the_world(tmp_path, make_fake):
    """The SIBLING park (T2 review, A-3). `conversion_beat()` is shared so the two parks can never
    serve different text — but their handling of the reply had drifted: the confirm-loop park
    stopped swallowing agreements and the intake park still did. Nothing invites a yes here, but
    the conversion is model-authored and a binary phrasing ("is it whether to hire, or hold?")
    makes yes the natural reply. An agreement cannot convert a topic, so it takes the honest-fit
    beat — which names the stretch and carries the doors escape."""
    for reply in ["yes", "sure", "Yes, this is the decision I want to make."]:
        topic = "what should optimal onboarding look like?"
        db = str(tmp_path / f"intake-agree-{abs(hash(reply))}.db")
        reg = SessionRegistry(
            db,
            model_factory=_mapper_factory(
                make_fake, [{"verdict": "topic", "conversion": "Is it A, or B?"}]
            ),
        )
        reg.start("s1", now=NOW)
        tag, data = reg.step("s1", topic)
        assert data["text"] == "Is it A, or B?"
        tag, data = reg.step("s1", reply)
        store = SittingStore(db)
        assert store.read_world(store.live_sitting()["id"]) == topic, reply
        desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
        assert data["text"] == _HONEST_FIT.format(desc=desc), reply


def test_a_click_at_the_confirm_beat_forges_the_door_that_was_clicked(tmp_path, make_fake):
    """A door click at the confirm beat is its own consent — for the door SHE picked. Forging the
    mapped territory instead survived the whole suite (T2 review, M15): no test clicked a
    NON-mapped door at this beat, and the static consent guard passes on `clicked=True` alone
    without ever checking which territory the call names."""
    db = str(tmp_path / "confirm-click.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)  # mapped territory is _T1
    idx = reg._ch["s1"].last_menu_eids.index(_T3)  # she clicks a DIFFERENT door
    tag, data = reg.step("s1", idx)
    assert tag == "say" and data["text"] == _SCENARIO
    store = SittingStore(db)
    row = store.read_generated_problem(f"gen:{store.live_sitting()['id']}:1")
    assert row is not None and row["experience_id"] == _T3  # hers, not the mapper's


def test_the_conversion_answer_is_what_the_next_beat_and_the_forge_are_built_on(
    tmp_path, make_fake
):
    """The re-map after the conversion must run on her ANSWER, not on the correction that
    triggered it. Ordering the two the other way is invisible to a mapper that ignores its input
    and produces a scenario assembled from two different inputs — the exact defect the cap-path
    comment names. This mapper is a FUNCTION OF THE TEXT, so the order is observable."""
    briefs = []

    def factory():
        m = _world_factory(make_fake, briefs=briefs)()
        orig = m.map_territories

        def by_text(s, t):
            out = orig(s, t)
            if "client" in s:  # the correction: a topic whose best stretch is T1
                return out.model_copy(
                    update={
                        "verdict": "topic",
                        "confidence": "low",
                        "conversion": "What call?",
                        "ranked": [_T1, _T2, _T3],
                    }
                )
            if "rebuild" in s:  # her ANSWER to the conversion: a decision, and a DIFFERENT door
                return out.model_copy(update={"ranked": [_T3, _T1, _T2]})
            return out

        m.map_territories = by_text
        return m

    db = str(tmp_path / "conv-answer.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    tag, data = reg.step("s1", "how to get my first client")
    assert data["text"] == "What call?"
    answer = "whether to promise a full rebuild to win them"
    tag, data = reg.step("s1", answer)
    desc3 = " ".join(load_territory_text(_T3).split()).rstrip(".")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc3)  # HER ANSWER's territory, not T1's
    tag, data = reg.step("s1", "yes")
    assert tag == "say" and data["text"] == _SCENARIO
    assert answer in briefs[-1][0]
    store = SittingStore(db)
    row = store.read_generated_problem(f"gen:{store.live_sitting()['id']}:1")
    assert row is not None and row["experience_id"] == _T3


def test_a_ranking_the_library_does_not_contain_cannot_pick_the_door(tmp_path, make_fake):
    """The hallucination-proof half of the mapping seam, which had no executable coverage before
    the T2 review looked for it: a `ranked` naming ids that do not exist, and an EMPTY `ranked`.
    Unfiltered, the first forges an experience_id the library has never heard of (StopIteration
    inside the worker thread); unguarded, the second is an IndexError. Both must land on a real
    territory and forge."""
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    for tag_, ranked in [("fake", ["not_a_territory", "also_fake"]), ("empty", [])]:
        db = str(tmp_path / f"rank-{tag_}.db")
        reg = SessionRegistry(db, model_factory=_mapper_factory(make_fake, [{"ranked": ranked}]))
        reg.start("s1", now=NOW)
        tag, data = reg.step("s1", _SITUATION)
        assert tag == "say" and data["text"] == _CONFIRM_COPY.format(desc=desc), (tag_, data)
        tag, data = reg.step("s1", "yes")
        assert tag == "say" and data["text"] == _SCENARIO, (tag_, data)
        store = SittingStore(db)
        row = store.read_generated_problem(f"gen:{store.live_sitting()['id']}:1")
        assert row is not None and row["experience_id"] == _T1, tag_


def test_a_correction_that_lands_cleanly_at_the_cap_is_not_a_content_gap(tmp_path, make_fake):
    """§4b: the gap ledger is the content axis's only mechanical input, so it records what the
    door COULD NOT serve — never every correction. Two corrections that both re-map cleanly
    (decision/high) reach the cap and must leave the ledger empty; the topic/low arm below is the
    same path with the condition true."""
    db = str(tmp_path / "gap-clean.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    reg.step("s1", "no, it's the second delivery clause")
    tag, data = reg.step("s1", "no, it's really the board review timing")  # cap -> honest fit
    assert "doors first?" in data["text"] or "other doors" in data["text"]
    tag, data = reg.step("s1", "start there")
    assert tag == "say" and data["text"] == _SCENARIO
    import sqlite3

    c = sqlite3.connect(db)
    rows = c.execute("SELECT situation, verdict FROM web_content_gap").fetchall()
    c.close()
    assert rows == [], rows  # a correction the mapper served cleanly is not a content gap


def test_a_correction_the_remap_still_cannot_serve_is_a_content_gap(tmp_path, make_fake):
    """The other arm: at the cap, a re-map that is still not decision/high IS the gap."""
    script = [{}, {}, {"verdict": "topic", "confidence": "low", "conversion": "c"}]
    db = str(tmp_path / "gap-miss.db")
    reg = SessionRegistry(db, model_factory=_mapper_factory(make_fake, script))
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    reg.step("s1", "no, it's the second delivery clause")
    reg.step("s1", "no, it's really about finding anyone to sell to")  # cap: topic/low
    import sqlite3

    c = sqlite3.connect(db)
    rows = c.execute(
        "SELECT situation, verdict, confidence, corrected FROM web_content_gap"
    ).fetchall()
    c.close()
    assert rows == [("no, it's really about finding anyone to sell to", "topic", "low", 1)], rows


def test_resume_parked_at_the_confirm_loop_conversion_reserves_it(tmp_path, make_fake):
    """Triage fold 2026-07-03, on the new park: a reload must re-serve the question ACTUALLY
    pending. Re-serving the plain confirm ask here would invite a fresh situation that the parked
    worker then consumes as an answer to a conversion she never saw."""
    conversion = "What's the call you have to make in that?"
    script = [{}, {"verdict": "topic", "conversion": conversion}]
    reg = SessionRegistry(
        str(tmp_path / "conv-correct-resume.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)  # the confirm beat
    tag, data = reg.step("s1", "no, it's really about finding anyone to sell to")
    assert data["text"] == conversion
    tag, rdata = reg.resume_or_start("s1")
    assert tag == "resume"
    assert rdata["frontdoor"]["text"] == conversion  # the pending question, not the plain ask
    assert not (rdata["turns"] and rdata["turns"][-1]["text"] == conversion)  # deduped


def test_honest_fit_reflects_her_words_when_the_mapper_authors_a_safe_fit(tmp_path, make_fake):
    """Honest-fit reflection fix (2026-07-05 founder dogfood): the fit beat names the pressable
    edge in HER words (mapper `fit`, screened like the conversion) — NOT the generic territory
    description that "never adjusts"."""
    her = "how you price your subscription tiers against a saturated competitor"
    script = [
        {"verdict": "topic", "conversion": "First conversion question?"},
        {"verdict": "topic", "conversion": "second", "fit": her},
    ]
    reg = SessionRegistry(
        str(tmp_path / "fit.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    reg.step("s1", "a question about strategy")
    tag, data = reg.step("s1", "what pricing strategy should we use?")
    assert her in data["text"]  # HER words named as the pressable edge
    generic = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert generic not in data["text"]  # the canned territory description is NOT recited


def test_honest_fit_falls_back_to_generic_when_fit_is_empty(tmp_path, make_fake):
    """An empty `fit` takes the generic territory description (the safe fallback, unchanged)."""
    script = [
        {"verdict": "topic", "conversion": "First?"},
        {"verdict": "topic", "conversion": "second", "fit": ""},
    ]
    reg = SessionRegistry(
        str(tmp_path / "fit2.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    reg.step("s1", "q1")
    tag, data = reg.step("s1", "q2")
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _HONEST_FIT.format(
        desc=desc
    )  # generic fallback (variant 0, first serve)


def test_honest_fit_leaky_fit_falls_back_to_generic(tmp_path, make_fake):
    """A `fit` that PERFORMS a hidden move falls to the generic description (L-13 teeth on the
    honest-fit surface, mirroring the conversion screen)."""
    from elenchus.model import EgressScreen

    leaky_fit = "just embed every credential you need as a list"

    def factory():
        m = _world_factory(make_fake)()
        orig_map = m.map_territories
        script = [
            {"verdict": "topic", "conversion": "First?"},
            {"verdict": "topic", "conversion": "second", "fit": leaky_fit},
        ]
        m.map_territories = lambda s, t: (
            orig_map(s, t).model_copy(update=script.pop(0)) if script else orig_map(s, t)
        )
        orig_screen = m.screen_moves
        m.screen_moves = lambda moves, text: (
            EgressScreen(performed=[1], evidence="performs move 1")
            if text == leaky_fit
            else orig_screen(moves, text)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "leak-fit.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", "q1")
    tag, data = reg.step("s1", "q2")
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _HONEST_FIT.format(desc=desc)  # leaky fit rejected -> generic
    assert leaky_fit not in data["text"]


def test_conversion_screen_failure_serves_the_static_and_never_deflects(tmp_path, make_fake):
    """Spec §2a: an empty/refused/leaky authored conversion takes _STATIC_CONVERSION — which
    itself converts; the words 'out of scope' can never serve (founder constraint)."""
    from elenchus.web.session_runner import _STATIC_CONVERSION

    script = [{"verdict": "topic", "conversion": ""}, {}]
    reg = SessionRegistry(
        str(tmp_path / "conv3.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a question")
    assert data["text"] == _STATIC_CONVERSION
    assert "out of scope" not in _STATIC_CONVERSION.lower()
    tag, data = reg.step("s1", "the call I face is X vs Y")
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert data["text"] == _SCENARIO  # the beat converted; the reply proceeded


def test_scope_phrase_conversion_is_structurally_unservable(tmp_path, make_fake):
    """Review fold 2026-07-04 (probe-confirmed): the founder's forbidden phrase must be
    unservable STRUCTURALLY — the move screen is blind to deflection language, so a
    disobedient authored conversion containing 'out of scope' must fall to the static."""
    from elenchus.web.session_runner import _STATIC_CONVERSION

    script = [
        {
            "verdict": "topic",
            "conversion": "That's a bit out of scope for me — but what's the call you face?",
        },
        {},
    ]
    reg = SessionRegistry(
        str(tmp_path / "scope.db"), model_factory=_mapper_factory(make_fake, script)
    )
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a question")
    assert data["text"] == _STATIC_CONVERSION  # the phrase never serves


def test_leaky_conversion_serves_the_static(tmp_path, make_fake):
    """Review fold 2026-07-04 (mutation survived): the conversion egress screen needs teeth —
    a conversion that PERFORMS a hidden move of the rank-head territory must fall to the
    static, never serve (the L-13 gate on the new learner-facing surface)."""
    from elenchus.model import EgressScreen
    from elenchus.web.session_runner import _STATIC_CONVERSION

    leaky = "Just list every credential you need and embed them — now, what call do you face?"

    def factory():
        m = _world_factory(make_fake)()
        orig_map = m.map_territories
        script = [{"verdict": "topic", "conversion": leaky}]
        m.map_territories = lambda s, t: (
            orig_map(s, t).model_copy(update=script.pop(0)) if script else orig_map(s, t)
        )
        orig_screen = m.screen_moves
        m.screen_moves = lambda moves, text: (
            EgressScreen(performed=[1], evidence="performs move 1")
            if text == leaky
            else orig_screen(moves, text)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "leak-conv.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a question")
    assert data["text"] == _STATIC_CONVERSION  # the leaky authored text never serves


def test_out_of_range_click_reserves_the_menu_instead_of_reaching_the_worker(tmp_path, make_fake):
    """Review fold 2026-07-04 (probe-confirmed): a crafted index must not reach the worker —
    -1 silently forged the LAST door (Python negative indexing), 99 IndexError'd the segment.
    choose() bounds-checks at the boundary and re-serves the pending menu, nonce unburned."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    db = str(tmp_path / "bounds.db")
    reg = SessionRegistry(db, model_factory=factory)
    tag, data = reg.start("s1", now=NOW)
    nonce = data["menu"].get("nonce", 0)
    reg.step("s1", _SITUATION)  # parked at the fit beat
    for bad in (-1, 99):
        tag, data = reg.choose("s1", bad, nonce)
        assert tag == "menu"  # re-served, never forwarded
        assert data["nonce"] == nonce  # the nonce was not burned by an invalid click
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_generated_problem(f"gen:{sit}:1") is None  # nothing forged


def test_clicked_forge_on_the_top_door_logs_accepted(tmp_path, make_fake):
    """Review fold 2026-07-04 (spec §4 test 9's other half): clicking the policy-top door at
    a fit park logs Outcome.accepted — pins the object-identity contract (spec_src is
    top_spec) a Proposal refactor could silently break."""
    import sqlite3 as _sq

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    db = str(tmp_path / "click-top.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    tag, data = reg.step("s1", 0)  # the policy top (menu order is the proposal order)
    assert tag == "say" and data["text"] == _SCENARIO
    tag, _ = _drive(reg, "s1", opening="a position on the top door")
    assert tag == "done"
    con = _sq.connect(db)
    outcome = con.execute(
        "SELECT outcome FROM selection_log ORDER BY rowid DESC LIMIT 1"
    ).fetchone()[0]
    con.close()
    assert outcome == "accepted"


def test_resume_parked_at_conversion_reserves_the_conversion_question(tmp_path, make_fake):
    """Spec §2a: frontdoor_pending carries the conversion — a reload re-serves the question
    actually pending (the 2026-07-03 resume-fidelity fix extends to the new park)."""
    script = [{"verdict": "topic", "conversion": "The conversion question?"}]
    reg = SessionRegistry(
        str(tmp_path / "conv4.db"), model_factory=_mapper_factory(make_fake, script)
    )
    tag, data = reg.start("s1", now=NOW)
    nonce = data["menu"].get("nonce", 0)
    reg.step("s1", "a question")
    tag, rdata = reg.resume_or_start("s1")
    assert tag == "resume"
    assert rdata["frontdoor"]["text"] == "The conversion question?"
    assert rdata["frontdoor"]["menu"]["nonce"] == nonce
    assert not (rdata["turns"] and rdata["turns"][-1]["text"] == "The conversion question?")


def test_honest_fit_copy_rotates_across_serves(tmp_path, make_fake):
    """Spec §2d: the fit beat must not repeat verbatim within a session (dogfood 2026-07-04:
    identical copy twice on one screen). Variant 0 is the original — first serves stay
    deterministic for the existing pins."""
    from elenchus.web.session_runner import _HONEST_FIT_VARIANTS

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    reg = SessionRegistry(str(tmp_path / "fit-var.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    tag, first = reg.step("s1", _SITUATION)
    assert "doors first?" in first["text"]  # parked at the fit beat
    tag, data = reg.step("s1", "start there")  # proceeds with the mapped territory
    assert tag == "say"  # the confirm beat
    tag, data = reg.step("s1", "yes")  # she agrees before it forges
    assert tag == "say"
    tag, _ = _drive(reg, "s1", opening="consent, and then a position")
    assert tag == "done"  # segment 1 converged
    assert reg.continue_session("s1", menu=True)[0] == "say"  # back through the front door
    tag, second = reg.step("s1", "a second situation this sitting")
    prefixes = [v.split("{desc}")[0] for v in _HONEST_FIT_VARIANTS]
    assert first["text"] != second["text"]  # no verbatim repeat
    assert any(first["text"].startswith(p) for p in prefixes)
    assert any(second["text"].startswith(p) for p in prefixes)


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
    assert tag == "say"
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    assert data["text"] == _CONFIRM_COPY.format(desc=desc)  # nothing forged until she agrees
    tag, data = reg.step("s1", "yes")
    assert tag == "say" and data["text"] == _SCENARIO  # the forged scenario IS the opening (M6)
    assert data.get("bridge") == "[reflect]"  # the screened heard-you reflection (D9)

    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_world(sit) == _SITUATION  # written BEFORE forging (P1 no-poisoning)
    row = store.read_generated_problem(f"gen:{sit}:1")
    assert row == {"experience_id": _T1, "scenario": _SCENARIO}

    tag, data = _drive(reg, "s1", opening="my position on the penalty")
    assert tag == "done" and data["landing"]
    # Continue: the NEXT territory's SHORT title in next_title, its description in next_desc
    # (spec §2d — the split; never the worked territory), and next_kind is "chapter" (this
    # segment forged+converged, so a sequel exists).
    assert data["next_desc"] == _territory_subtitle(_T2)
    assert data["next_kind"] == "chapter"
    log = store.converged_log()
    assert [(r["ref"], r["experience_id"]) for r in log] == [(f"gen:{sit}:1", _T1)]

    turns = store.turns(sit)
    kinds = [t["kind"] for t in turns]
    # ask, her text, the confirm beat, her agreement, bridge, opening
    assert kinds[:6] == ["vera", "you", "vera", "you", "bridge", "vera"]
    assert turns[0]["payload"]["text"] == _FRONTDOOR_ASK
    assert turns[1]["payload"]["text"] == _SITUATION
    assert turns[2]["payload"]["text"] == _CONFIRM_COPY.format(desc=desc)
    assert turns[3]["payload"]["text"] == "yes"
    assert turns[4]["payload"]["text"] == "[reflect]"
    assert turns[5]["payload"]["text"] == _SCENARIO
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
    tag, data = reg.step("s1", "yes — start there")  # proceeds with the MAPPED territory
    assert tag == "say" and data["text"] == _CONFIRM_COPY.format(desc=desc)  # then confirm
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert tag == "say" and data["text"] == _SCENARIO  # proceeds with the MAPPED territory
    assert data.get("bridge") == "[reflect]"
    store = SittingStore(db)
    assert store.read_world(store.live_sitting()["id"]) == _SITUATION  # her ORIGINAL situation


def test_resume_parked_at_honest_fit_reserves_the_honest_fit_question(tmp_path, make_fake):
    """Triage fold 2026-07-03: a same-process reload parked at the honest-fit beat re-served the
    PLAIN ask — inviting a fresh situation the parked worker then consumed as consent to the OLD
    mapping (half-losing whatever she typed). The resume must re-serve the question actually
    pending; the consent semantics themselves stay byte-identical (pinned by the
    low_confidence_honest_fit test above)."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories

        def low(situation, territories):
            return orig(situation, territories).model_copy(update={"confidence": "low"})

        m.map_territories = low
        return m

    reg = SessionRegistry(str(tmp_path / "fd-fit-resume.db"), model_factory=factory)
    tag, data = reg.start("s1", now=NOW)
    nonce = data["menu"].get("nonce", 0)
    tag, data = reg.step("s1", _SITUATION)
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    fit = _HONEST_FIT.format(desc=desc)
    assert data["text"] == fit  # parked at the honest-fit beat

    tag, rdata = reg.resume_or_start("s1")
    assert tag == "resume"
    assert rdata["frontdoor"]["text"] == fit  # the question actually pending, not the plain ask
    assert rdata["frontdoor"]["menu"]["nonce"] == nonce  # same pending menu — doors still answer
    assert not (
        rdata["turns"] and rdata["turns"][-1]["text"] == fit
    )  # the block owns the question; the trailing transcript turn deduped

    tag, data = reg.step("s1", "yes — start there")  # consent semantics unchanged
    assert tag == "say" and data["text"] == _CONFIRM_COPY.format(desc=desc)  # then confirm
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert tag == "say" and data["text"] == _SCENARIO


def test_front_door_low_confidence_int_takes_a_door(tmp_path, make_fake):
    """The honest-fit round-trip's other exit: an int with fed material this pass FORGES the
    clicked territory around it (front-door conversion spec §2b — dogfood 2026-07-04: the
    naked curated prompt served against a typed situation felt deaf)."""

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
    assert tag == "say" and data["text"] == _SCENARIO  # forged around her material (§2b)


def test_click_at_the_fit_park_forges_the_clicked_territory(tmp_path, make_fake):
    """Spec §2b: a door click after fed-in material this pass forges the CLICKED territory
    around it — never the naked curated prompt (dogfood 2026-07-04: firmware served against
    an onboarding situation)."""
    briefs = []

    def factory():
        m = _world_factory(make_fake, briefs=briefs)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    db = str(tmp_path / "click-forge.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert "other doors first?" in data["text"]  # parked at the fit beat
    idx = reg._ch["s1"].last_menu_eids.index(_T3)
    tag, data = reg.step("s1", idx)  # the click
    assert tag == "say" and data["text"] == _SCENARIO  # forged, not curated
    assert _SITUATION in briefs[-1][0]  # the brief carries her fed material
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    row = store.read_generated_problem(f"gen:{sit}:1")
    assert row is not None and row["experience_id"] == _T3  # the CLICKED territory


def _low_confidence_reg(db, make_fake):
    """A registry whose mapper always reports low confidence — every front-door submit parks at
    the honest-fit beat. Four doors-escape tests below need the same park."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    return SessionRegistry(db, model_factory=factory)


def test_fit_beat_doors_escape_answered_in_words_reserves_the_doors(tmp_path, make_fake):
    """The beat offers two options and only ONE of them was answerable. It ends *"Start there —
    or look at the other doors first?"*, and the doors escape is a CLICK: typing the second
    option proceeded with the FIRST — the mapped territory she had just declined, forged on the
    words that declined it. Her words now re-serve the doors where she is looking, and clicking
    one forges THAT territory."""
    db = str(tmp_path / "fit-doors-words.db")
    reg = _low_confidence_reg(db, make_fake)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say" and "other doors first?" in data["text"]  # parked at the fit beat

    tag, data = reg.step("s1", "look at the other doors first")
    assert tag == "menu", "her words took the beat's own second option — the doors must re-serve"
    assert data["problems"], "the re-serve carries the doors themselves"

    tag, data = reg.choose("s1", reg._ch["s1"].last_menu_eids.index(_T3), nonce=data["nonce"])
    assert tag == "say" and data["text"] == _SCENARIO  # the door she picked, forged on her words
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_generated_problem(f"gen:{sit}:1")["experience_id"] == _T3


def test_fit_beat_doors_reserve_still_proceeds_on_text(tmp_path, make_fake):
    """The re-serve must never dead-end: she asked for the doors, looked, and typed instead of
    clicking. That is the ORIGINAL contract — any text proceeds with the mapped territory — now
    taken only after the doors were actually put in front of her."""
    reg = _low_confidence_reg(str(tmp_path / "fit-doors-text.db"), make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    tag, data = reg.step("s1", "show me the other doors")
    assert tag == "menu"
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    tag, data = reg.step("s1", "fine, start there")
    assert tag == "say" and data["text"] == _CONFIRM_COPY.format(desc=desc)


def test_fit_beat_bare_rejection_reserves_the_doors(tmp_path, make_fake):
    """The same harm on the shorter reply: "no" to a beat whose two options are *start there* or
    *the doors* is not consent to the first one. It used to forge the mapped territory on a word
    that declined it — the 2026-07-27 class at the beat one step earlier."""
    reg = _low_confidence_reg(str(tmp_path / "fit-doors-no.db"), make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    tag, _ = reg.step("s1", "no")
    assert tag == "menu"


def test_fit_beat_a_situation_that_mentions_options_is_not_a_doors_request(tmp_path, make_fake):
    """The false-positive guard, and why the predicate requires the whole reply to sit inside a
    closed frame: a real situation can carry the word `options` and must still proceed. A miss
    here costs one extra beat; reading every such reply as a doors request would strand her."""
    reg = _low_confidence_reg(str(tmp_path / "fit-doors-fp.db"), make_fake)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    desc = " ".join(load_territory_text(_T1).split()).rstrip(".")
    tag, data = reg.step("s1", "I need to look at my options for the penalty clause")
    assert tag == "say" and data["text"] == _CONFIRM_COPY.format(desc=desc)


def test_click_at_the_conversion_park_forges_around_the_topic(tmp_path, make_fake):
    """Spec §2a/§2b: at the conversion park a click means 'give me the pressure on my
    material' — the topic text is the forge brief's situation."""
    briefs = []

    def factory():
        m = _world_factory(make_fake, briefs=briefs)()
        orig = m.map_territories
        script = [{"verdict": "topic", "conversion": "What call do you face in that?"}]
        m.map_territories = lambda s, t: (
            orig(s, t).model_copy(update=script.pop(0)) if script else orig(s, t)
        )
        return m

    reg = SessionRegistry(str(tmp_path / "click-conv.db"), model_factory=factory)
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", "a topic, not a decision")
    assert data["text"] == "What call do you face in that?"
    idx = reg._ch["s1"].last_menu_eids.index(_T2)
    tag, data = reg.step("s1", idx)
    assert tag == "say" and data["text"] == _SCENARIO
    assert "a topic, not a decision" in briefs[-1][0]


def test_cold_click_stays_curated(tmp_path, make_fake):
    """Spec §2b: a click at the initial ask (nothing typed this pass) is byte-identical to
    today — curated prompt, no forge, no instance row."""
    db = str(tmp_path / "cold-click.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    reg.start("s1", now=NOW)
    tag, data = reg.step("s1", reg.menu_index("s1", _ANCHOR))
    assert tag == "say" and data["text"] != _SCENARIO  # curated opening, not a forge
    store = SittingStore(db)
    sit = store.live_sitting()["id"]
    assert store.read_generated_problem(f"gen:{sit}:1") is None


def test_clicked_forge_logs_menu_outcome_semantics(tmp_path, make_fake):
    """Spec §2b: clicked forges log accepted-if-top else redirected — selection telemetry
    stays honest about who chose the door."""
    import sqlite3 as _sq

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"confidence": "low"})
        return m

    db = str(tmp_path / "click-outcome.db")
    reg = SessionRegistry(db, model_factory=factory)
    reg.start("s1", now=NOW)
    reg.step("s1", _SITUATION)
    eids = reg._ch["s1"].last_menu_eids
    non_top = next(i for i, e in enumerate(eids) if e != eids[0])
    tag, data = reg.step("s1", non_top)
    assert tag == "say" and data["text"] == _SCENARIO
    tag, _ = _drive(reg, "s1", opening="a position on the clicked door")
    assert tag == "done"  # log_decision writes at the segment's end, not at the opening
    con = _sq.connect(db)
    outcome = con.execute(
        "SELECT outcome FROM selection_log ORDER BY rowid DESC LIMIT 1"
    ).fetchone()[0]
    con.close()
    assert outcome == "redirected"


def test_leaking_reflection_serves_the_static_bridge(tmp_path, make_fake):
    """L4 review F2 (D9 teeth): a reflection that PERFORMS a move of the mapped territory must
    not ride the opening — the static bridge serves instead. The leak fake flags ONLY the exact
    reflection text, so the forge's union screen (the scenario) and every other authored
    surface stay clean — this test discriminates the reflection gate specifically."""
    from elenchus.model import EgressScreen

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
    assert tag == "say"
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
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
    assert tag == "say"
    tag, data = reg2.step("s1", "yes")  # the confirm beat: she agrees before it forges
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
    # degraded rebuild → the honest static, never SAFE_CONTRACT's "I'll push" lie (spec §2c)
    assert tag == "say" and data["text"] == _voice._CONVERSE_DONE_FRESH
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
    assert tag == "say"
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
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
    assert tag == "resume" and data["honesty"] == _HONESTY_LOST_LANDED  # cause-neutral (C7/C16)
    tag, data = reg2.continue_session("s1")
    assert tag == "say" and data["text"] == _SCENARIO
    assert data.get("seam") == _REOPEN_SEAM_TEXT  # re-entering the interrupted TERRITORY


_REOPEN_SEAM_TEXT = (
    "Starting this one over — restate your position, or build on what you wrote above."
)


def _expected_return_line(db: str) -> str:
    """The invariant, computed the honest way: the caption counts convergence ROWS (Model A: house
    = one convergence, plan Task 2 — pinned copy "N judgment(s) across your domains"); 'regions
    alight' QUOTES the rendered count of the frozen village the user last saw (never a territory
    count — batch-review fold: the two can diverge and the line must never contradict the close
    copy)."""
    store = SittingStore(db)
    n = len(store.converged_log())
    line = f"{n} judgment{'s' if n != 1 else ''} across your domains."
    terrain = store.latest_terrain()
    if terrain:
        m = sum(1 for r in terrain if r.get("render") == "rendered")
        if m:
            regions = "region" if m == 1 else "regions"
            line = f"{n} judgment{'s' if n != 1 else ''} across your domains, {m} {regions} alight."
    return line


def test_return_visit_line_rides_the_cold_front_door(tmp_path, make_fake):
    """Review P10: a cold start with closed worlds is not amnesiac — one muted line above the
    ask. Pinned as the INVARIANT (the line quotes the frozen village + the converged log — it can
    never contradict the close copy), plus both plural branches ('1 judgment' / '2 judgments';
    Model A pins each convergence as its own judgment, plan Task 2 review code-truth 5)."""
    db = str(tmp_path / "fd-return.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="p1")
    reg.close("s1")  # the sitting ends; the log survives (L-3)

    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg2.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "say" and data.get("frontdoor")
    assert data["returning"] == _expected_return_line(db)
    assert data["returning"].startswith("1 judgment across your domains")  # singular branch

    # A second sitting converges the SAME territory (the free-text map ignores the window):
    # the judgment count grows; the regions clause keeps quoting the frozen village.
    tag, data = reg2.step("s1", _SITUATION)
    assert tag == "say"
    tag, data = reg2.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert tag == "say"
    tag, _ = _drive(reg2, "s1", opening="p2")
    assert tag == "done"
    reg2.close("s1")

    reg3 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg3.resume_or_start("s1", now=datetime.now(timezone.utc))
    assert tag == "say" and data.get("frontdoor")
    assert data["returning"] == _expected_return_line(db)
    assert data["returning"].startswith("2 judgments across your domains")  # plural branch


def test_forge_brief_positions_exclude_non_converged_landings(tmp_path, make_fake):
    """Triage fold 2026-07-03: post-Earned-Landing every stop lands, so a landing alone is not
    commitment — a plateaued segment's final hedge must not ship in the forge brief as 'her
    committed position'. stop_reason rides the landing payload server-side; the resume wire
    stays kind+text only."""
    briefs = []
    outcome = {"v": "closed"}
    reg = SessionRegistry(
        str(tmp_path / "fd-pos.db"),
        model_factory=_world_factory(make_fake, briefs=briefs, outcome=outcome),
    )
    _open_world(reg, "s1")
    tag, data = reg.step("s1", "the committed call")
    while tag == "say":
        tag, data = reg.step("s1", "landed-reply")
    assert tag == "done"  # converged landing
    outcome["v"] = "unchanged"
    assert reg.continue_session("s1")[0] == "say"
    tag, data = reg.step("s1", "a hedge not a commitment")
    while tag == "say":
        tag, data = reg.step("s1", "hedge-reply")
    assert tag == "done"  # honest NON-converged landing (plateau)
    outcome["v"] = "closed"
    assert reg.continue_session("s1")[0] == "say"  # third forge: its brief reads _positions
    brief = briefs[-1][0]
    assert "landed-reply" in brief  # the converged segment's final turn IS a position
    assert "hedge-reply" not in brief  # the plateaued segment's hedge is NOT
    # server-side only: the persisted landing rows carry stop_reason, the resume wire does not
    sit = reg._sitting_id["s1"]
    reasons = [t["payload"]["stop_reason"] for t in reg._store.turns(sit) if t["kind"] == "landing"]
    assert reasons[:2] == ["converged", "plateau"]
    _, rdata = reg.resume_or_start("s1")
    assert all(set(t) == {"kind", "text"} for t in rdata["turns"])


def test_post_landing_converse_attaches_to_the_segment_it_is_about(tmp_path, make_fake):
    """Triage fold 2026-07-03: converse turns typed between a landing and the Continue press are
    ABOUT the just-landed problem — the close author must receive them in that segment's block,
    never woven into the next problem's chapter (splitting on landings alone did exactly that)."""
    closes = []

    def factory():
        m = _world_factory(make_fake)()
        orig = m.concierge_sitting_close

        def rec(situation, segments, voice=""):
            closes.append(segments)
            return orig(situation, segments, voice)

        m.concierge_sitting_close = rec
        return m

    reg = SessionRegistry(str(tmp_path / "fd-tail.db"), model_factory=factory)
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="position one")
    tag, _ = reg.converse("s1", "one more thought about that call")  # the wind-down
    assert tag == "say"
    assert reg.continue_session("s1")[0] == "say"
    _drive(reg, "s1", opening="position two")
    reg.close("s1")
    segments = closes[0]
    assert len(segments) == 2
    seg1_texts = [t for _, t in segments[0]]
    seg2_texts = [t for _, t in segments[1]]
    assert "one more thought about that call" in seg1_texts  # attached to the landed segment
    assert "one more thought about that call" not in seg2_texts
    assert any("position two" == t for t in seg2_texts)  # the next chapter starts clean


def test_heard_you_screen_failure_does_not_leak_the_forge_registry_entry(tmp_path, make_fake):
    """Triage fold 2026-07-03: the forge registers the entry BEFORE the heard-you screen runs —
    a raise there killed the worker (honest) but left the entry in the module-global registry
    for the process lifetime. The decide()-local cleanup pops exactly the ref it registered."""
    from elenchus.forge import forge_registry

    def factory():
        m = _world_factory(make_fake)()
        orig = m.screen_moves
        calls = {"n": 0}

        def screen(moves, text):
            calls["n"] += 1
            if calls["n"] >= 2:  # call 1 = the forge's union gate; call 2 = the heard-you screen
                raise RuntimeError("heard-you screen died")
            return orig(moves, text)

        m.screen_moves = screen
        return m

    forge_registry.clear()
    reg = SessionRegistry(str(tmp_path / "fd-leak.db"), model_factory=factory)
    tag, data = reg.start("s1", now=NOW)
    assert tag == "say" and data.get("frontdoor")
    tag, data = reg.step("s1", _SITUATION)
    assert tag == "say"
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
    assert tag == "error"  # the worker died loudly (honest path, unchanged)
    assert forge_registry == {}  # ...and took its registered entry with it


def test_positions_includes_legacy_landing_rows_without_stop_reason(tmp_path, make_fake):
    """Review fold 2026-07-03 (mutation survived): the founder's real dbs hold landing rows
    persisted BEFORE stop_reason existed — they must keep reading as converged, or every
    pre-batch committed position silently vanishes from future forge briefs."""
    db = str(tmp_path / "legacy.db")
    st = SittingStore(db)
    sid = st.create_sitting(NOW)
    st.append_turn(sid, "you", {"text": "the old committed call"}, NOW)
    st.append_turn(sid, "landing", {"text": "you owned it"}, NOW)  # legacy: no stop_reason key
    reg = SessionRegistry(db, model_factory=make_fake)
    assert reg._positions(sid) == ["the old committed call"]


def test_rendered_front_door_continue_marks_the_segment_boundary(tmp_path, make_fake):
    """Review fold 2026-07-03 (mutation survived): the picker's continue re-enters the RENDERED
    front door, whose ask persists — without the muted boundary marker, the ask and her next
    situation ride the previous segment's wind-down tail into the close author's first block."""
    closes = []

    def factory():
        m = _world_factory(make_fake)()
        orig = m.concierge_sitting_close

        def rec(situation, segments, voice=""):
            closes.append(segments)
            return orig(situation, segments, voice)

        m.concierge_sitting_close = rec
        return m

    reg = SessionRegistry(str(tmp_path / "fd-picker.db"), model_factory=factory)
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="position one")
    assert reg.converse("s1", "picker wind-down thought")[0] == "say"
    tag, data = reg.continue_session("s1", menu=True)  # other doors: the rendered front door
    assert tag == "say" and data.get("frontdoor")
    tag, data = reg.step("s1", "a second free-text situation")
    assert tag == "say"
    _drive(reg, "s1", opening="position two")
    reg.close("s1")
    segments = closes[0]
    assert len(segments) == 2
    seg1_texts = [t for _, t in segments[0]]
    seg2_texts = [t for _, t in segments[1]]
    assert "picker wind-down thought" in seg1_texts  # the tail still lands with its segment
    assert "a second free-text situation" not in seg1_texts  # the boundary held
    assert "a second free-text situation" in seg2_texts  # the new chapter owns its own turns


def test_mapper_rank_survives_a_restart_for_continue_targeting(tmp_path, make_fake):
    """Triage fold 2026-07-03: the mapper's territory ranking lived only in process memory, so a
    mid-world restart's Continue targeting silently fell back to library order. The rank now
    persists on the state row and restores lazily; a library-removed eid can never enter
    through the durable row (hallucination-filter parity)."""

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories
        # rank head _T2 (forged first), then _T3 — the LIBRARY order after _T2 would say _T1
        m.map_territories = lambda s, t: orig(s, t).model_copy(update={"ranked": [_T2, _T3, _T1]})
        return m

    db = str(tmp_path / "fd-rank.db")
    reg = SessionRegistry(db, model_factory=factory)
    _open_world(reg, "s1")  # forges over _T2 (the rank head)
    tag, _ = _drive(reg, "s1", opening="p1")
    assert tag == "done"  # converged: _T2 is inside the rolling window now

    reg2 = SessionRegistry(db, model_factory=factory)  # the restart
    tag, rdata = reg2.resume_or_start("s1")
    assert tag == "resume"
    now = datetime.now(timezone.utc)
    assert reg2._next_territory("s1", now) == _T3  # the mapper's rank, not library order (_T1)

    # Hallucination-filter parity on the durable row (review fold, mutation survived): a
    # library-retired eid in the persisted rank must never become a forge target — decide()'s
    # next(...) over open_exps would StopIteration and kill every Continue on the sitting.
    sit = SittingStore(db).live_sitting()["id"]
    SittingStore(db).write_state(sit, territory_rank=["retired_territory", _T3, _T2])
    reg3 = SessionRegistry(db, model_factory=factory)
    assert reg3.resume_or_start("s1")[0] == "resume"
    assert reg3._next_territory("s1", now) == _T3  # filtered restore skips the retired eid
    SittingStore(db).write_state(sit, territory_rank=["retired_territory"])
    reg4 = SessionRegistry(db, model_factory=factory)
    reg4.resume_or_start("s1")
    assert reg4._next_territory("s1", now) == _T1  # all-stale rank falls through to library order


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
    # author-facing labels match every other brief's student/Vera convention (triage fold);
    # the store's wire kinds stay you/vera — the relabel lives at the brief-assembly boundary
    assert all(role in ("student", "Vera") for seg in segments for role, _ in seg)
    assert any(text == "position one" for role, text in segments[0] if role == "student")
    assert any(text == "position two" for role, text in segments[1] if role == "student")
    assert len(screens) - n_before == 1  # ONE union screen call over the sitting's moves
    union = screens[-1]
    assert len(union) == len(set(union))  # deduped
    # L4 review F6 (discriminating): the union must COVER every converged territory — a
    # regression to a single-territory union would silently shrink it otherwise.
    from elenchus.content_loader import load_library
    from elenchus.web import voice as _v2

    eids = {r["experience_id"] for r in SittingStore(db).converged_log()}
    assert len(eids) == 2
    by_eid = {e.experience_id: e for e in load_library()}
    for eid in eids:
        assert set(_v2._moves(by_eid[eid])) & set(union), f"union misses territory {eid}"
    assert isinstance(data["terrain"], list)


def test_sitting_close_falls_back_static_on_screen_failure(tmp_path, make_fake):
    """The union screen flags the authored sitting close -> the safe static serves."""
    from elenchus.model import EgressScreen

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
    tag, data = reg.step("s1", "yes")  # the confirm beat: she agrees before it forges
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
    from elenchus.web.sitting_store import SittingStore

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


# ---- The mid-flight close/continue cross-write class (deferred ticket, class fix
# ---- 2026-07-04: a channel's emissions write to the sitting it was BORN into) ----------------

import threading  # noqa: E402


def test_late_emission_after_close_writes_to_its_own_sitting_never_the_new_one(tmp_path, make_fake):
    """The deferred ticket's executed repro, now the regression: converge, continue through the
    rendered front door, block the step inside the mapper, close (sitting A ends), cold-start
    sitting B, release. The late emission (A's forged opening + rank + inflight + instance row)
    must land on A — its truthful home — never on B."""
    entered, gate = threading.Event(), threading.Event()
    calls = {"n": 0}

    def factory():
        m = _world_factory(make_fake)()
        orig = m.map_territories

        def mapper(s, t):
            calls["n"] += 1
            if calls["n"] >= 2:  # the continue pass's map blocks; the first flows
                entered.set()
                gate.wait(timeout=10)
            return orig(s, t)

        m.map_territories = mapper
        return m

    db = str(tmp_path / "race.db")
    reg = SessionRegistry(db, model_factory=factory)
    store = SittingStore(db)
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="position one")
    assert tag == "done"  # segment 1 converged; a record exists
    sit_a = store.live_sitting()["id"]
    assert reg.continue_session("s1", menu=True)[0] == "say"  # rendered front door, sitting A

    out = {}
    t = threading.Thread(target=lambda: out.update(r=reg.step("s1", "a second situation")))
    t.start()
    assert entered.wait(5)  # the worker is parked inside the gated mapper
    tag, _ = reg.close("s1")  # mid-flight close: sitting A ends (reap skipped, stepping guard)
    assert tag == "close"
    tag, _ = reg.resume_or_start("s1")  # cold start: sitting B
    sit_b = store.live_sitting()["id"]
    assert sit_b != sit_a
    gate.set()
    t.join(timeout=10)
    assert not t.is_alive()

    b_texts = [x["payload"].get("text") for x in store.turns(sit_b)]
    assert _SCENARIO not in b_texts  # the late opening never crossed sittings
    assert store.read_state(sit_b)["inflight"] is None
    assert store.read_state(sit_b)["territory_rank"] is None
    a_texts = [x["payload"].get("text") for x in store.turns(sit_a)]
    assert _SCENARIO in a_texts  # ...it landed on the sitting it belongs to
    import sqlite3 as _sq

    con = _sq.connect(db)
    homes = {r[0] for r in con.execute("SELECT sitting_id FROM web_generated_problem")}
    con.close()
    assert homes <= {sit_a}  # instance rows never mint under the new sitting


def test_stale_done_never_hijacks_the_new_sittings_session_state(tmp_path, make_fake):
    """The class's in-memory half: a done dequeued from a REPLACED channel must not overwrite
    the session's record/pick/dedupe maps (they belong to the new sitting's flow); its durable
    writes go to the channel's own sitting. Spec-1 5a: the stale converged flow above also
    captures no position — every row that DOES exist (the genuine convergence from sitting A)
    carries a position that is one of ITS OWN sitting's "you" turns."""
    db = str(tmp_path / "stale-done.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    store = SittingStore(db)
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="position one")
    assert tag == "done"
    old_ch = reg._ch["s1"]
    rec_before = reg._last_record["s1"]
    sit_a = store.live_sitting()["id"]

    reg.close("s1")  # sitting A ends
    reg.resume_or_start("s1")  # sitting B, new channel
    assert reg._ch["s1"] is not old_ch
    # Seed sitting B's session-keyed flow state — the stale done must NOT touch it (finding 2).
    reg._next_pick["s1"] = "guard:ref"
    reg._next_pick_title["s1"] = "Guard title"
    reg._lost_ref["s1"] = "guard:lost"
    reg._lost_exp_id["s1"] = "guard:lost_eid"
    rec_b = dict(rec_before)
    rec_b["stop_reason"] = "converged"
    rec_b["ledger_ref"] = "gen:stale:1"
    old_ch.record = rec_b
    n_conv_all = len(store.converged_log())
    reg._on_done("s1", old_ch, {"state": None, "landing": ""})
    assert reg._last_record.get("s1") is not rec_b  # the session's record was not hijacked
    assert "gen:stale:1" not in reg._sitting_done.get("s1", set())  # nor the sitting dedupe
    # A superseded-flow convergence banks NO house — anywhere (cross-write review finding 1):
    # the village count / repeat window must not gain a row for work the user walked away from.
    assert len(store.converged_log()) == n_conv_all
    assert all(r["ref"] != "gen:stale:1" for r in store.converged_log())
    # ...and the durable RECORD still lands on A (inert on the closed sitting, never re-read).
    assert store.read_state(sit_a)["record"] is not None
    # The session-keyed maps belong to sitting B's flow — the stale done left them untouched.
    assert reg._next_pick["s1"] == "guard:ref"
    assert reg._next_pick_title["s1"] == "Guard title"
    assert reg._lost_ref["s1"] == "guard:lost"
    assert reg._lost_exp_id["s1"] == "guard:lost_eid"
    # Spec-1 5a: the stale converged flow above logged no row -> captured no position; every row
    # that DOES exist (sitting A's genuine convergence) carries a position that is one of ITS OWN
    # sitting's "you" turns.
    assert store.converged_log()  # non-vacuous: sitting A's genuine convergence is in the log
    for r in store.converged_log():
        assert r["position"] is not None
        you = {t["payload"]["text"] for t in store.turns(r["sitting_id"]) if t["kind"] == "you"}
        assert r["position"] in you


def test_stale_say_persists_to_own_sitting_but_leaves_the_new_flows_maps(tmp_path, make_fake):
    """Finding-2 teeth (cross-write review 2026-07-04): a stale say's dequeue writes its turn +
    inflight + rank ROW to its own sitting (ch.sit), but must not clobber sitting B's session-
    keyed in-memory flow — the territory-rank cache and the pending seam."""
    db = str(tmp_path / "stale-say.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    store = SittingStore(db)
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="position one")
    assert tag == "done"
    old_ch = reg._ch["s1"]
    sit_a = store.live_sitting()["id"]

    reg.close("s1")
    reg.resume_or_start("s1")  # sitting B, new channel
    assert reg._ch["s1"] is not old_ch
    sit_b = reg._sitting_id["s1"]
    # Sitting B's live flow state.
    reg._territory_rank["s1"] = ["b_rank_head"]
    reg._seam_pending["s1"] = "B's pending seam"
    # A stale say arrives late, carrying A's worker-set attributes.
    old_ch.mapped_rank = ["a_rank_head"]
    old_ch.inflight_exp = ("a_eid", "gen:a:1")
    reg._persist_emit("s1", old_ch, "say", {"text": "A's late opening"})
    # Session-keyed maps for B are untouched.
    assert reg._territory_rank["s1"] == ["b_rank_head"]
    assert reg._seam_pending["s1"] == "B's pending seam"
    # A's durable truth landed on A (its own sitting), never on B.
    assert "A's late opening" in [t["payload"].get("text") for t in store.turns(sit_a)]
    assert store.read_state(sit_a)["inflight"] == {
        "experience_id": "a_eid",
        "ledger_ref": "gen:a:1",
    }
    assert store.read_state(sit_a)["territory_rank"] == ["a_rank_head"]
    assert "A's late opening" not in [t["payload"].get("text") for t in store.turns(sit_b)]
    assert store.read_state(sit_b)["inflight"] is None


def test_multi_restart_interleaved_turns_never_stack_identical_asks(tmp_path, make_fake):
    """The duplicate-ask re-verify's offered pin (2026-07-03): mid-map deaths + restarts with a
    user turn between produce only honest, user-turn-separated re-asks — never back-to-back
    identical vera turns."""

    def factory():
        m = _world_factory(make_fake)()

        def boom(s, t):
            raise RuntimeError("mid-map death")

        m.map_territories = boom
        return m

    db = str(tmp_path / "ask3.db")
    store = SittingStore(db)
    for i in range(3):  # fresh registry per loop = a restart
        reg = SessionRegistry(db, model_factory=factory)
        tag, _ = reg.resume_or_start("s1")
        assert tag in ("say", "resume")
        tag2, _ = reg.step("s1", f"situation {i}")
        assert tag2 == "error"  # the worker died mid-map, honestly
    turns = [(t["kind"], t["payload"].get("text")) for t in store.turns(store.live_sitting()["id"])]
    for a, b in zip(turns, turns[1:]):
        assert not (a[0] == "vera" and b[0] == "vera" and a[1] == b[1])  # no stacked asks


# ---- Stay-in-scenario (spec 2026-07-05): _story predicate, sequel wiring, honest wind-down ----


def test_story_returns_the_prior_scenario_after_a_forged_converged_segment(tmp_path, make_fake):
    """Spec §2b: _story reads the last landed record's gen: instance-row scenario, durably."""
    db = str(tmp_path / "story.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="position one")
    assert tag == "done"
    sit = reg._sitting_id["s1"]
    assert reg._story(sit) == _SCENARIO  # the forged chapter-one scenario


def test_story_is_none_after_a_plateaued_segment_without_logging(tmp_path, make_fake, caplog):
    """A non-converged last record is a CORRECT fresh forge — None, and NOT a fault (no error log)."""
    outcome = {"v": "unchanged"}
    reg = SessionRegistry(
        str(tmp_path / "story2.db"), model_factory=_world_factory(make_fake, outcome=outcome)
    )
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="a hedge")
    assert tag == "done"  # plateaued landing
    sit = reg._sitting_id["s1"]
    caplog.clear()
    assert reg._story(sit) is None
    assert not [r for r in caplog.records if r.levelno >= 40]  # no error/exception logged


def test_story_missing_instance_row_on_converged_record_logs_loudly(tmp_path, make_fake, caplog):
    """Review point 2: a forged+converged record whose instance row is GONE is a storage fault —
    None (fresh forge, no crash) but logged loudly, so P1-by-storage-failure is visible."""
    import sqlite3 as _sq

    db = str(tmp_path / "story3.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="position one")
    sit = reg._sitting_id["s1"]
    con = _sq.connect(db)
    con.execute("DELETE FROM web_generated_problem WHERE sitting_id=?", (sit,))
    con.commit()
    con.close()
    caplog.clear()
    assert reg._story(sit) is None
    assert [r for r in caplog.records if r.levelno >= 40]  # the fault was logged


def test_territory_title_is_the_short_display_title(tmp_path, make_fake):
    reg = SessionRegistry(str(tmp_path / "tt.db"), model_factory=make_fake)
    title = reg._territory_title(_T1)  # continuity_lock_in
    assert title and "veldra:" not in title and len(title) < 60  # short, clean


def test_continue_after_forged_converged_forges_a_sequel_with_the_prior_story(tmp_path, make_fake):
    """Spec §2b: Continue after a forged+converged segment feeds the prior chapter's scenario to
    the forge (story=), so chapter two continues the SAME world."""
    briefs = []
    reg = SessionRegistry(
        str(tmp_path / "seq.db"), model_factory=_world_factory(make_fake, briefs=briefs)
    )
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one position")  # forged+converged
    assert reg.continue_session("s1")[0] == "say"  # boot chapter two
    reg.step("s1", "chapter two position")
    assert any(_SCENARIO in b[0] for b in briefs)  # the prior scenario rode the sequel brief


def test_next_kind_is_chapter_after_forged_converged_else_pressure(tmp_path, make_fake):
    """Spec §2d: next_kind derives from the ONE _story predicate; the payload sends a SHORT
    title + a description, not the paragraph in the title."""
    reg = SessionRegistry(str(tmp_path / "kind.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, data = _drive(reg, "s1", opening="position one")
    assert tag == "done"
    assert data["next_kind"] == "chapter"  # a story exists to continue
    assert data["next_title"] and len(data["next_title"]) < 60  # SHORT title
    assert data.get("next_desc")  # the description rides separately (muted line)


def test_next_kind_is_pressure_after_a_plateau(tmp_path, make_fake):
    outcome = {"v": "unchanged"}
    reg = SessionRegistry(
        str(tmp_path / "kind2.db"), model_factory=_world_factory(make_fake, outcome=outcome)
    )
    _open_world(reg, "s1")
    tag, data = _drive(reg, "s1", opening="a hedge")
    assert tag == "done"
    assert data["next_kind"] == "pressure"  # no sequel to continue


def test_label_kind_and_forge_path_agree_on_the_same_record(tmp_path, make_fake):
    """Review point 3: the label the user sees and the sequel the forge builds derive from the
    SAME _story predicate — they can never disagree on one landed record."""
    briefs = []
    reg = SessionRegistry(
        str(tmp_path / "agree.db"), model_factory=_world_factory(make_fake, briefs=briefs)
    )
    _open_world(reg, "s1")
    tag, data = _drive(reg, "s1", opening="chapter one")
    sit = reg._sitting_id["s1"]
    is_chapter = data["next_kind"] == "chapter"
    story_present = reg._story(sit) is not None
    assert is_chapter == story_present  # agreement by construction
    reg.continue_session("s1")
    reg.step("s1", "chapter two")
    forged_sequel = any(_SCENARIO in b[0] for b in briefs)
    assert forged_sequel == is_chapter  # the forge did what the label promised


def test_post_landing_converse_uses_the_honest_static_not_safe_contract(tmp_path, make_fake):
    """The founder's disclosure-question bounce (2026-07-04): a screened/refused post-landing
    converse must serve the honest static, never SAFE_CONTRACT's 'I'll push' lie."""
    from elenchus.web import voice as _v

    def factory():
        m = _world_factory(make_fake)()
        m.concierge_converse = lambda problem, recent, *, stop_reason="converged", voice="": (
            ConverseTurn(reply="", next_pressure="")
        )
        return m

    reg = SessionRegistry(str(tmp_path / "wind.db"), model_factory=factory)
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="position one")  # forged+converged -> a sequel exists
    assert tag == "done"
    tag, data = reg.converse("s1", "If Halvmark exposes a defect, do you disclose it?")
    assert tag == "say"
    assert data["text"] == _v._CONVERSE_DONE_STORY
    assert data["text"] != _v.SAFE_CONTRACT


def test_next_kind_survives_a_restart_on_the_resume_payload(tmp_path, make_fake):
    """Spec §4 test 7 (review fold): the resume-path label derives from the SAME _story predicate,
    so a resumed Continue keeps 'chapter' across a restart; a plateaued sitting resumes 'pressure'."""
    db = str(tmp_path / "resume-kind.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    tag, _ = _drive(reg, "s1", opening="chapter one position")
    assert tag == "done"  # forged+converged
    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))  # the restart
    tag, data = reg2.resume_or_start("s1")
    assert tag == "resume"
    assert data["next_kind"] == "chapter"  # the sequel survives the restart
    assert data["next_desc"]  # the description rides too

    db2 = str(tmp_path / "resume-kind2.db")
    reg3 = SessionRegistry(db2, model_factory=_world_factory(make_fake, outcome={"v": "unchanged"}))
    _open_world(reg3, "s2")
    _drive(reg3, "s2", opening="a hedge")  # plateaued
    reg4 = SessionRegistry(db2, model_factory=_world_factory(make_fake, outcome={"v": "unchanged"}))
    _, d2 = reg4.resume_or_start("s2")
    assert d2["next_kind"] == "pressure"  # no sequel to continue


def test_interrupted_converse_fail_closed_is_honest_not_the_push_lie(tmp_path, make_fake):
    """Review fold (informational note): the lost-context fail-closed path served SAFE_CONTRACT's
    'I'll push' lie — the whole batch kills that lie. It now serves the honest fresh static
    (equally safe: a static, no move, no push promise)."""
    from elenchus.web import voice as _v

    # The screen against a lost exp fail-closes: force it by making every reply "leak".
    def factory():
        m = _world_factory(make_fake)()
        m.concierge_converse = lambda problem, recent, *, stop_reason="converged", voice="": (
            ConverseTurn(reply="ok", next_pressure="")
        )
        return m

    reg = SessionRegistry(str(tmp_path / "lost.db"), model_factory=factory)
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="position one")
    # simulate an unresolvable lost context: a lost exp id that no library entry matches
    reg._lost_exp_id["s1"] = "no_such_experience_xyz"
    reg._lost_ref["s1"] = "gen:lost:1"
    tag, data = reg.converse("s1", "a probe")
    assert tag == "say"
    assert data["text"] == _v._CONVERSE_DONE_FRESH  # honest static, not the push lie
    assert data["text"] != _v.SAFE_CONTRACT


# --- User-steered chapters: capture + the wind-down label (S-T4) --------------------------------


def test_converse_captures_servable_steer_and_labels(tmp_path, make_fake):
    """§2b/§2c: a servable fresh pressure becomes the pending steer; the wind-down say carries the
    steer label with HER raw words, and the distilled pressure never reaches the wire (L-13/F2)."""
    reg = SessionRegistry(str(tmp_path / "steer.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    assert _drive(reg, "s1", opening="chapter one")[0] == "done"
    target = _arm_steer(reg, "s1", next_pressure="whether to disclose the defect now")
    tag, data = reg.converse("s1", "Now I have to decide whether to tell the board.")
    assert tag == "say"
    assert data["next_kind"] == "steer"
    assert data["next_title"] == ""  # the button is a fixed short lead
    assert data["next_desc"] == "Now I have to decide whether to tell the board."  # HER raw words
    assert "whether to disclose the defect now" not in str(data)  # distillation off the wire
    assert reg._steer_pending["s1"] == (
        "Now I have to decide whether to tell the board.",
        "whether to disclose the defect now",
        target,
    )


def test_converse_unservable_pressure_leaves_prior_steer(tmp_path, make_fake):
    """F5 last-SERVABLE-wins: a non-empty pressure that maps LOW confidence is not servable and
    leaves any prior steer untouched."""
    reg = SessionRegistry(str(tmp_path / "steer2.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="P1")
    reg.converse("s1", "raw one")
    first = reg._steer_pending["s1"]
    _arm_steer(reg, "s1", next_pressure="P2", confidence="low")  # unservable
    reg.converse("s1", "raw two")
    assert reg._steer_pending["s1"] == first  # the unservable turn left P1's steer


def test_converse_empty_pressure_leaves_prior_steer(tmp_path, make_fake):
    reg = SessionRegistry(str(tmp_path / "steer3.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="P1")
    reg.converse("s1", "raw one")
    first = reg._steer_pending["s1"]
    _arm_steer(reg, "s1", next_pressure="")  # chatter — no capture call at all
    reg.converse("s1", "just a comment")
    assert reg._steer_pending["s1"] == first


def test_converse_windowed_pressure_not_servable(tmp_path, make_fake):
    """A pressure mapping to the JUST-WORKED (windowed) territory is not servable — no steer."""
    reg = SessionRegistry(str(tmp_path / "steer4.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    worked = reg._last_record["s1"]["exp"].experience_id
    _arm_steer(reg, "s1", next_pressure="P", ranked_first=worked)  # windowed
    reg.converse("s1", "raw")
    assert "s1" not in reg._steer_pending


def test_end_sitting_clears_steer(tmp_path, make_fake):
    reg = SessionRegistry(str(tmp_path / "steer5.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="P1")
    reg.converse("s1", "raw one")
    assert "s1" in reg._steer_pending
    reg.close("s1")  # End -> _end_sitting
    assert "s1" not in reg._steer_pending
    assert "s1" not in reg._steer_consume


# --- User-steered chapters: the deterministic consume (S-T5) ------------------------------------


def _other_open_territory(reg, sid):
    from elenchus.content_loader import load_library

    worked = reg._last_record[sid]["exp"].experience_id
    open_eids = [e.experience_id for e in load_library() if e.regime is Regime.open_ended]
    return next(e for e in open_eids if e != worked)


def test_continue_consumes_steer_forges_pre_mapped_with_focus_no_second_map(tmp_path, make_fake):
    """§2d: a pending steer at Continue forges the PRE-MAPPED territory with focus= carrying the
    pressure, and makes NO second map_territories call (deterministic consume)."""
    from elenchus.content_loader import load_territory_text

    briefs, maps = [], []
    reg = SessionRegistry(
        str(tmp_path / "consume.db"),
        model_factory=_world_factory(make_fake, briefs=briefs, maps=maps),
    )
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    target = _other_open_territory(reg, "s1")
    # inject a servable pending steer directly (capture is covered in S-T4)
    reg._steer_pending["s1"] = ("her raw words", "raise a bridge round now", target)
    briefs.clear()
    n_maps = len(maps)  # the open_world front-door map call
    reg.continue_session("s1")
    assert len(maps) == n_maps  # deterministic consume — no second map call
    assert briefs, "no forge brief captured"
    assert any("raise a bridge round now" in b[0] for b in briefs)  # focus threaded
    assert any(load_territory_text(target) in b[0] for b in briefs)  # the PRE-MAPPED territory
    assert "s1" not in reg._steer_pending  # consumed


def test_steer_label_agrees_with_delivery(tmp_path, make_fake):
    """§4 test 6: whenever the wind-down shows next_kind='steer', Continue delivers the SAME
    territory the steer named — label == delivery by construction."""
    from elenchus.content_loader import load_territory_text

    briefs = []
    reg = SessionRegistry(
        str(tmp_path / "agree.db"), model_factory=_world_factory(make_fake, briefs=briefs)
    )
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    target = _arm_steer(reg, "s1", next_pressure="a new call")
    _, data = reg.converse("s1", "raw words")
    assert data["next_kind"] == "steer"  # the label promises a steer...
    assert reg._steer_pending["s1"][2] == target  # ...to `target`
    briefs.clear()
    reg.continue_session("s1")  # delivery
    assert any(load_territory_text(target) in b[0] for b in briefs)  # forged the promised territory


def test_window_stale_steer_falls_back_to_rotation(tmp_path, make_fake):
    """§2d: a steer whose territory windows mid-converse falls back to rotation at consume (the
    cheap window re-check) — no crash, steer cleared."""
    reg = SessionRegistry(str(tmp_path / "stale.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    target = _arm_steer(reg, "s1", next_pressure="P")
    reg.converse("s1", "raw")
    assert reg._steer_pending["s1"][2] == target
    reg._store.territories_within = lambda now: {target}  # the steer's territory now windows
    tag, _ = reg.continue_session("s1")
    assert tag in ("say", "reserve")  # rotation (or reserve if all windowed) — never a crash
    assert "s1" not in reg._steer_pending  # popped either way


def test_picker_clears_steer(tmp_path, make_fake):
    """§2d picker interaction: choosing 'other doors' (menu=True) supersedes a pending steer."""
    reg = SessionRegistry(str(tmp_path / "picker.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="P1")
    reg.converse("s1", "raw one")
    assert "s1" in reg._steer_pending
    reg.continue_session("s1", menu=True)  # other doors
    assert "s1" not in reg._steer_pending
    assert "s1" not in reg._steer_consume


def test_no_steer_continue_carries_no_focus(tmp_path, make_fake):
    """§4 test 9 regression pin: with NO steer pending, a world Continue is the rotation path —
    the forge brief carries no focus block."""
    briefs = []
    reg = SessionRegistry(
        str(tmp_path / "rot.db"), model_factory=_world_factory(make_fake, briefs=briefs)
    )
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    briefs.clear()
    reg.continue_session("s1")  # rotation — no steer
    assert briefs
    assert all("The pressure she wants to press next" not in b[0] for b in briefs)


# --- User-steered chapters: adversarial-review folds (label window re-check, interrupted, sweep) ---


def test_windowed_steer_label_is_suppressed_on_a_later_turn(tmp_path, make_fake):
    """Review F2: a steer whose territory windows AFTER capture must not keep showing the 'steer'
    label on a later chatter turn — the label tracks the LIVE window (agreement invariant)."""
    reg = SessionRegistry(str(tmp_path / "stale-label.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    target = _arm_steer(reg, "s1", next_pressure="P1")
    _, data = reg.converse("s1", "raw words")
    assert data["next_kind"] == "steer"  # captured, non-windowed -> steer label
    reg._store.territories_within = lambda now: {target}  # the steer's territory now windows
    _arm_steer(reg, "s1", next_pressure="")  # a chatter turn (no fresh pressure)
    _, data2 = reg.converse("s1", "just a comment")
    assert data2["next_kind"] != "steer"  # windowed -> rotation label, not a false promise


def test_interrupted_turn_does_not_capture_a_steer(tmp_path, make_fake):
    """Review F3: an interrupted/lost-context converse (reply fail-closed to the honest static)
    must not simultaneously capture a steer and promise 'press what you raised'."""
    reg = SessionRegistry(str(tmp_path / "interrupt.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="a fresh call")
    reg._lost_exp_id["s1"] = "no_such_experience_xyz"  # unresolvable lost context -> fail-close
    reg._lost_ref["s1"] = "gen:lost:1"
    _, data = reg.converse("s1", "raw")
    assert data.get("next_kind") != "steer"  # no steer promise on a degraded turn
    assert "s1" not in reg._steer_pending  # and nothing captured


def test_distilled_pressure_never_reaches_the_projected_wire(tmp_path, make_fake):
    """Spec §4 test 10 + review Minor: the distilled next_pressure/focus never reaches ANY client
    payload — sweep the REAL converse -> _emit projection AND the continue payload (composition
    seam, not a hand-built dict)."""
    from elenchus.web.app import _emit

    reg = SessionRegistry(str(tmp_path / "sweep.db"), model_factory=_world_factory(make_fake))
    _open_world(reg, "s1")
    _drive(reg, "s1", opening="chapter one")
    _arm_steer(reg, "s1", next_pressure="DISTILLED_SECRET_CLAUSE")
    tag, data = reg.converse("s1", "her raw typed words")
    wire = _emit(reg, tag, data)  # the ACTUAL projected client payload
    assert wire["kind"] == "say" and wire["next_kind"] == "steer"
    assert wire["next_desc"] == "her raw typed words"  # HER words, not the distillation
    assert "DISTILLED_SECRET_CLAUSE" not in str(wire)  # the distillation never projects (L-13)
    ctag, cdata = reg.continue_session("s1")
    assert "DISTILLED_SECRET_CLAUSE" not in str(_emit(reg, ctag, cdata))  # nor the continue wire


def test_returning_line_counts_convergence_rows(tmp_path, make_fake):
    """Model A (the revert, plan Task 2): the returning caption counts CONVERGENCE ROWS — a saga
    of N chapters now contributes N to the count, matching len(houses) (the old 'group by
    sitting_id' premise — and the '6 houses' count-bug fix it guarded — is gone; the honest count
    is the point). Pinned copy asserted literally: 'N judgment(s) across your domains'
    (review code-truth 5)."""
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "saga_count.db")
    store = SittingStore(db)
    wall = datetime.now(timezone.utc)
    # sitting A converges twice, sitting B once -> THREE rows -> three houses -> "3 judgments"
    store.log_converged("A", "gen:A:1", wall - timedelta(hours=3), "eid1")
    store.log_converged("A", "gen:A:2", wall - timedelta(hours=2), "eid1")
    store.log_converged("B", "gen:B:1", wall - timedelta(hours=1), "eid2")
    reg = SessionRegistry(db, model_factory=make_fake)
    tag, data = reg.resume_or_start("single")
    assert "3 judgments across your domains" in data["returning"]  # 3 rows, NOT "2 judgments"
    assert "2 judgments" not in data["returning"]


def test_frontdoor_load_payload_carries_homebase_terrain_and_houses(tmp_path, make_fake):
    """Phase 2 2a/2b: on a returning load (no live sitting) the front-door payload carries the
    frozen cumulative (terrain, houses) so the world renders on landing — and _emit surfaces
    them behind the frontdoor allowlist."""
    from elenchus.web.sitting_store import SittingStore
    from elenchus.web.session_runner import SessionRegistry
    from elenchus.web.app import _emit

    db = str(tmp_path / "hbpay.db")
    store = SittingStore(db)  # seed via the store...
    sit = store.create_sitting(NOW)
    store.log_converged(
        sit, "gen:x:1", NOW, "eid1"
    )  # (sit, ref, now, eid) — matches _on_done's call
    terrain = [{"region_id": "r0", "render": "rendered", "vitality": 2, "elevation": 1}]
    houses = [{"region": 0, "bucket": 2}]
    store.write_state(sit, record={"terrain": terrain, "houses": houses})
    store.close_sitting(sit)  # no live sitting -> resume_or_start -> frontdoor branch
    reg = SessionRegistry(db, model_factory=make_fake)  # ...read via a registry on the SAME db PATH
    tag, data = reg.resume_or_start("single")
    assert data.get("terrain") == terrain
    assert data.get("houses") == houses
    wire = _emit(reg, tag, data)
    assert wire["kind"] == "frontdoor"
    assert wire["terrain"] == terrain
    assert wire["houses"] == houses


def test_frontdoor_load_payload_omits_homebase_on_first_visit(tmp_path, make_fake):
    """First-ever visit (no landed record): no terrain/houses on the wire -> the shell shows an
    empty world (just the front door), never a crash or a phantom village."""
    from elenchus.web.session_runner import SessionRegistry
    from elenchus.web.app import _emit

    reg = SessionRegistry(str(tmp_path / "fresh.db"), model_factory=make_fake)
    tag, data = reg.resume_or_start("single")
    wire = _emit(reg, tag, data)
    assert wire["kind"] == "frontdoor"
    assert "terrain" not in wire and "houses" not in wire


def test_resume_parked_at_frontdoor_carries_the_homebase(tmp_path, make_fake):
    """Phase 2 T7 (Decision 3 on reload): a resume PARKED at the front door is a landing too — it
    must carry the frozen homebase so the world shows on reload, not only on a fresh cold start.
    The first resume_or_start creates the parked live sitting (frontdoor); the second hits _resume."""
    import json
    from elenchus.web.sitting_store import SittingStore
    from elenchus.web.session_runner import SessionRegistry
    from elenchus.web.app import _emit

    db = str(tmp_path / "t7.db")
    store = SittingStore(db)
    sit = store.create_sitting(NOW)
    store.log_converged(sit, "gen:x:1", NOW, "eid1")
    terrain = [{"region_id": "r0", "render": "rendered", "vitality": 2, "elevation": 1}]
    houses = [{"region": 0, "bucket": 2}]
    store.write_state(sit, record={"terrain": terrain, "houses": houses})
    store.close_sitting(sit)  # a PRIOR landed saga (the cumulative world so far)
    reg = SessionRegistry(db, model_factory=make_fake)
    reg.resume_or_start("single")  # 1st: frontdoor — CREATES the parked live sitting
    tag, data = reg.resume_or_start("single")  # 2nd: _resume, parked at the front door
    assert tag == "resume"
    assert data.get("frontdoor")  # parked at the front door (not mid-conversation)
    assert data.get("terrain") == terrain
    assert data.get("houses") == houses
    wire = _emit(reg, tag, data)  # resume branch spreads **data -> terrain/houses on the wire
    assert wire["kind"] == "resume"
    assert wire["terrain"] == terrain and wire["houses"] == houses
    # L-13 on the resume passthrough: house keys safe, no ref/id/sitting_id token
    for h in wire["houses"]:
        assert set(h) == {"region", "bucket"}
    blob = json.dumps(wire["terrain"]) + json.dumps(wire["houses"])
    assert "gen:" not in blob and "veldra:" not in blob and "eid1" not in blob and sit not in blob


def test_plateau_only_returning_user_gets_no_homebase_on_either_path(tmp_path, make_fake):
    """Whole-branch consistency fold: a plateau/budget-only returning user has a NON-EMPTY seed
    terrain frozen but NO convergences (empty converged_log). The homebase must be absent on BOTH
    the fresh-frontdoor AND the reload-parked payloads — the two gates must agree (Decision 3)."""
    from elenchus.web.sitting_store import SittingStore
    from elenchus.web.session_runner import SessionRegistry

    db = str(tmp_path / "plateau.db")
    store = SittingStore(db)
    sit = store.create_sitting(NOW)
    # a landed PLATEAU record: seed terrain, NO houses, and NO log_converged (converged_log empty)
    store.write_state(
        sit,
        record={
            "terrain": [{"region_id": "r0", "render": "seed", "vitality": None, "elevation": None}],
            "houses": [],
        },
    )
    store.close_sitting(sit)
    reg = SessionRegistry(db, model_factory=make_fake)
    tag1, data1 = reg.resume_or_start("single")  # 1st: fresh frontdoor (no live sitting)
    assert data1.get("frontdoor")
    assert "terrain" not in data1 and "houses" not in data1  # plateau-only: no world on fresh load
    tag2, data2 = reg.resume_or_start("single")  # 2nd: reload -> resume parked at front door
    assert tag2 == "resume" and data2.get("frontdoor")
    assert "terrain" not in data2 and "houses" not in data2  # ...and none on reload either


def test_reset_session_state_clears_every_per_sid_map_but_not_the_nonce(tmp_path, make_fake):
    reg = SessionRegistry(str(tmp_path / "x.db"), model_factory=make_fake)
    sid = "s1"
    # Seed a guard value into every sitting-scoped map _end_sitting clears (the §5d list).
    reg._sitting_id[sid] = "sitX"
    reg._last_record[sid] = {"guard": True}
    reg._fit_variant_idx[sid] = 2
    reg._sitting_done[sid] = {"ref"}
    reg._next_pick[sid] = "guard:ref"
    reg._next_pick_title[sid] = "guard"
    reg._seam_pending[sid] = "guard"
    reg._inflight_synced[sid] = True
    reg._lost_ref[sid] = "guard:ref"
    reg._lost_exp_id[sid] = "guard"
    reg._territory_rank[sid] = ["guard"]
    reg._level_idx[sid] = 1
    reg._forge_n[sid] = 9
    reg._frontdoor_swallow.add(sid)
    reg._steer_pending[sid] = ("t", "p", "w")
    reg._steer_consume[sid] = ("t", "p")
    reg._continue_target[sid] = "guard"
    reg._menu_nonce[sid] = 41

    reg._reset_session_state(sid)

    for m in (
        reg._sitting_id,
        reg._last_record,
        reg._fit_variant_idx,
        reg._sitting_done,
        reg._next_pick,
        reg._next_pick_title,
        reg._seam_pending,
        reg._inflight_synced,
        reg._lost_ref,
        reg._lost_exp_id,
        reg._territory_rank,
        reg._level_idx,
        reg._forge_n,
        reg._steer_pending,
        reg._steer_consume,
        reg._continue_target,
    ):
        assert sid not in m
    assert sid not in reg._frontdoor_swallow
    # deliberately survives: monotonic per process (C18)
    assert reg._menu_nonce.get(sid) == 41


def test_reload_with_a_pending_steer_keeps_the_button_naming_the_steer(tmp_path, make_fake):
    """The _wind_down_label agreement invariant on its surviving trigger (plain reload):
    a pending steer must label the resume Continue as the steer, matching what
    continue_session forges (cross-arc fix 2026-07-09, re-pointed after /enter removal)."""
    from elenchus.content_loader import load_library, load_territory_text

    briefs = []
    reg = SessionRegistry(
        str(tmp_path / "steer_reload.db"), model_factory=_world_factory(make_fake, briefs=briefs)
    )
    _open_world(reg, "s1")
    assert _drive(reg, "s1", opening="chapter one")[0] == "done"
    worked = reg._last_record["s1"]["exp"].experience_id
    rotation = reg._next_territory("s1", NOW)
    open_eids = [e.experience_id for e in load_library() if e.regime is Regime.open_ended]
    steer_target = next(e for e in open_eids if e not in (worked, rotation))
    _arm_steer(reg, "s1", next_pressure="the bridge round vs run lean", ranked_first=steer_target)
    tag, data = reg.converse("s1", "Do I raise a bridge round or cut to survive?")
    assert tag == "say" and data["next_kind"] == "steer"
    tag, ep = reg.resume_or_start("s1")  # the RELOAD
    assert tag == "resume"
    assert ep["next_kind"] == "steer"
    assert ep["next_desc"] == "Do I raise a bridge round or cut to survive?"
    briefs.clear()
    reg.continue_session("s1")
    assert any(load_territory_text(steer_target) in b[0] for b in briefs)
    assert not any(load_territory_text(rotation) in b[0] for b in briefs)


def test_convergence_captures_the_final_you_turn_never_a_vera_push(tmp_path, make_fake):
    """Spec 5a: the position is captured AT log_converged from the last persisted "you" turn —
    the _positions selection (kind=="you" only), never a vera push, and the landing turn is not
    yet appended at capture time. Stale/superseded flows never log -> never capture."""
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg.resume_or_start("s1")
    assert tag == "say" and data.get("frontdoor")
    tag, data = reg.step("s1", "my company, my hard call")
    last_you = None
    while tag == "say":
        last_you = "mechanism " + str(id(tag))  # unique final reply text
        tag, data = reg.step("s1", last_you)
    assert tag == "done"
    rows = SittingStore(db).converged_log()
    assert len(rows) == 1
    assert rows[0]["position"] == last_you  # her verbatim final substantive turn
    # and it is a "you" turn's text, not any vera-authored push
    turns = SittingStore(db).turns(rows[0]["sitting_id"])
    you_texts = [t["payload"]["text"] for t in turns if t["kind"] == "you"]
    assert rows[0]["position"] == you_texts[-1]

    # (3f, review N4/SF2): a SECOND convergence in the same sitting captures ITS OWN final "you"
    # turn — never chapter 1's, never a converse turn — and agrees with the shared _positions
    # selection (the seam pin: capture at log_converged ≡ _positions' per-landing selection).
    tag, data = reg.continue_session("s1")
    assert tag == "say"
    last_you_2 = None
    while tag == "say":
        last_you_2 = "chapter2 " + str(id(data))
        tag, data = reg.step("s1", last_you_2)
    assert tag == "done"
    assert last_you_2 != last_you
    rows = SittingStore(db).converged_log()
    assert len(rows) == 2
    assert rows[0]["position"] == last_you  # chapter 1's row is untouched by chapter 2
    assert rows[1]["position"] == last_you_2  # chapter 2 captured its OWN final turn
    sit = rows[1]["sitting_id"]
    assert sit == rows[0]["sitting_id"]  # same sitting, two convergences
    assert rows[-1]["position"] == reg._positions(sit)[-1]  # capture ≡ _positions — the seam pin


# ---- The memory bubble (Spec-1 5b/5d, plan Task 3): a BY-REF pure read of one convergence -----


def test_memory_returns_situation_position_when_for_each_convergence(tmp_path, make_fake):
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg.resume_or_start("s1")
    tag, data = reg.step("s1", "my company, my hard call")
    final = None
    while tag == "say":
        final = "I commit: hold the line on the exclusivity clause."
        tag, data = reg.step("s1", final)
    assert tag == "done"
    rows = SittingStore(db).converged_log()
    tag, m = reg.memory("s1", 0)
    assert tag == "memory"
    assert m["position"] == final  # verbatim her words (L-4: recalled)
    assert m["situation"] == _SCENARIO  # the SERVED forged scenario, byte-equal
    assert m["when"] == rows[0]["converged_at"]
    # L-13: no identifiers in the payload
    import json

    blob = json.dumps(m)
    for needle in ("gen:", "veldra:", rows[0]["sitting_id"], "experience_id", "ledger_ref"):
        assert needle not in blob, needle


def test_memory_bounds_and_legacy_are_honest(tmp_path, make_fake):
    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    _ = reg.resume_or_start("s1")
    tag, m = reg.memory("s1", 0)  # nothing converged yet -> no house_refs -> unavailable
    assert tag == "memory" and m.get("unavailable") is True
    # bounds (review SF4: converge FIRST so refs is non-empty and the bounds branch — not the
    # empty short-circuit — is what fires; -1 must never python-index)
    tag, data = reg.step("s1", "my company, my hard call")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    for bad in (-1, 1, 99):
        tag, m = reg2.memory("s1", bad)
        assert tag == "nudge", (bad, tag)  # the _MEMORY_UNKNOWN_NUDGE branch, genuinely exercised
    tag, m = reg2.memory("s1", 0)
    assert tag == "memory" and m.get("position")  # and index 0 still resolves correctly


def test_memory_drift_guard_returns_unavailable_on_ref_mismatch(tmp_path, make_fake):
    """house_refs[i] is the drift guard: if the frozen refs and the live log ever disagree
    (a legacy or corrupted record), the bubble refuses rather than serving a WRONG memory."""
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, data = reg.resume_or_start("s1")
    tag, data = reg.step("s1", "opening")
    while tag == "say":
        tag, data = reg.step("s1", "mechanism")
    store = SittingStore(db)
    sit = store.converged_log()[0]["sitting_id"]
    rec = store.read_state(sit)["record"]
    rec["house_refs"] = ["gen:WRONG:9"]
    store.write_state(sit, record=rec)
    reg2 = SessionRegistry(db, model_factory=_world_factory(make_fake))
    tag, m = reg2.memory("s1", 0)
    assert tag == "memory" and m.get("unavailable") is True


def test_memory_curated_situation_is_the_gated_prompt_never_territory_text(tmp_path, make_fake):
    from elenchus.content_loader import load_library, load_territory_text
    from elenchus.types import Regime
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    exp = next(e for e in load_library() if e.regime is Regime.open_ended)
    t = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    store = SittingStore(db)
    sit = store.create_sitting(t)
    store.log_converged(sit, exp.ledger_ref, t, exp.experience_id, position="my call")
    store.write_state(
        sit,
        record={
            "terrain": [{"render": "rendered"}],
            "houses": [{"region": 0, "bucket": 2}],
            "house_refs": [exp.ledger_ref],
        },
        now=t,
    )
    store.close_sitting(sit)
    tag, m = reg.memory("s1", 0)
    assert tag == "memory"
    assert m["situation"] == exp.prompt  # POSITIVE pin: the gated frame-blind prompt (review SF1)
    assert m["situation"] != load_territory_text(exp.experience_id)  # NEVER the category text (S3)
    assert m["position"] == "my call"
    # origin (D4): sitting created 2026-07-21 but... use a differing converged_at to pin the format
    assert m["when"] == t.isoformat()


def test_memory_origin_is_a_date_only_handle_and_null_position_is_a_placeholder_bubble(
    tmp_path, make_fake
):
    """D4: origin = YYYY-MM-DD from the sitting id, shown only when it differs from `when`'s day;
    the raw sitting_id NEVER rides (positive derivation assert — spec §8/review N5). A legacy row
    (position=NULL) still gets a BUBBLE with position None (the chrome placeholder), NOT
    unavailable (spec §5a; review N6)."""
    from elenchus.content_loader import load_library
    from elenchus.types import Regime
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    exp = next(e for e in load_library() if e.regime is Regime.open_ended)
    t0 = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)  # sitting born day 19
    t1 = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)  # converged day 21 (differs)
    store = SittingStore(db)
    sit = store.create_sitting(t0)
    store.log_converged(sit, exp.ledger_ref, t1, exp.experience_id)  # legacy: NO position
    store.write_state(
        sit,
        record={
            "terrain": [{"render": "rendered"}],
            "houses": [{"region": 0, "bucket": 2}],
            "house_refs": [exp.ledger_ref],
        },
        now=t1,
    )
    store.close_sitting(sit)
    tag, m = reg.memory("s1", 0)
    assert tag == "memory" and not m.get("unavailable")
    assert m["position"] is None  # placeholder bubble, never unavailable (N6)
    assert m["origin"] == "2026-07-19"  # POSITIVE derivation pin (N5); differs from when's day
    assert sit not in str(m)  # the raw id never rides (L-13)


def test_memory_drift_guard_checks_row_identity_not_ref_alone(tmp_path, make_fake):
    """S1 (whole-branch review): a ref string alone is not a unique row identity. A CURATED ref
    can reconverge after the 24h window; if the wall clock stepped backwards between the two
    convergences, converged_log() (ORDER BY converged_at, rowid) reorders so the SAME ref string
    lands back at the frozen index — a ref-only drift guard false-passes and serves the WRONG
    convergence's position. house_at (converged_at, frozen index-parallel with house_refs at the
    freeze site) pins WHICH convergence house 0 names, so the guard must refuse here."""
    from elenchus.content_loader import load_library
    from elenchus.types import Regime
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    exp = next(e for e in load_library() if e.regime is Regime.open_ended)
    store = SittingStore(db)
    t2 = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)  # earlier — the backwards clock step

    # Sitting A: the FROZEN convergence — house 0's true position, at the true (later) time.
    sit_a = store.create_sitting(t2)
    store.log_converged(sit_a, exp.ledger_ref, t2, exp.experience_id, position="POS-OLD")
    store.write_state(
        sit_a,
        record={
            "terrain": [{"render": "rendered"}],
            "houses": [{"region": 0, "bucket": 2}],
            "house_refs": [exp.ledger_ref],
            "house_at": [t2.isoformat()],
        },
        now=t2,
    )
    store.close_sitting(sit_a)

    # Sitting B: the SAME curated ref reconverges with an EARLIER converged_at — reorders the
    # live log so rows[0] is now B's row, same ref string as the frozen refs[0].
    sit_b = store.create_sitting(t1)
    store.log_converged(sit_b, exp.ledger_ref, t1, exp.experience_id, position="POS-NEW")

    tag, m = reg.memory("s1", 0)
    assert tag == "memory"
    assert m == {"unavailable": True}  # refuses — never POS-NEW, never B's `when`


def test_memory_curated_situation_honors_the_row_experience_id(tmp_path, make_fake):
    """N1 (whole-branch review): `_memory_situation` must not first-match on ledger_ref alone —
    two library entries share `veldra:license_fork_risk` (continuity_lock_in, license_continuity)
    with DIFFERENT prompts. The situation returned must be the prompt of the entry whose
    experience_id actually converged (the row's), not whichever entry sorts first."""
    from elenchus.content_loader import load_library
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "x.db")
    reg = SessionRegistry(db, model_factory=_world_factory(make_fake))
    library = load_library()
    continuity_lock_in = next(e for e in library if e.experience_id == "continuity_lock_in")
    license_continuity = next(e for e in library if e.experience_id == "license_continuity")
    assert continuity_lock_in.ledger_ref == license_continuity.ledger_ref
    assert continuity_lock_in.ledger_ref == "veldra:license_fork_risk"
    assert continuity_lock_in.prompt != license_continuity.prompt

    store = SittingStore(db)
    t = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    sit = store.create_sitting(t)
    store.log_converged(
        sit,
        license_continuity.ledger_ref,
        t,
        license_continuity.experience_id,
        position="my call",
    )
    store.write_state(
        sit,
        record={
            "terrain": [{"render": "rendered"}],
            "houses": [{"region": 0, "bucket": 2}],
            "house_refs": [license_continuity.ledger_ref],
            "house_at": [t.isoformat()],
        },
        now=t,
    )
    store.close_sitting(sit)
    tag, m = reg.memory("s1", 0)
    assert tag == "memory"
    assert m["situation"] == license_continuity.prompt  # matches the row's experience_id
    assert m["situation"] != continuity_lock_in.prompt  # never the other entry sharing the ref


# ---- Phase A T3: the _on_done identity seam — slot match/commit/freeze, per-house prefix
# copy-forward, and the transient confluence event (Spec-2 §4/§5) ------------------------------
#
# Every world_* fixture below drives GENUINE landings through the real registry path (L-9: no
# hand-built records) — a fresh session_id per segment (sharing ONE SessionRegistry/db: the
# engine's LearnerState and the web_converged/web_domain_slot registries are both global to the
# db, never sitting-scoped, so separate session_ids simply accrete onto the same state) using the
# file's own `_agnostic`/`_drive` drive helpers and `menu_index` door-picking (the same mechanics
# `test_runner_assessment_equals_direct_run_session` already exercises).

_CONTINUITY_REF = "veldra:license_fork_risk"  # continuity_lock_in: 1 frame (embed...)
_STAKES_REF = "veldra:concentrated_market_pricing_power"  # decision_under_stakes: 2 frames
_PROOF_REF = "veldra:first_customer_proof_loop"  # proof_before_promise: protect + choose


def _landed_record(reg, sid):
    return reg._last_record[sid]


def _land(reg, sid, ref, *, now=NOW):
    """Drive ONE genuine segment (fresh session_id, curated door by ledger_ref) to its `done`
    emission through the real `_on_done` seam."""
    tag, _data = reg.start(sid, now=now)
    assert tag == "say"  # front door (curated doors embedded)
    idx = reg.menu_index(sid, ref)
    tag, _data = reg.step(sid, idx)
    assert tag == "say"  # scenario + invite
    tag, data = _drive(reg, sid)
    assert tag == "done"
    return data


@pytest.fixture
def world_registry(tmp_path, make_fake):
    """ONE genuine convergence (continuity_lock_in): the minimal slotted terrain+house fixture."""
    reg = SessionRegistry(
        str(tmp_path / "wreg.db"), model_factory=lambda: _agnostic(make_fake, "closed")
    )
    _land(reg, "s1", _CONTINUITY_REF)
    return reg, "s1"


@pytest.fixture
def world_registry_two_domains(tmp_path, make_fake):
    """P2/P3: domain A (continuity_lock_in alone — a permanent seed, 1 frame/1 problem) then
    domain B built across TWO landings (decision_under_stakes, then proof_before_promise — merged
    via the shared choose_the_failure_default_deliberately frame code into a 2-frame/2-problem
    region that CLEARS the render guard) so B outranks seed-A on the positional sort and the
    terrain reorders — while each house's SLOT stays frozen regardless."""
    reg = SessionRegistry(
        str(tmp_path / "w2d.db"), model_factory=lambda: _agnostic(make_fake, "closed")
    )
    _land(reg, "s1", _CONTINUITY_REF)
    first_rec = _landed_record(reg, "s1")
    _land(reg, "s2", _STAKES_REF)
    _land(reg, "s3", _PROOF_REF)  # merges into domain B, clears the guard -> reorder
    second_rec = _landed_record(reg, "s3")
    return reg, "s3", first_rec, second_rec


@pytest.fixture
def world_cross_domain(tmp_path, make_fake):
    """P1 (probe-verified recipe): continuity_lock_in -> decision_under_stakes ->
    irreversible_anchor. The third landing closes BOTH of irreversible_anchor's frames, merging
    the two prior slots into one: Confluence(from_slot=1, to_slot=0)."""
    reg = SessionRegistry(
        str(tmp_path / "wcd.db"), model_factory=lambda: _agnostic(make_fake, "closed")
    )
    _land(reg, "s1", _CONTINUITY_REF)
    _land(reg, "s2", _STAKES_REF)
    _land(reg, "s3", _ANCHOR)
    return reg, "s3", reg._store


@pytest.fixture
def world_with_deflection(tmp_path, make_fake):
    """P4: one real domain lands first (n_slots_before), then a SEPARATE segment whose pushes all
    deflect (frames seen, none closed) — no new registry rows, no confluence, and the deflected
    (houseless) components are absent from the frozen terrain."""
    reg = SessionRegistry(
        str(tmp_path / "wdef.db"), model_factory=lambda: _agnostic(make_fake, "closed")
    )
    _land(reg, "s1", _CONTINUITY_REF)
    n_slots_before = len(reg._store.domain_slots())
    reg._model_factory = lambda: _agnostic(make_fake, "unchanged")  # every push deflects
    _land(reg, "s2", _STAKES_REF)
    return reg, "s2", reg._store, n_slots_before


@pytest.fixture
def world_legacy_record(tmp_path, make_fake):
    """A prior record WITHOUT slots (pre-Phase-A freeze): a durable convergence + a persisted
    record whose house carries no "slot" key at all (the pre-freeze shape). The next genuine
    landing (adopting the SAME live sitting) must self-heal — stamp a slot on EVERY house,
    including this pre-existing one, from current components — and never crash on the missing
    key (D1/L-32)."""
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "wlegacy.db")
    store = SittingStore(db)
    sit = store.create_sitting(NOW)
    store.log_converged(sit, _CONTINUITY_REF, NOW, "continuity_lock_in", position="old call")
    store.write_state(
        sit,
        record={
            "experience_id": "continuity_lock_in",
            "ledger_ref": _CONTINUITY_REF,
            "posture": None,
            "recent": [],
            "stop_reason": "converged",
            "terrain": [{"region_id": "r0", "render": "seed", "vitality": None, "elevation": None}],
            "houses": [{"region": 0, "bucket": None}],  # no "slot" — pre-Phase-A shape
            "house_refs": [_CONTINUITY_REF],
            "house_at": [NOW.isoformat()],
        },
        now=NOW,
    )
    reg = SessionRegistry(db, model_factory=lambda: _agnostic(make_fake, "closed"))
    # The next genuine landing adopts the SAME live sitting (only one may be live) and engages the
    # SAME frame — self-healing both the pre-existing house's slot and the new one's, in one pass.
    _land(reg, "s1", _CONTINUITY_REF)
    return reg, "s1"


@pytest.fixture
def world_bulk_assignment(tmp_path, make_fake):
    """The founder's real-db day-one path (review SHOULD-FIX): two domains land BEFORE any
    registry (OR any per-house slot bookkeeping) exists — `web_domain_slot` wiped AND the
    persisted record's houses cleared (`write_state(record=None)`) after they land, so
    `latest_homebase()` (the copy-forward's prior source, per the follow-up review) has nothing
    to copy forward either — simulating a genuinely pre-Phase-A db. The first post-Phase-A
    landing then assigns ALL qualifying components in one pass, in the projection's positional
    order. The trigger segment (irreversible_anchor, deflected on both its already-existing
    frames) introduces no new component and converges nothing new — it only exercises the
    mechanics fresh over the two pre-existing, now-unslotted domains."""
    import sqlite3

    db = str(tmp_path / "wbulk.db")
    reg = SessionRegistry(db, model_factory=lambda: _agnostic(make_fake, "closed"))
    _land(reg, "s1", _CONTINUITY_REF)
    _land(reg, "s2", _STAKES_REF)
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM web_domain_slot")
    conn.commit()
    conn.close()
    sit = reg._store.live_sitting()["id"]
    reg._store.write_state(sit, record=None)  # no prior houses/slots to copy forward either
    reg._model_factory = lambda: _agnostic(make_fake, "unchanged")
    _land(reg, "s3", _ANCHOR)
    return reg, "s3", reg._store


def test_slots_appear_on_frozen_terrain_and_houses_after_a_landing(world_registry):
    reg, sid = world_registry  # fixture: drive one sitting to a genuine convergence
    rec = _landed_record(reg, sid)
    assert all(isinstance(r.get("slot"), int) for r in rec["terrain"])
    assert all("slot" in h for h in rec["houses"])
    # regions carry the standard keys PLUS slot — nothing else new
    assert set(rec["terrain"][0]) == {"region_id", "render", "vitality", "elevation", "slot"}


def test_slots_stable_under_vitality_shuffle_between_landings(world_registry_two_domains):
    # P2/P3: land in domain A, then land in domain B (B stronger -> positional sort DOES
    # reorder). The SLOT is the frozen field; region ordinal and bucket legitimately refresh
    # each landing (review MUST-FIX: byte-prefix equality fails a CORRECT implementation).
    reg, sid, first_rec, second_rec = world_registry_two_domains
    a_slot_first = first_rec["terrain"][0]["slot"]
    n = len(first_rec["houses"])
    assert [h["slot"] for h in second_rec["houses"][:n]] == [
        h["slot"] for h in first_rec["houses"]
    ]  # per-house slot copy-forward: frozen forever
    assert any(r["slot"] == a_slot_first for r in second_rec["terrain"])  # A's slot survives
    # And PROVE the shuffle happened (the regression has no teeth otherwise): A's positional
    # ordinal moved while its slot did not.
    a_row_second = [r for r in second_rec["terrain"] if r["slot"] == a_slot_first][0]
    assert second_rec["terrain"].index(a_row_second) != 0


def test_cross_domain_judgment_fires_confluence_and_retires_young_slot(world_cross_domain):
    # P1: two slotted domains, then one convergence engaging frames of both.
    reg, sid, store = world_cross_domain
    rec = _landed_record(reg, sid)
    assert rec["confluence"] == {"from_slot": 1, "to_slot": 0}
    rows = store.domain_slots()
    assert rows[1]["status"] == "confluent-into:0"
    # And the serialized record NEVER carries the event:
    from elenchus.web.session_runner import _serialize_record

    assert "confluence" not in (_serialize_record(rec) or {})
    # Per-house slot-at-arrival is frozen forever (Spec-2 §5): the confluence landing must not
    # overwrite a PRIOR house's slot with the merged component's current resolution — the
    # younger domain's house keeps its retired slot so the renderer can lay it out as its own
    # translated sub-cluster (review: copy-forward must source the PRIOR record from the store,
    # not from the fresh per-landing ch.record).
    slots = [h["slot"] for h in rec["houses"]]
    assert slots[0] == 0  # first landing's house: elder domain, frozen at arrival
    assert slots[1] == 1  # second landing's house: YOUNGER slot preserved post-confluence
    assert slots[2] == 0  # the confluence landing's new house: stamped elder


def test_deflected_push_claims_no_slot_and_fires_no_confluence(world_with_deflection):
    # P4: a sitting whose pushes deflect (frames seen, none closed) -> no new registry rows,
    # no confluence, and the deflected singleton is ABSENT from the frozen terrain.
    reg, sid, store, n_slots_before = world_with_deflection
    rec = _landed_record(reg, sid)
    assert len(store.domain_slots()) == n_slots_before
    assert "confluence" not in rec


def test_legacy_record_backfills_slots_at_next_landing(world_legacy_record):
    # A prior record WITHOUT slots (pre-Phase-A freeze): the next landing stamps every house
    # from current components (the D1/L-32 self-heal), never crashes on the missing keys.
    reg, sid = world_legacy_record
    rec = _landed_record(reg, sid)
    assert all("slot" in h for h in rec["houses"])


def test_bulk_first_assignment_on_a_multi_domain_db(world_bulk_assignment):
    # Several domains landed BEFORE any registry exists (state accreted pre-Phase-A); the
    # first post-Phase-A landing assigns ALL qualifying components in one pass, in the
    # projection's positional order, and freezes them.
    reg, sid, store = world_bulk_assignment
    rec = reg._last_record[sid]
    slots = [r["slot"] for r in rec["terrain"]]
    assert slots == sorted(slots) and len(store.domain_slots()) == len(slots)
    # Minor #3 (whole-branch review): the assertion that would have caught the MUST-FIX bug —
    # every house's slot must equal its OWN region's terrain slot, not some other component's.
    assert all(h["slot"] == rec["terrain"][h["region"]]["slot"] for h in rec["houses"])


@pytest.fixture
def world_deflected_before_new_house(tmp_path, make_fake):
    """MUST-FIX regression (whole-branch review, `probe_e2e_v2.py` recipe): deflect one problem
    in a first sitting — decision_under_stakes fully deflected (frames seen, none closed) yields
    TWO houseless empty-breadth singleton components (`choose_the_failure_default_deliberately`,
    `lead_with_what_you_refuse_to_do`) — then cleanly close a DIFFERENT problem in a second
    sitting: continuity_lock_in (`embed_credentials_as_a_list`) converges to a brand-new house
    (`i >= len(prior_refs)` -> the `else` branch). Alphabetically `choose_...` sorts before
    `embed_...`, so the houseless singleton sits at projection index 0 and the housed region at
    index 1; the seam filters index 0 (houseless), remapping the housed region to index 0. The
    buggy `else` branch read `res.slot_of_component[0]` — `choose`'s ORIGINAL slot (None, since it
    never claimed a domain) — instead of the housed region's own decorated terrain slot."""
    reg = SessionRegistry(
        str(tmp_path / "wdeflect_new.db"), model_factory=lambda: _agnostic(make_fake, "unchanged")
    )
    _land(reg, "s1", _STAKES_REF)  # deflected: two houseless singletons, no new house
    reg._model_factory = lambda: _agnostic(make_fake, "closed")
    _land(reg, "s2", _CONTINUITY_REF)  # cleanly converges -> a NEW house (else branch)
    return reg, "s2"


def test_house_slot_reads_the_filtered_terrain_row_not_the_original_index_component(
    world_deflected_before_new_house,
):
    # MUST-FIX (whole-branch review): a houseless component that sorts BEFORE a NEW housed
    # region gets filtered out of the frozen terrain, shifting the housed region's index. The
    # else branch must read the region's OWN decorated terrain slot at its remapped position,
    # never `res.slot_of_component` keyed by the ORIGINAL (pre-filter) projection index.
    reg, sid = world_deflected_before_new_house
    rec = _landed_record(reg, sid)
    assert len(rec["terrain"]) == 1  # both houseless singletons filtered out
    assert rec["terrain"][0]["slot"] == 0
    assert rec["houses"] == [{"region": 0, "bucket": None, "slot": 0}]
    # The general invariant the review names: every house's slot equals its own terrain row's slot.
    assert all(h["slot"] == rec["terrain"][h["region"]]["slot"] for h in rec["houses"])
