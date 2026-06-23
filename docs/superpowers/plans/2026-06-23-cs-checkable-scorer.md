# CS Checkable Scorer + `cs_technical` Selector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `cs_technical` regime end to end — a checkable scorer and a content-concept domain-path selector — so a second assessment regime runs through the same six-link plumbing as the founder open-ended path.

**Architecture:** Approach 1 (shared types, regime-dispatched behavior). One `Experience` type and one orchestration loop, extended not forked. CS drives the existing-but-unused `declarative_seed`/`SpacedItem` spaced index (new `concepts` SQLite table); founder process-frames and CS content-concepts never share state. Behavior dispatches by regime through registries mirroring the existing `ASSESSORS`/`SELECTORS` pattern. Spec: `docs/superpowers/specs/2026-06-23-cs-checkable-scorer-design.md`.

**Tech Stack:** Python ≥3.12, pydantic ≥2, pyyaml, anthropic SDK (lazy, only for the live grader), pytest, ruff. Run all Python via the project venv: `source .venv/bin/activate`.

## Global Constraints

- **Venv:** all `python`/`pytest`/`ruff` commands run after `source .venv/bin/activate` (system python has no pytest).
- **ruff:** `line-length = 100`; every commit runs `ruff format .` then `ruff check .` and both must be clean.
- **TDD:** failing test first, watch it fail, minimal implementation, watch it pass, commit.
- **Commits:** NEVER add a `Co-Authored-By` trailer. Stage explicit paths only — never `git add -A`/`.`/`-f`.
- **DEVLOG:** every task appends a `docs/DEVLOG.md` entry in the same commit (a change without a DEVLOG entry did not happen).
- **Confidentiality (L-2):** never track Berkeley/Blueprint/Brief/FounderCEO/JudgmentLoop/LiftTest/MVP_Scope/`*.pdf` or `data/`. After any content work: `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` must be empty. CS content authored here is generic CS knowledge — nothing confidential.
- **Never collapse the two paths (Complete Picture §10):** CS concepts never enter the `frames` table; founder frames never enter `concepts`.
- **Reversible decay (L-3):** a missed concept is demoted/rescheduled — its row is updated, never deleted.
- **Doctrine as data (L-1):** CS concepts, questions, answer keys, the grader prompt, and the spacing policy live under `content/`, never hardcoded in `src/`.
- **SDD scratch (L-7):** implementer/reviewer reports go under `.superpowers/sdd/` (gitignored). Never commit them.
- Branch: `step4-cs-checkable-scorer` (already created off `main`).
- Baseline before Task 1: `pytest -q` = 62 passed, 1 skipped.

---

## File Structure

- `src/retnovation/types.py` — modify: new checkable types; `Experience` gains optional `rubric`/`checkable` + regime/payload validator; `Aim`/`Core` `content_core` widened.
- `content/maps/cs_systems.yaml` — create: CS domain content core. `content/maps/founder_ceo.yaml` — modify: add `path_type: posture`.
- `content/checkables/*.yaml` — create: 2 checkable experiences. `content/prompts/grade.md`, `content/cadence/spacing.yaml` — create.
- `src/retnovation/content_loader.py` — modify: `load_path_type`, `load_content_map`, `load_spacing`, `load_checkable_experience`, `load_checkable_library`.
- `src/retnovation/model.py` — modify: `Model.grade_answer`; `FakeModel` scripted grades; `AnthropicModel.grade_answer`.
- `src/retnovation/assessment/checkable_scorer.py` — replace stub: deterministic + model-graded scoring → `CheckableAssessment`.
- `src/retnovation/generator.py` — modify: implement `select_cs_technical`.
- `src/retnovation/state.py` — modify: `update_state_checkable` + `STATE_UPDATERS` registry.
- `src/retnovation/scheduler.py` — modify: regime-aware `schedule_next`.
- `src/retnovation/persistence.py` — modify: `concepts` table + `declarative_seed` I/O.
- `src/retnovation/aim.py` — modify: domain-path onboarding.
- `src/retnovation/orchestration.py` + `src/retnovation/cli.py` — modify: regime-aware present/dispatch/print.
- Tests: extend `test_types.py`, `test_content_loader.py`, `test_model.py`, `test_anthropic_model.py`, `test_live_model.py`, `test_scheduler.py`, `test_state.py`, `test_persistence.py`, `test_aim.py`, `test_dispatch.py`, `test_generator.py`, `test_experience.py`, `test_cli.py`; create `test_checkable_scorer.py`, `test_cs_dry_run.py`.

---

### Task 1: Checkable types + `Experience` regime/payload invariant

**Files:**
- Modify: `src/retnovation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces:
  - `CheckType(str, Enum)`: `deterministic`, `model_graded`.
  - `CheckableQuestion(BaseModel)`: `question_id: str`, `concept: str`, `prompt: str`, `check_type: CheckType`, `choices: list[str] = []`, `answer_key: list[str] = []`, `criteria: str | None = None`.
  - `CheckableSet(BaseModel)`: `questions: list[CheckableQuestion]`.
  - `ConceptResult(BaseModel)`: `concept: str`, `question_id: str`, `correct: bool`, `check_type: CheckType`.
  - `CheckableAssessment(BaseModel)`: `results: list[ConceptResult]`.
  - `CheckableGrade(BaseModel)`: `correct: bool`.
  - `Experience`: `rubric: Rubric | None = None`, `checkable: CheckableSet | None = None`, with a `model_validator(mode="after")` enforcing: `open_ended` ⇒ rubric set & checkable None; `cs_technical` ⇒ checkable set & rubric None.
  - `Aim.content_core: list[str] | None`, `Core.content_core: list[str] | None`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_types.py`:

