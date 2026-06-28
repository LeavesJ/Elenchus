# SP3 Live Content-Elicitation Probe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a calibration probe that measures whether real frame-naive Opus reads `embed_credentials_as_a_list` as `present_reasoned` at intake on the two authored SP3 problems — which, for these rubrics, is the proven equivalent of embed ∈ `reasoned_unprompted` (the property SP3 leans on).

**Architecture:** A pure module (`elicitation.py`) orchestrates `generate_output(prompt, None)` → `classify_intake` over the `Model` protocol — no doctrine, no I/O. A rubric-shape guard (`assert_intake_equivalence`) refuses any rubric where the intake↔`reasoned_unprompted` equivalence would not hold; a fixtured loop-side guardian test pins the loop half of that equivalence. A thin I/O entrypoint runs it live and writes a gitignored artifact; the human adjudicates the verbatim + verdicts.

**Tech Stack:** Python 3, Pydantic v2, pytest. Real model: `AnthropicModel` (Claude Opus 4.8). Tests run offline via fakes; one `@live` smoke self-skips without a key.

**Spec:** `docs/superpowers/specs/2026-06-27-sp3-live-content-elicitation-design.md` (committed `1d1f056`).

## Global Constraints

- **Tests:** `PYTHONPATH=src .venv/bin/pytest -q` (run from repo root `~/Documents/Retnovation`).
- **Pre-commit (per `docs/lessons.md`):** `ruff format .` → `ruff check .` → run the suite → stage **explicit paths only** (never `git add -A`, never `-f`) → **no `Co-Authored-By`** trailer.
- **Confidentiality gate (must stay empty):** `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf|content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$'`.
- **Artifact location:** `data/elicitation/<utc>.json` — `/data/` is already gitignored; verbatim learner openings are Veldra-ore-derived and **never committed**. Tests write to `tmp_path`, never `data/`.
- **DEVLOG:** one consolidated feature entry is written in the final task (Task 7); intermediate task commits keep the suite green and stage code+tests only. (Adaptation of the per-commit DEVLOG gate for a multi-task subagent build — the narrative lands once, complete.)
- **Doctrine invariants:** L-13 (never surface the frame to the learner — `injection=None`, and the prompt must not contain any `frame_code`); L-1 (doctrine in `content/`, not `src/`); the probe is pure (Model-protocol-only, no client/file access inside `elicitation.py`).
- **Target frame:** `embed_credentials_as_a_list` (the `DEFAULT_TARGET` constant).
- **Sampling default:** `RUNS_BY_ID = {"irreversible_anchor": 8, "continuity_lock_in": 5}`.

## File Structure

- **Create** `src/retnovation/elicitation.py` — pure orchestration: `DEFAULT_TARGET`, `assert_intake_equivalence`, `assert_no_frame_code_leak`, `run_elicitation_probe`. No I/O, no SDK.
- **Create** `src/retnovation/run_elicitation.py` — I/O entrypoint: `run(...)` (injectable) + `main()`; writes the gitignored artifact, prints the abstracted summary. Run by the human.
- **Modify** `src/retnovation/types.py` — add `ProbeRun`, `ProbeSummary`, `ProbeResult` (after the `LiftResult` class, before `class Provenance`).
- **Create** `tests/test_elicitation.py` — fake-model unit tests: aggregation, refusal handling, guard refusals, the L-13 real-prompt floor.
- **Modify** `tests/test_sp3_progression.py` — add the P2 loop-side equivalence guardian.
- **Create** `tests/test_elicitation_acceptance.py` — `@live` smoke (self-skips without a key).

---

### Task 1: Probe result types in `types.py`

**Files:**
- Modify: `src/retnovation/types.py` (insert after the `LiftResult` class — after its `below_floor` property, before `class Provenance`)
- Test: `tests/test_elicitation.py`

