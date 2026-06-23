import pytest

from retnovation.aim import aim, derive_core
from retnovation.experience import SELECTORS, select_experience
from retnovation.persistence import Store
from retnovation.types import CorpusEntry, LearnerState, NextExperienceSpec, Regime

SEED_REFS = (
    "veldra:license_fork_risk",
    "veldra:concentrated_market_pricing_power",
    "veldra:first_customer_proof_loop",
)


def _seed_corpus(store: Store):
    """Synthetic (non-confidential) corpus covering every authored seed's ledger_ref."""
    for ref in SEED_REFS:
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


def test_selectors_registry_routes_by_regime():
    assert Regime.open_ended in SELECTORS and Regime.cs_technical in SELECTORS


def test_select_experience_dispatches_open_ended_and_gates(tmp_path):
    store = Store(tmp_path / "e.db")
    _seed_corpus(store)
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp.regime is Regime.open_ended
    assert exp.experience_id and exp.ledger_ref.startswith("veldra:")
    assert any(f.frame_code == "protect_the_core_lane" for f in exp.rubric.frames)


def test_select_experience_cs_technical_is_stubbed(tmp_path):
    store = Store(tmp_path / "e2.db")
    _seed_corpus(store)
    spec = NextExperienceSpec(target_frames=[], ledger_ref="", regime=Regime.cs_technical)
    with pytest.raises(NotImplementedError):
        select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)


def test_fixed_experience_is_retired():
    import retnovation.experience as experience_mod

    assert not hasattr(experience_mod, "FIXED_EXPERIENCE")
