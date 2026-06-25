"""CS checkable dry run: the six links close end-to-end for the cs_technical regime,
proving a second regime runs through the same plumbing (deterministic, model-free)."""

from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.model import FakeModel, IntakeClassification
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.types import CheckableAssessment, NextExperienceSpec, Regime, Work


def _now():
    return datetime(2026, 6, 23, tzinfo=timezone.utc)


def _model_unused():
    # deterministic CS questions never call the model; supply an inert one
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})


def test_cs_dry_run_closes_the_loop(tmp_path):
    store = Store(tmp_path / "cs.db")
    # target the all-deterministic experience's concepts so it is selected, model-free
    store.queue_push(
        NextExperienceSpec(
            target_frames=["safety_vs_liveness", "idempotency_under_retry", "quorum_intersection"],
            ledger_ref="veldra:consensus_correctness",
            regime=Regime.cs_technical,
        )
    )
    core = derive_core(aim("cs_systems"))

    def fixture(exp):
        # answer each question correctly via its first answer_key entry, in order
        answers = iter(q.answer_key[0] for q in exp.checkable.questions)
        return Work(opening="", respond=lambda push: next(answers, ""))  # noqa: E731

    state, assessment = run_session(store, core, _model_unused(), _now(), present=fixture)

    # 1) the checkable scorer ran every question, all correct
    assert isinstance(assessment, CheckableAssessment)
    assert assessment.results and all(r.correct for r in assessment.results)
    # 2) the concept spaced-index moved and persisted
    reloaded = Store(tmp_path / "cs.db").load_state(_now())
    assert "safety_vs_liveness" in reloaded.declarative_seed
    assert reloaded.declarative_seed["safety_vs_liveness"].interval_days >= 1
    # 3) a fresh cs_technical next experience is queued (cadence closed the loop)
    nxt = Store(tmp_path / "cs.db").queue_pop()
    assert nxt is not None and nxt.regime is Regime.cs_technical
