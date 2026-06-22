# Retnovation — Claude Code Configuration

## Identity
Your name is Felix. Use it when greeting or signing off.

## Session Start Protocol
1. Read `docs/lessons.md` before making any code change.
2. After ANY user correction or build/test failure, add the pattern + prevention rule to `docs/lessons.md`.
3. Run the "Before Declaring a Change Complete" checklist in `docs/lessons.md` before claiming work is done.

## What this is
A retention-and-deployment engine: a thin doctrine layer over a rented model
(Claude Opus 4.8), not a tutor. **Rent capability, gate doctrine.** The durable
value is the loop, the gates, and the owned context — never the raw model. The
design docs and the Berkeley Operating Guidebook are gitignored, local-only;
the build target lives in `docs/superpowers/specs/`.

## Architecture — module boundaries (hard requirement)
The six-link loop: `aim → core → experience → assessment → state → cadence → ↺`.
Each module has one responsibility and communicates only through the typed
interfaces in `src/retnovation/types.py`:
- `orchestration` — wires the six links (`run_session`)
- `aim` / `core` — onboarding (run once)
- `experience` — selects/loads the experience (MVP: fixed)
- `assessment` — regime-split behind `ASSESSORS[regime]`: `judgment_loop`
  (open_ended), `checkable_scorer` (cs_technical)
- `state` — updates learner state; weak/forming/strong estimator
- `scheduler` — queues the next experience
- `persistence` — SQLite store for state, ledger, queue (the ONLY things that persist)

Adding a domain later = new content + map under `content/`, NEVER an engine edit.

## Doctrine as data (non-negotiable)
- Curated maps (`content/maps/*.yaml`) and curator rubrics (`content/rubrics/*.yaml`)
  are first-class versioned content kept OUT of `src/`. The model never holds the doctrine.
- The judgment loop NEVER: hands the answer, names the frame, agrees/reassures to
  soften, removes effort, or grades the conclusion. It only pushes and scores the
  reasoning trajectory.
- Decay is reversible, de-prioritized review — NEVER deletion (Guidebook §5:
  forgetting is retrieval failure, not erasure). State rows are demoted, never deleted.
- Open-ended state updates come from rigor/trajectory evidence, never from correctness.
- The unlabeled problem is the moat: if recognizing the type + running a procedure
  solves it, it is homework in a costume and does not ship.

## Build order (locked)
1. Harness on the fixed experience (done = Loop v0.1 dry run closes, no manual stitching).
2. Veldra ingestion (ledger + corpus).
3. Experience generator + anti-label gate.
4. CS checkable scorer.
5. Harden judgment loop (regression/plateau stops, independent grader).

## Engineering discipline
- TDD: write the failing test first, then the implementation.
- Core-path changes (`orchestration`, `judgment_loop`, `persistence`, `types`) get an
  independent adversarial subagent review before commit.
- Keep files focused and under ~500 lines. Validate input at system boundaries.

## Commit rules
- NEVER add a `Co-Authored-By` trailer.
- NEVER track confidential design docs (Berkeley Guidebook, Blueprint, Build Brief,
  FounderCEO, JudgmentLoop, LiftTest, MVP Scope, any `*.pdf`) or `data/` (runtime
  ledger/learner state). They are gitignored; verify with `git ls-files` after any doc work.
- Stage explicit paths only — never `git add -A` / `git add .`.
- Update `docs/DEVLOG.md` in the same change (a change without a DEVLOG entry did not happen).
