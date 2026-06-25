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


def _to_license(proposal):
    from retnovation.types import Outcome, Selection

    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.problem_menu():
        if spec.ledger_ref == "veldra:license_fork_risk":
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(
                proposed_receipt=top_receipt,
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=outcome,
            )
    raise AssertionError("license_fork_risk not in the proposal")


def test_dry_run_closes_the_loop(tmp_path):
    store = Store(tmp_path / "dryrun.db")
    store.add_ledger_entry(
        LedgerEntry(
            id="veldra:license_fork_risk",
            owned_problem="A licensing-continuity decision under a same-day deadline.",
        )
    )
    for ref in (
        "veldra:license_fork_risk",
        "veldra:concentrated_market_pricing_power",
        "veldra:first_customer_proof_loop",
    ):
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain="founder_ceo",
                why_owned="real stakes",
                unlabeled="genuinely unlabeled",
                provenance="synthetic-test",
                corpus_pointers=[],
            )
        )
    core = derive_core(aim())
    student_replies = iter(
        [
            "I refuse to weaken the core promise; here is the mechanism...",
            "and I hold the core lane by...",
        ]
    )

    def fixture(exp):
        return Work(
            opening="my opening reasoning", respond=lambda push: next(student_replies, "...")
        )  # noqa: E731

    state, assessment = run_session(
        store,
        core,
        _cooperative_model(),
        _now(),
        present=fixture,
        decide=_to_license,
        decide_core=lambda c: [],
    )
    assert assessment.trajectory
    assert assessment.stop_reason is StopReason.converged
    assert all(
        d.code
        in {"lead_with_what_you_refuse_to_do", "protect_the_core_lane", "commit_under_the_deadline"}
        for d in assessment.frame_deltas
    )
    reloaded = Store(tmp_path / "dryrun.db").load_state(_now())
    assert reloaded.frames
    assert any(fs.strength != Strength.weak for fs in reloaded.frames.values())
