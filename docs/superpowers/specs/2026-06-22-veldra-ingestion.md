# Veldra Ingestion (Step 2) — Design Spec

- **Date:** 2026-06-22
- **Status:** Approved (brainstorming). Inline TDD.
- **Sources:** Build Brief build-order step 2; Berkeley Operating Guidebook §6 (the problem ledger:
  10–20 owned problems written *as problems*); Blueprint (curated middle path — "model drafts, expert
  vets"; runtime never live-derives doctrine).

## 1. Goal
Generalize the single fixed experience into a **curated ledger of real Veldra owned-problems** plus a
**pointer corpus**, loaded idempotently into the (gitignored) SQLite store. Curated at build time and
vetted by the user; the runtime never re-mines Veldra.

## 2. Scope
**In:** a confidential seed file (`data/seed/veldra_ledger.yaml`, gitignored); `SeedEntry`/`CorpusEntry`
types; a `corpus` table in persistence (upsert/load); a `veldra_ingest` module (`load_seed`, idempotent
`ingest`, `main` entrypoint) + a `retnovation-ingest` console script.
**Out:** experience generation/selection across the ledger (Step 3); excerpt extraction (pointers only);
any automated live re-mining of Veldra.

## 3. Confidentiality (hard guardrail)
The ledger `owned_problem`s and the corpus are Veldra's deepest business/security frictions. They live
**only** in gitignored `data/` (the seed YAML + the SQLite db). They are never tracked, never placed in
`content/`. Tracked code contains **no** confidential friction text. Tests use synthetic temp seeds
(`tmp_path`), never the real seed.

## 4. Data shapes
- `SeedEntry`: `slug`, `domain` (`founder_ceo`|`cs_technical`), `owned_problem`, `why_owned`,
  `unlabeled`, `provenance`, `corpus_pointers: list[str]`.
- `ledger_ref = f"veldra:{slug}"`.
- `LedgerEntry` (existing): `id=ledger_ref`, `owned_problem`, `links_to_experiences=[]`.
- `CorpusEntry` (new, in `types.py`): `ledger_ref`, `domain`, `why_owned`, `unlabeled`, `provenance`,
  `corpus_pointers: list[str]`.

## 5. Persistence (`persistence.py`)
New `corpus` table: `ledger_ref PK, domain, why_owned, unlabeled, provenance, corpus_pointers_json`.
- `upsert_corpus(entry: CorpusEntry) -> None` (UPSERT)
- `load_corpus() -> list[CorpusEntry]`
- `get_corpus(ledger_ref: str) -> CorpusEntry | None`

## 6. Ingestion (`src/retnovation/veldra_ingest.py`)
- `DEFAULT_SEED = Path("data/seed/veldra_ledger.yaml")`
- `load_seed(path) -> list[SeedEntry]` — parse the YAML list of entries.
- `ingest(store, seeds) -> int` — for each: `store.add_ledger_entry(LedgerEntry(id=ledger_ref,
  owned_problem=..., links_to_experiences=[]))` + `store.upsert_corpus(CorpusEntry(...))`. **Idempotent**
  (upserts; re-running yields the same row counts, no duplicates). Returns the number ingested.
- `main(argv=None) -> int` — load `DEFAULT_SEED`, ingest into `data/retnovation.db`, print a summary
  (counts by domain). Wired as console script `retnovation-ingest`.

## 7. How it generalizes the fixed experience
Before: one hardcoded `veldra:licensing_continuity` ledger entry. After: the ledger holds these real
owned problems, and the corpus carries each one's framing + provenance for the scheduler (and the Step-3
generator) to draw on. `experience.select_experience` still returns the fixed experience for now;
broadening selection across the ledger is Step 3.

## 8. Acceptance
- `corpus` CRUD round-trips; re-`upsert` of the same `ledger_ref` does not duplicate.
- `load_seed` parses a temp YAML into `SeedEntry`s.
- `ingest` over 14 entries seeds 14 ledger + 14 corpus rows; **re-running keeps it at 14** (idempotent).
- Full suite green; ruff clean.
- Post-merge (in main): the real `data/seed/veldra_ledger.yaml` (14, gitignored) ingests into
  `data/retnovation.db`; `git ls-files` shows **no** seed file, db, or confidential text.

## 9. Guardrails
- Confidential ledger/corpus only in gitignored `data/`.
- Curated at build time; no runtime live derivation from Veldra.
- Idempotent ingestion (safe to re-run as the curated seed evolves).
