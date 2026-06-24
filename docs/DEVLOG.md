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

## 2026-06-22 — Task 10: Experience selection (TDD PASS)
- Wrote `src/retnovation/experience.py`: FIXED_EXPERIENCE="veldra_licensing_continuity"; select_experience(core, state, ledger, spec, root) loads the fixed experience from content, overriding ledger_ref if spec is given. Test verifies real load of protect_the_core_lane rubric frame and open_ended regime. 24/24 suite green; ruff clean.

## 2026-06-22 — Task 11: Orchestration (run_session) (TDD PASS)
- Wrote `src/retnovation/orchestration.py`: present_and_collect (interactive default) and run_session wiring all six links (persistence, experience, assessment, state, scheduler, model) into one cycle; present is injectable for tests. 25/25 suite green; ruff clean.

## 2026-06-22 — Task 12: Dry-run acceptance test (TDD PASS)
- Wrote `tests/test_dry_run.py`: end-to-end test proving all six links close without manual stitching; real Store, real FakeModel, fixture student; four acceptance assertions (trajectory, converged, frame_deltas trace to rubric codes, persisted frames, fresh NextExperienceSpec queued). 26/26 suite green; ruff clean.

## 2026-06-22 — Strengthen criterion-3 assertion (frame strength movement)
- Test criterion 3 now asserts `assert any(fs.strength != Strength.weak for fs in reloaded.frames.values())` — proves a frame strength actually moved, not just that frames persisted. Criterion 3 still proves persistence via `assert reloaded.frames`. 26/26 suite green; ruff clean.

## 2026-06-22 — Final-review fixes (experience-id provenance, graceful CLI, cleanups)
- Fix 1: orchestration now passes FIXED_EXPERIENCE (not exp.ledger_ref) as experience_id; test_orchestration asserts FIXED_EXPERIENCE appears in last_evidence. Fix 2: main() wraps run_session in NotImplementedError guard, prints frames_total. Fix 3: state.py emits fstate.value not enum repr in last_evidence. Fix 4: clarifying comments on unreachable strong branch and vacuous _converged. 28/28 suite green; ruff clean.

## 2026-06-22 — Task 13: CLI entrypoint + non-consuming queue_len (TDD PASS)
- Added `queue_len() -> int` non-consuming method to Store (Task 3); build_store checks empty state via queue_len (not consuming queue_pop); main wires aim, core, model, run_session. Tests verify seeding and non-consuming invariant. 28/28 suite green; ruff clean.

## 2026-06-22 — Post-review hygiene
- Reverted an erroneous force-add of the gitignored SDD scratch report (commit 670f6b7, removed). Added lesson L-7; gitignored `.superpowers/` and `.claude-flow/` tooling scratch.

## 2026-06-22 — Step two: live Opus 4.8 model adapter (branch live-model)
- Pushed the repo to GitHub: `LeavesJ/Retnovation` (private). Started step two: wire the
  real `AnthropicModel` so the judgment loop runs against `claude-opus-4-8` instead of the
  scripted `FakeModel`.
- Consulted the `claude-api` reference: model `claude-opus-4-8`, adaptive thinking +
  `effort="high"`, no sampling params, structured output via `messages.parse`.
- Approved design (inline TDD): doctrine prompts as versioned `content/prompts/`; list-of-pairs
  wire schema for strict structured outputs; mock unit tests + gated live smoke (skips with no
  key — none in env). Spec: `docs/superpowers/specs/2026-06-22-live-model-adapter.md`.
- Authored `content/prompts/{intake,push,response}.md` (disband rules + sharper definition) +
  `content_loader.load_prompt`; tests in `tests/test_prompts.py`.
- Implemented `AnthropicModel.{classify_intake,generate_push,classify_response}` against
  `claude-opus-4-8` (adaptive thinking, `effort=high`, no sampling params). Doctrine loaded
  from `content/prompts/`; rubric rendered by the adapter. Intake uses a list-of-pairs wire
  schema (`_IntakeWire`) for strict structured outputs → `IntakeClassification` with
  `absent`/`not_tripped` defaulting. Refusal/empty raises `ModelError`. Client injectable for
  tests (no SDK/network in unit tests).
- Tests: `tests/test_anthropic_model.py` (4, mock client) + gated `tests/test_live_model.py`
  (`@pytest.mark.live`, skips without a key); registered the `live` marker. 34 passed, 1 skipped;
  ruff clean. Next: adversarial core-path review, then merge to main + push.
- Adversarial review (independent subagent) of the Opus 4.8 SDK path + doctrine. Fixes applied:
  - **Critical:** `classify_intake` now ignores hallucinated codes not in the rubric — an invented
    key would corrupt `judgment_loop._converged`/`_select_target`. Test
    `test_classify_intake_ignores_hallucinated_codes` added.
  - Minor: `_render_rubric` omits `(paired trap: None)`; `response.md` wording matches where the
    angle is actually provided; live smoke asserts value types.
  - Dismissed the reviewer's ValidationError-bubble finding: `messages.parse` sets
    `parsed_output=None` on a schema miss (does not raise), already handled by `_require`.
  - 35 passed, 1 skipped; ruff clean.

## 2026-06-22 — Step 2: Veldra ingestion (branch veldra-ingestion)
- Read-only Workflow sweep of Veldra docs (5 parallel readers over blockers/ADRs/BIZLOG/EXECLOG/
  runbooks/vision) surfaced 30 candidate owned-problems; curated to a balanced 14 (7 founder + 7 CS),
  user-vetted: ingest all 14, storage = gitignored `data/`, corpus = pointers + metadata.
- Spec `docs/superpowers/specs/2026-06-22-veldra-ingestion.md`: seed YAML (gitignored `data/seed/`) +
  `corpus` table + `veldra_ingest` (load_seed, idempotent ingest, `retnovation-ingest` console script);
  generalizes the single fixed experience. Confidential ledger/corpus live only in gitignored `data/`;
  tests use synthetic temp seeds.
- Implemented (TDD): `types.CorpusEntry`; persistence `corpus` table + `upsert_corpus`/`load_corpus`/
  `get_corpus` (idempotent UPSERT); `veldra_ingest` (`SeedEntry`, `load_seed` YAML→model,
  idempotent `ingest` upserting ledger+corpus with `ledger_ref=veldra:<slug>`, `main` +
  `retnovation-ingest` console script). `tests/test_ingestion.py` (corpus CRUD+idempotent, load_seed,
  ingest+idempotent) with hermetic temp seeds. 38 passed, 1 skipped; ruff clean.
- Adversarial review (independent subagent): confidentiality clean (no Critical). Fixes applied:
  - **Important:** ledger UPSERT now preserves `links_json` on conflict — a re-ingest no longer
    clobbers downstream-accumulated experience links (the seed is not their authority).
  - **Important:** `load_seed` rejects a non-list YAML with a clear `ValueError`.
  - Minor: `retnovation-ingest` anchors seed + db paths to repo root (no cwd foot-gun); idempotency
    test now asserts field stability; added link-preservation + non-list-seed tests.
  - 40 passed, 1 skipped; ruff clean.
- Next: merge to main + push, then create the confidential 14-entry seed in main `data/seed/` + run ingestion.

## 2026-06-22 — Step 2 COMPLETE + handoff for Step 3
- Veldra ingestion merged (`8f4c5e0`); the confidential 14-entry ledger + corpus is seeded into
  gitignored `data/` (`data/retnovation.db`: 14 ledger + 14 corpus; 7 founder_ceo + 7 cs_technical).
  Run/refresh anytime with `retnovation-ingest`; git tracks none of the seed/db.
