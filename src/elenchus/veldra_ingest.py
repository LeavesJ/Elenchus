"""Curated ingestion of real Veldra owned-problems into the (gitignored) store.

Curated at build time and vetted by the user; the runtime never re-mines Veldra. The seed and
the resulting ledger/corpus are confidential and live only under gitignored ``data/``.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .persistence import Store
from .types import CorpusEntry, LedgerEntry, Scene

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED = _REPO_ROOT / "data" / "seed" / "veldra_ledger.yaml"
DEFAULT_DB = _REPO_ROOT / "data" / "elenchus.db"


class SeedEntry(BaseModel):
    slug: str
    domain: str
    owned_problem: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)
    scene: Scene | None = None


def ledger_ref(slug: str) -> str:
    return f"veldra:{slug}"


def load_seed(path: str | Path) -> list[SeedEntry]:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, list):
        raise ValueError(f"seed file must be a YAML list, got {type(data).__name__}: {path}")
    return [SeedEntry(**e) for e in data]


def ingest(store: Store, seeds: list[SeedEntry]) -> int:
    """Upsert each seed into the ledger + corpus. Idempotent: re-running does not duplicate."""
    for s in seeds:
        ref = ledger_ref(s.slug)
        store.add_ledger_entry(
            LedgerEntry(id=ref, owned_problem=s.owned_problem, links_to_experiences=[])
        )
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain=s.domain,
                why_owned=s.why_owned,
                unlabeled=s.unlabeled,
                provenance=s.provenance,
                corpus_pointers=s.corpus_pointers,
                scene=s.scene,
            )
        )
    return len(seeds)


def main(argv: list[str] | None = None) -> int:
    store = Store(DEFAULT_DB)
    seeds = load_seed(DEFAULT_SEED)
    n = ingest(store, seeds)
    by_domain: dict[str, int] = {}
    for s in seeds:
        by_domain[s.domain] = by_domain.get(s.domain, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_domain.items()))
    print(f"ingested {n} ledger entries ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