```python
def test_checkable_types_build_and_regime_invariant():
    import pytest
    from retnovation.types import (
        CheckType,
        CheckableQuestion,
        CheckableSet,
        ConceptResult,
        CheckableAssessment,
        CheckableGrade,
        Experience,
        Regime,
    )

    q = CheckableQuestion(
        question_id="q1",
        concept="safety_vs_liveness",
        prompt="Which property guarantees nothing bad ever happens?",
        check_type=CheckType.deterministic,
        choices=["safety", "liveness"],
        answer_key=["safety"],
    )
    cs = CheckableSet(questions=[q])
    exp = Experience(
        experience_id="cs1",
        prompt="Answer the following.",
        ledger_ref="veldra:consensus_correctness",
        regime=Regime.cs_technical,
        checkable=cs,
    )
    assert exp.checkable.questions[0].answer_key == ["safety"]
    assert exp.rubric is None

    asmt = CheckableAssessment(
        results=[ConceptResult(concept="safety_vs_liveness", question_id="q1",
                               correct=True, check_type=CheckType.deterministic)]
    )
    assert asmt.results[0].correct is True
    assert CheckableGrade(correct=False).correct is False

    # invariant: cs_technical with a rubric is rejected
    from retnovation.types import Rubric, Mode
    with pytest.raises(Exception):
        Experience(experience_id="bad", prompt="p", ledger_ref="r",
                   regime=Regime.cs_technical,
                   rubric=Rubric(frames=[], traps=[], mode=Mode.genuinely_open),
                   checkable=cs)
    # invariant: open_ended without a rubric is rejected
    with pytest.raises(Exception):
        Experience(experience_id="bad2", prompt="p", ledger_ref="r",
                   regime=Regime.open_ended)


def test_aim_core_content_core_accepts_a_concept_list():
    from retnovation.types import Aim, Core

    a = Aim(posture="cs_systems", process_dial=0, content_core=["safety_vs_liveness"])
    c = Core(process_frames=[], declarative_seed=["safety_vs_liveness"],
             content_core=["safety_vs_liveness"])
    assert a.content_core == ["safety_vs_liveness"]
    assert c.content_core == ["safety_vs_liveness"]
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q`
Expected: FAIL (ImportError on `CheckType` / validation not enforced).

- [ ] **Step 3: Implement in `src/retnovation/types.py`**

Change the pydantic import line to include `model_validator`:

```python
from pydantic import BaseModel, Field, model_validator
```

Add after the `GateCode` enum:

```python
class CheckType(str, Enum):
    deterministic = "deterministic"
    model_graded = "model_graded"
```

Add the new models (place near `Rubric` / `Assessment`):

```python
class CheckableQuestion(BaseModel):
    question_id: str
    concept: str
    prompt: str
    check_type: CheckType
    choices: list[str] = Field(default_factory=list)
    answer_key: list[str] = Field(default_factory=list)
    criteria: str | None = None


class CheckableSet(BaseModel):
    questions: list[CheckableQuestion]


class ConceptResult(BaseModel):
    concept: str
    question_id: str
    correct: bool
    check_type: CheckType


class CheckableAssessment(BaseModel):
    results: list[ConceptResult]


class CheckableGrade(BaseModel):
    correct: bool
```

Replace the `Experience` class:

```python
class Experience(BaseModel):
    experience_id: str
    prompt: str
    ledger_ref: str
    regime: Regime
    rubric: Rubric | None = None
    checkable: CheckableSet | None = None

    @model_validator(mode="after")
    def _regime_payload_invariant(self) -> "Experience":
        if self.regime is Regime.open_ended:
            if self.rubric is None or self.checkable is not None:
                raise ValueError("open_ended experience requires a rubric and no checkable")
        elif self.regime is Regime.cs_technical:
            if self.checkable is None or self.rubric is not None:
                raise ValueError("cs_technical experience requires a checkable and no rubric")
        return self
```

Widen `content_core` on both `Aim` and `Core`:

```python
class Aim(BaseModel):
    posture: str
    process_dial: int
    content_core: list[str] | None = None
```

```python
class Core(BaseModel):
    process_frames: list[str]
    declarative_seed: list[str]
    content_core: list[str] | None = None
```

Add a clarifying comment above `NextExperienceSpec.target_frames`:

```python
class NextExperienceSpec(BaseModel):
    # target codes for the next experience: process frames for open_ended, content concepts
    # for cs_technical. Overloaded by name (not renamed) to avoid a persisted-queue migration.
    target_frames: list[str]
    ledger_ref: str
    regime: Regime
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): checkable types + Experience regime/payload invariant"
```
(DEVLOG line: "Task 1 — checkable types (`CheckType`, `CheckableQuestion/Set`, `ConceptResult`, `CheckableAssessment`, `CheckableGrade`); `Experience.rubric` optional + regime/payload validator; `Aim`/`Core` content_core widened.")

---

### Task 2: CS content + content-loader functions

**Files:**
- Create: `content/maps/cs_systems.yaml`, `content/checkables/consensus_safety_liveness.yaml`, `content/checkables/replication_models.yaml`, `content/cadence/spacing.yaml`, `content/prompts/grade.md`
- Modify: `content/maps/founder_ceo.yaml` (add `path_type: posture`), `src/retnovation/content_loader.py`
- Test: `tests/test_content_loader.py`

**Interfaces:**
- Consumes: `CheckableQuestion`, `CheckableSet`, `Experience`, `Regime` (Task 1).
- Produces:
  - `load_path_type(name, root=None) -> str` (`"posture"` default if key absent).
  - `load_content_map(name, root=None) -> list[str]` (the `content_core` list).
  - `load_spacing(root=None) -> dict` with int `initial_interval_days`, float `ease_factor`, int `min_interval_days`.
  - `load_checkable_experience(name, root=None) -> Experience` (regime cs_technical).
  - `load_checkable_library(root=None) -> list[Experience]` (sorted by stem).

- [ ] **Step 1: Author the content files.**

`content/maps/cs_systems.yaml`:

```yaml
path_type: domain
content_core:
  - safety_vs_liveness
  - linearizability_vs_eventual
  - idempotency_under_retry
  - quorum_intersection
  - at_least_once_vs_exactly_once
  - partition_tolerance_tradeoff
```

Append one line to `content/maps/founder_ceo.yaml` (top, additive — leave existing keys unchanged):

```yaml
path_type: posture
```

`content/cadence/spacing.yaml`:

```yaml
initial_interval_days: 1
ease_factor: 2.0
min_interval_days: 1
```

`content/prompts/grade.md`:

```markdown
You are a strict grader for a checkable computer-science question. Decide only whether the
student's answer is correct against the supplied criteria and reference answer(s).

Rules:
- Grade correctness only. Do not reward fluency, length, confidence, or partial vibes.
- A wrong-but-articulate answer is incorrect. An imprecise-but-correct answer is correct.
- Judge against the criteria and reference answer(s) you are given, not your own preferences.
- Output a single boolean `correct`.
```

`content/checkables/consensus_safety_liveness.yaml` (all deterministic — the dry-run uses this):

```yaml
experience_id: consensus_safety_liveness
ledger_ref: "veldra:consensus_correctness"
regime: cs_technical
prompt: >
  Answer these questions on consensus correctness. (Generic CS — anchored to a real systems
  concern for provenance.)
checkable:
  questions:
    - question_id: csl_safety
      concept: safety_vs_liveness
      prompt: "Which property guarantees that nothing bad ever happens (no two nodes decide differently)?"
      check_type: deterministic
      choices: ["safety", "liveness"]
      answer_key: ["safety"]
    - question_id: csl_idempotency
      concept: idempotency_under_retry
      prompt: "One word: a handler you can apply twice with the same effect as once is ____."
      check_type: deterministic
      answer_key: ["idempotent", "idempotency"]
    - question_id: csl_quorum
      concept: quorum_intersection
      prompt: "Two majority quorums of an odd-sized cluster always share at least how many nodes?"
      check_type: deterministic
      answer_key: ["one", "1", "at least one"]
```

