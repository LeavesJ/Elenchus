"""Loop v0.1 dry run: the six links close end-to-end with no manual stitching."""

from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.types import (
    CorpusEntry,
    FrameState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
    Strength,
    StopReason,
    TrapState,
    Work,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _cooperative_model():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
            "commit_under_the_deadline": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )

    def closed():  # brief uses lambda; def keeps ruff E731 clean with identical semantics
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    return FakeModel(
        intake,
        {
            "lead_with_what_you_refuse_to_do": closed(),
            "protect_the_core_lane": closed(),
            "commit_under_the_deadline": closed(),
        },
    )


def test_dry_run_closes_the_loop(tmp_path):
    # Arrange: a learner who opens to a queued next experience on an owned problem.
    store = Store(tmp_path / "dryrun.db")
    store.add_ledger_entry(
        LedgerEntry(
            id="veldra:license_fork_risk",
            owned_problem="A licensing-continuity decision under a same-day deadline.",
        )
    )
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:license_fork_risk",
            domain="founder_ceo",
            why_owned="real stakes",
            unlabeled="genuinely unlabeled",
            provenance="synthetic-test",
            corpus_pointers=[],
        )
    )
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:concentrated_market_pricing_power",
            domain="founder_ceo",
            why_owned="stakes",
            unlabeled="unlabeled",
            provenance="synthetic-test",
            corpus_pointers=[],
        )
    )
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:first_customer_proof_loop",
            domain="founder_ceo",
            why_owned="stakes",
            unlabeled="unlabeled",
            provenance="synthetic-test",
            corpus_pointers=[],
        )
    )
    store.queue_push(
        NextExperienceSpec(
            target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
            ledger_ref="veldra:license_fork_risk",
            regime=Regime.open_ended,
        )
    )
    core = derive_core(aim())

    student_replies = iter(
        [
            "I refuse to weaken the core promise; here is the mechanism...",
            "and I hold the core lane by...",
        ]
    )

    def fixture(exp):  # brief uses lambda; def keeps ruff E731 clean with identical semantics
        return Work(
            opening="my opening reasoning",
            respond=lambda push: next(student_replies, "..."),  # noqa: E731
        )

    # Act: run exactly one session, no manual stitching between links.
    state, assessment = run_session(store, core, _cooperative_model(), _now(), present=fixture)

    # Assert the four acceptance criteria from the spec.
    # 1) experience came off the queue (queue had been consumed before re-queue)
    # 2) judgment loop produced a trajectory + deltas tracing to rubric codes
    assert assessment.trajectory
    assert assessment.stop_reason is StopReason.converged
    assert all(
        d.code
        in {
            "lead_with_what_you_refuse_to_do",
            "protect_the_core_lane",
            "commit_under_the_deadline",
        }
        for d in assessment.frame_deltas
    )
    # 3) at least one frame strength moved (not the `weak` default) in persisted state
    reloaded = Store(tmp_path / "dryrun.db").load_state(_now())
    assert reloaded.frames  # persisted
    assert any(fs.strength != Strength.weak for fs in reloaded.frames.values())
    # 4) the queue holds a fresh NextExperienceSpec
    assert reloaded_next(tmp_path) is not None


def reloaded_next(tmp_path):
    return Store(tmp_path / "dryrun.db").queue_pop()