- Live Opus 4.8 is wired and verified (a real classify call + a full live `run_session`); key lives in
  gitignored `.env` — **rotate it** (it was echoed into a session transcript).
- **NEXT SESSION -> Step 3: experience generator + the anti-label gate (the moat).** Read first per the
  session-start protocol: `docs/lessons.md` (esp. L-6, the unlabeled-problem test) and the design docs
  the Build Brief points to — Build Brief build-order #3 + "anti label gate",
  `Retnovation_JudgmentLoop_v0.1.md`, `Retnovation_FounderCEO_Design_v0.1.md`,
  `Berkeley_Operating_Guidebook_v2.1.md` (all **local-only, gitignored** — present on this machine, do
  NOT travel with a clone).
- **Where Step 3 starts:** `src/retnovation/experience.py::select_experience` still returns the single
  fixed experience. The 14-entry ledger is seeded in `data/` but not yet driving selection. Step 3:
  generate experiences against the ledger's `weak`/`forming` frames + an owned problem, and gate each so
  it is genuinely unlabeled (recognize-type-and-run-procedure => rejected). `checkable_scorer`
  (cs_technical) is still a `NotImplementedError` stub (Step 4).

## 2026-06-23 — Task 7: Raise MAX_PUSHES 6→8 (COMPLETE)
- Baseline judgment-loop tests: 3 passed (cooperative paths green).
- Change: `src/retnovation/assessment/judgment_loop.py` line 16, `MAX_PUSHES = 6` → `MAX_PUSHES = 8` with
  comment explaining 8-angle depth floor + budget-only semantics.
- Post-change: judgment-loop tests 3 passed, full suite 61 passed + 1 skipped; no regression.
- Linting: ruff format + check all clean.
- Commit: `1cf6f4b` on `step3-experience-generator` with message "feat: raise MAX_PUSHES 6->8 to fit the 8-angle depth floor (budget-only)".
- Self-review: Loop mechanics untouched; cooperative paths (`converged`, `bounded_error_violation`) remain green; budget-only prep for Step 5 deeper interrogation.

## 2026-06-23 — Step 3 COMPLETE: experience generator + anti-label gate (the moat) + Step 4 handoff
- Built on branch `step3-experience-generator` via subagent-driven development (7 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review). Spec:
  `docs/superpowers/specs/2026-06-23-experience-generator-anti-label-gate.md`; plan:
  `docs/superpowers/plans/2026-06-23-experience-generator-anti-label-gate.md`.
- **What shipped:** `select_experience` retired the single fixed experience. It now dispatches by regime
  through a `SELECTORS` registry (mirroring `assessment.ASSESSORS`): `open_ended` →
  `generator.select_open_ended` (deterministic: ranks the authored library by process-frame coverage of
  the scheduler's `target_frames`, tie-break by `experience_id`, binds the candidate's own
  `ledger_ref`); `cs_technical` → a `NotImplementedError` Step-4 stub.
- **The gate** (`generator.anti_label_gate`, `src/retnovation/generator.py`): deterministic, closed
  `GateCode` enum — 5 hard rejects (`recoverable_label`, `pre_named_framework`, `type_hint_scaffold`,
  `softened_ambiguity`, `cosmetic_engagement`) + 1 user depth floor
  (`insufficient_interrogation_depth`, ≥8 angles = frames+traps+binding+4 artifact dims) + 2 quality
  floors (`owned_or_real`, `process_layer_load`, downgrade-not-reject). It verifies anchoring to the
  curated corpus + structure; the curator's `unlabeled` rationale holds the semantic judgment.
  `load_gated_library` fails loud (raises `GateError`) on any hard-reject rubric. Denylists + the depth
  threshold are versioned content under `content/gate/` (L-1).
- **Content:** founder thin seed = 3 abstracted `open_ended` rubrics bound to real founder ledger refs
  (`license_continuity`→`license_fork_risk`, `decision_under_stakes`→`concentrated_market_pricing_power`,
  `proof_before_promise`→`first_customer_proof_loop`, one `bounded_error`); the orphan
  `veldra_licensing_continuity.yaml` (dangling `ledger_ref`) was re-homed, not deleted. Tracked rubrics
  carry only abstracted prompts + codes + a ref id; the confidential corpus stays in gitignored `data/`.
- **Doctrine correction absorbed mid-build (Complete Picture §10, interest tree):** Founder CEO is a
  *posture path* (process core, ledger-driven, `open_ended`); CS is a *domain path* (content core,
  checkable, `cs_technical`) — different types. Selection is pluggable-by-regime so the two never
  collapse. Bobby-Axe = a founder articulation/decision-rep experience (in scope), not executive.
- **MAX_PUSHES 6→8** (budget-only; the loop still pushes frames/traps — deeper dimension interrogation
  is Step 5).
- **Final adversarial review (opus)** confirmed the core-path invariants (gate soundness/no
  false-negative, selection determinism, confidentiality, fail-loud, orphan retirement, loop closes,
  cooperative path unchanged) and caught one real bug the green suite masked: `cli.build_store` seeded
  only 1 of the 3 required corpus refs, so a *fresh* DB raised an uncaught `GateError`. Fixed
  (`51029e3`): `build_store` now seeds every authored `open_ended` ref + a fresh-DB regression test.
- **Verified:** full suite **62 passed, 1 skipped** (only skip = `@pytest.mark.live`, no key); ruff
  clean; fresh-DB `build_store`→`select_experience` returns `license_continuity` with no error.
- **NEXT SESSION -> Step 4: the CS checkable scorer + the cs_technical domain-path selector.** Two clean
  seams are waiting, both `NotImplementedError`: `src/retnovation/assessment/checkable_scorer.py::assess`
  (the checkable regime — answer keys, retrieval strength read off performance) and
  `src/retnovation/generator.py::select_cs_technical` (the domain-path selector — selects by
  *content-concept* coverage, not process-frame coverage). Adding CS is "content + a map + a registered
  selector + the scorer", not an engine rewrite. Read first per the session-start protocol:
  `docs/lessons.md`, then the local-only gitignored corpus — `Retnovation_Complete_Picture.md` §10–§12,
  MVP Scope §4 (the two regimes), and the Build Brief build-order #4.

