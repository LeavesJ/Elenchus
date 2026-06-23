from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import (
    CorpusEntry,
    FrameState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
    TrapState,
    Work,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _fake_model():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():  # brief uses lambda; def keeps ruff happy with identical semantics
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    return FakeModel(
        intake, {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()}
    )


def test_run_session_closes_one_cycle(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_ledger_entry(LedgerEntry(id="veldra:license_fork_risk", owned_problem="..."))
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:license_fork_risk",
            domain="founder_ceo",
            why_owned="stakes",
            unlabeled="unlabeled",
            provenance="synthetic-test",
            corpus_pointers=[],
        )
    )
    store.queue_push(
        NextExperienceSpec(
            target_frames=["protect_the_core_lane"],
            ledger_ref="veldra:license_fork_risk",
            regime=Regime.open_ended,
        )
    )
    core = derive_core(aim())

    def fixture(exp):  # brief uses lambda; def keeps ruff happy with identical semantics
        return Work(opening="my reasoning", respond=lambda push: "reply")  # noqa: E731

    state, assessment = run_session(store, core, _fake_model(), _now(), present=fixture)
    assert assessment.trajectory  # something happened
    assert state.frames  # state moved
    assert store.queue_pop() is not None  # a fresh next was queued
    assert any("license_continuity" in fs.last_evidence for fs in state.frames.values())
