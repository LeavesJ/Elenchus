# Retnovation

A retention-and-deployment engine — a thin doctrine layer over a rented model
(Claude Opus 4.8). Not a tutor: it owns every encounter *after* you first meet the
material and makes the knowledge stay, and stay usable. **Rent capability, gate doctrine.**

Single-user dogfood MVP across two domains — Founder CEO (open-ended) and CS technical
(checkable) — exercising both assessment regimes through one pluggable interface.

## Status
Build-order step 1: standing up the six-link harness
(`aim → core → experience → assessment → state → cadence`) on a fixed experience.
Done = the dry run closes end-to-end with no manual stitching. See `docs/superpowers/specs/`.

## Layout
- `src/retnovation/` — engine (orchestration, assessment, state, scheduler, persistence, types)
- `content/` — curated maps + curator rubrics (versioned doctrine-as-data; not code)
- `docs/` — lessons, DEVLOG, specs, plans
- `data/` — runtime SQLite (gitignored; holds ledger + learner state)

## Develop
    python3 -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]" --config-settings editable_mode=compat
    pytest

(The `editable_mode=compat` flag installs a plain `src`-on-path editable so newly added
modules/subpackages import without a reinstall — robust on Python 3.14. Tests also run
without any install via `tests/conftest.py`.)
