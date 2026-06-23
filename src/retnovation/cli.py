from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .aim import aim, derive_core
from .content_loader import load_library
from .model import AnthropicModel
from .orchestration import run_session
from .persistence import Store
from .types import CorpusEntry, LedgerEntry, NextExperienceSpec, Regime

DEFAULT_DB = Path("data/retnovation.db")
_SEED_REF = "veldra:license_fork_risk"


def build_store(db_path: str | Path = DEFAULT_DB) -> Store:
    store = Store(db_path)
    # Seed an abstracted ledger + corpus entry for every authored open_ended experience so the
    # gated generator runs on a fresh DB. `retnovation-ingest` overwrites these placeholders with
    # the real (confidential, gitignored) corpus when run.
    existing_ledger = {e.id for e in store.load_ledger()}
    for exp in load_library():
        if exp.regime is not Regime.open_ended:
            continue
        ref = exp.ledger_ref
        if ref not in existing_ledger:
            store.add_ledger_entry(
                LedgerEntry(id=ref, owned_problem=f"Abstracted seed for {exp.experience_id}.")
            )
            existing_ledger.add(ref)
        if store.get_corpus(ref) is None:
            store.upsert_corpus(
                CorpusEntry(
                    ledger_ref=ref,
                    domain="founder_ceo",
                    why_owned="seed stakes (abstracted)",
                    unlabeled="genuinely unlabeled (abstracted seed)",
                    provenance="seed",
                    corpus_pointers=[],
                )
            )
    if store.queue_len() == 0:
        store.queue_push(
            NextExperienceSpec(
                target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
                ledger_ref=_SEED_REF,
                regime=Regime.open_ended,
            )
        )
    return store


def main(argv: list[str] | None = None) -> int:
    store = build_store()
    core = derive_core(aim())
    model = AnthropicModel()
    try:
        state, assessment = run_session(store, core, model, datetime.now(timezone.utc))
    except NotImplementedError:
        print(
            "Retnovation step-1 harness: the live Opus 4.8 adapter is not wired yet "
            "(deferred). The six-link loop is proven by the test suite — run `pytest`. "
            "Interactive runs arrive with the model adapter."
        )
        return 1
    print(f"stop_reason={assessment.stop_reason.value} frames_total={len(state.frames)}")
    return 0
