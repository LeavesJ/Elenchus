# Immersive Scenes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a founder open-ended experience present a concrete, situated scene (prompt + situation) sourced from the gitignored corpus, while tracked content stays abstract — so the dogfood feels real and nothing confidential is tracked.

**Architecture:** A `Scene` (concrete `prompt` + `situation`) lives on the gitignored `CorpusEntry`. `select_experience` validates the scene against the anti-label moat, then overrides the displayed prompt + attaches the scene. `AnthropicModel` weaves the `situation` into its three judgment-loop calls when a scene is present. No scene → byte-identical to today. Spec: `docs/superpowers/specs/2026-06-23-immersive-scenes-design.md`.

**Tech Stack:** Python ≥3.12, pydantic ≥2, pyyaml, anthropic SDK (lazy), pytest, ruff. Run via the project venv: `source .venv/bin/activate`.

## Global Constraints

- **Venv:** all `python`/`pytest`/`ruff` after `source .venv/bin/activate`.
- **ruff:** `line-length = 100`; every commit runs `ruff format .` then `ruff check .`, both clean.
- **TDD:** failing test first, watch it fail, minimal implementation, watch it pass, commit.
- **Commits:** NEVER add a `Co-Authored-By` trailer. Stage explicit paths only — never `git add -A`/`.`/`-f`.
- **DEVLOG:** every task appends a `docs/DEVLOG.md` entry in the same commit.
- **Confidentiality (L-2):** scenes are confidential — they live ONLY in the gitignored seed → `data/` corpus, NEVER in tracked content. `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` stays empty; `data/` untracked. The authored `license_continuity` scene is NOT committed.
- **The moat holds over the concrete prompt:** a scene's `prompt` must pass the same anti-label checks (no named framework, no leaked frame/trap code, no type-hint scaffold, no cosmetic wrapper word) as the abstract one — `validate_scene` fails loud.
- **Fallback byte-stability:** no scene → the experience and all model prompts behave exactly as today. Scenes are founder / open_ended only; CS untouched; `run_session`/`STATE_UPDATERS` unchanged.
- **L-8 migration:** the corpus `scene_json` column must work on a fresh DB AND migrate the existing `data/retnovation.db`.
- Branch: `immersive-scenes` (created off `main`).
- Baseline before Task 1: `pytest -q` = 97 passed, 3 skipped.

---

## File Structure

- `src/retnovation/types.py` — modify: `Scene`; `CorpusEntry.scene`; `Experience.scene`.
- `src/retnovation/persistence.py` — modify: `scene_json` column + guarded migration + scene I/O.
- `src/retnovation/veldra_ingest.py` — modify: `SeedEntry.scene` threads into the corpus.
- `src/retnovation/generator.py` — modify: `validate_scene`.
- `src/retnovation/experience.py` — modify: `select_experience` attaches + validates a scene.
- `src/retnovation/model.py` — modify: `AnthropicModel` weaves `situation` into its 3 calls.
- Tests: extend `test_types.py`, `test_persistence.py`, `test_ingestion.py`, `test_generator.py`, `test_experience.py`, `test_anthropic_model.py`.
- Final (controller): the gitignored `data/seed/veldra_ledger.yaml` gains a `scene` on `license_fork_risk`; re-ingest; a gated tracked moat test.

---

### Task 1: Types — `Scene`, `CorpusEntry.scene`, `Experience.scene`

**Files:**
- Modify: `src/retnovation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces:
  - `Scene(BaseModel)`: `prompt: str`, `situation: str`.
  - `CorpusEntry.scene: Scene | None = None`.
  - `Experience.scene: Scene | None = None` (runtime-only; never set from tracked content).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_types.py`:

