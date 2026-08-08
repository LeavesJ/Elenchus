from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .aim import aim, derive_core
from .content_loader import load_library
from .model import AnthropicModel
from .orchestration import run_session
from .persistence import Store
from .types import CorpusEntry, LedgerEntry, Regime

DEFAULT_DB = Path("data/elenchus.db")
_log = logging.getLogger(__name__)


def build_store(db_path: str | Path = DEFAULT_DB) -> Store:
    """Open the store, seeding an abstracted ledger + corpus row for any authored open_ended
    experience that has none, so the gated generator runs on a fresh DB. `elenchus-ingest`
    overwrites these placeholders with the real (confidential, gitignored) corpus.

    THE SEEDING IS NOW LOUD, and that is the point. This runs on every web worker start
    (`web/session_runner.py`), so it silently authored canonical-looking rows for any ref that
    lacked one -- which is exactly how a content or migration defect disguised itself as a healthy
    boot. Concretely: a `ledger_ref` split whose migration had not been run yet got placeholders
    on the new ref at boot, and the migration's `INSERT OR IGNORE` then became a permanent no-op
    reporting `corpus: 0`, byte-indistinguishable from a clean idempotent re-run. The migration now
    upgrades placeholders rather than skipping them, and every row authored here says so in the log.

    NOT YET SPLIT INTO read-at-boot / mutate-at-seed, which is the right end state: startup should
    validate and refuse, and only explicit migration or seed tooling should author canonical data.
    That is a behaviour change to first-run with a wide blast radius -- 30+ call sites, and every
    web test constructs a `SessionRegistry` over a fresh db -- so it belongs in its own change with
    its own sweep, not folded into a data-integrity repair. Logged loudly in the meantime, because
    an invisible mutation is the part that actually caused harm."""
    store = Store(db_path)
    existing_ledger = {e.id for e in store.load_ledger()}
    authored: list[str] = []
    for exp in load_library():
        if exp.regime is not Regime.open_ended:
            continue
        ref = exp.ledger_ref
        if ref not in existing_ledger:
            store.add_ledger_entry(
                LedgerEntry(id=ref, owned_problem=f"Abstracted seed for {exp.experience_id}.")
            )
            existing_ledger.add(ref)
            authored.append(f"ledger:{ref}")
        if store.get_corpus(ref) is None:
            authored.append(f"corpus:{ref}")
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
    if authored:
        _log.warning(
            "build_store authored %d placeholder row(s) at open: %s. A ref with no canonical row "
            "is a content or migration defect, not a healthy boot -- run the ingest or the "
            "relevant migration rather than leaving machine text as the owned-problem record.",
            len(authored),
            ", ".join(authored),
        )
    return store


def main(argv: list[str] | None = None) -> int:
    store = build_store()
    core = derive_core(aim())
    model = AnthropicModel()
    try:
        state, assessment = run_session(
            store, core, model, datetime.now(timezone.utc), regime=Regime.open_ended
        )
    except NotImplementedError:
        print(
            "Elenchus step-1 harness: the live Opus 5 adapter is not wired yet "
            "(deferred). The six-link loop is proven by the test suite — run `pytest`. "
            "Interactive runs arrive with the model adapter."
        )
        return 1
    from .types import CheckableAssessment

    if isinstance(assessment, CheckableAssessment):
        recalled = sum(1 for r in assessment.results if r.correct)
        print(f"concepts_scored={len(assessment.results)} recalled={recalled}")
    else:
        print(f"stop_reason={assessment.stop_reason.value} frames_total={len(state.frames)}")
    return 0
