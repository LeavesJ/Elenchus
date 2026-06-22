# Retnovation Step 1 — The Harness on the Fixed Experience

- **Date:** 2026-06-22
- **Status:** Approved (brainstorming). Implementation plan to follow.
- **Sources:** Build Brief (build-order step 1); Loop v0.1 (typed interfaces — "build to
  these"); Berkeley Operating Guidebook §5–6 (doctrine); JudgmentLoop v0.1; FounderCEO
  Design v0.1; LiftTest EXP-001/002-003.

## 1. Goal
Wire the six links of the loop into one running cycle on a single fixed (seeded)
experience, with simple persistence and a simple scheduler. **Done = the Loop v0.1 dry
run closes end-to-end with no manual stitching between links.**

This step proves the plumbing and the typed interfaces. It is not the product shrunk
down; it is the skeleton everything else hangs on.

## 2. Scope
**In:** `types`; `persistence` (SQLite); `aim`/`core` (hardcoded `founder_ceo`);
`experience` loader (fixed); assessment dispatch + `judgment_loop` (current form);
`state` update + weak/forming/strong estimator; `scheduler`; `orchestration`; the
dry-run acceptance test; minimal content (one map + one rubric).

**Out:** experience generator + anti-label gate (step 3); full `checkable_scorer` —
stub raises `NotImplementedError` (step 4); regression/plateau stop hardening +
independent grader (step 5); Veldra ingestion (step 2); multi-user; calibrated strength
model.

## 3. Typed interfaces (`src/retnovation/types.py`) — from Loop v0.1
Modeled with pydantic v2.

- `Aim{ posture: "founder_ceo"|"cs_technical"; process_dial: int; content_core: None }`
- `Core{ process_frames: list[str]; declarative_seed: list[str]; content_core: None }`
- `Experience{ prompt: str; rubric: Rubric; ledger_ref: str; regime: Regime }`
  - `Rubric{ frames: list[Frame]; traps: list[Trap]; mode: Mode; binding_constraint: str|None }`
  - `Frame{ frame_code: str; frame_detail: str; paired_trap: str|None }`
  - `Trap{ trap_code: str; trap_detail: str }`
- `Assessment{ trajectory: list[Push]; frame_deltas: list[FrameDelta];
  frames_closed_under_pressure: list[str]; hard_wrong_flags: list[str]; stop_reason: StopReason }`
  - `Push{ target_code: str; kind: str; text: str; response_classification: str }`
  - `FrameDelta{ frame_code: str; before: FrameState; after: FrameState }`
- `LearnerState{ frames: dict[str, FrameStrength]; trap_gallery: dict[str, list[TrapOccurrence]];
  declarative_seed: dict[str, SpacedItem] }`
  - `FrameStrength{ strength: Strength; last_seen: datetime; due: datetime; last_evidence: str }`
- `LedgerEntry{ id: str; owned_problem: str; links_to_experiences: list[str] }`
- `NextExperienceSpec{ target_frames: list[str]; ledger_ref: str; regime: Regime }`

**Enums (`Literal`):** `Strength = weak|forming|strong`; `Regime = open_ended|cs_technical`;
`Mode = genuinely_open|bounded_error`; `FrameState = absent|present_asserted|present_reasoned`;
`TrapState = not_tripped|tripped|repaired`;
`StopReason = converged|bounded_error_violation|plateau|regression|budget`.

The **regime** is the per-experience assessor selector (Founder CEO experiences are
`open_ended`; CS experiences are `cs_technical`) — distinct from the onboarding posture.

## 4. Modules (one responsibility each)
- `orchestration.py` — `run_session(state, core, ledger) -> LearnerState`.
- `aim.py` — `aim() -> Aim` (hardcoded `founder_ceo`, `process_dial=MAX`),
  `derive_core(aim) -> Core` (from the curated map).
- `experience.py` — `select_experience(core, state, ledger) -> Experience`
  (MVP: returns the one fixed experience loaded from content).
- `assessment/__init__.py` — `ASSESSORS` registry + dispatch.
- `assessment/judgment_loop.py` — `assess(exp, work, model) -> Assessment` (open_ended).
- `assessment/checkable_scorer.py` — `assess(...)` stub, raises `NotImplementedError`.
- `state.py` — `update_state(state, assessment) -> LearnerState`; the weak/forming/strong estimator.
- `scheduler.py` — `schedule_next(state, ledger) -> NextExperienceSpec`.
- `persistence.py` — SQLite store: load/save state, ledger, queue.
- `content_loader.py` — load maps + rubrics from `content/*.yaml`.
- `model.py` — `Model` Protocol + a thin Opus 4.8 adapter. Tests inject a scripted fake;
  the real adapter is **not** exercised by the dry-run test.

## 5. Persistence (SQLite) — `persistence.py`
One DB file under `data/`. Tables:
- `frames(frame_code PK, strength, last_seen, due, last_evidence)`
- `trap_gallery(id PK, trap_code, experience_id, occurred_at, detail)`
- `declarative_seed(concept PK, schedule_json)`
- `ledger(id PK, owned_problem, links_json)`
- `queue(id PK, position, target_frames_json, ledger_ref, regime)`

**Decay = `UPDATE` of `strength`/`due`. Rows are never `DELETE`d** (Guidebook §5; lesson L-3).

## 6. Assessment dispatch + judgment loop
`ASSESSORS = {"open_ended": judgment_loop.assess, "cs_technical": checkable_scorer.assess}`;
Link 4 = `ASSESSORS[exp.regime](exp, work, model)`.

`judgment_loop` (current form): intake-classify → push loop (one rubric-anchored target
per cycle) → stop. **Sharper = a gap closed with a supplied mechanism** (absent →
`present_reasoned`, or a tripped trap repaired). Target order: tripped traps /
binding-constraint-adjacent first, then the most load-bearing absent frame. Disband rules
enforced: never name the frame, never hand the answer, assent/length ≠ sharper, the
conclusion is never graded. Stops `converged`/`bounded_error_violation`/`budget` are
trusted; `plateau`/`regression` exist but are flagged untested (step 5). Every push traces
to authored rubric codes. The model is called through the `Model` interface for classify +
push generation; tests use a scripted fake.

`checkable_scorer`: stub (`NotImplementedError`) until step 4.

## 7. State + estimator (`state.py`)
`update_state` moves each frame's strength on evidence: applied unprompted → `strong`;
closed under pressure → `forming`; failed to close → `weak`. Tripped traps are recorded in
`trap_gallery`. **On the open_ended path, never update from correctness** (L-4). The
estimator is the 3-level heuristic; the known sharp edge (calling `strong` off a single
unprompted use) is documented, not yet calibrated.

## 8. Scheduler (`scheduler.py`)
`schedule_next(state, ledger) -> NextExperienceSpec`: spaced reactivation for `weak`,
transfer (`forming` against a new ledger problem), decay (`strong` → longer interval).
Pushes the next spec onto the queue so the daily "what do I study" question disappears.

## 9. Orchestration — `run_session` (Loop v0.1 reference)
```
exp   = queue.pop() or select_experience(core, state, ledger)
work  = present_and_collect(exp)          # interactive OR fixture
a     = ASSESSORS[exp.regime](exp, work, model)
state = update_state(state, a)
queue.push(schedule_next(state, ledger))
persist(state, queue)
return state
```
`present_and_collect` has two modes: interactive (real user) and fixture (scripted
student) for the dry-run test.

## 10. Fixed experience + content
- `content/maps/founder_ceo.yaml` — `process_frames = [choose_the_failure_default_deliberately,
  lead_with_what_you_refuse_to_do, protect_the_core_lane]`;
  `declarative_seed = [reversible_vs_irreversible, build_vs_buy]`.
- `content/rubrics/veldra_licensing_continuity.yaml` — the curator rubric for the fixed
  experience (frames, traps, `mode=genuinely_open`, `binding_constraint=null`). The rubric
  format also supports `bounded_error` so the `sre_outage_gate` case
  (`distributes_known_invalid_work`) can drop in later as a second fixture.
- Ledger entry `veldra:licensing_continuity`: a **sanitized** owned-problem statement.
  Real/confidential specifics live in `data/` (gitignored), not in tracked content; full
  ledger seeding is step 2.

## 11. Acceptance — the dry run
`tests/test_dry_run.py`: one full `run_session` on the fixed experience with an authored
cooperative-student fixture and a scripted fake `Model`. Assert, with **no manual glue**:
1. the experience came off the queue;
2. `judgment_loop` returned a non-empty `trajectory` + `frame_deltas` tracing to rubric codes;
3. at least one frame strength moved in persisted state;
4. the queue holds a fresh `NextExperienceSpec`.

Plus unit tests per module: types round-trip; persistence CRUD + no-delete-on-decay;
estimator transitions (weak↔forming↔strong); scheduler output; dispatch by regime;
content_loader; judgment_loop stop conditions against fixtures.

## 12. Doctrine guardrails (must not contradict)
- Reversible decay, never deletion (§5).
- Open-ended state from rigor/trajectory, never correctness.
- Judgment-loop disband rules.
- Doctrine as data (maps/rubrics in `content/`, not `src/`).
- The fixed experience must pass the unlabeled-problem test (it requires working out what
  is asked and which tool applies, not type-recognition + procedure).

## 13. Honest gaps (deferred by design)
Generator + anti-label gate (step 3); `checkable_scorer` (step 4); resistant stops +
independent grader (step 5); Veldra ingestion (step 2); calibrated estimator. The fake
`Model` stands in for Opus 4.8 in tests; the real adapter is wired (consult the
`claude-api` reference for SDK usage + model id `claude-opus-4-8`) but not exercised by the
dry run.