`content/checkables/replication_models.yaml` (mixes a model-graded question):

```yaml
experience_id: replication_models
ledger_ref: "veldra:replication_consistency"
regime: cs_technical
prompt: >
  Answer these questions on replication and delivery semantics. (Generic CS.)
checkable:
  questions:
    - question_id: rm_consistency
      concept: linearizability_vs_eventual
      prompt: "Which model lets two reads after a write briefly disagree: linearizable or eventual?"
      check_type: deterministic
      choices: ["linearizable", "eventual"]
      answer_key: ["eventual"]
    - question_id: rm_delivery
      concept: at_least_once_vs_exactly_once
      prompt: "Explain why at-least-once delivery plus idempotent handlers approximates exactly-once."
      check_type: model_graded
      answer_key: ["retries can duplicate, but an idempotent handler makes a duplicate a no-op"]
      criteria: >
        Correct iff the answer states that at-least-once can deliver duplicates AND that an
        idempotent handler makes a duplicate have no additional effect, yielding effectively-once.
    - question_id: rm_partition
      concept: partition_tolerance_tradeoff
      prompt: "Under a network partition, CAP forces a choice between consistency and ____?"
      check_type: deterministic
      answer_key: ["availability"]
```

- [ ] **Step 2: Write the failing tests** — append to `tests/test_content_loader.py`:

```python
def test_load_path_type_and_content_map():
    from retnovation.content_loader import load_path_type, load_content_map

    assert load_path_type("founder_ceo") == "posture"
    assert load_path_type("cs_systems") == "domain"
    core = load_content_map("cs_systems")
    assert "safety_vs_liveness" in core and "quorum_intersection" in core


def test_load_spacing_returns_policy():
    from retnovation.content_loader import load_spacing

    sp = load_spacing()
    assert sp["initial_interval_days"] == 1
    assert sp["ease_factor"] == 2.0
    assert sp["min_interval_days"] == 1


def test_load_checkable_library_builds_cs_experiences():
    from retnovation.content_loader import load_checkable_experience, load_checkable_library
    from retnovation.types import Experience, Regime, CheckType

    lib = load_checkable_library()
    assert lib, "content/checkables should hold at least one cs experience"
    assert all(isinstance(e, Experience) and e.regime is Regime.cs_technical for e in lib)
    one = load_checkable_experience("consensus_safety_liveness")
    assert one.checkable.questions[0].concept == "safety_vs_liveness"
    assert one.rubric is None and one.ledger_ref == "veldra:consensus_correctness"
    # both check types are represented across the library
    kinds = {q.check_type for e in lib for q in e.checkable.questions}
    assert CheckType.deterministic in kinds and CheckType.model_graded in kinds
```

- [ ] **Step 3: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_content_loader.py -q`
Expected: FAIL (ImportError on `load_path_type`).

- [ ] **Step 4: Implement loaders** — append to `src/retnovation/content_loader.py` and update its import line.

Update the top-of-file import to add the checkable types:

```python
from .types import (
    CheckableQuestion,
    CheckableSet,
    Experience,
    Frame,
    Mode,
    Regime,
    Rubric,
    Trap,
)
```

Append:

```python
def load_path_type(name: str, root: Path | None = None) -> str:
    data = yaml.safe_load((_root(root) / "maps" / f"{name}.yaml").read_text())
    return str(data.get("path_type", "posture"))


def load_content_map(name: str, root: Path | None = None) -> list[str]:
    data = yaml.safe_load((_root(root) / "maps" / f"{name}.yaml").read_text())
    return list(data["content_core"])


def load_spacing(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "cadence" / "spacing.yaml").read_text())
    return {
        "initial_interval_days": int(data["initial_interval_days"]),
        "ease_factor": float(data["ease_factor"]),
        "min_interval_days": int(data["min_interval_days"]),
    }


def load_checkable_experience(name: str, root: Path | None = None) -> Experience:
    data = yaml.safe_load((_root(root) / "checkables" / f"{name}.yaml").read_text())
    questions = [CheckableQuestion(**q) for q in data["checkable"]["questions"]]
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
        checkable=CheckableSet(questions=questions),
    )


def load_checkable_library(root: Path | None = None) -> list[Experience]:
    files = sorted((_root(root) / "checkables").glob("*.yaml"))
    return [load_checkable_experience(p.stem, root=root) for p in files]
```

- [ ] **Step 5: Run to verify pass + confidentiality check**

Run:
```bash
source .venv/bin/activate && pytest tests/test_content_loader.py -q && ruff format . && ruff check .
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo CLEAN
```
Expected: PASS; ruff clean; `CLEAN` (note: content files are new/untracked until staged — the check confirms nothing confidential is tracked).

- [ ] **Step 6: Commit**

```bash
git add content/maps/cs_systems.yaml content/maps/founder_ceo.yaml \
  content/checkables/consensus_safety_liveness.yaml content/checkables/replication_models.yaml \
  content/cadence/spacing.yaml content/prompts/grade.md \
  src/retnovation/content_loader.py tests/test_content_loader.py docs/DEVLOG.md
git commit -m "feat(content): generic CS systems content core + checkables + loaders"
```

---

### Task 3: Model grader (`grade_answer`)

**Files:**
- Modify: `src/retnovation/model.py`
- Test: `tests/test_model.py`, `tests/test_anthropic_model.py`, `tests/test_live_model.py`

**Interfaces:**
- Consumes: `CheckableGrade`, `CheckableQuestion`, `Experience` (Task 1); `load_prompt("grade")` (existing).
- Produces:
  - `Model.grade_answer(self, exp: Experience, question: CheckableQuestion, answer: str) -> CheckableGrade` (Protocol method).
  - `FakeModel(intake, responses, grades=None)` where `grades: dict[str, list[CheckableGrade]]` keyed by `question_id` (popped); `grade_answer` pops from it.
  - `AnthropicModel.grade_answer` — `messages.parse` with `output_format=CheckableGrade`, `_require`-guarded.

- [ ] **Step 1: Write the failing tests.**

Append to `tests/test_model.py` (note: `IntakeClassification` is imported from `retnovation.model`, not `types`):

```python
def test_fake_model_grade_answer_is_scripted():
    from retnovation.model import FakeModel, IntakeClassification
    from retnovation.types import CheckableGrade, CheckableQuestion, CheckType

    q = CheckableQuestion(question_id="q1", concept="c", prompt="p",
                          check_type=CheckType.model_graded, answer_key=["ref"], criteria="be right")
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}),
                  responses={}, grades={"q1": [CheckableGrade(correct=True)]})
    assert m.grade_answer(None, q, "an answer").correct is True