```python
def test_scene_and_corpus_experience_scene_fields():
    from retnovation.types import (
        CheckableSet,
        CorpusEntry,
        Experience,
        Frame,
        Mode,
        Regime,
        Rubric,
        Scene,
        Trap,
    )

    sc = Scene(prompt="A concrete, situated decision.", situation="The world, the actors, the stakes.")
    assert sc.prompt and sc.situation

    ce = CorpusEntry(ledger_ref="veldra:x", domain="founder_ceo", why_owned="stakes",
                     unlabeled="unlabeled", provenance="docs/X", corpus_pointers=[])
    assert ce.scene is None  # default
    ce2 = CorpusEntry(ledger_ref="veldra:y", domain="founder_ceo", why_owned="stakes",
                      unlabeled="unlabeled", provenance="docs/Y", corpus_pointers=[], scene=sc)
    assert ce2.scene.prompt == "A concrete, situated decision."

    exp = Experience(
        experience_id="e", prompt="abstract", ledger_ref="veldra:y", regime=Regime.open_ended,
        rubric=Rubric(frames=[Frame(frame_code="f", frame_detail="d", paired_trap="t")],
                      traps=[Trap(trap_code="t", trap_detail="d")], mode=Mode.genuinely_open))
    assert exp.scene is None  # default; runtime-only
    assert exp.model_copy(update={"scene": sc}).scene.situation == "The world, the actors, the stakes."
    # CheckableSet import unused-guard: keep regimes coherent (CS experiences never get a scene)
    assert CheckableSet(questions=[]).questions == []
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q`
Expected: FAIL (ImportError on `Scene`).

- [ ] **Step 3: Implement in `src/retnovation/types.py`.**

Add the `Scene` model (place near `CorpusEntry`):

```python
class Scene(BaseModel):
    prompt: str
    situation: str
```

Add `scene` to `CorpusEntry`:

```python
class CorpusEntry(BaseModel):
    ledger_ref: str
    domain: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)
    scene: Scene | None = None
```

Add `scene` to `Experience` (after `checkable`):

```python
    scene: Scene | None = None
```

(`Scene` must be defined before `CorpusEntry` and `Experience` reference it; `from __future__ import annotations` is already at the top, so definition order is flexible, but place `Scene` above both for clarity.)

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite 97 passed + new test, 3 skipped (defaults keep existing constructions valid); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): Scene + CorpusEntry.scene + Experience.scene"
```

---

### Task 2: Persistence — `scene_json` column, migration, scene I/O

**Files:**
- Modify: `src/retnovation/persistence.py`
- Test: `tests/test_persistence.py`

**Interfaces:**
- Consumes: `Scene`, `CorpusEntry.scene` (Task 1).
- Produces: corpus `scene_json TEXT` column (fresh-DB schema + guarded `ADD COLUMN` migration); `upsert_corpus`/`load_corpus`/`get_corpus` round-trip `CorpusEntry.scene`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_persistence.py`:

```python
def test_corpus_scene_roundtrip_and_none_default(tmp_path):
    from retnovation.types import CorpusEntry, Scene

    s = Store(tmp_path / "sc.db")
    s.upsert_corpus(CorpusEntry(ledger_ref="veldra:a", domain="founder_ceo", why_owned="stakes",
                                unlabeled="u", provenance="p", corpus_pointers=[],
                                scene=Scene(prompt="concrete", situation="world")))
    s.upsert_corpus(CorpusEntry(ledger_ref="veldra:b", domain="founder_ceo", why_owned="stakes",
                                unlabeled="u", provenance="p", corpus_pointers=[]))  # no scene
    loaded = Store(tmp_path / "sc.db")
    assert loaded.get_corpus("veldra:a").scene.prompt == "concrete"
    assert loaded.get_corpus("veldra:a").scene.situation == "world"
    assert loaded.get_corpus("veldra:b").scene is None


def test_corpus_scene_column_is_migrated_onto_an_old_table(tmp_path):
    import sqlite3

    from retnovation.types import CorpusEntry, Scene

    db = tmp_path / "old.db"
    # an OLD corpus table without scene_json
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE corpus (ledger_ref TEXT PRIMARY KEY, domain TEXT NOT NULL, "
        "why_owned TEXT NOT NULL, unlabeled TEXT NOT NULL, provenance TEXT NOT NULL, "
        "corpus_pointers_json TEXT NOT NULL)"
    )
    con.commit()
    con.close()
    # opening via Store migrates the table; a scene then round-trips
    s = Store(db)
    s.upsert_corpus(CorpusEntry(ledger_ref="veldra:a", domain="founder_ceo", why_owned="s",
                                unlabeled="u", provenance="p", corpus_pointers=[],
                                scene=Scene(prompt="c", situation="w")))
    assert Store(db).get_corpus("veldra:a").scene.prompt == "c"
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_persistence.py -q`
Expected: FAIL (`CorpusEntry.scene` not persisted → `None`; or migration missing → `sqlite3.OperationalError` on the `scene_json` column).