**Interfaces:**
- Consumes: `FrameState`, `TrapState` (already in `types.py`), `BaseModel`, `Field`.
- Produces:
  - `ProbeRun(experience_id: str, run_index: int, opening: str, refused: bool = False, frame_states: dict[str, FrameState] = {}, trap_states: dict[str, TrapState] = {})`
  - `ProbeSummary(experience_id: str, total_runs: int, refused_runs: int, usable_runs: int, target_present_reasoned: int, target_present_asserted: int, target_absent: int, trap_trips: dict[str, int])`
  - `ProbeResult(target_frame_code: str, runs: list[ProbeRun])` with method `summarize() -> list[ProbeSummary]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_elicitation.py`:

```python
from retnovation.types import FrameState, ProbeResult, ProbeRun, TrapState


def _run(eid, i, target_state, trips=(), refused=False):
    return ProbeRun(
        experience_id=eid,
        run_index=i,
        opening="" if refused else f"opening-{eid}-{i}",
        refused=refused,
        frame_states={} if refused else {"embed_credentials_as_a_list": target_state},
        trap_states={} if refused else {t: TrapState.tripped for t in trips},
    )


def test_summarize_counts_states_trips_and_refusals():
    result = ProbeResult(
        target_frame_code="embed_credentials_as_a_list",
        runs=[
            _run("irreversible_anchor", 0, FrameState.present_reasoned, trips=()),
            _run("irreversible_anchor", 1, FrameState.absent, trips=("deferred_the_one_time_choice",)),
            _run("irreversible_anchor", 2, FrameState.absent, refused=True),
        ],
    )
    (s,) = result.summarize()
    assert s.experience_id == "irreversible_anchor"
    assert (s.total_runs, s.usable_runs, s.refused_runs) == (3, 2, 1)
    assert (s.target_present_reasoned, s.target_present_asserted, s.target_absent) == (1, 0, 1)
    assert s.trap_trips == {"deferred_the_one_time_choice": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py::test_summarize_counts_states_trips_and_refusals -q`
Expected: FAIL with `ImportError` / `cannot import name 'ProbeResult'`.

- [ ] **Step 3: Add the types**

Insert into `src/retnovation/types.py` after the `LiftResult` class (its `below_floor` property), before `class Provenance`:

```python
class ProbeRun(BaseModel):
    experience_id: str
    run_index: int
    opening: str  # verbatim learner output — gitignored artifact only, never committed
    refused: bool = False
    frame_states: dict[str, FrameState] = Field(default_factory=dict)
    trap_states: dict[str, TrapState] = Field(default_factory=dict)


class ProbeSummary(BaseModel):
    experience_id: str
    total_runs: int
    refused_runs: int
    usable_runs: int  # total_runs - refused_runs; the present-reasoned-rate denominator
    target_present_reasoned: int
    target_present_asserted: int
    target_absent: int
    trap_trips: dict[str, int]  # trap_code -> tripped count across usable runs (first-class)


class ProbeResult(BaseModel):
    target_frame_code: str
    runs: list[ProbeRun]

    def summarize(self) -> list[ProbeSummary]:
        by_exp: dict[str, list[ProbeRun]] = {}
        for r in self.runs:
            by_exp.setdefault(r.experience_id, []).append(r)
        out: list[ProbeSummary] = []
        for eid, runs in by_exp.items():
            usable = [r for r in runs if not r.refused]
            trips: dict[str, int] = {}
            for r in usable:
                for code, st in r.trap_states.items():
                    if st is TrapState.tripped:
                        trips[code] = trips.get(code, 0) + 1
            tgt = self.target_frame_code
            out.append(
                ProbeSummary(
                    experience_id=eid,
                    total_runs=len(runs),
                    refused_runs=len(runs) - len(usable),
                    usable_runs=len(usable),
                    target_present_reasoned=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.present_reasoned
                    ),
                    target_present_asserted=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.present_asserted
                    ),
                    target_absent=sum(
                        1 for r in usable if r.frame_states.get(tgt) is FrameState.absent
                    ),
                    trap_trips=trips,
                )
            )
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/types.py tests/test_elicitation.py
git commit -m "feat(elicitation): ProbeRun/ProbeSummary/ProbeResult types + summarize aggregation"
```
Expected: suite green; commit created.

---

### Task 2: Equivalence + L-13 guards in `elicitation.py`

**Files:**
- Create: `src/retnovation/elicitation.py`
- Test: `tests/test_elicitation.py`

