"""Vessels = the ledger's genuinely-owned problems, projected as a bare count (Spec-2 §6).

Predicate (D-S2-4): corpus provenance != 'seed' (cli.build_store placeholders excluded — any
non-'seed' provenance counts; veldra_ingest passes the seed file's provenance through,
veldra_ingest.py:42-59) AND non-`gen:` ref (forged-world rows excluded for MVP — promoting one is
Spec 3's moor gesture). Reads a raw Store (schema-only init) — NEVER cli.build_store, whose side
effect is the seeding that would break empty=empty. Clamp 20 (doctrine's 10-20 bound as a
projection cap). L-13: the count is user-authored inventory cardinality; nothing per-entry ever
leaves this module.
"""

from __future__ import annotations

from ..persistence import Store

_CAP = 20


def vessel_count(db_path: str) -> int:
    store = Store(db_path)
    try:
        n = 0
        for entry in store.load_ledger():
            if entry.id.startswith("gen:"):
                continue
            corpus = store.get_corpus(entry.id)
            if corpus is None or corpus.provenance == "seed":
                continue
            n += 1
        return min(n, _CAP)
    finally:
        store.close()  # never leak a connection on the production landing path
