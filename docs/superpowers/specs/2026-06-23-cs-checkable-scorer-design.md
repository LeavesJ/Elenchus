# Step 4 — CS Checkable Scorer + `cs_technical` Domain-Path Selector

Date: 2026-06-23
Status: design (awaiting user review before plan)
Build order: #4 (after the harness, Veldra ingestion, and the experience generator + anti-label gate)

## 1. Goal

Implement the `cs_technical` regime end to end so a **second assessment regime runs
through the same six-link plumbing** as the founder open-ended path. This is the step that
proves the "pluggable by regime" claim (Build Brief #4, Complete Picture §12): the checkable
contrast that makes the open-ended half legible.

Two registered `NotImplementedError` seams are filled:

- `assessment/checkable_scorer.py::assess` — score correctness, read retrieval strength off
  performance.
- `generator.py::select_cs_technical` — the domain-path selector, ranking by **content-concept
  coverage** (never process-frame coverage).

Done = a CS dry-run acceptance test closes all six links (aim → core → experience → assessment
→ state → cadence → ↺) with no manual stitching, mirroring `tests/test_dry_run.py`, plus the
founder path unchanged.

## 2. Non-goals (YAGNI)

- No rich CS experience types (sims, generated question banks). A small authored set only.
- No CS expansion beyond one subpath (we author one: distributed-systems / consensus concepts).
- No anti-label gate over CS. CS is the **labeled, checkable** contrast; the anti-label gate is
  the open-ended moat and is deliberately *not* applied here (Complete Picture §15: CS is "the
  domain… the unlabeled condition is weakest").
- No crystallization mirror, no blend, no multi-user. All deferred per MVP Scope §5.
- No change to the judgment loop's behavior. Founder path is touched only where a shared
  contract widens (and is regression-tested to be byte-stable).

## 3. Doctrine constraints this must honor

- **L-1 / "doctrine as data":** CS concepts, questions, answer keys, the model-grader prompt,
  and the spacing policy are versioned content under `content/`, never hardcoded in `src/`.
- **Never collapse the two paths (Complete Picture §10):** founder process-frames and CS
  content-concepts are separate state, separate scheduling, separate selection. CS concepts do
  **not** enter the `frames` table; they live in the concept (spaced-index) state.
- **L-3 reversible decay, never deletion:** a missed CS concept is demoted/rescheduled (interval
  reset), its row is never deleted.
- **Retrieval strength is read off performance (MVP Scope §4, success criterion):** the spaced
  interval *is* the strength signal — correct lengthens it, a miss resets it.
- **Checkable means checkable:** the deterministic path scores correctness with no model call.
- Validate input at boundaries (the regime/payload invariant on `Experience`); keep files < 500
  lines; stage explicit paths; update `DEVLOG.md` in the same change.

## 4. Confirmed decisions (from brainstorming)

1. **Scoring: deterministic by default, model-graded optional per question.** Each question
   carries its own `check_type`. Deterministic questions never call the model; model-graded
   questions go through a gated live path (mock unit tests + a skipped live smoke), exactly like
   the judgment-loop adapter.
2. **CS content: generic, tracked in `content/`.** A non-confidential CS subpath
   (distributed-systems / consensus fundamentals) authored as versioned content. Each checkable
   experience anchors to a `cs_technical` ledger ref for provenance, but the questions are
   generic CS knowledge — nothing confidential is tracked.
3. **Architecture: Approach 1 — shared types, regime-dispatched behavior.** One `Experience`
   type and one orchestration loop, extended (not forked); behavior dispatches by regime through
   registries that mirror the existing `ASSESSORS` / `SELECTORS` pattern. (Approach 2, parallel
   CS types end to end, was rejected for weakening the "same plumbing" proof; Approach 3,
   generalize to a regime-agnostic tagged-union core, was rejected as YAGNI for two regimes.)

A note on the Step-3 handoff: it described CS as "content + a map + a registered selector + the
scorer," implying no engine change. That under-counted. Because the engine was built
open-ended-first (`Assessment` is judgment-loop-shaped, state moves only `frames`, `Experience`
requires a `Rubric`, the concept spaced-index is unpersisted), honoring "never collapse the two
paths" requires threading a concept-based state/scheduling path. The set below is the **bounded**
engine work needed — it adds a parallel path, it does not rewrite the loop.

## 5. Component design

### 5.1 Types (`types.py`)

New:

- `CheckType(str, Enum)`: `deterministic`, `model_graded`.
- `CheckableQuestion(BaseModel)`:
  - `question_id: str`
  - `concept: str` — the content-core concept this question tests (the spaced-index key)
  - `prompt: str` — the question text shown to the student
  - `check_type: CheckType`
  - `choices: list[str] = []` — optional MCQ options for presentation (empty = free response)
  - `answer_key: list[str] = []` — deterministic: acceptable normalized answers. model_graded:
    optional reference answer(s).
  - `criteria: str | None = None` — model_graded: what counts as correct (the grader rubric).
- `CheckableSet(BaseModel)`: `questions: list[CheckableQuestion]` (the CS analog of `Rubric`).
- `ConceptResult(BaseModel)`: `concept: str`, `question_id: str`, `correct: bool`,
  `check_type: CheckType`.
- `CheckableAssessment(BaseModel)`: `results: list[ConceptResult]`. (Sibling to `Assessment`;
  the CS scorer returns this. No `stop_reason`/`trajectory` — those are judgment-loop concepts.)
- `CheckableGrade(BaseModel)`: `correct: bool` — the model grader's verdict for one question.

Changed:

- `Experience`: `rubric: Rubric | None = None` (was required); add `checkable: CheckableSet |
  None = None`. A `model_validator` enforces the **regime/payload invariant** at the boundary:
  `open_ended` ⇒ `rubric` present and `checkable` is None; `cs_technical` ⇒ `checkable` present
  and `rubric` is None. Malformed experiences raise at construction.
- `Aim.content_core: list[str] | None = None` (widened from `None`).
- `Core.content_core: list[str] | None = None` (widened from `None`).
- `NextExperienceSpec.target_frames`: **kept by name**, but its docstring is widened to "target
  codes for the next experience — process frames for `open_ended`, content concepts for
  `cs_technical`." Rationale: renaming would touch the persisted queue column
  (`target_frames_json`) and risk an L-8-style fresh-vs-existing-DB divergence on the live local
  `data/retnovation.db`; the field is already regime-tagged by the spec's `regime`. Overload with
  a precise docstring, not a migration.

### 5.2 Content (new files under `content/`)

- `content/maps/cs_systems.yaml` — the CS domain-path content core:
  - `path_type: domain`
  - `content_core: [ ~6 concept codes ]` (e.g. `safety_vs_liveness`,
    `linearizability_vs_eventual`, `idempotency_under_retry`, `quorum_intersection`,
    `at_least_once_vs_exactly_once`, `partition_tolerance_tradeoff`). Generic CS knowledge.
- `content/maps/founder_ceo.yaml` — add `path_type: posture` (additive; existing keys unchanged).
- `content/checkables/*.yaml` — 2–3 checkable experiences, each:
  - `experience_id`, `ledger_ref: "veldra:<cs_problem>"` (provenance), `regime: cs_technical`,
    `checkable: { questions: [ … ] }`. At least one deterministic-MCQ question, at least one
    deterministic short-answer, and at least one `model_graded` free-response, so both scoring
    paths are exercised by real content. `concept` fields reference `cs_systems` content-core
    codes.
- `content/prompts/grade.md` — the model-grader doctrine prompt: grade strictly against the
  supplied `criteria`/`answer_key`; output `correct: bool`; do not reward fluency, length, or
  confidence; do not be lenient on a wrong-but-articulate answer.
- `content/cadence/spacing.yaml` — `initial_interval_days`, `ease_factor`, `min_interval_days`
  (policy as data, following the `content/gate/depth.yaml` precedent).

### 5.3 Content loader (`content_loader.py`)

- `load_content_map(name, root)` → reads a `path_type: domain` map, returns its `content_core`
  list. (`load_map` for `path_type: posture` stays as-is; it ignores the new optional
  `path_type` key on `founder_ceo.yaml`.)
- `load_checkable_experience(name, root)` / `load_checkable_library(root)` → read
  `content/checkables/*.yaml` into `Experience(regime=cs_technical, checkable=CheckableSet,
  rubric=None)`. Kept **separate** from `load_library` (open-ended rubrics) so the anti-label
  gate, which iterates `load_library`, never sees a CS experience.
- `load_spacing(root)` → returns the spacing policy (3 ints).
- `load_prompt("grade")` already works (generic prompt loader).

### 5.4 Checkable scorer (`assessment/checkable_scorer.py`)

`assess(exp, work, model) -> CheckableAssessment`:

```
for q in exp.checkable.questions:
    answer = work.respond(render(q))        # reuses the same Work channel as the judgment loop
    correct = score_question(q, answer, model)
    results.append(ConceptResult(concept=q.concept, question_id=q.question_id,
                                 correct=correct, check_type=q.check_type))
return CheckableAssessment(results=results)
```

- `score_question`:
  - `deterministic`: `normalize(answer) in {normalize(k) for k in q.answer_key}`. `normalize` =
    lowercase, strip, collapse internal whitespace, strip surrounding punctuation. No model call.
  - `model_graded`: `model.grade_answer(exp, q, answer).correct`.
- `render(q)`: the prompt plus, if `choices`, the enumerated options.
- Boundary validation: a `cs_technical` experience with `checkable is None`, or a deterministic
  question with an empty `answer_key`, raises a clear `ValueError` (a checkable with no key is
  not checkable). This is the L-8 lesson applied: fail loud rather than silently pass.

### 5.5 CS selector (`generator.py::select_cs_technical`)

`select_cs_technical(core, state, ledger, corpus, spec, root) -> Experience`:

- Load CS experiences via `load_checkable_library` (NOT `load_gated_library` — no anti-label
  gate for CS).
- Rank by **content-concept coverage** of the scheduler's targets: `concepts(exp) = {q.concept
  for q in exp.checkable.questions}`; coverage = `len(target_concepts ∩ concepts(exp))`.
  `target_concepts = spec.target_frames` (the overloaded "target codes") when a spec is given;
  cold start (no spec / empty targets) falls back to covering `core.content_core`, then
  tie-breaks by `experience_id` for determinism.
- Raise `GateError` (reused as the "no shippable experience" signal, matching
  `select_open_ended`) if the CS library is empty.
- The returned experience carries its own `ledger_ref` from its YAML (provenance binding,
  mirroring `select_open_ended`).

### 5.6 State (`state.py`)

- Existing `update_state(state, assessment, now, experience_id)` (open-ended, frames) unchanged.
- New `update_state_checkable(state, assessment: CheckableAssessment, now, experience_id,
  spacing)`:
  - Aggregate `results` by concept. A concept is **recalled** iff all its questions are correct;
    any miss → **missed** (strict; documented).
  - For each concept, update `state.declarative_seed[concept]` (`SpacedItem`):
    - new concept: `SpacedItem(concept, due=now + initial_interval, interval_days=initial)`.
    - recalled: `interval_days = max(min_interval, round(interval_days * ease_factor))`;
      `due = now + interval_days`.
    - missed: `interval_days = min_interval`; `due = now + min_interval` (reversible demotion —
      the row is updated, never deleted; L-3).
  - Retrieval strength is read off `interval_days` (longer = stronger). No `frames` are touched.
- `STATE_UPDATERS: dict[Regime, Callable]` registry (mirrors `ASSESSORS`/`SELECTORS`):
  `open_ended → update_state`, `cs_technical → update_state_checkable`. Orchestration dispatches
  through it.

### 5.7 Scheduler (`scheduler.py`)

`schedule_next(state, ledger, now, regime)` becomes regime-aware:

- `open_ended`: unchanged (targets weak → forming → soonest-due strong **frames**).
- `cs_technical`: targets **concepts** from `declarative_seed` — due concepts (`due <= now`)
  ordered by `due`, else the soonest-due concept; `target_frames` carries those concept codes;
  `regime=cs_technical`. `ledger_ref` is informational (the selector binds the chosen
  experience's own ref), so it stays `ledger[0].id if ledger else ""`.

### 5.8 Persistence (`persistence.py`)

- New table `concepts (concept TEXT PRIMARY KEY, due TEXT NOT NULL, interval_days INTEGER NOT
  NULL)` for `declarative_seed`.
- `load_state` also loads `declarative_seed` from `concepts`; `save_state` UPSERTs every
  `SpacedItem` (no delete — reversible). Frames I/O unchanged.
- The fresh-DB regression (L-8): the `concepts` table is created in `_SCHEMA`, so a fresh DB
  supports the CS path with no manual migration.

### 5.9 Model (`model.py`)

- `Model` Protocol gains `grade_answer(self, exp, question, answer) -> CheckableGrade`.
- `FakeModel`: scripted grades (a `grades: dict[question_id, list[CheckableGrade]]`, popped),
  so model-graded scoring is deterministic in tests.
- `AnthropicModel.grade_answer`: a `messages.parse` call against `claude-opus-4-8` (adaptive
  thinking, `effort=high`, no sampling params) with `output_format=CheckableGrade`; system =
  `load_prompt("grade")` + the question's `criteria`/`answer_key`; `_require` raises on refusal /
  empty (doctrine-critical: a grader that silently defaults would corrupt the strength read).

### 5.10 Onboarding (`aim.py`)

- `aim(posture)` for a domain path sets a low process dial (content axis maxed, process near
  empty — Complete Picture §10). Introduce `MIN_PROCESS_DIAL = 0`; `aim` chooses the dial by
  reading the map's `path_type` (`posture` → `MAX_PROCESS_DIAL`, `domain` → `MIN_PROCESS_DIAL`).
- `derive_core(aim, root)`:
  - posture path (`founder_ceo`): unchanged — `process_frames` + `declarative_seed` from the map.
  - domain path (`cs_systems`): `content_core = load_content_map(...)`; `process_frames = []`;
    `declarative_seed = content_core` (the CS declarative layer schedules on the concept index).

### 5.11 Orchestration (`orchestration.py`) + CLI (`cli.py`)

- `present_and_collect` becomes regime-aware: `open_ended` reads an opening then wires `respond`
  (unchanged); `cs_technical` returns `Work(opening="", respond=…)` (no wasted opening prompt —
  the scorer drives via `respond` per question).
- `run_session`: assessor return widens to `Assessment | CheckableAssessment`; state update
  dispatches via `STATE_UPDATERS[exp.regime]`; `schedule_next(..., exp.regime)` already passes
  the regime. Return type → `tuple[LearnerState, Assessment | CheckableAssessment]`.
- `cli.main`: print branch by regime — `open_ended` prints `stop_reason=…`; `cs_technical`
  prints `concepts_scored=… recalled=…`. `build_store` is **unchanged** (founder remains the
  default first experience); the CS regime is proven by the CS dry-run test, not the CLI default.

## 6. Data flow (CS session)

```
aim(cs_systems) → derive_core → Core(content_core, declarative_seed=concepts)
   ↓
Store.queue_pop → NextExperienceSpec(regime=cs_technical, target_frames=<concept codes>)
   ↓
select_experience → SELECTORS[cs_technical] → select_cs_technical (concept-coverage rank)
   ↓
present_and_collect (regime-aware) → Work
   ↓
get_assessor(cs_technical) → checkable_scorer.assess → CheckableAssessment(results)
   ↓
STATE_UPDATERS[cs_technical] → update_state_checkable → declarative_seed intervals move
   ↓
save_state (concepts table) ; schedule_next(cs_technical) → fresh cs spec queued ↺
```

## 7. Error handling

- Malformed `Experience` (regime/payload mismatch) → `ValidationError` at construction.
- Deterministic question with empty `answer_key` → `ValueError` (not checkable).
- Empty CS library → `GateError` (matches `select_open_ended`).
- Model grader refusal / empty → `ModelError` (no silent default).
- All deterministic CS scoring is model-free, so a missing API key never blocks a
  deterministic-only CS session.

## 8. Testing strategy (TDD, failing test first)

- `test_types.py`: new types; `Experience` regime/payload invariant (both bad directions raise).
- `test_content_loader.py`: `load_content_map` (CS core), `load_checkable_library`,
  `load_spacing`, founder map still loads with the new `path_type` key.
- `test_checkable_scorer.py`: deterministic correct/incorrect/normalization (whitespace, case,
  punctuation), MCQ, model_graded via `FakeModel`, mixed set; empty-answer-key raises;
  builds `CheckableAssessment`.
- `test_cs_selector.py`: concept-coverage ranking, cold-start fallback to `content_core`,
  determinism tie-break, binds own `ledger_ref`, empty library raises.
- `test_state.py`: `update_state_checkable` grows interval on recall, resets on miss, **never
  deletes** a concept row (reversible), strict per-concept aggregation; founder `update_state`
  regression unchanged.
- `test_scheduler.py`: `cs_technical` targets due/weakest concepts; `open_ended` unchanged.
- `test_persistence.py`: `concepts` round-trip (declarative_seed persists across reload),
  no-delete on demote; frames I/O unchanged.
- `test_anthropic_model.py`: `grade_answer` mock client; `test_live_model.py`: gated
  (`@pytest.mark.live`) grade smoke that skips with no key.
- `test_aim.py`: `derive_core` for the CS domain map → `content_core`, empty process_frames.
- `test_dispatch.py`: update — `cs_technical` assessor is now implemented (the existing
  `test_cs_technical_is_registered_but_unimplemented` flips to assert it scores).
- `test_cs_dry_run.py`: **acceptance** — real `Store`, CS content, a fixture student, no model
  for the deterministic path (and `FakeModel` for a model-graded variant). Assert: every question
  scored, concept index moved, concepts persisted on reload, a fresh `cs_technical`
  `NextExperienceSpec` queued, loop closed with no manual stitching.
- `test_orchestration.py` / `test_cli.py`: `run_session` CS path; `cli.main` CS print branch.

## 9. Adversarial review checklist (core-path; independent subagent before merge)

1. The two paths never collapse — CS concepts never enter `frames`; founder frames never enter
   `concepts`.
2. Deterministic scoring is sound — normalization is safe (no false positives/negatives on the
   authored set); no model call on the deterministic path.
3. Reversible decay — a missed concept is demoted, never deleted; `save_state` issues no DELETE.
4. Fresh-DB end to end (L-8) — a fresh-tempdir `Store` runs the CS dry-run with no raise; the
   `concepts` table exists; the CS library gates-free loads.
5. `Experience` invariant rejects both malformed directions.
6. Confidentiality — `git ls-files` clean (no Berkeley/Blueprint/Brief/pdf/`data/`); CS content
   is generic.
7. The anti-label gate is **not** applied to CS, and `load_library`/the gate never picks up a
   CS YAML.
8. Model-grader doctrine — strict, no leniency, `_require` guards refusal/empty.
9. Founder open-ended path is byte-stable (regression: `test_dry_run` and judgment-loop tests
   unchanged and green).
10. Loop closes; `schedule_next(cs_technical)` queues a real next experience.

## 10. Execution plan (subagent-driven development, mirroring Step 3)

- Branch `step4-cs-checkable-scorer` (already created).
- `writing-plans` decomposes this into right-sized TDD tasks (types → content → loaders →
  scorer → selector → state → scheduler → persistence → model grader → aim → orchestration/cli →
  CS dry-run). Each task: fresh implementer + independent task reviewer; reports under
  `.superpowers/sdd/` (gitignored, L-7); stage explicit paths only; `ruff format`/`ruff
  check`/`pytest` green; `DEVLOG.md` updated.
- Final whole-branch adversarial review against §9 before merge to `main`.

## 11. Open items resolved here (so the plan need not reopen them)

- CS subpath = distributed-systems / consensus (generic CS, adjacent to the builder's CTO
  depth). The user may swap the concept set on review.
- `target_frames` is overloaded (kept by name), not renamed (no persistence migration).
- Spacing policy lives in `content/cadence/spacing.yaml` (data, per the `depth.yaml` precedent).
- CS reuses the `Work` present channel (not a new collection abstraction) to maximize the
  "same plumbing" proof.
- `build_store`/CLI default stays founder-first; CS is proven by `test_cs_dry_run.py`.