**Interfaces:**
- Consumes: `Rubric`, `Frame`, `Trap`, `Mode` (from `types.py`); `load_experience` (from `content_loader.py`).
- Produces:
  - `DEFAULT_TARGET = "embed_credentials_as_a_list"`
  - `assert_intake_equivalence(rubric: Rubric | None, target_frame_code: str) -> None` — raises `ValueError` unless: rubric is not None; `target_frame_code` is one of the rubric's frames; `rubric.decision_frame is None`; `rubric.binding_constraint != target_frame_code`.
  - `assert_no_frame_code_leak(prompt: str, frame_codes: list[str]) -> None` — raises `ValueError` if any code is a substring of `prompt`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_elicitation.py`:

```python
import pytest

from retnovation.content_loader import load_experience
from retnovation.elicitation import (
    DEFAULT_TARGET,
    assert_intake_equivalence,
    assert_no_frame_code_leak,
)
from retnovation.types import Frame, Mode, Rubric, Trap

TARGET = "embed_credentials_as_a_list"


def _rubric(*, decision_frame=None, binding_constraint=None, frames=(TARGET,)):
    return Rubric(
        frames=[Frame(frame_code=c, frame_detail="d", paired_trap=None) for c in frames],
        traps=[Trap(trap_code="t", trap_detail="d")],
        mode=Mode.genuinely_open,
        binding_constraint=binding_constraint,
        decision_frame=decision_frame,
    )


def test_guard_passes_the_two_real_rubrics():
    for eid in ("irreversible_anchor", "continuity_lock_in"):
        assert_intake_equivalence(load_experience(eid).rubric, DEFAULT_TARGET)  # no raise


def test_guard_refuses_decision_frame():
    with pytest.raises(ValueError, match="decision_frame"):
        assert_intake_equivalence(_rubric(decision_frame=TARGET), TARGET)


def test_guard_refuses_target_as_binding_constraint():
    with pytest.raises(ValueError, match="binding_constraint"):
        assert_intake_equivalence(_rubric(binding_constraint=TARGET), TARGET)


def test_guard_refuses_target_not_in_rubric():
    with pytest.raises(ValueError, match="not a frame"):
        assert_intake_equivalence(_rubric(frames=("some_other_frame",)), TARGET)


def test_guard_refuses_none_rubric():
    with pytest.raises(ValueError, match="rubric"):
        assert_intake_equivalence(None, TARGET)


def test_no_frame_code_leak_passes_real_prompts():
    for eid in ("irreversible_anchor", "continuity_lock_in"):
        exp = load_experience(eid)
        assert_no_frame_code_leak(exp.prompt, [f.frame_code for f in exp.rubric.frames])


def test_no_frame_code_leak_raises_on_a_planted_code():
    with pytest.raises(ValueError, match="frame code"):
        assert_no_frame_code_leak("decide using embed_credentials_as_a_list now", [TARGET])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q -k "guard or leak"`
Expected: FAIL with `ModuleNotFoundError: No module named 'retnovation.elicitation'`.

- [ ] **Step 3: Create `src/retnovation/elicitation.py`**

```python
from __future__ import annotations

from .types import Rubric

DEFAULT_TARGET = "embed_credentials_as_a_list"


def assert_intake_equivalence(rubric: Rubric | None, target_frame_code: str) -> None:
    """Refuse any rubric where intake `present_reasoned` is NOT provably equivalent to the
    target landing in `reasoned_unprompted`. Encodes the rubric half of the proof (the loop
    half is pinned by the fixtured guardian in tests/test_sp3_progression.py). See the spec's
    "Durability of the proof" section."""
    if rubric is None:
        raise ValueError("intake-only equivalence requires an open_ended rubric; got None")
    frame_codes = {f.frame_code for f in rubric.frames}
    if target_frame_code not in frame_codes:
        raise ValueError(
            f"target {target_frame_code!r} is not a frame in the rubric ({sorted(frame_codes)})"
        )
    if rubric.decision_frame is not None:
        raise ValueError(
            "intake-only equivalence requires decision_frame is None; "
            f"rubric has decision_frame={rubric.decision_frame!r} (it would be force-probed)"
        )
    if rubric.binding_constraint == target_frame_code:
        raise ValueError(
            "intake-only equivalence requires the target not be the binding_constraint; "
            f"target {target_frame_code!r} is the binding_constraint (it could be probed)"
        )