- [ ] **Step 3: Implement in `src/retnovation/persistence.py`.**

Add `Scene` to the types import. Add `scene_json TEXT` to the corpus table in `_SCHEMA`:

```python
CREATE TABLE IF NOT EXISTS corpus (
  ledger_ref TEXT PRIMARY KEY, domain TEXT NOT NULL, why_owned TEXT NOT NULL,
  unlabeled TEXT NOT NULL, provenance TEXT NOT NULL, corpus_pointers_json TEXT NOT NULL,
  scene_json TEXT);
```

In `Store.__init__`, after `self._db.executescript(_SCHEMA)` and its `commit()`, add the guarded migration (idempotent; existing tables get the column, existing rows get NULL):

```python
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(corpus)")}
        if "scene_json" not in cols:
            self._db.execute("ALTER TABLE corpus ADD COLUMN scene_json TEXT")
            self._db.commit()
```

Update `upsert_corpus` to write `scene_json`:

```python
    def upsert_corpus(self, entry: CorpusEntry) -> None:
        self._db.execute(
            "INSERT INTO corpus(ledger_ref,domain,why_owned,unlabeled,provenance,"
            "corpus_pointers_json,scene_json) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(ledger_ref) DO UPDATE SET "
            "domain=excluded.domain,why_owned=excluded.why_owned,unlabeled=excluded.unlabeled,"
            "provenance=excluded.provenance,corpus_pointers_json=excluded.corpus_pointers_json,"
            "scene_json=excluded.scene_json",
            (
                entry.ledger_ref,
                entry.domain,
                entry.why_owned,
                entry.unlabeled,
                entry.provenance,
                json.dumps(entry.corpus_pointers),
                entry.scene.model_dump_json() if entry.scene else None,
            ),
        )
        self._db.commit()
```

Update `_corpus_row` to parse `scene_json`:

```python
    @staticmethod
    def _corpus_row(r: sqlite3.Row) -> CorpusEntry:
        scene_json = r["scene_json"]
        return CorpusEntry(
            ledger_ref=r["ledger_ref"],
            domain=r["domain"],
            why_owned=r["why_owned"],
            unlabeled=r["unlabeled"],
            provenance=r["provenance"],
            corpus_pointers=json.loads(r["corpus_pointers_json"]),
            scene=Scene.model_validate_json(scene_json) if scene_json else None,
        )
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_persistence.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/persistence.py tests/test_persistence.py docs/DEVLOG.md
git commit -m "feat(persistence): corpus scene_json column + guarded migration + round-trip"
```

---

### Task 3: Ingestion — `SeedEntry.scene` threads into the corpus

**Files:**
- Modify: `src/retnovation/veldra_ingest.py`
- Test: `tests/test_ingestion.py`

