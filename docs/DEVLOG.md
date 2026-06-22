# Retnovation — DEVLOG

## 2026-06-22 — Repo init
- Created the **separate** Retnovation git repo at `~/Documents/Retnovation` (Python, src
  layout, branch `main`). The home dir is an inert git repo (0 tracked files, no remote);
  Retnovation is its own nested repo, and the confidential design docs are gitignored and
  untracked anywhere.
- Ported lean session hygiene from Veldra: `.claude/CLAUDE.md` (Felix protocol, module
  boundaries, doctrine-as-data, commit rules), `docs/lessons.md` (checklists + seeded
  principles L-1..L-6), this DEVLOG.
- Approved stack decisions: Python + SQLite (runtime state/ledger/queue); curated maps +
  curator rubrics as versioned YAML in `content/`; lean hygiene.
- Read doctrine source: Berkeley Operating Guidebook §5 (retention: reversible decay, not
  erasure) and §6 (innovation bridge: the ledger of owned, unlabeled problems).
- Next: commit the approved harness design as a spec; produce the Step-1 implementation
  plan (writing-plans); execute Step 1 (six-link harness on the fixed experience) under TDD.