def assert_no_frame_code_leak(prompt: str, frame_codes: list[str]) -> None:
    """L-13 automated floor: the learner-facing prompt must not contain any frame code verbatim.
    (A plain-words paraphrase is caught by the human verbatim adjudication, not here.)"""
    leaked = [c for c in frame_codes if c in prompt]
    if leaked:
        raise ValueError(f"L-13 floor: frame code(s) {leaked} appear in the learner-facing prompt")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q`
Expected: PASS (all elicitation tests green).

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/elicitation.py tests/test_elicitation.py
git commit -m "feat(elicitation): intake-equivalence guard + L-13 no-frame-code floor"
```

> **Reviewer:** OPUS — verify the guard encodes exactly the rubric half of the proof's hypotheses (decision_frame, binding, target-in-rubric, non-None) and nothing it cannot honestly check.

---

### Task 3: `run_elicitation_probe` in `elicitation.py`

**Files:**
- Modify: `src/retnovation/elicitation.py`
- Test: `tests/test_elicitation.py`

**Interfaces:**
- Consumes: `assert_intake_equivalence`, `assert_no_frame_code_leak`, `DEFAULT_TARGET` (Task 2); `ProbeRun`, `ProbeResult` (Task 1); `Model` protocol (`generate_output(scenario_prompt, injection) -> GeneratedOutput`, `classify_intake(exp, opening) -> IntakeClassification`); `Experience`.
- Produces: `run_elicitation_probe(experiences: list[Experience], model: Model, *, runs_by_id: dict[str, int], target_frame_code: str = DEFAULT_TARGET) -> ProbeResult`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_elicitation.py`:

```python
from retnovation.elicitation import run_elicitation_probe
from retnovation.model import IntakeClassification
from retnovation.types import FrameState, GeneratedOutput, ProbeResult, TrapState


class _FakeProbeModel:
    """generate_output pops scripted outputs in order; classify_intake returns a fixed intake
    keyed by the opening text. Raises if classify_intake is called on a refused (empty) opening."""

    def __init__(self, outputs, intake_by_text):
        self._outputs = list(outputs)
        self._intake_by_text = intake_by_text
        self.classify_calls = 0

    def generate_output(self, scenario_prompt, injection):
        assert injection is None  # frame-naive by construction (bare = the SP2 control call)
        return self._outputs.pop(0)

    def classify_intake(self, exp, opening):
        self.classify_calls += 1
        return self._intake_by_text[opening]


def _intake(target_state, traps):
    return IntakeClassification(
        frame_states={"embed_credentials_as_a_list": target_state},
        trap_states=traps,
    )


def test_probe_records_states_and_verbatim_per_run():
    exp = load_experience("continuity_lock_in")
    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="op-0"), GeneratedOutput(text="op-1")],
        intake_by_text={
            "op-0": _intake(FrameState.present_reasoned, {"shipped_the_one_shot_term": TrapState.not_tripped}),
            "op-1": _intake(FrameState.absent, {"shipped_the_one_shot_term": TrapState.tripped}),
        },
    )
    result = run_elicitation_probe([exp], model, runs_by_id={"continuity_lock_in": 2})
    assert isinstance(result, ProbeResult) and len(result.runs) == 2
    assert [r.opening for r in result.runs] == ["op-0", "op-1"]
    assert result.runs[0].frame_states["embed_credentials_as_a_list"] is FrameState.present_reasoned
    assert result.runs[1].trap_states["shipped_the_one_shot_term"] is TrapState.tripped


def test_probe_records_refusal_and_skips_intake():
    exp = load_experience("continuity_lock_in")
    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="", refused=True)],
        intake_by_text={},  # classify_intake would KeyError if called — proves it is skipped
    )
    result = run_elicitation_probe([exp], model, runs_by_id={"continuity_lock_in": 1})
    assert result.runs[0].refused is True
    assert result.runs[0].frame_states == {}
    assert model.classify_calls == 0


