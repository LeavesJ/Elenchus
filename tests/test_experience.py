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


def test_select_experience_dispatches_cs_technical(tmp_path):
    from retnovation.types import Core

    spec = NextExperienceSpec(
        target_frames=["safety_vs_liveness"], ledger_ref="", regime=Regime.cs_technical
    )
    core = Core(
        process_frames=[],
        declarative_seed=["safety_vs_liveness"],
        content_core=["safety_vs_liveness"],
    )
    exp = select_experience(core, LearnerState(), [], [], spec)
    assert exp.regime is Regime.cs_technical
    assert exp.checkable is not None and exp.rubric is None


def test_fixed_experience_is_retired():
    import retnovation.experience as experience_mod

    assert not hasattr(experience_mod, "FIXED_EXPERIENCE")


def test_select_experience_attaches_a_corpus_scene_and_overrides_prompt(tmp_path):
    from retnovation.types import CorpusEntry, NextExperienceSpec, Regime, Scene

    store = Store(tmp_path / "sc.db")
    _seed_corpus(store)
    # attach a clean scene to the founder experience that will be selected
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    ref = exp.ledger_ref
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref=ref,
            domain="founder_ceo",
            why_owned="real stakes",
            unlabeled="genuinely unlabeled",
            provenance="synthetic-test",
            corpus_pointers=[],
            scene=Scene(
                prompt="A same-day call forces a real trade-off.",
                situation="A long client mid-rollout; a guarantee under pressure.",
            ),
        )
    )
    exp2 = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp2.prompt == "A same-day call forces a real trade-off."  # concrete override
    assert exp2.scene is not None and "mid-rollout" in exp2.scene.situation


def test_select_experience_without_a_scene_is_unchanged(tmp_path):
    from retnovation.types import NextExperienceSpec, Regime

    store = Store(tmp_path / "ns.db")
    _seed_corpus(store)  # corpus has no scenes
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp.scene is None
    assert exp.prompt  # the abstract content prompt, unchanged