```

Append to `tests/test_anthropic_model.py`:

```python
def test_grade_answer_parses_correctness_against_criteria():
    from retnovation.types import CheckableGrade, CheckableQuestion, CheckType

    q = CheckableQuestion(question_id="q1", concept="at_least_once_vs_exactly_once",
                          prompt="Explain effectively-once.", check_type=CheckType.model_graded,
                          answer_key=["idempotent handler makes a duplicate a no-op"],
                          criteria="must mention duplicates and idempotency")
    client = _Client(parse_result=_Resp(parsed_output=CheckableGrade(correct=True)))
    out = AnthropicModel(client=client).grade_answer(_exp(), q, "duplicates are no-ops if idempotent")
    assert out.correct is True
    call = client.messages.parse_calls[0]
    sys = _system_text(call)
    assert "must mention duplicates and idempotency" in sys  # criteria reach the grader
    assert "duplicates are no-ops if idempotent" in _user_text(call)


def test_grade_answer_refusal_raises():
    from retnovation.types import CheckableQuestion, CheckType

    q = CheckableQuestion(question_id="q1", concept="c", prompt="p",
                          check_type=CheckType.model_graded, criteria="x")
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).grade_answer(_exp(), q, "answer")
```

Append to `tests/test_live_model.py` (gated smoke — mirror the existing `live`-marked pattern in that file):

```python
@pytest.mark.live
def test_live_grade_answer_smoke():
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY")
    from retnovation.model import AnthropicModel
    from retnovation.types import CheckableQuestion, CheckType, Experience, CheckableSet

    q = CheckableQuestion(question_id="q1", concept="idempotency_under_retry",
                          prompt="One word: a handler safe to apply twice is ____.",
                          check_type=CheckType.model_graded, answer_key=["idempotent"],
                          criteria="correct iff the answer means idempotent")
    exp = Experience(experience_id="live", prompt="p", ledger_ref="veldra:x",
                     regime=Regime.cs_technical, checkable=CheckableSet(questions=[q]))
    grade = AnthropicModel().grade_answer(exp, q, "idempotent")
    assert isinstance(grade.correct, bool)
```

(If `tests/test_live_model.py` lacks `import pytest` / `from retnovation.types import Regime`, add them.)

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_model.py tests/test_anthropic_model.py -q`
Expected: FAIL (`FakeModel` has no `grade_answer` / unexpected `grades` kwarg).

- [ ] **Step 3: Implement in `src/retnovation/model.py`.**

Add to the types import:

```python
from .types import CheckableGrade, CheckableQuestion, Experience, FrameState, TrapState
```

Add `grade_answer` to the `Model` Protocol:

```python
    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade: ...
```

Update `FakeModel.__init__` and add the method:

```python
    def __init__(
        self,
        intake: IntakeClassification,
        responses: dict[str, list[ResponseClassification]],
        grades: dict[str, list[CheckableGrade]] | None = None,
    ):
        self._intake = intake
        self._responses = responses
        self._grades = grades or {}

    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade:
        return self._grades[question.question_id].pop(0)
```

Add `AnthropicModel.grade_answer`:

```python
    def grade_answer(
        self, exp: Experience, question: CheckableQuestion, answer: str
    ) -> CheckableGrade:
        system = (
            load_prompt("grade")
            + f"\n\nQuestion: {question.prompt}"
            + f"\nReference answer(s): {question.answer_key}"
            + f"\nCriteria: {question.criteria}"
        )
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"Student answer:\n{answer}"}],
            output_format=CheckableGrade,
            **_PARAMS,
        )
        return _require(resp)
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_model.py tests/test_anthropic_model.py tests/test_live_model.py -q && ruff format . && ruff check .`
Expected: PASS (live smoke skipped); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/model.py tests/test_model.py tests/test_anthropic_model.py tests/test_live_model.py docs/DEVLOG.md
git commit -m "feat(model): grade_answer (deterministic-default optional model grader)"
```

---

### Task 4: Checkable scorer

**Files:**
- Modify: `src/retnovation/assessment/checkable_scorer.py` (replace the stub)
- Test: `tests/test_checkable_scorer.py` (create)

**Interfaces:**
- Consumes: `CheckableAssessment`, `CheckType`, `ConceptResult`, `Experience`, `Work` (Task 1); `Model.grade_answer` (Task 3).
- Produces: `assess(exp, work, model) -> CheckableAssessment`; `score_question(exp, q, answer, model) -> bool`; `_normalize(s) -> str`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_checkable_scorer.py`:

```python
import pytest

from retnovation.assessment import checkable_scorer
from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import (
    CheckableGrade,
    CheckableQuestion,
    CheckableSet,
    CheckType,
    Experience,
    Regime,
    Work,
)


def _exp(questions):
    return Experience(
        experience_id="cs", prompt="answer", ledger_ref="veldra:consensus_correctness",
        regime=Regime.cs_technical, checkable=CheckableSet(questions=questions),
    )


def _det(qid, concept, key):
    return CheckableQuestion(question_id=qid, concept=concept, prompt="p",
                             check_type=CheckType.deterministic, answer_key=key)


def _work(answers):
    it = iter(answers)
    return Work(opening="", respond=lambda push: next(it, ""))


def _no_model():
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})


def test_deterministic_scoring_is_normalized_and_model_free():
    exp = _exp([_det("q1", "safety_vs_liveness", ["safety"]),
                _det("q2", "idempotency_under_retry", ["idempotent", "idempotency"])])
    work = _work(["  Safety. ", "IDEMPOTENT"])
    asmt = checkable_scorer.assess(exp, work, _no_model())
    assert [r.correct for r in asmt.results] == [True, True]
    assert [r.concept for r in asmt.results] == ["safety_vs_liveness", "idempotency_under_retry"]


def test_deterministic_wrong_answer_scores_false():
    exp = _exp([_det("q1", "safety_vs_liveness", ["safety"])])
    asmt = checkable_scorer.assess(exp, _work(["liveness"]), _no_model())
    assert asmt.results[0].correct is False


def test_model_graded_question_uses_the_grader():
    q = CheckableQuestion(question_id="q1", concept="c", prompt="p",
                          check_type=CheckType.model_graded, criteria="x")
    model = FakeModel(IntakeClassification(frame_states={}, trap_states={}),
                      responses={}, grades={"q1": [CheckableGrade(correct=True)]})
    asmt = checkable_scorer.assess(_exp([q]), _work(["some prose"]), model)
    assert asmt.results[0].correct is True
    assert asmt.results[0].check_type is CheckType.model_graded


def test_deterministic_without_answer_key_raises():
    bad = CheckableQuestion(question_id="q1", concept="c", prompt="p",
                            check_type=CheckType.deterministic, answer_key=[])
    with pytest.raises(ValueError):
        checkable_scorer.assess(_exp([bad]), _work(["x"]), _no_model())
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_checkable_scorer.py -q`
Expected: FAIL (stub raises `NotImplementedError`).