def test_probe_enforces_the_equivalence_guard():
    # a cs_technical experience has rubric=None -> guard refuses before any model call
    from retnovation.content_loader import load_checkable_experience

    exp = load_checkable_experience("consensus_safety_liveness")  # checkable -> rubric is None
    with pytest.raises(ValueError):
        run_elicitation_probe([exp], _FakeProbeModel([], {}), runs_by_id={exp.experience_id: 1})
```

> `content/checkables/consensus_safety_liveness.yaml` exists (confirmed). The test only needs an experience whose `rubric is None`; if that file is ever renamed, any present checkable stem works.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q -k "probe"`
Expected: FAIL with `cannot import name 'run_elicitation_probe'`.

- [ ] **Step 3: Add `run_elicitation_probe`**

Append to `src/retnovation/elicitation.py` (and extend the import line):

```python
from .model import Model
from .types import Experience, ProbeResult, ProbeRun, Rubric
```

```python
def run_elicitation_probe(
    experiences: list[Experience],
    model: Model,
    *,
    runs_by_id: dict[str, int],
    target_frame_code: str = DEFAULT_TARGET,
) -> ProbeResult:
    """Pure orchestration over the Model protocol. For each experience: assert the equivalence
    + L-13 preconditions once, then per run capture a bare frame-naive opening and its real
    intake classification. A refused opening is recorded and its intake skipped."""
    runs: list[ProbeRun] = []
    for exp in experiences:
        assert_intake_equivalence(exp.rubric, target_frame_code)
        assert_no_frame_code_leak(exp.prompt, [f.frame_code for f in exp.rubric.frames])
        for i in range(runs_by_id[exp.experience_id]):
            output = model.generate_output(exp.prompt, None)  # bare = no system = frame-naive
            if output.refused:
                runs.append(
                    ProbeRun(
                        experience_id=exp.experience_id,
                        run_index=i,
                        opening=output.text,
                        refused=True,
                    )
                )
                continue
            intake = model.classify_intake(exp, output.text)
            runs.append(
                ProbeRun(
                    experience_id=exp.experience_id,
                    run_index=i,
                    opening=output.text,
                    refused=False,
                    frame_states=dict(intake.frame_states),
                    trap_states=dict(intake.trap_states),
                )
            )
    return ProbeResult(target_frame_code=target_frame_code, runs=runs)
```

> Note: `Rubric` is already imported from Task 2; only add `Model`, `Experience`, `ProbeResult`, `ProbeRun` to the imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/elicitation.py tests/test_elicitation.py
git commit -m "feat(elicitation): run_elicitation_probe — bare opening -> real intake, refusal-aware, guard-gated"
```

> **Reviewer:** OPUS — verify purity (no I/O/SDK in the module), the refusal path skips `classify_intake`, the guard runs before any model call, and `injection=None` on every `generate_output`.

---

### Task 4: `run_elicitation.py` I/O entrypoint

**Files:**
- Create: `src/retnovation/run_elicitation.py`
- Test: `tests/test_elicitation.py`

**Interfaces:**
- Consumes: `run_elicitation_probe`, `DEFAULT_TARGET`; `load_experience`; `AnthropicModel`; `ProbeResult`.
- Produces: `run(model=None, *, runs_by_id=RUNS_BY_ID, data_dir=DATA_DIR, target_frame_code=DEFAULT_TARGET, now=None) -> tuple[Path, ProbeResult]`; `main() -> None`; module constants `RUNS_BY_ID`, `DATA_DIR`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_elicitation.py`:

```python
import json
from datetime import datetime, timezone


def test_run_writes_artifact_and_returns_result(tmp_path):
    from retnovation import run_elicitation

    model = _FakeProbeModel(
        outputs=[GeneratedOutput(text="op-x")],
        intake_by_text={"op-x": _intake(FrameState.present_reasoned, {})},
    )
    path, result = run_elicitation.run(
        model,
        runs_by_id={"continuity_lock_in": 1},
        data_dir=tmp_path,
        now=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
    )
    assert path == tmp_path / "20260627T120000Z.json"
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk["runs"][0]["opening"] == "op-x"
    assert isinstance(result, ProbeResult)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py::test_run_writes_artifact_and_returns_result -q`
