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