- [ ] **Step 3: Implement `src/retnovation/assessment/checkable_scorer.py`:**

```python
from __future__ import annotations

import re

from ..model import Model
from ..types import CheckableAssessment, CheckableQuestion, CheckType, ConceptResult, Experience, Work


def _normalize(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    return s.strip(".,;:!?\"'")


def _render(q: CheckableQuestion) -> str:
    if q.choices:
        opts = "\n".join(f"  - {c}" for c in q.choices)
        return f"{q.prompt}\n{opts}"
    return q.prompt


def score_question(exp: Experience, q: CheckableQuestion, answer: str, model: Model) -> bool:
    if q.check_type is CheckType.deterministic:
        if not q.answer_key:
            raise ValueError(f"deterministic question {q.question_id} has no answer_key")
        return _normalize(answer) in {_normalize(k) for k in q.answer_key}
    return model.grade_answer(exp, q, answer).correct


def assess(exp: Experience, work: Work, model: Model) -> CheckableAssessment:
    if exp.checkable is None:
        raise ValueError("cs_technical experience has no checkable set")
    results: list[ConceptResult] = []
    for q in exp.checkable.questions:
        answer = work.respond(_render(q))
        results.append(
            ConceptResult(
                concept=q.concept,
                question_id=q.question_id,
                correct=score_question(exp, q, answer, model),
                check_type=q.check_type,
            )
        )
    return CheckableAssessment(results=results)
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_checkable_scorer.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/assessment/checkable_scorer.py tests/test_checkable_scorer.py docs/DEVLOG.md
git commit -m "feat(assessment): checkable scorer (deterministic + model-graded -> CheckableAssessment)"
```

---

### Task 5: CS domain-path selector

**Files:**
- Modify: `src/retnovation/generator.py` (implement `select_cs_technical`)
- Test: `tests/test_generator.py` (replace the stub test), `tests/test_experience.py` (replace the stub test)

**Interfaces:**
- Consumes: `load_checkable_library` (Task 2); `Experience` (Task 1); existing `GateError`.
- Produces: `select_cs_technical(core, state, ledger, corpus, spec, root=None) -> Experience` — ranks the checkable library by content-concept coverage of `spec.target_frames` (falling back to `core.content_core`), tie-break by `experience_id`; raises `GateError` if empty.

- [ ] **Step 1: Replace the stub tests.**

In `tests/test_generator.py`, replace `test_select_cs_technical_is_a_step4_stub` with:

```python
def test_select_cs_technical_ranks_by_concept_coverage():
    from retnovation.generator import select_cs_technical
    from retnovation.types import LearnerState, NextExperienceSpec, Regime

    spec = NextExperienceSpec(
        target_frames=["safety_vs_liveness", "quorum_intersection"],
        ledger_ref="", regime=Regime.cs_technical,
    )
    exp = select_cs_technical(core=None, state=LearnerState(), ledger=[], corpus=[], spec=spec)
    # consensus_safety_liveness covers both target concepts; replication_models covers neither
    assert exp.experience_id == "consensus_safety_liveness"
    assert exp.regime is Regime.cs_technical and exp.ledger_ref == "veldra:consensus_correctness"


def test_select_cs_technical_cold_start_falls_back_to_content_core():
    from retnovation.generator import select_cs_technical
    from retnovation.types import Core, LearnerState

    core = Core(process_frames=[], declarative_seed=["linearizability_vs_eventual"],
                content_core=["linearizability_vs_eventual"])
    exp = select_cs_technical(core=core, state=LearnerState(), ledger=[], corpus=[], spec=None)
    assert exp.experience_id == "replication_models"  # the one covering that concept
```

In `tests/test_experience.py`, replace `test_select_experience_cs_technical_is_stubbed` with:

```python
def test_select_experience_dispatches_cs_technical(tmp_path):
    from retnovation.types import Core

    spec = NextExperienceSpec(
        target_frames=["safety_vs_liveness"], ledger_ref="", regime=Regime.cs_technical
    )
    core = Core(process_frames=[], declarative_seed=["safety_vs_liveness"],
                content_core=["safety_vs_liveness"])
    exp = select_experience(core, LearnerState(), [], [], spec)
    assert exp.regime is Regime.cs_technical
    assert exp.checkable is not None and exp.rubric is None
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_generator.py tests/test_experience.py -q`
Expected: FAIL (still `NotImplementedError`).

- [ ] **Step 3: Implement in `src/retnovation/generator.py`.**

Add `load_checkable_library` to the content-loader import:

```python
from .content_loader import (
    load_checkable_library,
    load_denylist,
    load_library,
    load_min_angle_count,
)
```

Replace `select_cs_technical`:

```python
def _concept_coverage(exp: Experience, targets: list[str]) -> int:
    concepts = {q.concept for q in exp.checkable.questions}
    return sum(1 for t in targets if t in concepts)


def select_cs_technical(core, state, ledger, corpus, spec, root=None) -> Experience:
    lib = load_checkable_library(root)
    if not lib:
        raise GateError("no cs_technical experience in the checkable library")
    if spec is not None and spec.target_frames:
        targets = spec.target_frames
    elif core is not None and core.content_core:
        targets = core.content_core
    else:
        targets = []
    ranked = sorted(lib, key=lambda e: (-_concept_coverage(e, targets), e.experience_id))
    return ranked[0]
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_generator.py tests/test_experience.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/generator.py tests/test_generator.py tests/test_experience.py docs/DEVLOG.md
git commit -m "feat(generator): select_cs_technical by content-concept coverage"
```

---

### Task 6: Concept state update + `STATE_UPDATERS` registry

**Files:**
- Modify: `src/retnovation/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `CheckableAssessment`, `ConceptResult`, `SpacedItem`, `Regime` (Task 1); `load_spacing` (Task 2).
- Produces:
  - `update_state_checkable(state, assessment, now, experience_id, spacing=None) -> LearnerState` — aggregates results per concept (recalled iff all correct), updates `state.declarative_seed[concept]` as a `SpacedItem` (recall grows interval by `ease_factor`, miss resets to `min_interval_days`; never deletes).
  - `STATE_UPDATERS: dict[Regime, Callable]` = `{open_ended: update_state, cs_technical: update_state_checkable}`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_state.py`:

```python
def _casmt(pairs):
    from retnovation.types import CheckableAssessment, ConceptResult, CheckType

    return CheckableAssessment(
        results=[ConceptResult(concept=c, question_id=f"{c}_q", correct=ok,
                               check_type=CheckType.deterministic) for c, ok in pairs]
    )


def test_checkable_recall_grows_interval_miss_resets():
    from retnovation.state import update_state_checkable
    from retnovation.types import LearnerState

    sp = {"initial_interval_days": 1, "ease_factor": 2.0, "min_interval_days": 1}
    st = LearnerState()
    st = update_state_checkable(st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", spacing=sp)
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # initial
    st = update_state_checkable(st, _casmt([("safety_vs_liveness", True)]), _now(), "cs", spacing=sp)
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 2  # grew by ease
    st = update_state_checkable(st, _casmt([("safety_vs_liveness", False)]), _now(), "cs", spacing=sp)
    assert st.declarative_seed["safety_vs_liveness"].interval_days == 1  # reset, not deleted
    assert "safety_vs_liveness" in st.declarative_seed


def test_checkable_concept_recalled_only_if_all_questions_correct():
    from retnovation.state import update_state_checkable
    from retnovation.types import LearnerState

    sp = {"initial_interval_days": 1, "ease_factor": 2.0, "min_interval_days": 1}
    a = _casmt([("c", True), ("c", False)])  # same concept, one miss
    st = update_state_checkable(LearnerState(), a, _now(), "cs", spacing=sp)
    assert st.declarative_seed["c"].interval_days == 1  # treated as missed


def test_state_updaters_registry_routes_by_regime():
    from retnovation.state import STATE_UPDATERS, update_state, update_state_checkable
    from retnovation.types import Regime

    assert STATE_UPDATERS[Regime.open_ended] is update_state
    assert STATE_UPDATERS[Regime.cs_technical] is update_state_checkable
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_state.py -q`
Expected: FAIL (ImportError on `update_state_checkable`).

- [ ] **Step 3: Implement in `src/retnovation/state.py`.**

Update imports:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from .content_loader import load_spacing
from .types import (
    Assessment,
    CheckableAssessment,
    FrameState,
    FrameStrength,
    LearnerState,
    Regime,
    SpacedItem,
    Strength,
    TrapOccurrence,
)
```

Append after `update_state`:

```python
def update_state_checkable(
    state: LearnerState,
    assessment: CheckableAssessment,
    now: datetime,
    experience_id: str,
    spacing: dict | None = None,
) -> LearnerState:
    if spacing is None:
        spacing = load_spacing()
    initial = spacing["initial_interval_days"]
    ease = spacing["ease_factor"]
    floor = spacing["min_interval_days"]

    by_concept: dict[str, list[bool]] = {}
    for r in assessment.results:
        by_concept.setdefault(r.concept, []).append(r.correct)

    for concept, corrects in by_concept.items():
        recalled = all(corrects)
        prev = state.declarative_seed.get(concept)
        if prev is None:
            interval = initial if recalled else floor
        elif recalled:
            interval = max(floor, round(prev.interval_days * ease))
        else:
            interval = floor  # reversible demotion — row is updated, never deleted (L-3)
        state.declarative_seed[concept] = SpacedItem(
            concept=concept, due=now + timedelta(days=interval), interval_days=interval
        )
    return state


STATE_UPDATERS: dict[Regime, Callable] = {
    Regime.open_ended: update_state,
    Regime.cs_technical: update_state_checkable,
}
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_state.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/state.py tests/test_state.py docs/DEVLOG.md
git commit -m "feat(state): concept spaced-index update + STATE_UPDATERS registry"
```

---

### Task 7: Regime-aware scheduler

**Files:**
- Modify: `src/retnovation/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `LearnerState.declarative_seed` (`SpacedItem`) (Task 1).
- Produces: `schedule_next(state, ledger, now, regime=open_ended)` — for `cs_technical`, targets due concepts (`due <= now`, ordered by `due`), else the soonest-due concept; `open_ended` unchanged.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_scheduler.py`:

```python
def _cs_state(items):
    from retnovation.types import LearnerState, SpacedItem

    st = LearnerState()
    for concept, (due, interval) in items.items():
        st.declarative_seed[concept] = SpacedItem(concept=concept, due=due, interval_days=interval)
    return st


def test_cs_technical_targets_due_concepts_first():
    from datetime import timedelta

    now = _now()
    st = _cs_state({
        "overdue": (now - timedelta(days=1), 1),
        "future": (now + timedelta(days=5), 4),
    })
    spec = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["overdue"]
    assert spec.regime is Regime.cs_technical


def test_cs_technical_with_nothing_due_targets_soonest():
    from datetime import timedelta

    now = _now()
    st = _cs_state({
        "soon": (now + timedelta(days=1), 1),
        "later": (now + timedelta(days=9), 8),
    })
    spec = schedule_next(st, [], now, regime=Regime.cs_technical)
    assert spec.target_frames == ["soon"]
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_scheduler.py -q`
Expected: FAIL (cs branch not implemented; returns frame logic / empty targets).

- [ ] **Step 3: Implement in `src/retnovation/scheduler.py`** — insert the cs branch before the frame logic:

```python
def schedule_next(
    state: LearnerState,
    ledger: list[LedgerEntry],
    now: datetime,
    regime: Regime = Regime.open_ended,
) -> NextExperienceSpec:
    ledger_ref = ledger[0].id if ledger else ""

    if regime is Regime.cs_technical:
        items = state.declarative_seed
        due = sorted((c for c, si in items.items() if si.due <= now), key=lambda c: items[c].due)
        if due:
            targets = due
        elif items:
            targets = [min(items.items(), key=lambda kv: kv[1].due)[0]]
        else:
            targets = []
        return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime)

    weak = [c for c, fs in state.frames.items() if fs.strength is Strength.weak]
    forming = [c for c, fs in state.frames.items() if fs.strength is Strength.forming]
    if weak:
        targets = sorted(weak)
    elif forming:
        targets = sorted(forming)
    else:
        strong = sorted(state.frames.items(), key=lambda kv: kv[1].due)
        targets = [strong[0][0]] if strong else []
    return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime)
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_scheduler.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/scheduler.py tests/test_scheduler.py docs/DEVLOG.md
git commit -m "feat(scheduler): regime-aware schedule_next targets due CS concepts"
```

---

### Task 8: Persistence — `concepts` table + `declarative_seed` I/O

**Files:**
- Modify: `src/retnovation/persistence.py`
- Test: `tests/test_persistence.py`

**Interfaces:**
- Consumes: `SpacedItem` (Task 1).
- Produces: `concepts` table; `load_state` populates `declarative_seed`; `save_state` UPSERTs every `SpacedItem` (no DELETE — reversible).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_persistence.py`:

```python
def test_concepts_roundtrip_and_never_deleted(tmp_path):
    from retnovation.types import SpacedItem

    s = Store(tmp_path / "c.db")
    st = LearnerState()
    st.declarative_seed["safety_vs_liveness"] = SpacedItem(
        concept="safety_vs_liveness", due=_now(), interval_days=4
    )
    s.save_state(st)
    loaded = Store(tmp_path / "c.db").load_state()
    assert loaded.declarative_seed["safety_vs_liveness"].interval_days == 4

    # demote (shorter interval) — row stays present
    st.declarative_seed["safety_vs_liveness"] = SpacedItem(
        concept="safety_vs_liveness", due=_now(), interval_days=1
    )
    s.save_state(st)
    re2 = Store(tmp_path / "c.db").load_state()
    assert set(re2.declarative_seed) == {"safety_vs_liveness"}
    assert re2.declarative_seed["safety_vs_liveness"].interval_days == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_persistence.py -q`
Expected: FAIL (`declarative_seed` not persisted / empty after reload).

- [ ] **Step 3: Implement in `src/retnovation/persistence.py`.**

Add `SpacedItem` to the types import. Append a table to `_SCHEMA`:

```python
CREATE TABLE IF NOT EXISTS concepts (
  concept TEXT PRIMARY KEY, due TEXT NOT NULL, interval_days INTEGER NOT NULL);
```

In `load_state`, after the frames loop and before `return st`:

```python
        for r in self._db.execute("SELECT * FROM concepts"):
            st.declarative_seed[r["concept"]] = SpacedItem(
                concept=r["concept"],
                due=datetime.fromisoformat(r["due"]),
                interval_days=r["interval_days"],
            )
```

In `save_state`, after the frames loop and before `self._db.commit()`:

```python
        for concept, si in state.declarative_seed.items():
            self._db.execute(
                "INSERT INTO concepts(concept,due,interval_days) VALUES(?,?,?) "
                "ON CONFLICT(concept) DO UPDATE SET due=excluded.due, "
                "interval_days=excluded.interval_days",
                (concept, si.due.isoformat(), si.interval_days),
            )
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_persistence.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/persistence.py tests/test_persistence.py docs/DEVLOG.md
git commit -m "feat(persistence): concepts table persists the CS spaced index (no-delete)"
```

---

### Task 9: Domain-path onboarding (`aim` / `derive_core`)

**Files:**
- Modify: `src/retnovation/aim.py`
- Test: `tests/test_aim.py`

**Interfaces:**
- Consumes: `load_path_type`, `load_content_map`, `load_map` (Tasks 2/existing).
- Produces: `MIN_PROCESS_DIAL = 0`; `aim(posture="founder_ceo", root=None)` sets the dial by `path_type`; `derive_core(a, root=None)` builds a domain Core (`content_core` + `declarative_seed` = concepts, empty `process_frames`) for `path_type == "domain"`, posture Core otherwise.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_aim.py`:

```python
def test_aim_domain_path_is_low_dial():
    from retnovation.aim import aim, MIN_PROCESS_DIAL

    a = aim("cs_systems")
    assert a.posture == "cs_systems"
    assert a.process_dial == MIN_PROCESS_DIAL


def test_derive_core_domain_path_loads_content_core():
    from retnovation.aim import aim, derive_core

    core = derive_core(aim("cs_systems"))
    assert "safety_vs_liveness" in core.content_core
    assert core.declarative_seed == core.content_core
    assert core.process_frames == []
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_aim.py -q`
Expected: FAIL (`MIN_PROCESS_DIAL` missing / `derive_core` raises on the CS map's missing `process_frames`).

- [ ] **Step 3: Implement `src/retnovation/aim.py`:**

```python
from __future__ import annotations

from pathlib import Path

from .content_loader import load_content_map, load_map, load_path_type
from .types import Aim, Core

MAX_PROCESS_DIAL = 10
MIN_PROCESS_DIAL = 0


def aim(posture: str = "founder_ceo", root: Path | None = None) -> Aim:
    path_type = load_path_type(posture, root=root)
    dial = MAX_PROCESS_DIAL if path_type == "posture" else MIN_PROCESS_DIAL
    return Aim(posture=posture, process_dial=dial, content_core=None)


def derive_core(a: Aim, root: Path | None = None) -> Core:
    if load_path_type(a.posture, root=root) == "domain":
        concepts = load_content_map(a.posture, root=root)
        return Core(process_frames=[], declarative_seed=concepts, content_core=concepts)
    frames, seed = load_map(a.posture, root=root)
    return Core(process_frames=frames, declarative_seed=seed, content_core=None)
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_aim.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/aim.py tests/test_aim.py docs/DEVLOG.md
git commit -m "feat(aim): domain-path onboarding loads the CS content core"
```

---

### Task 10: Orchestration + CLI regime dispatch + dispatch test

**Files:**
- Modify: `src/retnovation/orchestration.py`, `src/retnovation/cli.py`
- Test: `tests/test_dispatch.py` (replace the stub test), `tests/test_orchestration.py` (founder regression stays green)

**Interfaces:**
- Consumes: `get_assessor` (existing), `STATE_UPDATERS` (Task 6), `schedule_next` (Task 7), `select_experience` (Task 5 via dispatch), `CheckableAssessment` (Task 1).
- Produces: regime-aware `present_and_collect`; `run_session` dispatches state update via `STATE_UPDATERS[exp.regime]`; `cli.main` prints a regime-appropriate line.

- [ ] **Step 1: Replace the dispatch stub test.**

In `tests/test_dispatch.py`, replace `test_cs_technical_is_registered_but_unimplemented` with:

```python
def test_cs_technical_dispatches_to_checkable_scorer():
    from retnovation.assessment import checkable_scorer

    assert get_assessor(Regime.cs_technical) is checkable_scorer.assess
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_dispatch.py -q`
Expected: FAIL (import of `checkable_scorer` ref / identity assertion) — or the old test name no longer exists. Confirm the new test fails before the wiring, then passes after.

Note: this test passes once `checkable_scorer.assess` is the registered callable (already true from Task 4). If it passes immediately, that is acceptable — proceed; the real wiring under test in this task is in `orchestration`/`cli`, verified by Steps 3–4 and the full-suite run.

- [ ] **Step 3: Implement `src/retnovation/orchestration.py`.**

Update imports and the two functions:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .assessment import get_assessor
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import schedule_next
from .state import STATE_UPDATERS
from .types import Assessment, CheckableAssessment, Core, Experience, LearnerState, Regime, Work


def present_and_collect(exp: Experience) -> Work:
    def respond(push: str) -> str:
        print(push)
        return input("> ")

    if exp.regime is Regime.cs_technical:
        return Work(opening="", respond=respond)
    print(exp.prompt)
    opening = input("> ")
    return Work(opening=opening, respond=respond)


def run_session(
    store: Store,
    core: Core,
    model: Model,
    now: datetime,
    present: Callable[[Experience], Work] = present_and_collect,
) -> tuple[LearnerState, Assessment | CheckableAssessment]:
    state = store.load_state()
    ledger = store.load_ledger()
    corpus = store.load_corpus()
    spec = store.queue_pop()
    exp = select_experience(core, state, ledger, corpus, spec)
    work = present(exp)
    assessment = get_assessor(exp.regime)(exp, work, model)
    state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id)
    store.save_state(state)
    store.queue_push(schedule_next(state, ledger, now, exp.regime))
    return state, assessment
```