**Interfaces:**
- Consumes: `Scene` (Task 1); `upsert_corpus` scene round-trip (Task 2).
- Produces: `SeedEntry.scene: Scene | None = None`; `ingest` passes it into `CorpusEntry.scene`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_ingestion.py`:

```python
def test_seed_scene_threads_into_the_corpus(tmp_path):
    from retnovation.persistence import Store
    from retnovation.types import Scene
    from retnovation.veldra_ingest import SeedEntry, ingest

    store = Store(tmp_path / "ing.db")
    seeds = [
        SeedEntry(slug="with_scene", domain="founder_ceo", owned_problem="op", why_owned="w",
                  unlabeled="u", provenance="p",
                  scene=Scene(prompt="concrete prompt", situation="the world")),
        SeedEntry(slug="no_scene", domain="founder_ceo", owned_problem="op", why_owned="w",
                  unlabeled="u", provenance="p"),
    ]
    ingest(store, seeds)
    assert store.get_corpus("veldra:with_scene").scene.prompt == "concrete prompt"
    assert store.get_corpus("veldra:no_scene").scene is None
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_ingestion.py -q`
Expected: FAIL (`SeedEntry` has no `scene`, or the corpus scene is `None`).

- [ ] **Step 3: Implement in `src/retnovation/veldra_ingest.py`.**

Add `Scene` to the types import (`from .types import CorpusEntry, LedgerEntry, Scene`). Add `scene` to `SeedEntry`:

```python
class SeedEntry(BaseModel):
    slug: str
    domain: str
    owned_problem: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)
    scene: Scene | None = None
```

Pass it through in `ingest`'s `upsert_corpus` call:

```python
        store.upsert_corpus(
            CorpusEntry(
                ledger_ref=ref,
                domain=s.domain,
                why_owned=s.why_owned,
                unlabeled=s.unlabeled,
                provenance=s.provenance,
                corpus_pointers=s.corpus_pointers,
                scene=s.scene,
            )
        )
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_ingestion.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/veldra_ingest.py tests/test_ingestion.py docs/DEVLOG.md
git commit -m "feat(ingest): SeedEntry.scene threads into the corpus"
```

---

### Task 4: `generator.validate_scene` — the moat guard over the concrete prompt

**Files:**
- Modify: `src/retnovation/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: `Scene` (Task 1); existing `_contains_phrase`, `_frame_trap_phrases`, `WRAPPER_WORDS`, `GateError`.
- Produces: `validate_scene(scene, rubric, framework_denylist, scaffold_denylist) -> None` — raises `GateError` if `scene.prompt` names a framework, leaks a frame/trap code, contains a scaffold phrase, or contains a cosmetic wrapper word.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_generator.py`:

```python
def test_validate_scene_passes_clean_and_rejects_leaks():
    from retnovation.generator import GateError, validate_scene
    from retnovation.types import Scene

    rubric = _exp().rubric  # frames lead_with_what_you_refuse_to_do, protect_the_core_lane
    kw = dict(framework_denylist=["swot", "five forces"], scaffold_denylist=["this is a", "apply the"])

    # clean concrete prompt: no framework, no frame leak, no scaffold, no wrapper
    validate_scene(Scene(prompt="A same-day call forces a real trade-off.", situation="w"),
                   rubric, **kw)  # no raise

    import pytest

    with pytest.raises(GateError):  # named framework
        validate_scene(Scene(prompt="Run a SWOT and decide.", situation="w"), rubric, **kw)
    with pytest.raises(GateError):  # leaked frame code (spaced)
        validate_scene(Scene(prompt="Lead with what you refuse to do.", situation="w"), rubric, **kw)
    with pytest.raises(GateError):  # type-hint scaffold
        validate_scene(Scene(prompt="This is a tradeoff problem.", situation="w"), rubric, **kw)
    with pytest.raises(GateError):  # cosmetic wrapper
        validate_scene(Scene(prompt="Keep your streak and decide.", situation="w"), rubric, **kw)
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_generator.py::test_validate_scene_passes_clean_and_rejects_leaks -q`
Expected: FAIL (ImportError on `validate_scene`).

- [ ] **Step 3: Implement in `src/retnovation/generator.py`** — add `Scene` to the types import, then add:

```python
def validate_scene(
    scene: Scene,
    rubric: Rubric,
    *,
    framework_denylist: list[str],
    scaffold_denylist: list[str],
) -> None:
    """The concrete prompt the student SEES must clear the same anti-label bar as the abstract
    one: no named framework, no leaked frame/trap code, no type-hint scaffold, no wrapper word."""
    prompt_lc = scene.prompt.lower()
    banned = [t.lower() for t in framework_denylist] + _frame_trap_phrases(rubric)
    if any(_contains_phrase(prompt_lc, p) for p in banned):
        raise GateError("scene prompt names a framework or leaks a frame/trap code")
    if any(_contains_phrase(prompt_lc, p) for p in scaffold_denylist):
        raise GateError("scene prompt contains a type-hint scaffold")
    if any(w in prompt_lc for w in WRAPPER_WORDS):
        raise GateError("scene prompt contains a cosmetic wrapper word")