Expected: FAIL with `cannot import name 'run_elicitation'`.

- [ ] **Step 3: Create `src/retnovation/run_elicitation.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_experience
from .elicitation import DEFAULT_TARGET, run_elicitation_probe
from .types import ProbeResult

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "elicitation"
RUNS_BY_ID = {"irreversible_anchor": 8, "continuity_lock_in": 5}


def run(
    model=None,
    *,
    runs_by_id: dict[str, int] = RUNS_BY_ID,
    data_dir: Path = DATA_DIR,
    target_frame_code: str = DEFAULT_TARGET,
    now: datetime | None = None,
) -> tuple[Path, ProbeResult]:
    if model is None:
        from .model import AnthropicModel  # lazy: tests never need the SDK

        model = AnthropicModel()
    if now is None:
        now = datetime.now(timezone.utc)
    experiences = [load_experience(eid) for eid in runs_by_id]
    result = run_elicitation_probe(
        experiences, model, runs_by_id=runs_by_id, target_frame_code=target_frame_code
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(result.model_dump_json(indent=2))
    return path, result


def main() -> None:
    path, result = run()
    print(f"wrote {path}")
    for s in result.summarize():
        print(f"\n[{s.experience_id}] usable={s.usable_runs}/{s.total_runs} refused={s.refused_runs}")
        print(
            f"  {result.target_frame_code}: present_reasoned={s.target_present_reasoned} "
            f"present_asserted={s.target_present_asserted} absent={s.target_absent}"
        )
        print(f"  trap trips: {s.trap_trips or '{}'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/run_elicitation.py tests/test_elicitation.py
git commit -m "feat(elicitation): run_elicitation entrypoint — gitignored artifact + abstracted summary"
```

---

### Task 5: P2 loop-side equivalence guardian

