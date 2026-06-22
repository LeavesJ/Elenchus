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
- Committed the approved harness design as a spec (`docs/superpowers/specs/2026-06-22-harness-skeleton-design.md`).
- Produced the Step-1 implementation plan via writing-plans: 13 right-sized TDD tasks
  (`docs/superpowers/plans/2026-06-22-harness-skeleton.md`), self-reviewed for spec
  coverage, placeholders, and type consistency.
- Next: isolate an execution worktree (using-git-worktrees) and execute Step 1 task-by-task
  under TDD; adversarial review on the core path (judgment loop, orchestration) before done.

## 2026-06-22 — Task 1: Types & enums (TDD PASS)
- Wrote the full `src/retnovation/types.py` module: 6 str Enums, 13 BaseModel classes, 1 dataclass; all match the brief specification exactly.

## 2026-06-22 — Task 2: Content loader (TDD PASS)
- Wrote `src/retnovation/content_loader.py` (load_map, load_rubric, load_experience_meta) with YAML maps and rubrics in `content/`. All 3 tests pass; ruff clean.

## 2026-06-22 — Task 3: Persistence (SQLite Store) (TDD PASS)
- Wrote `src/retnovation/persistence.py` (Store class: load_state, save_state, decay_frame, ledger I/O, queue FIFO); decay_frame enforces no-delete invariant (UPDATE only). All 3 tests pass; ruff clean.

## 2026-06-22 — Task 4: Model protocol + FakeModel (TDD PASS)
- Wrote `src/retnovation/model.py`: Model Protocol (classify_intake, generate_push, classify_response); IntakeClassification and ResponseClassification Pydantic models; FakeModel deterministic test double (pops responses); AnthropicModel stub (raises NotImplementedError). Fixed conftest.py to add src to path. All 11 tests pass; ruff clean.

## 2026-06-22 — Fix editable install (controller infra)
- Task 4 switched packaging to explicit `packages=["retnovation"]`, which broke `import retnovation` outside pytest and would have hidden Task 8 subpackages. Reverted to `[tool.setuptools.packages.find] where=["src"]` and reinstalled with `editable_mode=compat` (plain src-on-path .pth): plain import works, new modules/subpackages import without reinstall. Kept tests/conftest.py as a safety net; documented the compat flag in README.

## 2026-06-22 — Task 5: Aim & Core (onboarding) (TDD PASS)
- Wrote `src/retnovation/aim.py`: aim(posture="founder_ceo") → Aim at MAX_PROCESS_DIAL=10; derive_core(a: Aim, root=None) → Core pulling frames and seed from load_map. Both tests pass; ruff clean.

## 2026-06-22 — Task 6: State update + strength estimator (TDD PASS)
- Wrote `src/retnovation/state.py`: update_state(state, assessment, now, experience_id) → LearnerState with rigor/trajectory-only strength heuristic (strong: reasoned without push; forming: closed under pressure; weak: absent/asserted/regressed); trap_gallery records tripped traps (kind=="trap", response != "closed"). All 3 tests pass; ruff clean.

## 2026-06-22 — Task 7: Scheduler (TDD PASS)
- Wrote `src/retnovation/scheduler.py`: schedule_next(state, ledger, now, regime=open_ended) → NextExperienceSpec with ledger_ref=first ledger entry id; targets weakest frames (all weak, else all forming, else soonest-due strong). Both tests pass; ruff clean.

## 2026-06-22 — Task 8: Judgment loop (assessment subpackage) (TDD PASS)
- Created `src/retnovation/assessment/__init__.py` (empty marker) and `src/retnovation/assessment/judgment_loop.py`: assess(exp, work, model) → Assessment; MAX_PUSHES=6; five stops (converged, bounded_error_violation, budget, plateau; regression in enum but not triggered); sharper = closed AND mechanism_supplied; target order = tripped traps / binding-adjacent / remaining absent. Updated FakeModel.generate_push to return `[push:{kind}]` (no frame_code in output) to enforce the disband rule in tests. All 3 tests pass; ruff clean; 21/21 suite green.

## 2026-06-22 — Strengthen judgment-loop disband assertion (verbatim passthrough)
- Added `assert all(p.text == f"[push:{p.kind}]" for p in a.trajectory)` to `test_cooperative_student_converges`; confirms loop relays generate_push output verbatim without frame_code wrapping. 21/21 suite green; ruff clean.

## 2026-06-22 — Task 9: Assessor dispatch + checkable_scorer stub (TDD PASS)
- Created `src/retnovation/assessment/checkable_scorer.py`: assess raises NotImplementedError (built in step 4). Overwrote `__init__.py` with ASSESSORS registry (open_ended → judgment_loop, cs_technical → checkable_scorer) and get_assessor(regime) dispatch. Both tests pass; ruff clean; 23/23 suite green.