## 2026-06-23 — Step 4 design spec (branch step4-cs-checkable-scorer)
- Read the session-start docs (lessons.md) + the local-only design corpus (Complete Picture §9–§12,
  §15; MVP Scope §4; Build Brief build-order #4) and mapped both Step-4 seams against every engine
  contract before designing.
- Brainstormed the design with the user; two decisions confirmed: (1) **scoring = deterministic by
  default, model-graded optional per question** (each question carries its own `check_type`; the
  live grader path stays gated like the judgment-loop adapter); (2) **CS content = generic,
  tracked in `content/`** (a non-confidential distributed-systems/consensus concept set; questions
  anchor to `cs_technical` ledger refs for provenance but nothing confidential is tracked).
- Chose **Approach 1 — shared types, regime-dispatched behavior** (over parallel CS types, and over
  a regime-agnostic tagged-union core). One `Experience`/one loop, extended not forked; behavior
  dispatches by regime through registries mirroring `ASSESSORS`/`SELECTORS`. CS drives the existing
  unused `declarative_seed`/`SpacedItem` spaced index (new `concepts` persistence table); the two
  paths (founder process-frames vs CS content-concepts) never collapse (Complete Picture §10).
- Recorded that the Step-3 handoff's "content + map + selector + scorer" under-counted: honoring
  "never collapse the two paths" needs a bounded engine change (a parallel concept-based
  state/scheduling path), not a rewrite.
- Spec committed: `docs/superpowers/specs/2026-06-23-cs-checkable-scorer-design.md` (self-reviewed:
  no placeholders, internally consistent, single-plan scope). Baseline green before any code: 62
  passed, 1 skipped; confidential-docs `git ls-files` check clean.
- Next: user review of the spec, then `writing-plans` → subagent-driven TDD → final adversarial
  review (§9 checklist) → merge.

## 2026-06-23 — Step 4 implementation plan (branch step4-cs-checkable-scorer)
- User approved the spec. Authored the TDD implementation plan:
  `docs/superpowers/plans/2026-06-23-cs-checkable-scorer.md` — 11 right-sized tasks
  (types/invariant → CS content + loaders → model grader → checkable scorer → cs selector →
  concept state + `STATE_UPDATERS` → regime-aware scheduler → `concepts` persistence →
  domain-path onboarding → orchestration/CLI dispatch → CS dry-run acceptance), then a final
  adversarial core-path review against spec §9.
- Plan grounded in the real test suite (read all existing tests first) so every step has complete,
  fixture-accurate code and no placeholders; verified against the project's ruff line-length=100
  and the gated `live` marker. Self-review: full spec coverage, no placeholders, type-consistent
  signatures end to end.
- Next: execute via subagent-driven development (fresh implementer + independent reviewer per task).

## 2026-06-23 — Step 4 Task 1: Checkable types + Experience regime/payload invariant (TDD PASS)
Task 1 — checkable types (`CheckType`, `CheckableQuestion/Set`, `ConceptResult`, `CheckableAssessment`, `CheckableGrade`); `Experience.rubric` optional + regime/payload validator; `Aim`/`Core` content_core widened.

## 2026-06-23 — Step 4 Task 2: CS content + content-loader functions (TDD PASS)
- Authored all CS content files: `content/maps/cs_systems.yaml` (domain path, 6 content-core
  concepts), `content/cadence/spacing.yaml` (initial 1d, ease 2.0, min 1d),
  `content/prompts/grade.md` (strict grader doctrine), `content/checkables/consensus_safety_liveness.yaml`
  (3 deterministic questions), `content/checkables/replication_models.yaml` (2 deterministic + 1
  model-graded question).
- Additive edit to `content/maps/founder_ceo.yaml`: prepended `path_type: posture`; existing
  `process_frames` / `declarative_seed` keys unchanged.
- CS content lives in `content/checkables/` (separate from `content/rubrics/`) so
  `load_library` / anti-label gate never pick it up.
- Updated `src/retnovation/content_loader.py`: expanded import to include checkable types
  (`CheckableQuestion`, `CheckableSet`); appended `load_path_type`, `load_content_map`,
  `load_spacing`, `load_checkable_experience`, `load_checkable_library`.
- TDD: wrote 3 failing tests first (RED — ImportError); implemented loaders; all 3 turned GREEN.
- Full suite: 67 passed, 1 skipped; ruff format + check clean; confidentiality gate CLEAN.

## 2026-06-23 — Step 4 Task 4: Checkable scorer (cs_technical regime) (TDD PASS)
- Replaced the `NotImplementedError` stub in `src/retnovation/assessment/checkable_scorer.py`
  with the real scorer: `_normalize` (lowercase, strip, collapse whitespace, strip punctuation),
  `_render` (question prompt + choices if any), `score_question` (deterministic: normalized
  match against `answer_key`, model-free; model_graded: `model.grade_answer(...).correct`),
  `assess` (iterates `exp.checkable.questions`, collects answers via `work.respond`, returns
  `CheckableAssessment`). Empty `answer_key` on deterministic raises `ValueError` (fail loud).
- TDD: wrote `tests/test_checkable_scorer.py` first (4 tests); confirmed RED (all 4 failed
  with `NotImplementedError`); implemented; all 4 GREEN.
- Updated `tests/test_dispatch.py`: replaced the old stub-era `NotImplementedError` expectation
  with a real-registration assertion (`checkable_scorer.assess is get_assessor(Regime.cs_technical)`).
- Full suite: 74 passed, 2 skipped (was 70 + 2 baseline; net +4 scorer tests); ruff clean.

## 2026-06-23 — Step 4 Task 5: CS domain-path selector `select_cs_technical` (TDD PASS)
- Replaced the `NotImplementedError` stub in `src/retnovation/generator.py::select_cs_technical`
  with the real CS selector: `_concept_coverage(exp, targets)` counts how many target codes appear
  in `{q.concept for q in exp.checkable.questions}`; `select_cs_technical` loads the checkable
  library via `load_checkable_library` (NEVER `load_gated_library` / `load_library` — the anti-label
  gate must never touch CS experiences), raises `GateError` if empty, resolves targets from
  `spec.target_frames` → `core.content_core` → `[]` (cold start), ranks by
  `(-coverage, experience_id)`, returns `ranked[0]`.
- Added `load_checkable_library` to the import block in `generator.py`.
- TDD: replaced `test_select_cs_technical_is_a_step4_stub` with two new tests (RED first — both
  failed `NotImplementedError`); replaced `test_select_experience_cs_technical_is_stubbed` in
  `test_experience.py` with `test_select_experience_dispatches_cs_technical`; confirmed RED (3
  failures); implemented; all 3 GREEN.
- Removed now-unused `import pytest` from `tests/test_experience.py` (ruff F401).
- Full suite: 75 passed, 2 skipped (baseline was 74 + 2); ruff format + check clean.

## 2026-06-23 — Step 4 Task 6: Concept state update + `STATE_UPDATERS` registry (TDD PASS)
- Added `update_state_checkable(state, assessment, now, experience_id, spacing=None) -> LearnerState`
  to `src/retnovation/state.py`. Aggregates `CheckableAssessment.results` by concept; recalled iff
  ALL questions correct (strict `all(corrects)`); recall multiplies interval by `ease_factor`
  (floored at `min_interval_days`); miss resets to `min_interval_days` — the `SpacedItem` is
  UPDATED, never deleted (L-3 reversible decay). Writes ONLY to `state.declarative_seed`; never
  touches `state.frames` (NEVER-COLLAPSE invariant, Complete Picture §10).
- Added `STATE_UPDATERS: dict[Regime, Callable]` = `{open_ended: update_state, cs_technical:
  update_state_checkable}`, mirroring `ASSESSORS`/`SELECTORS` registries for orchestration dispatch
  (Task 10).
- Updated imports in `state.py`: `Callable`, `timedelta`, `load_spacing`, `CheckableAssessment`,
  `Regime`, `SpacedItem`.
- TDD: 3 failing tests appended to `tests/test_state.py` first (RED — ImportError on
  `update_state_checkable`/`STATE_UPDATERS`); implemented; all 3 GREEN. Original 3 founder tests
  unaffected.
- Full suite: 78 passed, 2 skipped (was 75+2); ruff format + check clean.

## 2026-06-23 — Step 4 Task 7: Regime-aware scheduler (TDD PASS)
- Made `schedule_next` regime-aware: inserted a `cs_technical` branch before the existing frame
  logic. For `cs_technical`, reads `state.declarative_seed` (`SpacedItem`); returns all
  due concepts (`due <= now`, ordered by `due`) when any exist; otherwise the single
  soonest-due concept; puts codes in `NextExperienceSpec.target_frames` with `regime=cs_technical`.
- `open_ended` branch byte-identical — no logic touched.
- TDD: 2 failing tests appended first (RED — both returned `[]`); implemented cs branch;
  both GREEN. Existing 2 open_ended tests unchanged and still pass.
- ruff: 1 file reformatted (dict-literal style in test); check clean.
- Full suite: 80 passed, 2 skipped (baseline was 78+2; net +2).

## 2026-06-23 — Step 4 Task 3: Model grader (`grade_answer`) (TDD PASS)
- Added `grade_answer(exp, question, answer) -> CheckableGrade` to the `Model` Protocol,
  `FakeModel`, and `AnthropicModel`; updated the types import in `model.py`.
- `FakeModel.__init__` gains an optional `grades: dict[str, list[CheckableGrade]] | None = None`
  third param (pops by `question_id`); existing callers with 2 positional args unchanged.
- `AnthropicModel.grade_answer`: builds system prompt from `load_prompt("grade")` + question
  prompt/answer_key/criteria, sends student answer as user message, parses via `messages.parse`
  with `output_format=CheckableGrade`; refusal/empty raises `ModelError` via `_require` (mirrors
  `classify_response`).
- TDD: 3 failing tests first (RED — unexpected kwarg + AttributeError); implemented; all 3 GREEN.
- Full suite: 70 passed, 2 skipped (added 3 tests; live smoke stays skipped without key); ruff clean.

## 2026-06-23 — Step 4 Task 8: Persistence — `concepts` table + `declarative_seed` I/O (TDD PASS)
- Added `SpacedItem` to the types import in `src/retnovation/persistence.py`.
- Appended `CREATE TABLE IF NOT EXISTS concepts (concept TEXT PRIMARY KEY, due TEXT NOT NULL,
  interval_days INTEGER NOT NULL)` to `_SCHEMA` — fresh DB supports the CS path with no migration
  (L-8: fresh-DB end-to-end; Spec §5.8).
- Extended `load_state`: after the frames loop, reads every `concepts` row and populates
  `st.declarative_seed[concept]` as a `SpacedItem`.
- Extended `save_state`: after the frames loop, UPSERTs every `(concept, si)` in
  `state.declarative_seed` via `INSERT ... ON CONFLICT(concept) DO UPDATE SET ...` — NO DELETE
  (L-3: reversible decay; a demoted concept keeps its row, interval shrinks).
- Frames I/O and all existing tables (frames, ledger, queue, corpus) are unchanged.
- TDD: `test_concepts_roundtrip_and_never_deleted` appended first; ran RED (KeyError —
  `declarative_seed` not persisted); implemented; GREEN in 0.14 s.
- Full suite: 81 passed, 2 skipped (was 80+2; net +1); ruff format + check clean.

## 2026-06-23 — Step 4 Task 10: Orchestration + CLI regime dispatch (COMPLETE)
- Updated `src/retnovation/orchestration.py`: swapped `from .state import update_state` for
  `from .state import STATE_UPDATERS`; added `CheckableAssessment, Regime` to the types import.
  `present_and_collect` is now regime-aware — `cs_technical` skips the opening prompt (returns
  `Work(opening="", respond=respond)`); `open_ended` path byte-identical. `run_session` dispatches
  the state update via `STATE_UPDATERS[exp.regime]`; return type widens to
  `tuple[LearnerState, Assessment | CheckableAssessment]`.
- Updated `src/retnovation/cli.py`: replaced the single `print(f"stop_reason=...")` line with a
  regime-aware `isinstance(assessment, CheckableAssessment)` branch — CS prints
  `concepts_scored=/recalled=`; founder prints `stop_reason=/frames_total=`.
- Verification: no new tests this task; verification gate = founder-regression-stays-green + ruff
  + full suite. Command:
  `pytest tests/test_dispatch.py tests/test_orchestration.py tests/test_cli.py tests/test_dry_run.py -q`
  → 6 passed. `ruff format . && ruff check .` → clean. Full suite `pytest -q` → **83 passed,
  2 skipped** (baseline unchanged).
- Files changed: `src/retnovation/orchestration.py`, `src/retnovation/cli.py`, `docs/DEVLOG.md`.
- `tests/test_dispatch.py` NOT touched (Task 4 already provides the stronger assertion).

## 2026-06-23 — Step 4 Task 11: CS dry-run acceptance test (TDD PASS)
- Created `tests/test_cs_dry_run.py` (verbatim from brief): builds a real `Store`, queues a
  `cs_technical` `NextExperienceSpec` targeting `safety_vs_liveness`, `idempotency_under_retry`,
  `quorum_intersection`; derives a CS `Core` via `aim("cs_systems")`; runs `run_session` with a
  fixture that answers each question correctly via `answer_key[0]` (fully deterministic, model-free).
- Three acceptance assertions: (1) scorer ran every question, all correct; (2) concept spaced-index
  moved + persisted across a `Store` reopen; (3) a fresh `cs_technical` next experience is queued.
- Result: 1 passed in 0.15s. Full suite: **84 passed, 2 skipped** (was 83+2; net +1);
  ruff format + check clean; confidentiality gate CLEAN.
- Files changed: `tests/test_cs_dry_run.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Step 4 Task 9: Domain-path onboarding (`aim` / `derive_core`) (TDD PASS)
- Added `MIN_PROCESS_DIAL = 0` constant to `src/retnovation/aim.py` (CS — content axis maxed,
  process near-empty per Complete Picture §10).
- Made `aim(posture, root=None)` path-type-aware: calls `load_path_type(posture, root=root)`;
  sets `dial = MAX_PROCESS_DIAL` for `path_type == "posture"` (founder), `MIN_PROCESS_DIAL`
  otherwise (domain / CS). Signature now accepts `root` parameter (mirrors `derive_core`).
- Made `derive_core(a, root=None)` branch by path type: for `domain` maps loads
  `load_content_map` → `concepts`; returns `Core(process_frames=[], declarative_seed=concepts,
  content_core=concepts)` — frames empty, seed = content concepts; for `posture` maps the
  original `load_map` path is byte-identical (frames + seed, `content_core=None`).
- Founder posture path (`aim()` / `derive_core(aim())`) fully unchanged — existing two tests
  still pass.
- TDD (RED then GREEN): appended 2 CS domain-path tests to `tests/test_aim.py` first;
  ran RED (`ImportError: cannot import name 'MIN_PROCESS_DIAL'` + `KeyError: 'process_frames'`);
  implemented; all 4 aim tests GREEN.
- Full suite: 83 passed, 2 skipped (was 81+2; net +2 new CS tests); ruff format + check clean.

## 2026-06-23 — Step 4 final-review fixes (MERGE-CLEAN verdict, 3 minor closures)

Whole-branch adversarial review returned MERGE CLEAN with one Minor finding and two
guard-coverage gaps (L-8: cover fail-loud guards). Applied exactly three changes:

1. **Scheduler tie-determinism** (`src/retnovation/scheduler.py`): Added concept-code
   tiebreak to both sort keys in the `cs_technical` branch of `schedule_next`, matching
   the deliberate `sorted()` determinism of the `open_ended` branch. Due-list key:
   `(items[c].due, c)`; soonest-due fallback key: `(kv[1].due, kv[0])`.
   New test: `test_cs_technical_due_ties_break_by_concept_code` asserts
   `["alpha", "zebra"]` when both have identical due timestamps.

2. **Guard regression test — `checkable is None`** (`tests/test_checkable_scorer.py`):
   `test_assess_raises_when_checkable_is_none` uses `Experience.model_construct` to
   bypass the regime validator and constructs a `cs_technical` experience with
   `checkable=None`, then asserts the scorer's defensive `ValueError` guard fires.

3. **Guard regression test — empty checkable library** (`tests/test_generator.py`):
   `test_select_cs_technical_raises_on_empty_library` creates an empty `checkables/`
   directory in a `tmp_path` and asserts `select_cs_technical` raises `GateError`.

Results: 87 passed, 2 skipped (was 84+2; +3 new tests); ruff format + check clean.

## 2026-06-23 — Step 4 COMPLETE: CS checkable scorer + cs_technical regime + Step 5 handoff
- Built on branch `step4-cs-checkable-scorer` via subagent-driven development (11 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review on opus).
  Spec: `docs/superpowers/specs/2026-06-23-cs-checkable-scorer-design.md`; plan:
  `docs/superpowers/plans/2026-06-23-cs-checkable-scorer.md`. Approach 1 (shared types,
  regime-dispatched behavior) — one `Experience`/one loop, extended not forked.
- **What shipped — the second assessment regime runs through the same six-link plumbing:**
  - `assessment/checkable_scorer.py::assess` retired its stub: iterates `exp.checkable.questions`,
    collects each answer over the SAME `Work` channel the judgment loop uses, scores correctness, and
    returns a `CheckableAssessment`. **Deterministic by default** (normalized answer-key match, NO model
    call), **optional `model_graded` per question** (Opus grader via `Model.grade_answer`, `_require`-guarded
    so refusal/empty raises — no silent leniency; gated live smoke).
  - `generator.py::select_cs_technical` — the domain-path selector: ranks the checkable library by
    **content-concept coverage** of the scheduler's target codes (cold-start fallback to `core.content_core`),
    tie-break by `experience_id`. CS is **ungated** (the anti-label gate is the open_ended moat; CS is the
    labeled/checkable contrast) — it loads from `content/checkables/`, which `load_library`/the gate never touch.
  - CS drives the previously-unused `declarative_seed`/`SpacedItem` spaced index via
    `state.update_state_checkable` (recall grows the interval by `ease_factor`, a miss resets to the floor —
    reversible demotion, never deletion, L-3); new `concepts` SQLite table persists it; regime-aware
    `schedule_next` targets due concepts. Dispatch is table-driven (`STATE_UPDATERS` mirroring
    `ASSESSORS`/`SELECTORS`). **The two paths never collapse**: founder process-frames stay in `frames`,
    CS content-concepts stay in `declarative_seed`/`concepts`.
  - Domain-path onboarding: `aim("cs_systems")` → `MIN_PROCESS_DIAL`; `derive_core` loads the CS content
    core (Complete Picture §10 — domain path maxes the content axis). Founder posture path byte-stable.
  - `Experience` gained a regime/payload invariant (open_ended ⇒ rubric; cs_technical ⇒ checkable).
- **Content (generic, non-confidential, tracked):** `content/maps/cs_systems.yaml` (a distributed-systems /
  consensus content core), two `content/checkables/*.yaml` experiences (MCQ + short-answer + one model-graded),
  `content/prompts/grade.md`, `content/cadence/spacing.yaml`. Nothing confidential tracked (`git ls-files` clean).
- **Final adversarial review (opus): MERGE CLEAN** — all ten §9 invariants verified with live repros
  (fresh-DB CS session closes the loop end-to-end; never-collapse holds across a 5-session run; confidentiality
  `git ls-files` empty; founder path byte-stable). One Minor (scheduler tie-order determinism) fixed +
  two fail-loud-guard regression tests added (L-8).
- **Verified:** full suite **87 passed, 2 skipped** (only skips = the two `@pytest.mark.live` smokes, no key);
  ruff format + check clean; confidentiality + `data/`-untracked clean; `test_cs_dry_run.py` closes the six
  links for `cs_technical`.
- **NEXT SESSION -> Step 5 (the last build-order item): harden the judgment loop.** Exercise the stops that
  have never fired — `regression` and `plateau` (only the cooperative `converged`/`bounded_error_violation`
  paths are proven; the model won't play a caving/safety-inverting student, so these need authored fixtures or
  the dogfood) — and add the independent-grader pass for the "sharper" calls. Read first per the session-start
  protocol: `docs/lessons.md`, then the local-only gitignored corpus — `Retnovation_JudgmentLoop_v0.1.md`,
  `Retnovation_Complete_Picture.md` §12 (the judgment loop) + §13 (the empirical spine), and Build Brief
  build-order #5.

## 2026-06-23 — Step 5 design spec (branch step5-harden-judgment-loop)
- Resumed under the user's standing delegation (do Step 5, then continue autonomously, "quadruple-check /
  be mindful", user away). Read the session-start docs + the local-only Step-5 corpus
  (`Retnovation_JudgmentLoop_v0.1.md` §2/§5/§6/Decisions, Build Brief #5) and the current
  `assessment/judgment_loop.py` before designing.
- **Diagnosis:** `regression` is in the `StopReason` enum but the loop has no branch for a `"regressed"`
  outcome (silently treated as `"unchanged"`) → never fires. `plateau` fires on two consecutive non-moves
  but the loop re-hammers one target, so it means "stuck on one angle", not the doctrine's "two *distinct*
  targets moved nothing" (§2/§6). No independent grader exists — the instructor scores sharper in-line,
  the over-credit confound §6 flagged.
- **Design (Approach: extend the open_ended assessor; cs_technical untouched):** (1) regression stops on the
  first genuine backslide (lower the frame one level + record delta); (2) plateau becomes distinct-target via
  an `exhausted` set that rotates `_select_target` to a fresh angle, firing on two distinct consecutive
  non-moves (or no fresh angle left while not converged); (3) a separate **blind skeptical grader**
  (`assessment/sharper_grader.py::audit_sharper` + `Model.grade_sharper` + `content/prompts/grade_sharper.md`)
  re-audits each closed frame and gates sharper by 2-vote — a disputed call is dropped from
  `frames_closed_under_pressure` AND its `FrameDelta` reverted (so `update_state` scores it weak, not strong).
  `Push` gains the raw `response` so the grader re-judges independently; `judgment_loop.assess` runs the loop
  then the audit; `run_session`/`STATE_UPDATERS`/cs_technical all unchanged.
- Resolved all design forks autonomously (recorded in spec §4/§11): regression-on-first-backslide,
  distinct-target plateau via rotation, separate-pass 2-vote grader, `FakeModel` grader agrees-by-default
  (disputes scripted) so existing open_ended tests stay green untouched.
- Spec committed: `docs/superpowers/specs/2026-06-23-harden-judgment-loop-design.md` (self-reviewed: no
  placeholders, internally consistent, single-plan scope). Baseline before any code: 87 passed, 2 skipped;
  confidentiality `git ls-files` clean.
- Next: `writing-plans` → subagent-driven TDD → final adversarial review (§9) → merge.

## 2026-06-23 — Step 5 implementation plan (branch step5-harden-judgment-loop)
- Authored the TDD plan `docs/superpowers/plans/2026-06-23-harden-judgment-loop.md` — 6 right-sized
  tasks then a final opus adversarial review: (1) types (`Push.response`, `SharperVerdict`,
  `SharperAuditItem`, `Assessment.sharper_audit`) → (2) `Model.grade_sharper` + blind skeptical
  `content/prompts/grade_sharper.md` → (3) `assessment/sharper_grader.py::audit_sharper` (2-vote
  demote+revert) → (4) regression stop + capture raw responses → (5) distinct-target plateau via
  angle rotation → (6) wire the audit into `assess` + strengthen/extend the loop tests.
- Plan grounded in the real suite (read judgment_loop + all touched tests first); every step has
  complete, fixture-accurate code; quadruple-checked the cooperative/bounded/budget paths survive
  rotation and the audit-wiring no-ops on no-closed-frame assessments. Self-review: full spec
  coverage, no placeholders, type-consistent signatures end to end.
- Next: execute via subagent-driven development (fresh implementer + independent reviewer per task),
  then the final adversarial review.

## 2026-06-23 — Step 5 Task 1: Types — Push.response + sharper-audit types + Assessment.sharper_audit (TDD PASS)
Task 1 — added `Push.response` (default ""), `SharperVerdict`, `SharperAuditItem`, `Assessment.sharper_audit` (default []); 89 passed, 2 skipped; ruff clean.

## 2026-06-23 — Step 5 Task 2: Model grader — `grade_sharper` + blind doctrine prompt (TDD PASS)
- Created `content/prompts/grade_sharper.md`: skeptical auditor doctrine — assent≠sharper,
  length≠sharper, conclusion-agnostic, default to not-sharper; identifies sharper by mechanism/reason
  cited in the student's own words.
- Added `Model.grade_sharper(self, exp, kind, code, push, response) -> SharperVerdict` to the
  Protocol (blind: no instructor-outcome parameter).
- Extended `FakeModel.__init__` with optional `sharper_verdicts: dict[str, list[SharperVerdict]] | None = None`
  as the last param (existing callers unchanged). `FakeModel.grade_sharper` pops a scripted verdict
  for `code` if present, else returns `SharperVerdict(sharper=True, reason="(default agree)")` so all
  existing open_ended tests stay green without modification.
- Implemented `AnthropicModel.grade_sharper`: `messages.parse` with `output_format=SharperVerdict`,
  system = `load_prompt("grade_sharper")` + target detail via `_target_detail`, user = push + student
  reply; refusal/empty raises `ModelError` via `_require` (mirrors `classify_response`).
- Added `SharperVerdict` to the `model.py` types import.
- TDD evidence: 3 tests RED before implementation (`AttributeError: 'AnthropicModel'/'FakeModel'
  object has no attribute 'grade_sharper'`); GREEN after; live smoke (`test_live_grade_sharper_smoke`)
  gated with `@pytest.mark.skipif(not _HAS_KEY, ...)` — adds 3rd skip.
- Full suite: **92 passed, 3 skipped** (was 89+2; net +3 tests, +1 skip); ruff format + check clean.

## 2026-06-23 — Step 5 Task 4: Regression stop + populate `Push.response` in the loop (TDD PASS)
- Added `_LOWER` dict and `_lower(state) -> FrameState` helper after `MAX_PUSHES` in
  `src/retnovation/assessment/judgment_loop.py`: lowers `present_reasoned → present_asserted →
  absent → absent` (floor clamp).
- Inserted a `rc.outcome == "regressed"` branch immediately AFTER the `bounded_error hard_wrong`
  block and BEFORE the `rc.outcome == "closed"` block (bounded hard-wrong still pre-empts).
  On regression: lowers the frame one level, appends a `FrameDelta` if the level changed,
  appends a `Push(response=response)`, sets `stop_reason = StopReason.regression`, breaks.
  Doctrine: "the student is getting worse and more pushing harms" (§5.4).
- Added `response=response` to the bounded-error `hard_wrong` `Push` and the normal end-of-loop
  `Push` so every push carries the raw student reply (required by the Task 6 independent grader).
- TDD evidence: test `test_regression_stops_when_student_backslides` written first (RED — loop
  treated `"regressed"` as unchanged, re-hammered the target until `IndexError: pop from empty
  list`); implemented; GREEN in 0.13 s.
- Cooperative (`converged`), bounded-error, and budget/plateau paths all still pass (4/4
  judgment_loop tests green).
- Full suite: **95 passed, 3 skipped** (was 94+3; net +1 new test); ruff format + check clean.

## 2026-06-23 — Step 5 Task 5: Distinct-target plateau via angle rotation (TDD PASS)
- Replaced the single-target `recent_moved: list[bool]` plateau with a rotation-aware mechanism.
- `_select_target` gains an `exhausted: set[str]` parameter; skips any code already in `exhausted`
  so the loop rotates to a fresh angle on each non-moving push.
- In `assess`: `recent_moved` replaced by `exhausted: set[str]` + `recent: list[tuple[str, bool]]`
  (code, moved) for the last pushes.
- Plateau check updated: fires when `recent[-1][0] != recent[-2][0]` and both moves are False —
  i.e., two DISTINCT targets both moved nothing, matching JudgmentLoop §2/§6 doctrine.
- `_select_target(...)` call updated to pass `exhausted`; the `target is None` branch now maps to
  `StopReason.plateau` (out of distinct angles while not converged, not converged).
- Move/no-move handling: `else: exhausted.add(code)` added; `recent.append((code, moved))`
  replaces the old `recent_moved.append(moved)`.
- TDD evidence: `test_plateau_stops_on_two_distinct_unmoved_targets` written first (RED —
  `IndexError: pop from empty list` because loop re-hammered the first target); implemented;
  GREEN. All 5 judgment_loop tests pass.
- Regression checks: `test_cooperative_student_converges` (every push closes → moved=True → no
  rotation → still converges), `test_bounded_error_violation_stops_immediately`,
  `test_budget_caps_unproductive_loop` (stops at plateau, still in asserted set),
  `test_regression_stops_when_student_backslides` (Task 4) all GREEN.
- Full suite: **96 passed, 3 skipped** (was 95+3; net +1 new test); ruff format + check clean.

## 2026-06-23 — Step 5 Task 3: Independent blind sharper grader `audit_sharper` (TDD PASS)
- Created `src/retnovation/assessment/sharper_grader.py`: `audit_sharper(exp, assessment, model) ->
  Assessment` — a pure function that re-grades every closing push for frames in
  `frames_closed_under_pressure` (one audit per code, `kind == "frame"`,
  `response_classification == "closed"`) using `model.grade_sharper` (the blind Task-2 grader).
- A DISPUTED verdict (`verdict.sharper is False`) removes the code from
  `frames_closed_under_pressure` AND removes its `FrameDelta` from `frame_deltas`, so a subsequent
  `update_state` scores the frame `Strength.weak`, not strong — the misclassification trap is
  closed. Records the full `SharperAuditItem` trail on `Assessment.sharper_audit`.
- Returns via `assessment.model_copy(update={...})` — input Assessment is never mutated.
- TDD evidence: tests written first (`tests/test_sharper_grader.py`); RED
  (`ModuleNotFoundError: No module named 'retnovation.assessment.sharper_grader'`); implemented;
  both GREEN in 0.10s. The dispute test asserts the end-to-end `update_state` → `Strength.weak`
  chain, guarding the strong-misclassification trap.
- Full suite: **94 passed, 3 skipped** (was 92+3; net +2 new tests); ruff format + check clean.

## 2026-06-23 — Step 5 Task 6: Wire `audit_sharper` into `assess` + strengthen/extend loop tests (TDD PASS)
- Added `from .sharper_grader import audit_sharper` import to
  `src/retnovation/assessment/judgment_loop.py`.
- Replaced the final `return Assessment(...)` with: build the instructor `assessment = Assessment(...)`,
  then `return audit_sharper(exp, assessment, model)` — so every call to `assess` now runs the
  independent blind grader pass before the Assessment reaches `update_state`.
- `run_session`, `STATE_UPDATERS`, the `cs_technical` scorer, and all other modules are unchanged.
  The `FakeModel.grade_sharper` default-agree behaviour preserves all cooperative/dry-run/CS paths.
- **Strengthened** `test_cooperative_student_converges`: added 2 assertions at the end verifying
  that the grader ran and confirmed both sharper calls (`len(a.sharper_audit) == 2`,
  `all(item.confirmed for item in a.sharper_audit)`).
- **Added** `test_grader_dispute_demotes_a_sharper_call_in_the_full_loop`: instructor closes both
  frames; the scripted `FakeModel` disputes `protect_the_core_lane`; asserts demoted frame is absent
  from `frames_closed_under_pressure` and the audit item has `confirmed=False`.
- TDD evidence: tests written first; RED — `assert 0 == 2` (sharper_audit empty, audit not wired)
  and `AssertionError` on dispute demotion. Implemented; GREEN in 0.14 s.
- Regression: `test_dry_run`, `test_orchestration`, `test_state`, `test_cs_dry_run` all pass.
- Full suite: **97 passed, 3 skipped** (was 96+3; net +1 new test, +2 assertions); ruff format + check clean.
- Files changed: `src/retnovation/assessment/judgment_loop.py`, `tests/test_judgment_loop.py`,
  `docs/DEVLOG.md`.

## 2026-06-23 — Step 5 COMPLETE: judgment loop hardened + BUILD ORDER FINISHED
- Built on branch `step5-harden-judgment-loop` via subagent-driven development (6 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review on opus).
  Spec: `docs/superpowers/specs/2026-06-23-harden-judgment-loop-design.md`; plan:
  `docs/superpowers/plans/2026-06-23-harden-judgment-loop.md`. Done autonomously under the user's
  standing delegation (user away; "quadruple-check / be mindful").
- **What shipped (open_ended assessor only; cs_technical + run_session untouched):**
  - **Regression stop** now fires on a genuine `"regressed"` outcome (previously in the enum but
    never triggered): the targeted frame is lowered one level (`_lower`), the backslide delta is
    recorded, and the loop stops — "more pushing harms". It ends NOT present_reasoned → scored weak.
  - **Distinct-target plateau**: `_select_target` gained an `exhausted` set and rotates to a fresh
    angle after a non-moving push; plateau fires on two distinct consecutive non-moves (or when no
    fresh angle remains while not converged), matching JudgmentLoop §2/§6. The loop provably
    terminates (convergence progress / exhausted-set shrinkage / `MAX_PUSHES` backstop). Cooperative
    path never rotates; bounded hard-wrong still pre-empts.
  - **Independent blind grader**: `assessment/sharper_grader.py::audit_sharper` re-judges each closed
    frame via a separate skeptical `Model.grade_sharper` (`content/prompts/grade_sharper.md`;
    blind — no instructor outcome in the prompt; assent/length ≠ sharper; conclusion-agnostic;
    `_require`-guarded). A disputed sharper is dropped from `frames_closed_under_pressure` AND its
    delta reverted, so `update_state` scores it **weak**, not strong (the strong-misclassification
    trap is genuinely closed). `Push` now carries the raw `response`; `assess` runs the loop then the
    audit. The grader gates "sharper" by a 2-vote (instructor + blind grader must agree).
- **Final adversarial review (opus): MERGE CLEAN** — all ten §9 invariants verified with live repros
  (loop termination; plateau + regression repros; disputed-sharper → `update_state` weak end-to-end
  incl. fresh-DB persistence; bounded hard-wrong pre-empts a simultaneous regression; grader blind;
  cooperative/CS/dry-run byte-stable). Two Minors, both DEFER (no live trigger): `audit_sharper`
  requires a "closed" push (unreachable from the loop); a disputed frame persists evidence
  `"unmoved"` (observability nit). Not fixed (mindful: no speculative churn for unreachable paths).
- **Verified:** full suite **97 passed, 3 skipped** (only skips = the three `@pytest.mark.live`
  smokes, no key); ruff format + check clean; confidentiality + `data/`-untracked clean.
- **BUILD ORDER COMPLETE.** All 5 locked build-order steps are done (harness → Veldra ingestion →
  experience generator + anti-label gate → CS checkable scorer → harden the judgment loop). The MVP
  harness is feature-complete.
- **NO "Step 6" in the locked build order.** What remains is post-MVP and needs the user's direction
  (it was not autonomously started, per "be mindful"): (a) **dogfood** — run it as user-zero over a
  semester to exercise the resistant paths live (the model over-refuses to role-play a caving student,
  so regression/plateau/bounded are proven only by authored fixtures; real users are the validation);
  (b) the deferred items, each its own spec → plan → build (MVP Scope §5): **blend** (needs two mature
  stateful projects), the **crystallization mirror** (needs an accreted ledger), richer experience
  types, the **business-executive** domain expansion (first per the locked decision), multi-user infra;
  (c) a **usable surface** for the dogfood (today it is a CLI + `pytest`). See MVP Scope §7 success
  criteria for what the harness now satisfies vs. what only real use can prove.

## 2026-06-23 — First founder dogfood (live Opus 4.8) + immersive-scenes design (branch immersive-scenes)
- Ran the first real user-zero dogfood: a turn-by-turn relay against live Opus 4.8 (a `/tmp` background
  driver doing file-IPC around the unchanged `run_session`; the seeded `data/retnovation.db` selected the
  founder `license_continuity` experience). Smoke-tested the relay plumbing first.
- **Dogfood surfaced friction** (the loop working as intended — use → notice → improve): the abstracted
  `license_continuity` prompt felt flat / not immersive, and selection shows no progression. Three distinct
  threads: (a) immersion/concrete prompts, (b) a progression/curriculum model in selection, (c) the
  intro/onboarding arc. User chose to brainstorm **(a) immersion** first.
- **Root cause:** the immersive flatness is a confidentiality artifact — the tracked rubric prompt is
  abstracted because the concrete Veldra specifics are gitignored; the corpus carries
  `owned_problem`/`why_owned`/`unlabeled` but NO student-facing prompt. The JudgmentLoop ReserveGrid anchor
  (concrete, named, numbered) is the immersion bar.
- **Design (spec `docs/superpowers/specs/2026-06-23-immersive-scenes-design.md`):** add a `Scene` (concrete
  `prompt` + a reusable `situation` block) to the gitignored corpus/seed; `select_experience` overrides the
  displayed prompt + attaches the scene when present (abstract stays the fallback); `AnthropicModel` weaves
  the situation into all three judgment-loop calls so the back-and-forth stays situated; **the moat holds
  over the concrete prompt** via a new `generator.validate_scene` (same anti-label checks on what the student
  actually sees). Corpus gains a nullable `scene_json` column (fresh-DB `_SCHEMA` + guarded `ADD COLUMN`
  migration, L-8). Founder/open_ended only; CS untouched. v1 drafts ONE scene (`license_continuity`) from the
  gitignored material so the next dogfood is immediately immersive; the rest stay abstract.
- Baseline before any code: 97 passed, 3 skipped; confidentiality `git ls-files` clean. Next: user review of
  the spec → `writing-plans` → subagent-driven TDD → final adversarial review (§9) → merge → re-dogfood.
- User approved the spec. Authored the plan `docs/superpowers/plans/2026-06-23-immersive-scenes.md` — 6
  subagent TDD tasks (types → persistence scene_json+migration → ingest threading → validate_scene →
  select_experience attach → model situation-weaving) + a controller-executed Final (author the confidential
  `license_continuity` scene into the gitignored seed, re-ingest, a gated tracked moat test, opus adversarial
  review). Plan self-reviewed: full spec coverage, no placeholders, type-consistent.
- Also captured (user idea, graded high-ROI): a **mined founder/exec case library** as the NEXT project after
  scenes — diversify the posture path beyond Veldra with real cases (Stripe…, later Dimon/Solomon/Lip-Bu Tan).
  Reframe: founder path has two content sources (the learner's owned ledger vs. a curated case library); mined
  cases fill the latter. Memory: `retnovation-case-library-idea`. Sequenced after immersive-scenes ships.

## 2026-06-23 — Immersive-scenes Task 1: Types — `Scene`, `CorpusEntry.scene`, `Experience.scene` (TDD PASS)
Added `Scene(BaseModel)` (`prompt`, `situation`) before `CorpusEntry`; `CorpusEntry.scene: Scene | None = None`; `Experience.scene: Scene | None = None` (runtime-only, after `checkable`). 98 passed, 3 skipped; ruff clean.

## 2026-06-23 — Immersive-scenes Task 2: Persistence — `scene_json` column + guarded migration + round-trip (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/persistence.py`.
- Extended `_SCHEMA` corpus table with `scene_json TEXT` (nullable) — fresh DBs get the column
  automatically (L-8).
- Added a guarded `ALTER TABLE corpus ADD COLUMN scene_json TEXT` migration in `Store.__init__`
  (after `executescript`/`commit`): reads `PRAGMA table_info(corpus)`, adds the column only if
  absent — idempotent; existing `data/retnovation.db` (and any pre-existing corpus table) is
  migrated transparently on first open.
- Updated `upsert_corpus`: inserts/updates `scene_json` via `entry.scene.model_dump_json()` or NULL.
- Updated `_corpus_row`: parses `scene_json` back with `Scene.model_validate_json` when non-NULL;
  returns `scene=None` for NULL rows — round-trip lossless.
- TDD evidence: wrote 2 failing tests first (RED — `AttributeError: 'NoneType' has no attribute
  'prompt'` on both); implemented; GREEN in 0.20 s. Existing 5 persistence tests unaffected.
- Full suite: **100 passed, 3 skipped** (was 98+3; net +2 new tests); ruff format + check clean.

## 2026-06-23 — Immersive-scenes Task 3: Ingest — `SeedEntry.scene` threads into the corpus (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/veldra_ingest.py`
  (`from .types import CorpusEntry, LedgerEntry, Scene`).
- Added `scene: Scene | None = None` field to `SeedEntry` — optional; existing seed YAMLs without
  a `scene:` key parse identically (Pydantic default None); idempotent ingest unchanged.
- Added `scene=s.scene` to the `CorpusEntry(...)` call inside `ingest`'s `upsert_corpus` invocation
  so the scene propagates from seed → corpus row (persisted by Task 2's `scene_json` column).
- TDD evidence: appended `test_seed_scene_threads_into_the_corpus` first; ran RED
  (`AttributeError: 'NoneType' object has no attribute 'prompt'` — `SeedEntry` silently dropped the
  `scene` kwarg before the field existed, so corpus `scene` was always None); implemented; GREEN.
- Full suite: **101 passed, 3 skipped** (was 100+3; net +1 new test); ruff format + check clean.
- Files changed: `src/retnovation/veldra_ingest.py`, `tests/test_ingestion.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 4: `generator.validate_scene` — the moat over the concrete prompt (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/generator.py`.
- Implemented `validate_scene(scene, rubric, *, framework_denylist, scaffold_denylist) -> None`
  immediately before `anti_label_gate`, reusing the existing helpers `_contains_phrase`,
  `_frame_trap_phrases`, `WRAPPER_WORDS`, and `GateError` — no duplicated logic.
- Guard order mirrors `anti_label_gate`: framework+frame/trap codes first, then scaffold denylist,
  then wrapper words; raises `GateError` on the first violation found.
- TDD evidence: appended `test_validate_scene_passes_clean_and_rejects_leaks` to
  `tests/test_generator.py` first; ran RED (`ImportError: cannot import name 'validate_scene'`);
  implemented; GREEN in 0.11 s. All four `GateError` branches exercised (framework, frame-code
  spaced, scaffold, wrapper).
- Full suite: **102 passed, 3 skipped** (was 101+3; net +1 new test); ruff format + check clean.
- Files changed: `src/retnovation/generator.py`, `tests/test_generator.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 5: `select_experience` attaches + moat-validates the corpus scene (TDD PASS)
- Added `_attach_scene(exp, corpus, root) -> Experience` helper to `src/retnovation/experience.py`:
  looks up the corpus entry for `exp.ledger_ref`; if the entry has a `scene` AND `exp.rubric` is
  not None (open_ended), calls `validate_scene` via local imports of `load_denylist`
  (content_loader) and `validate_scene` (generator) — the moat holds over what the student sees;
  then returns `exp.model_copy(update={"prompt": scene.prompt, "scene": scene})`.
  No scene, no corpus entry, or `exp.rubric is None` (cs_technical) → `exp` unchanged.
- Updated `select_experience`: captures the selector result as `exp`, passes it through
  `_attach_scene(exp, corpus, root)`, returns the result. `run_session`, the selectors, and
  all other modules are untouched.
- TDD evidence: appended two failing tests to `tests/test_experience.py` first:
  `test_select_experience_attaches_a_corpus_scene_and_overrides_prompt` (RED —
  `exp2.prompt` still the abstract prompt; `exp2.scene` is None) and
  `test_select_experience_without_a_scene_is_unchanged` (RED — would have passed coincidentally,
  but the first test failure confirms the feature is not yet wired). Implemented; both GREEN.
- Regression: `test_dry_run.py` and `test_orchestration.py` (corpus has no scenes) → experiences
  unchanged; both pass. Full suite: **104 passed, 3 skipped** (was 102+3; net +2 new tests);
  ruff format + check clean.
- Files changed: `src/retnovation/experience.py`, `tests/test_experience.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 6 review-fix: complete situation-weaving test coverage (additive tests only)
- Extended `test_situation_is_woven_in_when_a_scene_is_present` with a `classify_response` block (asserts `"mid-rollout"` reaches the system text); extended `test_no_scene_calls_omit_the_situation` with `classify_intake` + `classify_response` byte-stability assertions (assert `"Situation:"` absent). No production code changed. 11 model tests pass; ruff clean.

## 2026-06-23 — Immersive-scenes Task 6: `AnthropicModel` weaves `situation` into judgment-loop calls (TDD PASS)
- Added module-level helper `_situation_block(exp) -> str` to `src/retnovation/model.py` (near
  `_render_rubric`): guards `getattr(exp, "scene", None)` — returns `"\n\nSituation:\n{situation}"`
  when a scene is present, `""` otherwise. Safe on any experience type.
- Wove `_situation_block(exp)` into all three judgment-loop calls:
  - `classify_intake` system: `load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)`
  - `generate_push` user: replaced single `user = ...` line with `prefix`/`user` two-line version —
    `prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""`
    then `user = f"{prefix}Experience:\n..."`. No unused local variable (ruff clean).
  - `classify_response` system: inserted `_situation_block(exp)` between `load_prompt("response")`
    and the mode/binding-constraint/target-angle lines.
- Byte-stability: when `exp.scene` is None, all three calls produce NO `Situation:` text —
  identical to pre-Task-6 behaviour. `FakeModel` unchanged (scripted; scenes irrelevant).
- TDD evidence: appended `_exp_with_scene`, `test_situation_is_woven_in_when_a_scene_is_present`,
  `test_no_scene_calls_omit_the_situation` to `tests/test_anthropic_model.py` BEFORE implementing.
  `test_situation_is_woven_in_when_a_scene_is_present` RED (assert "mid-rollout" in call failed —
  situation not yet in call). Implemented; both tests GREEN; all 11 model tests pass.
- Full suite: **106 passed, 3 skipped** (was 104+3; net +2 new tests); ruff format + check clean.
- Files changed: `src/retnovation/model.py`, `tests/test_anthropic_model.py`, `docs/DEVLOG.md`.



