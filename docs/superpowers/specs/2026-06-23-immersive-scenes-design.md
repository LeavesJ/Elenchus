# Immersive Scenes — Concrete Experience Prompts from the Corpus

Date: 2026-06-23
Status: design (awaiting user review before plan)
Origin: surfaced by the first founder dogfood — the abstracted `license_continuity` prompt felt
flat / not immersive. This is a post-MVP content-quality feature (not a locked build-order step).

## 1. Goal

Let a founder open-ended experience present a **concrete, situated scene** — a student-facing prompt
plus a reusable "situation" block (world, actors, constraints) the instructor draws on across every
push — sourced from the gitignored corpus, while the tracked content stays abstract. The dogfood on
the user's machine feels real (named actors, real stakes, ReserveGrid-anchor style); nothing
confidential is ever tracked.

This v1 builds the **mechanism** and drafts **one** concrete scene (`license_continuity`, the
experience the user just saw) so the next dogfood is immediately immersive. The other founder
experiences keep their abstract prompts (no scene → unchanged) until authored later.

## 2. Non-goals (YAGNI / be-mindful)

- **No concrete frame/trap details.** Frame/trap detail strings stay abstract internal grading
  anchors; the model still grounds its pushes because it sees the concrete prompt + situation.
- **No CS scenes.** cs_technical is a checkable question set — no scene. Scenes are founder /
  open_ended only.
- **No progression/curriculum model** and **no intro-arc redesign.** Those are the other two threads
  the dogfood surfaced; each is its own future spec. This spec is immersion only.
- **No re-authoring of the other founder scenes** in this build (only `license_continuity`).

## 3. Doctrine constraints this must honor

- **Confidentiality (L-2):** the concrete scene IS confidential Veldra content. It lives ONLY in the
  gitignored seed → gitignored `data/` corpus. Tracked content (`content/rubrics/*.yaml`) stays
  abstract. `git ls-files` confidential grep stays empty; `data/` untracked.
- **The unlabeled moat still holds over what the student SEES.** The concrete prompt is the student's
  actual prompt, so it must pass the same anti-label discipline as the abstract one — no named
  framework, no leaked frame/trap code, no type-hint scaffold, no cosmetic wrapper words. A pretty
  prompt that re-adds the label defeats the moat.
- **Abstract content is the fallback, never broken.** No scene → the experience behaves exactly as
  today. Every existing experience/test is unaffected.
- **L-1 doctrine as data:** scenes are versioned content (in the gitignored seed), not hardcoded in
  `src/`. **L-8:** the corpus-table schema change must work on a fresh DB AND migrate the existing
  `data/retnovation.db`.

## 4. Confirmed decisions (from brainstorming)

1. **Scene = concrete `prompt` + a `situation` block** (the richest of the three immersion levels —
   the instructor draws on the situation across every push, not just the opening).
2. **The corpus is the scene store** (reuse the existing gitignored per-`ledger_ref` confidential
   store, rather than a parallel gitignored content tree).
3. **Founder / open_ended only.**
4. **Author one scene now (`license_continuity`)**, drafted from the gitignored material
   (`veldra:license_fork_risk` ledger/corpus + the design docs), user refines; the rest stay abstract.

## 5. Component design

### 5.1 Types (`types.py`)

- `Scene(BaseModel)`: `prompt: str` (concrete student-facing), `situation: str` (world/actors/
  constraints, woven into the model calls).
- `CorpusEntry`: add `scene: Scene | None = None`.
- `SeedEntry` (in `veldra_ingest.py`): add `scene: Scene | None = None`.
- `Experience`: add a runtime-only `scene: Scene | None = None` (attached from the corpus at
  selection; never set from tracked content). Default None keeps the regime/payload invariant and all
  existing constructions valid.

### 5.2 Persistence (`persistence.py`)

- Corpus table gains a nullable `scene_json TEXT` column. Added to `_SCHEMA` (fresh DBs) AND a guarded
  migration in `Store.__init__`: if `pragma table_info(corpus)` lacks `scene_json`, `ALTER TABLE
  corpus ADD COLUMN scene_json TEXT` (idempotent; existing rows get NULL). This is the L-8 fix —
  fresh and existing DBs both work; the real `data/retnovation.db` is also rebuilt by re-ingest.
- `upsert_corpus`: writes `scene.model_dump_json()` or NULL. `load_corpus`/`get_corpus`: parse
  `Scene.model_validate_json(scene_json)` when present, else `None`.

### 5.3 Ingestion (`veldra_ingest.py`)

- `SeedEntry.scene` threads through `ingest` into `CorpusEntry.scene`. Idempotent UPSERT unchanged.
- The gitignored seed (`data/seed/veldra_ledger.yaml`) gains a `scene:` block on the
  `license_fork_risk` entry only (authored during implementation from the gitignored material).

### 5.4 Scene attach + moat guard (`experience.py` + `generator.py`)

- `select_experience`: after the selector returns `exp`, look up the corpus entry for
  `exp.ledger_ref`. If it carries a scene, **validate the scene prompt against the moat**, then
  return a copy with `prompt = scene.prompt` and `scene = scene`. No scene → `exp` unchanged.
- `generator.validate_scene(scene, rubric, framework_denylist, scaffold_denylist)` — reuses the
  gate's prompt-level helpers (`_contains_phrase`, `_frame_trap_phrases`, `WRAPPER_WORDS`) to check
  `scene.prompt` for: a named framework (denylist), a leaked frame/trap code (snake or spaced), a
  type-hint scaffold (denylist), or a cosmetic wrapper word. Raises `GateError` on any hit (fail
  loud — the concrete prompt the student sees must clear the same bar as the abstract one). The
  selector loads the denylists via the existing `load_denylist`.