```

(Add `Scene` to the existing `from .types import (...)` line in `generator.py`.)

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_generator.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/generator.py tests/test_generator.py docs/DEVLOG.md
git commit -m "feat(generator): validate_scene holds the moat over the concrete prompt"
```

---

### Task 5: `select_experience` — attach + validate the scene

**Files:**
- Modify: `src/retnovation/experience.py`
- Test: `tests/test_experience.py`

**Interfaces:**
- Consumes: `validate_scene` (Task 4); `CorpusEntry.scene`/`Experience.scene` (Task 1); `load_denylist` (existing).
- Produces: `select_experience` returns an experience whose `prompt` is overridden + `scene` attached when the corpus has a scene for its `ledger_ref` (validated first); no scene → unchanged.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_experience.py`:

```python
def test_select_experience_attaches_a_corpus_scene_and_overrides_prompt(tmp_path):
    from retnovation.types import CorpusEntry, NextExperienceSpec, Regime, Scene

    store = Store(tmp_path / "sc.db")
    _seed_corpus(store)
    # attach a clean scene to the founder experience that will be selected
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    ref = exp.ledger_ref
    store.upsert_corpus(
        CorpusEntry(ledger_ref=ref, domain="founder_ceo", why_owned="real stakes",
                    unlabeled="genuinely unlabeled", provenance="synthetic-test", corpus_pointers=[],
                    scene=Scene(prompt="A same-day call forces a real trade-off.",
                                situation="A long client mid-rollout; a guarantee under pressure."))
    )
    exp2 = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp2.prompt == "A same-day call forces a real trade-off."  # concrete override
    assert exp2.scene is not None and "mid-rollout" in exp2.scene.situation


def test_select_experience_without_a_scene_is_unchanged(tmp_path):
    from retnovation.types import NextExperienceSpec, Regime

    store = Store(tmp_path / "ns.db")
    _seed_corpus(store)  # corpus has no scenes
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp.scene is None
    assert exp.prompt  # the abstract content prompt, unchanged
```

(`test_experience.py` already imports `Store`, `aim`, `derive_core`, `select_experience`, `LearnerState`, and defines `_seed_corpus`.)

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_experience.py::test_select_experience_attaches_a_corpus_scene_and_overrides_prompt -q`
Expected: FAIL (`exp2.prompt` is still the abstract prompt; `exp2.scene` is `None`).

- [ ] **Step 3: Implement in `src/retnovation/experience.py`.**

Add the import for `load_denylist` and the `Path` is already imported. Add a helper + call it at the end of `select_experience`:

```python
def _attach_scene(exp: Experience, corpus: list[CorpusEntry], root: Path | None) -> Experience:
    entry = next((c for c in corpus if c.ledger_ref == exp.ledger_ref), None)
    if entry is None or entry.scene is None or exp.rubric is None:
        return exp  # no scene, or a non-open_ended (no rubric) experience → unchanged
    from .content_loader import load_denylist
    from .generator import validate_scene

    validate_scene(
        entry.scene,
        exp.rubric,
        framework_denylist=load_denylist("framework_denylist", root),
        scaffold_denylist=load_denylist("scaffold_denylist", root),
    )
    return exp.model_copy(update={"prompt": entry.scene.prompt, "scene": entry.scene})
```

