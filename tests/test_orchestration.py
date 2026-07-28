from datetime import datetime, timezone

from elenchus.aim import aim, derive_core
from elenchus.orchestration import run_session
from elenchus.persistence import Store
from elenchus.model import FakeModel, IntakeClassification, ResponseClassification
from elenchus.types import (
    CorpusEntry,
    FrameState,
    LedgerEntry,
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
            "commit_under_the_deadline": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )

    def closed():  # brief uses lambda; def keeps ruff happy with identical semantics
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
    # Steer to license_continuity specifically. SP3 added continuity_lock_in on the same ledger_ref,
    # so the deduped problem_menu serves the single-frame isolate; license_continuity is still in the
    # full candidate list — steer by experience_id over proposal.candidates (L-14 re-steer).
    from elenchus.types import Outcome, Selection

    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.candidates:
        if spec.experience_id == "license_continuity":
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(
                proposed_receipt=top_receipt,
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=outcome,
            )
    raise AssertionError("license_continuity not in the proposal")


def test_run_session_closes_one_cycle(tmp_path):
    store = Store(tmp_path / "t.db")
    for ref in (
        "veldra:license_fork_risk",
        "veldra:concentrated_market_pricing_power",
        "veldra:first_customer_proof_loop",
    ):
        store.add_ledger_entry(LedgerEntry(id=ref, owned_problem="..."))
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain="founder_ceo",
                why_owned="stakes",
                unlabeled="unlabeled",
                provenance="synthetic-test",
                corpus_pointers=[],
            )
        )
    core = derive_core(aim())

    def fixture(exp):
        return Work(opening="my reasoning", respond=lambda push: "reply")  # noqa: E731

    state, assessment = run_session(
        store,
        core,
        _fake_model(),
        _now(),
        present=fixture,
        decide=_to_license,
        decide_core=lambda c: [],
    )
    assert assessment.trajectory and state.frames
    assert any("license_continuity" in fs.last_evidence for fs in state.frames.values())
    rows = list(store._db.execute("SELECT * FROM selection_log"))
    assert len(rows) == 1 and rows[0]["chosen_problem"] == "veldra:license_fork_risk"
    assert store.queue_len() == 0  # open_ended path does not queue


def test_run_session_logs_selection_receipt(tmp_path):
    store = Store(tmp_path / "t2.db")
    for ref in (
        "veldra:license_fork_risk",
        "veldra:concentrated_market_pricing_power",
        "veldra:first_customer_proof_loop",
    ):
        store.add_ledger_entry(LedgerEntry(id=ref, owned_problem="..."))
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain="founder_ceo",
                why_owned="stakes",
                unlabeled="unlabeled",
                provenance="synthetic-test",
                corpus_pointers=[],
            )
        )
    core = derive_core(aim())

    def fixture(exp):
        return Work(opening="my reasoning", respond=lambda push: "reply")  # noqa: E731

    run_session(
        store,
        core,
        _fake_model(),
        _now(),
        present=fixture,
        decide=_to_license,
        decide_core=lambda c: [],
    )
    rows = list(store._db.execute("SELECT * FROM selection_log"))
    assert len(rows) == 1
    assert rows[0]["chosen_experience_id"] == "license_continuity"
    assert rows[0]["outcome"] in ("accepted", "redirected")


def test_decide_cli_accept_and_redirect(monkeypatch):
    from elenchus.orchestration import decide_cli
    from elenchus.types import (
        NextExperienceSpec,
        Outcome,
        Proposal,
        Regime,
        SelectionReceipt,
    )

    now = _now()

    def cand(ref, eid):
        spec = NextExperienceSpec(
            target_frames=["f"], ledger_ref=ref, regime=Regime.open_ended, experience_id=eid
        )
        rc = SelectionReceipt(
            frame="f",
            problem=ref,
            experience_id=eid,
            drive="diagnose",
            scores={"V": 0.5},
            runner_up_drive=None,
            margin=0.0,
            content_gaps=[],
            created_at=now,
        )
        return (spec, rc)

    prop = Proposal(candidates=[cand("veldra:p1", "e1"), cand("veldra:p2", "e2")])

    monkeypatch.setattr("builtins.input", lambda *_: "")  # accept
    sel = decide_cli(prop)
    assert sel.outcome is Outcome.accepted and sel.chosen_spec.experience_id == "e1"

    monkeypatch.setattr("builtins.input", lambda *_: "2")  # redirect to problem 2
    sel2 = decide_cli(prop)
    assert sel2.outcome is Outcome.redirected and sel2.chosen_spec.ledger_ref == "veldra:p2"