### 5.5 Model grounding (`model.py`)

- `AnthropicModel` weaves `exp.scene.situation` into its three judgment-loop calls when a scene is
  present: `classify_intake` (system context), `generate_push` (a `Situation:` block before the
  experience/angle), `classify_response` (system context). The concrete `exp.prompt` already flows
  through `generate_push`. `FakeModel` ignores scenes (scripted) — unit tests are unaffected.
- A small helper renders the situation prefix only when `exp.scene` is set; absent → byte-identical
  to today's prompts.

### 5.6 Content (the one authored scene)

- During implementation, draft a concrete `scene` (prompt + situation) for `license_fork_risk` into
  the gitignored seed, sourced from its real `owned_problem`/`why_owned`/`unlabeled` + the gitignored
  design docs (the Blueprint / JudgmentLoop ReserveGrid-anchor style). Re-ingest to populate the
  corpus. The prompt must clear `validate_scene` against the `license_continuity` rubric.

## 6. Data flow (founder session with a scene)

```
select_experience → selector returns abstract exp (rubric, abstract prompt)
   → corpus[exp.ledger_ref].scene present? → validate_scene(prompt) (fail loud if it leaks)
                                            → exp' = exp.copy(prompt=scene.prompt, scene=scene)
   → present(exp')  → student sees the CONCRETE prompt
   → judgment loop: AnthropicModel weaves scene.situation into intake/push/response
     so the back-and-forth stays situated → audited Assessment (unchanged downstream)
```

No scene → `exp` unchanged → identical to today.

## 7. Error handling

- A scene prompt that leaks (framework / frame-code / scaffold / wrapper) → `GateError` at attach
  (the moat fails loud; a bad immersive prompt never reaches a student).
- Missing/None scene → silent fallback to the abstract prompt (the common case for un-authored
  experiences).
- The migration is idempotent (guarded ADD COLUMN); re-running `Store(...)` is safe.

## 8. Testing strategy (TDD)

- `test_types.py`: `Scene`; `CorpusEntry.scene`/`Experience.scene` optional defaults.
- `test_persistence.py`: corpus scene round-trip (UPSERT + load); a corpus row with no scene loads
  `scene=None`; guarded migration adds `scene_json` to a table created without it.
- `test_ingestion.py`: `SeedEntry.scene` threads into the corpus; a seed without a scene → `None`.
- `test_generator.py`: `validate_scene` passes a clean concrete prompt and raises `GateError` on a
  framework name, a leaked frame/trap code, a scaffold phrase, and a wrapper word.
- `test_experience.py`: `select_experience` overrides `prompt` + attaches `scene` when the corpus has
  one (and validates it); no scene → `exp` unchanged (regression).
- `test_anthropic_model.py`: with a scene, `generate_push`/`classify_intake`/`classify_response`
  include the situation in the call; without a scene, the calls are byte-identical to today.
- `test_dry_run.py` / `test_orchestration.py`: stay green (FakeModel ignores scenes; corpus in those
  tests has no scenes → fallback).
- Gated (data/-present) `test_seeded_license_scene_clears_the_moat`: the authored `license_fork_risk`
  scene loads and passes `validate_scene` against its rubric (skipif `data/retnovation.db` absent).

## 9. Adversarial review checklist (core-path; independent subagent before merge)

1. Confidentiality: scenes live only in gitignored seed/`data/`; `git ls-files` confidential grep
   empty; the authored `license_continuity` scene is NOT tracked.
2. The moat holds over the concrete prompt: `validate_scene` actually rejects framework names, frame/
   trap leaks (snake + spaced), scaffolds, and wrapper words; the authored scene passes it.
3. Fallback byte-stability: no-scene experiences and all FakeModel tests behave exactly as before;
   the model prompts are byte-identical without a scene.
4. Migration (L-8): fresh DB has `scene_json`; an existing corpus table without it is migrated;
   round-trip is lossless; no scene → NULL → `None`.
5. The scene is runtime-only on `Experience` (never set from tracked content); selection determinism
   and the regime/payload invariant are intact.
6. Situation grounding reaches all three judgment-loop model calls when present; the disband rule
   still holds (the situation/ prompt never names a frame — covered by validate_scene).
7. CS path untouched; `run_session`/`STATE_UPDATERS` unchanged.

## 10. Execution plan (subagent-driven development, mirroring prior steps)

- Branch `immersive-scenes` (created).
- `writing-plans` → right-sized TDD tasks (types → persistence scene_json + migration → ingest
  threading → validate_scene → select_experience attach → model situation-weaving → author the
  `license_continuity` scene + re-ingest + the gated moat test). Each task: fresh implementer +
  independent reviewer; reports under `.superpowers/sdd/` (L-7); explicit-path staging; ruff +
  pytest green; `DEVLOG.md` updated.
- Final whole-branch adversarial review (opus) against §9 before merge.
- Then: re-run the live dogfood to feel the concrete `license_continuity` scene.

## 11. Open items resolved here

- Scene = prompt + situation; stored on the corpus; founder/open_ended only.
- The concrete prompt is gated by `validate_scene` at attach (the moat covers what the student sees).
- Schema change via `_SCHEMA` + a guarded `ADD COLUMN` migration (fresh + existing DBs).
- Author `license_continuity` only this build, from the gitignored material; others stay abstract.