Update `select_experience` to attach the scene before returning:

```python
def select_experience(
    core: Core,
    state: LearnerState,
    ledger: list[LedgerEntry],
    corpus: list[CorpusEntry],
    spec: NextExperienceSpec | None = None,
    root: Path | None = None,
) -> Experience:
    regime = spec.regime if spec is not None else Regime.open_ended
    exp = SELECTORS[regime](core, state, ledger, corpus, spec, root)
    return _attach_scene(exp, corpus, root)
```

- [ ] **Step 4: Run to verify pass + full suite (incl. dry-run/orchestration regression)**

Run: `source .venv/bin/activate && pytest tests/test_experience.py tests/test_dry_run.py tests/test_orchestration.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS — the override + attach work; no-scene corpus (dry_run/orchestration) → experiences unchanged; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/experience.py tests/test_experience.py docs/DEVLOG.md
git commit -m "feat(experience): attach + moat-validate a corpus scene at selection"
```

---

### Task 6: `AnthropicModel` weaves the `situation` into the judgment-loop calls

**Files:**
- Modify: `src/retnovation/model.py`
- Test: `tests/test_anthropic_model.py`

**Interfaces:**
- Consumes: `Experience.scene` (Task 1).
- Produces: `classify_intake`, `generate_push`, `classify_response` include `exp.scene.situation` when a scene is present; byte-identical (no `Situation:` text) when absent.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_anthropic_model.py`:

```python
def _exp_with_scene():
    from retnovation.types import Scene

    return _exp().model_copy(update={
        "prompt": "A same-day call forces a real trade-off.",
        "scene": Scene(prompt="A same-day call forces a real trade-off.",
                       situation="A long client is mid-rollout; a guarantee is under pressure."),
    })


def test_situation_is_woven_in_when_a_scene_is_present():
    # generate_push includes the situation (user/system blob)
    client = _Client(create_result=_Resp(content=[_TextBlock("What do you give up?")]))
    AnthropicModel(client=client).generate_push(_exp_with_scene(), "frame", "protect_the_core_lane")
    call = client.messages.create_calls[0]
    assert "mid-rollout" in _system_text(call) + " " + _user_text(call)

    # classify_intake includes the situation (system context)
    wire = _Wire(frames=[_Item("protect_the_core_lane", FrameState.present_reasoned)], traps=[])
    c2 = _Client(parse_result=_Resp(parsed_output=wire))
    AnthropicModel(client=c2).classify_intake(_exp_with_scene(), "opening")
    assert "mid-rollout" in _system_text(c2.messages.parse_calls[0])


def test_no_scene_calls_omit_the_situation():
    client = _Client(create_result=_Resp(content=[_TextBlock("push")]))
    AnthropicModel(client=client).generate_push(_exp(), "frame", "protect_the_core_lane")
    call = client.messages.create_calls[0]
    assert "Situation:" not in _system_text(call) + " " + _user_text(call)  # byte-identical to today
