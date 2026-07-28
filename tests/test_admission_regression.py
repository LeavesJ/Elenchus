"""SP2 admit regression: the provisional spine frame `embed_credentials_as_a_list` is reachable
through the REAL gated path (build_store -> propose -> select -> assess -> persist), not just a
synthetic fixture (L-8/L-9). Selection is STEERED to the admitted experience, never accepted from
proposal.top (L-14: a multi-frame rubric can rank below others and serve a different experience whose
codes the FakeModel does not script -> KeyError)."""

from datetime import datetime, timezone

from elenchus.aim import aim, derive_core
from elenchus.cli import build_store
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
from elenchus.orchestration import run_session
from elenchus.persistence import Store
from elenchus.types import (
    FrameState,
    Outcome,
    Regime,
    Selection,
    Strength,
    TrapState,
    Work,
)

LEDGER_REF = "veldra:embedded_anchor_lock_in"
FRAMES = ("embed_credentials_as_a_list", "choose_the_failure_default_deliberately")
TRAPS = ("deferred_the_one_time_choice", "assumed_the_happy_path")


def _now():
    return datetime(2026, 6, 26, tzinfo=timezone.utc)


def _cooperative_model():
    intake = IntakeClassification(
        frame_states={f: FrameState.absent for f in FRAMES},
        trap_states={t: TrapState.not_tripped for t in TRAPS},
    )

    def closed():
        return [
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            for _ in range(3)
        ]

    return FakeModel(intake, {f: closed() for f in FRAMES})


def _to_anchor(proposal):
    # L-14: steer to the admitted experience by its owned problem; never accept proposal.top blindly.
    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.problem_menu():
        if spec.ledger_ref == LEDGER_REF:
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(
                proposed_receipt=top_receipt,
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=outcome,
            )
    raise AssertionError(f"{LEDGER_REF} not in the proposal menu")


def test_admitted_frame_is_reachable_through_the_gated_path(tmp_path):
    store = build_store(tmp_path / "admit.db")  # auto-seeds the whole open_ended library (L-8)
    core = derive_core(aim())
    replies = iter(
        [
            "I will not ship the one-shot value; here is the mechanism that keeps the option open...",
            "and here is which way it fails if that value ever has to change...",
        ]
    )

    def present(exp):
        return Work(
            opening="my opening reasoning on the anchor I cannot change after shipping",
            respond=lambda push: next(replies, "..."),
        )

    state, assessment = run_session(
        store,
        core,
        _cooperative_model(),
        _now(),
        regime=Regime.open_ended,
        present=present,
        decide=_to_anchor,
        decide_core=lambda c: [],
    )

    # the admitted frame was exercised through the real loop (produces a frame delta)...
    assert any(d.code == "embed_credentials_as_a_list" for d in assessment.frame_deltas)
    # ...and persisted to a non-weak strength on reload (the production select->assess->persist path).
    reloaded = Store(tmp_path / "admit.db").load_state(_now())
    assert "embed_credentials_as_a_list" in reloaded.frames
    assert reloaded.frames["embed_credentials_as_a_list"].strength != Strength.weak
