"""The dock's moored vessels = genuinely-owned ledger rows ONLY (Spec-2 §6, D-S2-4):
corpus provenance != 'seed', non-gen refs, clamp 20. Empty harbor is true by predicate."""

from elenchus.cli import build_store
from elenchus.persistence import Store
from elenchus.types import CorpusEntry, LedgerEntry
from elenchus.web.vessels import vessel_count


def test_fresh_worker_seeded_db_has_an_empty_harbor(tmp_path):
    db = str(tmp_path / "r.db")
    build_store(db)  # the worker-start seeding (cli.py:16-42): provenance='seed' placeholders
    assert vessel_count(db) == 0


def test_owned_rows_count_and_gen_rows_do_not(tmp_path):
    db = str(tmp_path / "r.db")
    store = Store(db)
    store.add_ledger_entry(LedgerEntry(id="veldra:x", owned_problem="a real owned problem"))
    store.upsert_corpus(
        CorpusEntry(
            ledger_ref="veldra:x",
            domain="founder_ceo",
            why_owned="real",
            unlabeled="real",
            provenance="veldra_execlog",
            corpus_pointers=[],
        )
    )
    store.add_ledger_entry(LedgerEntry(id="gen:web-123", owned_problem="a typed situation"))
    store.close()
    assert vessel_count(db) == 1


def test_count_clamps_at_twenty(tmp_path):
    db = str(tmp_path / "r.db")
    store = Store(db)
    for i in range(25):
        ref = f"veldra:p{i}"
        store.add_ledger_entry(LedgerEntry(id=ref, owned_problem="p"))
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain="founder_ceo",
                why_owned="r",
                unlabeled="r",
                provenance="veldra_execlog",
                corpus_pointers=[],
            )
        )
    store.close()
    assert vessel_count(db) == 20