- [ ] **Step 4: Implement the CLI print branch in `src/retnovation/cli.py`** — replace the success-print block in `main`:

```python
    from .types import CheckableAssessment

    if isinstance(assessment, CheckableAssessment):
        recalled = sum(1 for r in assessment.results if r.correct)
        print(f"concepts_scored={len(assessment.results)} recalled={recalled}")
    else:
        print(f"stop_reason={assessment.stop_reason.value} frames_total={len(state.frames)}")
    return 0
```

- [ ] **Step 5: Run to verify pass (incl. founder regression)**

Run: `source .venv/bin/activate && pytest tests/test_dispatch.py tests/test_orchestration.py tests/test_cli.py -q && ruff format . && ruff check .`
Expected: PASS (founder path byte-stable); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/retnovation/orchestration.py src/retnovation/cli.py tests/test_dispatch.py docs/DEVLOG.md
git commit -m "feat(orchestration): regime-aware present + state dispatch + CS cli print"
```

---

### Task 11: CS dry-run acceptance test (the six links close for `cs_technical`)

**Files:**
- Create: `tests/test_cs_dry_run.py`

**Interfaces:**
- Consumes: everything above — real `Store`, `aim("cs_systems")`/`derive_core`, `run_session`, the authored `content/checkables/`.

- [ ] **Step 1: Write the acceptance test** — create `tests/test_cs_dry_run.py`:

```python
"""CS checkable dry run: the six links close end-to-end for the cs_technical regime,
proving a second regime runs through the same plumbing (deterministic, model-free)."""

from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.model import FakeModel, IntakeClassification
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.types import CheckableAssessment, NextExperienceSpec, Regime, Work


def _now():
    return datetime(2026, 6, 23, tzinfo=timezone.utc)


def _model_unused():
    # deterministic CS questions never call the model; supply an inert one
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})


def test_cs_dry_run_closes_the_loop(tmp_path):
    store = Store(tmp_path / "cs.db")
    # target the all-deterministic experience's concepts so it is selected, model-free
    store.queue_push(
        NextExperienceSpec(
            target_frames=["safety_vs_liveness", "idempotency_under_retry", "quorum_intersection"],
            ledger_ref="veldra:consensus_correctness",
            regime=Regime.cs_technical,
        )
    )
    core = derive_core(aim("cs_systems"))

    def fixture(exp):
        # answer each question correctly via its first answer_key entry, in order
        answers = iter(q.answer_key[0] for q in exp.checkable.questions)
        return Work(opening="", respond=lambda push: next(answers, ""))  # noqa: E731

    state, assessment = run_session(store, core, _model_unused(), _now(), present=fixture)

    # 1) the checkable scorer ran every question, all correct
    assert isinstance(assessment, CheckableAssessment)
    assert assessment.results and all(r.correct for r in assessment.results)
    # 2) the concept spaced-index moved and persisted
    reloaded = Store(tmp_path / "cs.db").load_state()
    assert "safety_vs_liveness" in reloaded.declarative_seed
    assert reloaded.declarative_seed["safety_vs_liveness"].interval_days >= 1
    # 3) a fresh cs_technical next experience is queued (cadence closed the loop)
    nxt = Store(tmp_path / "cs.db").queue_pop()
    assert nxt is not None and nxt.regime is Regime.cs_technical
```

- [ ] **Step 2: Run to verify it passes (all prior tasks make it green)**

Run: `source .venv/bin/activate && pytest tests/test_cs_dry_run.py -q`
Expected: PASS.

- [ ] **Step 3: Full suite + lint + confidentiality gate**

Run:
```bash
source .venv/bin/activate && pytest -q && ruff format . && ruff check .
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo CLEAN
```
Expected: all pass (≥ 62 prior + new tests; 1 skipped live); ruff clean; `CLEAN`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cs_dry_run.py docs/DEVLOG.md
git commit -m "test(cs): dry-run acceptance — six links close for the cs_technical regime"
```

---

## Final: adversarial review + completion

After Task 11, before any merge:

- [ ] **Adversarial core-path review.** Dispatch an independent reviewer subagent over the whole branch diff against the spec's §9 checklist (paths-never-collapse, deterministic-scoring soundness, reversible decay, fresh-DB end-to-end, the `Experience` invariant, confidentiality, no-gate-on-CS, grader strictness, founder regression byte-stable, loop closes). Address every finding; re-run `pytest -q` + `ruff`. Add a DEVLOG entry recording the review and fixes.
- [ ] **Completion.** Use superpowers:finishing-a-development-branch to verify tests and choose merge/PR. Update `docs/DEVLOG.md` with a "Step 4 COMPLETE + Step 5 handoff" entry (Step 5 = harden the judgment loop: regression/plateau stops + independent grader).

## Self-Review (author check, completed)

- **Spec coverage:** types/invariant (T1) ✓; generic CS content + loaders, both check types (T2) ✓; deterministic-default + optional model grader (T3/T4) ✓; concept-coverage selector, no anti-label gate on CS (T5) ✓; concept spaced-index state + never-collapse + reversible decay (T6) ✓; regime-aware scheduling (T7) ✓; concept persistence, fresh-DB (T8) ✓; domain-path onboarding/`content_core` (T9) ✓; regime dispatch in orchestration/CLI + `Work` reuse (T10) ✓; CS dry-run acceptance (T11) ✓; adversarial review (Final) ✓.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; every command has expected output.
- **Type consistency:** `update_state_checkable(..., spacing=None)` uniform 4-arg dispatch via `STATE_UPDATERS`; `select_cs_technical(core, state, ledger, corpus, spec, root=None)` matches the `SELECTORS` call site; `grade_answer(exp, question, answer)` consistent across Protocol/Fake/Anthropic and the scorer; `target_frames` overloaded (documented) end to end; `content_core: list[str] | None` consistent across `Aim`/`Core`/onboarding/selector.
