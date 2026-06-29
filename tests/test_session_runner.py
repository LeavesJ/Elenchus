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


def test_start_emits_error_on_worker_failure(tmp_path, make_fake):
    # tmp_path is a directory -> build_store's sqlite connect raises inside the worker
    # -> error emission (no hang); verifies the "exception inside worker → error, never hang" guarantee
    reg = SessionRegistry(str(tmp_path), model_factory=make_fake)
    tag, data = reg.start("s_err", now=NOW)
    assert tag == "error" and "message" in data


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
    # same inputs via the runner's queue bridge
    reg = SessionRegistry(str(tmp_path / "b.db"), model_factory=make_fake)
    tag, _ = reg.start("s1", now=NOW)
    assert tag == "menu"
    # choose irreversible_anchor by ledger_ref
    menu_idx = reg.menu_index("s1", "veldra:embedded_anchor_lock_in")
    tag, _ = reg.step("s1", menu_idx)
    assert tag == "problem"
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "push":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    runner_assess = data["assessment"]
    assert (
        runner_assess.model_dump() == direct_assess.model_dump()
    )  # byte-identical -> bridge transparent


def test_step_after_done_returns_error_and_does_not_hang(tmp_path, make_fake):
    """Terminal-state guard: step after 'done' must short-circuit, never put to the dead worker."""
    reg = SessionRegistry(str(tmp_path / "c.db"), model_factory=make_fake)
    tag, _ = reg.start("s_term", now=NOW)
    assert tag == "menu"
    menu_idx = reg.menu_index("s_term", "veldra:embedded_anchor_lock_in")
    tag, _ = reg.step("s_term", menu_idx)
    assert tag == "problem"
    tag, data = reg.step("s_term", "reasoning that already holds the move")
    while tag == "push":
        tag, data = reg.step("s_term", "mechanism")
    assert tag == "done"

    # Session is now terminal — further step must return error immediately, not hang.
    tag2, data2 = reg.step("s_term", "anything")
    assert tag2 == "error"
    assert "message" in data2


class _EchoFidelityModel(FakeModel):
    """Substantive entry; echo_push PREFIXES so the displayed push differs from the canonical one."""

    def classify_entry(self, prompt, opening, recent):
        return EntryClassification(entry_class=EntryClass.substantive, reply="")

    def echo_push(self, push_text, recent):
        return "ECHO::" + push_text


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
    return _EchoFidelityModel(intake, {"choose_the_failure_default_deliberately": closed})


def test_engine_records_canonical_push_not_echo(tmp_path):
    """Echo is display-only: the trajectory the engine records (and grades / reads for the
    unprompted signal) must be the canonical generate_push output, never the Echo re-skin."""
    reg = SessionRegistry(str(tmp_path / "f.db"), model_factory=_fid_factory)
    tag, _ = reg.start("sf", now=NOW)
    menu_idx = reg.menu_index("sf", "veldra:embedded_anchor_lock_in")
    reg.step("sf", menu_idx)
    tag, data = reg.step("sf", "reasoning that already holds the move")
    while tag == "push":
        assert data["text"].startswith("ECHO::")  # the user SEES the echo
        tag, data = reg.step("sf", "mechanism")
    assert tag == "done"
    for push in data["assessment"].trajectory:
        assert not push.text.startswith("ECHO::")  # the engine RECORDS the canonical push
        assert push.text == "[push:frame]"  # FakeModel.generate_push canonical output