**Files:**
- Modify: `tests/test_sp3_progression.py` (append; reuses that file's existing imports + `_closed` helper)

**Interfaces:**
- Consumes: `assess`, `Work`, `FakeModel`, `IntakeClassification`, `FrameState`, `TrapState`, `load_experience` (already imported in this file); `_closed()` (already defined).
- Produces: a regression that pins the *loop half* of the intake↔`reasoned_unprompted` equivalence for the `continuity_lock_in` rubric shape.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sp3_progression.py`:

```python
def test_loop_guardian_embed_unprompted_on_continuity_lock_in():
    # Loop-side equivalence guardian (P2 analogue of test_session1_...): embed present_reasoned at
    # intake on the isolate; one trap tripped so the loop ACTUALLY runs a probe on another target;
    # embed must still land in reasoned_unprompted and never be probed. A judgment-loop edit that
    # lets a present-at-intake frame be probed/lowered turns this red — the enforcement the
    # rubric-shaped guard (assert_intake_equivalence) structurally cannot provide.
    exp = load_experience("continuity_lock_in")
    intake = IntakeClassification(
        frame_states={"embed_credentials_as_a_list": FrameState.present_reasoned},
        trap_states={
            "shipped_the_one_shot_term": TrapState.tripped,
            "over_built_the_escape_hatch": TrapState.not_tripped,
            "treated_the_shipped_choice_as_amendable": TrapState.not_tripped,
        },
    )
    model = FakeModel(intake, {"shipped_the_one_shot_term": _closed()})
    work = Work(opening="reasoning that already holds the move", respond=lambda push: "mechanism")
    a = assess(exp, work, model)
    probed = {p.target_code for p in a.trajectory}
    assert "embed_credentials_as_a_list" in a.reasoned_unprompted
    assert "embed_credentials_as_a_list" not in probed
    assert "shipped_the_one_shot_term" in probed  # the loop did run a probe — guardian is non-trivial
```

- [ ] **Step 2: Run test to verify it passes immediately (it pins existing behavior)**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_sp3_progression.py::test_loop_guardian_embed_unprompted_on_continuity_lock_in -v`
Expected: PASS. (This is a *guardian* over already-correct loop behavior, not new code — it should pass on first run. If it FAILS, stop: either the loop does not behave as the equivalence proof claims, or the fixture is wrong. Investigate before proceeding — a red here means the spec's load-bearing claim is false.)

- [ ] **Step 3: Confirm it is a real guardian (sanity, no commit)**

Temporarily, in a scratch check only, confirm the assertion `"embed_credentials_as_a_list" not in probed` would catch a regression: re-read `judgment_loop._select_target:49-53` and confirm a `present_reasoned` frame is skipped. (Do not edit `judgment_loop.py`.)

- [ ] **Step 4: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add tests/test_sp3_progression.py
git commit -m "test(sp3): P2 loop-side equivalence guardian — embed unprompted + unprobed on continuity_lock_in"
```

> **Reviewer:** OPUS — confirm the guardian is non-trivial (the loop runs a probe on the trap), pins both halves it claims (`in reasoned_unprompted` AND `not in probed`), and that its green status is what the probe's intake-only validity is declared to depend on.

---

### Task 6: `@live` acceptance smoke

**Files:**
- Create: `tests/test_elicitation_acceptance.py`

**Interfaces:**
- Consumes: `run_elicitation_probe`, `DEFAULT_TARGET`; `load_experience`; `AnthropicModel`; `ProbeResult`, `FrameState`.

- [ ] **Step 1: Write the test**

Create `tests/test_elicitation_acceptance.py`:

```python
import os

import pytest

from retnovation.content_loader import load_experience
from retnovation.elicitation import DEFAULT_TARGET, run_elicitation_probe
from retnovation.types import FrameState, ProbeResult

_HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential")
def test_live_elicitation_smoke():
    """One real Opus run on the isolate: the pipeline returns a valid ProbeResult with the target
    classified. NO assertion on the substantive verdict — that is the human's (SP1/L-15)."""
    from retnovation.model import AnthropicModel

    exp = load_experience("continuity_lock_in")
    result = run_elicitation_probe(
        [exp], AnthropicModel(), runs_by_id={"continuity_lock_in": 1}
    )
    assert isinstance(result, ProbeResult) and len(result.runs) == 1
    run = result.runs[0]
    if not run.refused:
        assert DEFAULT_TARGET in run.frame_states
        assert all(isinstance(v, FrameState) for v in run.frame_states.values())
```

> The L-13 real-prompt floor is already always-run (non-live) via `test_no_frame_code_leak_passes_real_prompts` in `tests/test_elicitation.py` (Task 2), which asserts the invariant on the exact strings the probe sends (`exp.prompt`). Keeping it non-live means it never skips for want of a key — strictly stronger than gating it behind `@live`.

- [ ] **Step 2: Run to verify it collects and skips cleanly without a key shape**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_elicitation_acceptance.py -q -m "not live"`
Expected: `1 deselected` / no failures (the live test is deselected; the file imports cleanly).

Then confirm full-suite collection: `PYTHONPATH=src .venv/bin/pytest -q --collect-only >/dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add tests/test_elicitation_acceptance.py
git commit -m "test(elicitation): @live smoke (self-skips without a key)"
```

> **Reviewer:** OPUS — confirm the smoke asserts only loose invariants (valid result, target classified), never the verdict; and that the L-13 real-prompt floor is genuinely always-run, not skip-gated.

---

### Task 7: Whole-branch review, DEVLOG, finish

**Files:**
- Modify: `docs/DEVLOG.md`

- [ ] **Step 1: Full suite + gates**

```bash
ruff format . && ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf|content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$' || echo "CONFIDENTIALITY GATE EMPTY"
git status --short | grep -v '^??' || echo "no un-staged tracked changes"
```
Expected: suite green; gate EMPTY.

- [ ] **Step 2: OPUS whole-branch adversarial review**

Dispatch an OPUS reviewer over the full diff against the spec + lessons. Checklist: purity of `elicitation.py`; the guard encodes exactly the rubric half (no more, no less); the loop guardian pins the loop half and is non-trivial; refusal path; `injection=None` everywhere; L-13 floor always-run on the real prompt; artifact gitignored; no `Co-Authored-By`; no confidential paths staged. Fold findings; re-run the suite.

- [ ] **Step 3: Write the DEVLOG entry**

Prepend under the `# Retnovation — DEVLOG` header:

```markdown
## 2026-06-27 — SP3 live content-elicitation probe — BUILT (suite green)
- `src/retnovation/elicitation.py` (pure, Model-protocol-only): `run_elicitation_probe` (bare
  `generate_output(prompt, None)` -> real `classify_intake`, refusal-aware), `assert_intake_equivalence`
  (rubric half of the proof — refuses decision_frame / target-as-binding / target-not-in-rubric / None),
  `assert_no_frame_code_leak` (L-13 floor). `ProbeRun`/`ProbeSummary`/`ProbeResult` in `types.py`.
- `src/retnovation/run_elicitation.py`: gated I/O entrypoint -> gitignored `data/elicitation/<utc>.json`
  + abstracted summary (no verbatim).
- Tests: `tests/test_elicitation.py` (aggregation, refusal-skips-intake, guard refusals, L-13 floor on the
  REAL prompts — always-run); `tests/test_elicitation_acceptance.py` (@live smoke, self-skips); P2
  **loop-side equivalence guardian** in `tests/test_sp3_progression.py` (embed unprompted + unprobed while
  the loop probes a trap — pins the loop half the rubric guard cannot). Suite NNN passed / M skipped.
- NEXT: the gated live run (~26 Opus calls) WITH the user, then human adjudication of the verbatim +
  verdicts (reachable / hard-at-intake / borderline⇒rerun), then DEVLOG the calibration finding.
```
(Replace `NNN`/`M` with the observed counts from Step 1.)

- [ ] **Step 4: Commit**

```bash
git add docs/DEVLOG.md
git commit -m "docs: DEVLOG — SP3 live content-elicitation probe built"
```

---

## MANUAL (gated — NOT an automated plan step): the live run + adjudication

Performed **with the user**, because it spends ~26 Opus calls and the verdict is the human's.

1. Confirm with the user, then: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m retnovation.run_elicitation`
2. Read the printed abstracted summary; open the gitignored `data/elicitation/<utc>.json` for verbatim.
3. Surface to the user, per problem: the per-run **trap-trip pattern (first-class)**, each verbatim opening + the target's intake state, the other frame's state (P1 only), and the **refusal rate (first-class)** — a heavy-refusal run reads as "prompt mis-set," not silent denominator shrink.
4. The user adjudicates the three-way calibration read: **reachable** (then read the verbatim to confirm the scaffold did not leak the move in plain words, L-6), **genuinely-hard at intake** (trap tripped — counter-intuitive, no leak; note: the intake-only probe is blind to hard-at-intake-but-recoverable-under-pressure), or **borderline** (→ rerun with higher n; n cannot stably adjudicate the middle).
5. Record the abstracted calibration finding in DEVLOG + handoff + the `retnovation-project` memory.

---

## Self-Review (completed by author)

- **Spec coverage:** equivalence proof → guard (Task 2) + loop guardian (Task 5); intake-only probe (Task 3); bare learner / `injection=None` (Task 3, asserted in the fake); both problems + P1-weighted sampling (Task 4 `RUNS_BY_ID`); gitignored artifact + abstracted summary (Task 4); fake-aggregation + guard-refusal tests (Tasks 1–3); @live smoke + L-13 real-prompt floor (Tasks 2, 6); trap-pattern & refusal first-class + n-resolution + hard-at-intake (summary fields Task 1; MANUAL adjudication). All covered.
- **Placeholder scan:** none — every code/test step carries complete code; the only deferred numerals are the DEVLOG suite counts (filled from observed output) and the Task-3 checkable stem (a `ls` confirms it).
- **Type consistency:** `ProbeRun`/`ProbeSummary`/`ProbeResult`/`summarize`, `assert_intake_equivalence`, `assert_no_frame_code_leak`, `run_elicitation_probe`, `DEFAULT_TARGET`, `run`/`RUNS_BY_ID`/`DATA_DIR` used identically across tasks and tests.