```

(`FrameState` and the `_Wire`/`_Item`/`_Resp`/`_Client`/`_system_text`/`_user_text`/`_exp` helpers are already imported/defined in this file.)

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_anthropic_model.py::test_situation_is_woven_in_when_a_scene_is_present -q`
Expected: FAIL ("mid-rollout" not in the call — the situation isn't woven in yet).

- [ ] **Step 3: Implement in `src/retnovation/model.py`.**

Add a module-level helper (near `_render_rubric`):

```python
def _situation_block(exp) -> str:
    scene = getattr(exp, "scene", None)
    return f"\n\nSituation:\n{scene.situation}" if scene is not None else ""
```

In `classify_intake`, add the situation to the system context:

```python
        system = load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)
```

In `generate_push`, replace the existing `user = f"Experience:\n{exp.prompt}\n\nAngle to push on:\n{detail}"` line with a situation-prefixed version (rest of the method unchanged):

```python
        prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""
        user = f"{prefix}Experience:\n{exp.prompt}\n\nAngle to push on:\n{detail}"
```

In `classify_response`, add the situation to the system context:

```python
        system = (
            load_prompt("response")
            + _situation_block(exp)
            + f"\n\nMode: {exp.rubric.mode.value}"
            + f"\nBinding constraint: {exp.rubric.binding_constraint}"
            + f"\nTarget angle: {detail}"
        )
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_anthropic_model.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS — scene → situation woven in; no scene → no `Situation:` text (byte-stable); full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/model.py tests/test_anthropic_model.py docs/DEVLOG.md
git commit -m "feat(model): weave the scene situation into the judgment-loop calls"
```

---

## Final: author the `license_continuity` scene (controller) + gated moat test + review

This step is **controller-executed**, not dispatched to a subagent: it authors CONFIDENTIAL Veldra
content from gitignored sources and requires domain judgment.

- [ ] **Adversarial core-path review.** Dispatch an independent reviewer subagent (opus) over the whole
  branch diff against spec §9 (confidentiality; the moat holds over the concrete prompt — `validate_scene`
  rejects framework/frame-leak/scaffold/wrapper; fallback byte-stability with no scene; the migration on
  fresh + existing DBs; scene runtime-only on `Experience`; situation reaches all three model calls; CS
  untouched). Address every Critical/Important finding; re-run `pytest -q` + `ruff`. DEVLOG the review.
- [ ] **Author the scene.** Draft a concrete `scene` (prompt + situation, ReserveGrid-anchor style) for
  `license_fork_risk` from the gitignored material (its real `owned_problem`/`why_owned`/`unlabeled` + the
  design docs), add it under that entry in the gitignored `data/seed/veldra_ledger.yaml`, and run
  `retnovation-ingest` (or `PYTHONPATH=src python -m retnovation.veldra_ingest`) to re-populate the corpus.
  The prompt MUST clear `validate_scene` against the `license_continuity` rubric.
- [ ] **Gated moat test (tracked).** Add `tests/test_experience.py::test_seeded_license_scene_clears_the_moat`,
  `skipif` `data/retnovation.db` absent: load the corpus scene for `veldra:license_fork_risk`; if present,
  assert `validate_scene` passes against the `license_continuity` rubric (loaded via `load_experience`). Commit
  the tracked test + DEVLOG — NOT the gitignored seed.
- [ ] **Confirm confidentiality + re-dogfood.** `git ls-files | grep -iE 'berkeley|…|\.pdf'` empty; `data/`
  untracked. Re-run the live dogfood to feel the concrete `license_continuity` scene.
- [ ] **Completion.** Use superpowers:finishing-a-development-branch. DEVLOG "immersive-scenes COMPLETE".

## Self-Review (author check, completed)

- **Spec coverage:** `Scene`/`CorpusEntry.scene`/`Experience.scene` (T1) ✓; `scene_json` column + migration +
  round-trip (T2) ✓; `SeedEntry.scene` threading (T3) ✓; `validate_scene` moat guard (T4) ✓;
  `select_experience` attach + validate + fallback (T5) ✓; model situation-weaving + byte-stability (T6) ✓;
  authored `license_continuity` scene + gated moat test + confidentiality (Final) ✓; adversarial review (Final) ✓.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; every command has expected output.
  (Task 6 Step 3 gives the exact `prefix`/`user` lines to use and warns against leaving an unused local —
  the implementer must keep ruff clean.)
- **Type consistency:** `Scene(prompt, situation)` identical across T1–T6; `validate_scene(scene, rubric, *,
  framework_denylist, scaffold_denylist) -> None` matches its T5 call site; `CorpusEntry.scene`/`Experience.scene`
  optional defaults consistent; `_attach_scene` consumes `corpus: list[CorpusEntry]` + `root`; `_situation_block`
  guards `getattr(exp, "scene", None)` so it is safe on any experience.
