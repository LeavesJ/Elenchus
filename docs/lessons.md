# Retnovation — Lessons Learned

Read this checklist before every code change. Update it after every correction or build/test failure.

## Pre-Commit Checklist (every commit)
1. `ruff format .`
2. `ruff check .`
3. `pytest`
4. Update `docs/DEVLOG.md` with what changed and why.
5. No secrets/`.env` staged (`git diff --cached`).
6. No confidential docs tracked:
   `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'`
   must be empty.
7. Inversion check: `git status --short | grep -v '^??'` empty, or every Modified file
   has a written hold reason in DEVLOG.
8. Stage explicit paths only (no `git add -A`).

## Before Declaring a Change Complete
1. Pre-commit checklist passes.
2. The relevant test actually runs and passes — observe the output (evidence before assertion).
3. DEVLOG updated.
4. No confidential docs tracked (`git ls-files` check).
5. For core-path changes (`orchestration`, `judgment_loop`, `persistence`, `types`):
   an adversarial review pass was run and its findings addressed.

## Seeded principles
- **L-1 Doctrine is data.** Maps + curator rubrics live in `content/`, versioned, never
  hardcoded in `src/`. The model rents capability; the gates hold doctrine.
- **L-2 Confidential docs never tracked.** The Berkeley Guidebook is a personal life +
  financial plan; the design docs are internal. Gitignore + `git ls-files` verify, every
  time. (Mirrors the Veldra TP-3 near-miss where a private doc was nearly pushed.)
- **L-3 Reversible decay, never deletion.** State demotes/reschedules; rows are not deleted
  (Guidebook §5: forgetting is retrieval failure, not erasure).
- **L-4 Open-ended state moves on rigor/trajectory, never correctness.** The conclusion is
  never graded.
- **L-5 Judgment-loop disband rules.** It never hands the answer, names the frame, agrees to
  soften, removes effort, or grades the conclusion. The friction is the product.
- **L-6 The unlabeled problem is the moat.** If recognizing the type + running a procedure
  solves it, it is homework in a costume and does not ship.
- **L-7 Never force-add gitignored scratch.** The SDD workspace `.superpowers/sdd/` (task
  briefs, implementer reports, review packages) and tool dirs (`.claude-flow/`) are gitignored
  scratch and must never be committed. A fix subagent used `git add -f` to commit its report;
  it was reverted. Subagent dispatches must say: write reports under `.superpowers/sdd/` and
  stage ONLY source/test/docs paths — never `git add -A`, never `-f` on an ignored file.
- **L-8 A green suite can hide a broken bootstrap.** When a runtime gate fails loud over the
  *whole* content library (e.g. `load_gated_library` raises on any rubric lacking a corpus
  anchor), every state-builder entry point (`cli.build_store`) must seed the WHOLE library, not
  one hardcoded item. In Step 3 the e2e tests seeded all three refs explicitly AND the local
  `data/retnovation.db` was already fully seeded — both masked a fresh-DB `GateError`; only the
  final adversarial review, with a fresh-tempdir repro, caught it. Prevention: for any entry
  point that seeds state, add a fresh-DB end-to-end regression test that exercises the real gated
  path (build state → select → assert no raise), so fixtures and a pre-seeded local DB cannot hide
  a broken shipped seed.
