# Harness Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the six-link loop (`aim → core → experience → assessment → state → cadence`) into one running cycle on a single fixed experience, so the dry run closes end-to-end with no manual stitching.

**Architecture:** A thin orchestrator over a rented model. Pure-Python modules with one responsibility each, communicating only through typed interfaces in `types.py`. The rented model sits behind a `Model` Protocol so tests inject a scripted fake; doctrine (maps, rubrics) is versioned YAML loaded from `content/`, never hardcoded. SQLite persists the only three durable things: learner state, ledger, queue.

**Tech Stack:** Python ≥3.12, pydantic v2, PyYAML, anthropic SDK (real model adapter, not exercised in tests), pytest, ruff, sqlite3 (stdlib).

## Global Constraints

- Python `requires-python = ">=3.12"`; line length 100 (ruff).
- Dependencies are fixed: `pydantic>=2.0`, `pyyaml>=6.0`, `anthropic>=0.40`; dev `pytest>=8.0`, `ruff>=0.6`. Do not add others.
- Source layout is `src/retnovation/`; tests in `tests/`.
- **Doctrine as data:** frames/traps/maps live in `content/*.yaml`, never as literals in `src/`.
- **Reversible decay, never deletion:** learner-state frame rows are demoted/rescheduled with `UPDATE`, never `DELETE`. (The work `queue` may pop/delete normally — it is not decay-protected state.)
- **Open-ended state moves on rigor/trajectory, never correctness.** The conclusion is never graded.
- Real model id is `claude-opus-4-8` (used only in the untested adapter; consult the `claude-api` reference before wiring it).
- Commit rules: NEVER a `Co-Authored-By` trailer; stage explicit paths only (never `git add -A`); never stage confidential docs or `data/`. Update `docs/DEVLOG.md` after each task.
- Every task ends green: `ruff check . && pytest` pass before commit.

## File Structure

- `src/retnovation/types.py` — all pydantic models, enums, and the `Work` dataclass.
- `src/retnovation/content_loader.py` — load maps + rubrics from `content/`.
- `content/maps/founder_ceo.yaml`, `content/rubrics/veldra_licensing_continuity.yaml` — doctrine data.
- `src/retnovation/persistence.py` — `Store` (SQLite) for state, ledger, queue.
- `src/retnovation/model.py` — `Model` Protocol, classification types, `FakeModel`, `AnthropicModel` adapter.
- `src/retnovation/aim.py` — `aim()`, `derive_core()`.
- `src/retnovation/state.py` — `update_state()` + strength estimator.
- `src/retnovation/scheduler.py` — `schedule_next()`.
- `src/retnovation/assessment/judgment_loop.py` — `assess()` (open_ended).
- `src/retnovation/assessment/checkable_scorer.py` — `assess()` stub.
- `src/retnovation/assessment/__init__.py` — `ASSESSORS` registry + `get_assessor()`.
- `src/retnovation/experience.py` — `select_experience()`.
- `src/retnovation/orchestration.py` — `run_session()`, `present_and_collect()`.
- `src/retnovation/cli.py` — `main()`.
- `tests/...` — one test module per source module + `tests/test_dry_run.py`.

---

### Task 1: Types & enums

**Files:**
- Create: `src/retnovation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces: all enums and models below. Canonical signatures every later task depends on:
  - Enums (`str, Enum`): `Strength{weak,forming,strong}`, `Regime{open_ended,cs_technical}`, `Mode{genuinely_open,bounded_error}`, `FrameState{absent,present_asserted,present_reasoned}`, `TrapState{not_tripped,tripped,repaired}`, `StopReason{converged,bounded_error_violation,plateau,regression,budget}`.
  - `Frame(frame_code:str, frame_detail:str, paired_trap:str|None=None)`
  - `Trap(trap_code:str, trap_detail:str)`
  - `Rubric(frames:list[Frame], traps:list[Trap], mode:Mode, binding_constraint:str|None=None)`
  - `Aim(posture:str, process_dial:int, content_core:None=None)`
  - `Core(process_frames:list[str], declarative_seed:list[str], content_core:None=None)`
  - `Experience(prompt:str, rubric:Rubric, ledger_ref:str, regime:Regime)`
  - `Push(target_code:str, kind:str, text:str, response_classification:str)`
  - `FrameDelta(code:str, before:str, after:str)`
  - `Assessment(trajectory:list[Push], frame_deltas:list[FrameDelta], frames_closed_under_pressure:list[str], hard_wrong_flags:list[str], stop_reason:StopReason)`
  - `FrameStrength(strength:Strength, last_seen:datetime, due:datetime, last_evidence:str)`
  - `TrapOccurrence(experience_id:str, occurred_at:datetime, detail:str)`
  - `SpacedItem(concept:str, due:datetime, interval_days:int)`
  - `LearnerState(frames:dict[str,FrameStrength]={}, trap_gallery:dict[str,list[TrapOccurrence]]={}, declarative_seed:dict[str,SpacedItem]={})`
  - `LedgerEntry(id:str, owned_problem:str, links_to_experiences:list[str]=[])`
  - `NextExperienceSpec(target_frames:list[str], ledger_ref:str, regime:Regime)`
  - `Work` (dataclass): `opening:str`, `respond:Callable[[str],str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from datetime import datetime, timezone
from retnovation.types import (
    Strength, Regime, Mode, FrameState, StopReason,
    Frame, Trap, Rubric, Experience, Assessment, Push, FrameDelta,
    LearnerState, FrameStrength, NextExperienceSpec, Work,
)


def test_experience_roundtrips_through_json():
    rub = Rubric(
        frames=[Frame(frame_code="protect_the_core_lane", frame_detail="keep the core promise")],
        traps=[Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case one account")],
        mode=Mode.genuinely_open,
    )
    exp = Experience(prompt="...", rubric=rub, ledger_ref="veldra:licensing_continuity",
                     regime=Regime.open_ended)
    again = Experience.model_validate_json(exp.model_dump_json())
    assert again.regime is Regime.open_ended
    assert again.rubric.frames[0].frame_code == "protect_the_core_lane"


def test_learner_state_defaults_are_independent():
    a, b = LearnerState(), LearnerState()
    now = datetime.now(timezone.utc)
    a.frames["x"] = FrameStrength(strength=Strength.weak, last_seen=now, due=now, last_evidence="")
    assert b.frames == {}  # no shared mutable default


def test_assessment_holds_stop_reason_and_work_is_callable():
    asmt = Assessment(trajectory=[Push(target_code="f", kind="frame", text="t",
                                       response_classification="closed")],
                      frame_deltas=[FrameDelta(code="f", before=FrameState.absent,
                                               after=FrameState.present_reasoned)],
                      frames_closed_under_pressure=["f"], hard_wrong_flags=[],
                      stop_reason=StopReason.converged)
    assert asmt.stop_reason is StopReason.converged
    w = Work(opening="hi", respond=lambda push: "ok")
    assert w.respond("anything") == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'retnovation.types'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/types.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Strength(str, Enum):
    weak = "weak"
    forming = "forming"
    strong = "strong"


class Regime(str, Enum):
    open_ended = "open_ended"
    cs_technical = "cs_technical"


class Mode(str, Enum):
    genuinely_open = "genuinely_open"
    bounded_error = "bounded_error"


class FrameState(str, Enum):
    absent = "absent"
    present_asserted = "present_asserted"
    present_reasoned = "present_reasoned"


class TrapState(str, Enum):
    not_tripped = "not_tripped"
    tripped = "tripped"
    repaired = "repaired"


class StopReason(str, Enum):
    converged = "converged"
    bounded_error_violation = "bounded_error_violation"
    plateau = "plateau"
    regression = "regression"
    budget = "budget"


class Frame(BaseModel):
    frame_code: str
    frame_detail: str
    paired_trap: str | None = None


class Trap(BaseModel):
    trap_code: str
    trap_detail: str


class Rubric(BaseModel):
    frames: list[Frame]
    traps: list[Trap]
    mode: Mode
    binding_constraint: str | None = None


class Aim(BaseModel):
    posture: str
    process_dial: int
    content_core: None = None


class Core(BaseModel):
    process_frames: list[str]
    declarative_seed: list[str]
    content_core: None = None


class Experience(BaseModel):
    prompt: str
    rubric: Rubric
    ledger_ref: str
    regime: Regime


class Push(BaseModel):
    target_code: str
    kind: str
    text: str
    response_classification: str


class FrameDelta(BaseModel):
    code: str
    before: FrameState
    after: FrameState


class Assessment(BaseModel):
    trajectory: list[Push]
    frame_deltas: list[FrameDelta]
    frames_closed_under_pressure: list[str]
    hard_wrong_flags: list[str]
    stop_reason: StopReason


class FrameStrength(BaseModel):
    strength: Strength
    last_seen: datetime
    due: datetime
    last_evidence: str


class TrapOccurrence(BaseModel):
    experience_id: str
    occurred_at: datetime
    detail: str


class SpacedItem(BaseModel):
    concept: str
    due: datetime
    interval_days: int


class LearnerState(BaseModel):
    frames: dict[str, FrameStrength] = Field(default_factory=dict)
    trap_gallery: dict[str, list[TrapOccurrence]] = Field(default_factory=dict)
    declarative_seed: dict[str, SpacedItem] = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    id: str
    owned_problem: str
    links_to_experiences: list[str] = Field(default_factory=list)


class NextExperienceSpec(BaseModel):
    target_frames: list[str]
    ledger_ref: str
    regime: Regime


@dataclass
class Work:
    opening: str
    respond: Callable[[str], str]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_types.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: typed interfaces for the six-link loop"
```

---

### Task 2: Content loader + doctrine YAML

**Files:**
- Create: `src/retnovation/content_loader.py`, `content/maps/founder_ceo.yaml`, `content/rubrics/veldra_licensing_continuity.yaml`
- Test: `tests/test_content_loader.py`

**Interfaces:**
- Consumes: `types.Core`, `types.Rubric`.
- Produces:
  - `CONTENT_ROOT: Path` (defaults to repo `content/`, override via arg)
  - `load_map(posture:str, root:Path|None=None) -> tuple[list[str], list[str]]` returns `(process_frames, declarative_seed)`
  - `load_rubric(name:str, root:Path|None=None) -> Rubric`
  - `load_experience_meta(name:str, root:Path|None=None) -> dict` returns `{prompt, ledger_ref, regime}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_content_loader.py
from retnovation import content_loader
from retnovation.types import Mode


def test_load_founder_ceo_map():
    frames, seed = content_loader.load_map("founder_ceo")
    assert "protect_the_core_lane" in frames
    assert "reversible_vs_irreversible" in seed


def test_load_rubric_parses_frames_traps_mode():
    rub = content_loader.load_rubric("veldra_licensing_continuity")
    assert rub.mode is Mode.genuinely_open
    assert any(f.frame_code == "protect_the_core_lane" for f in rub.frames)
    assert any(t.trap_code == "erode_core_for_one_customer" for t in rub.traps)


def test_load_experience_meta():
    meta = content_loader.load_experience_meta("veldra_licensing_continuity")
    assert meta["ledger_ref"] == "veldra:licensing_continuity"
    assert meta["regime"] == "open_ended"
    assert meta["prompt"].strip()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_content_loader.py -v`
Expected: FAIL with `ModuleNotFoundError` / file-not-found.

- [ ] **Step 3: Write the YAML content, then the loader**

```yaml
# content/maps/founder_ceo.yaml
posture: founder_ceo
process_frames:
  - choose_the_failure_default_deliberately
  - lead_with_what_you_refuse_to_do
  - protect_the_core_lane
declarative_seed:
  - reversible_vs_irreversible
  - build_vs_buy
```

```yaml
# content/rubrics/veldra_licensing_continuity.yaml
experience_id: veldra_licensing_continuity
ledger_ref: "veldra:licensing_continuity"
regime: open_ended
mode: genuinely_open
binding_constraint: null
prompt: >
  A long-standing customer is mid-rollout when a contract ambiguity surfaces:
  honoring their reading costs you a guarantee you make to everyone else; refusing
  risks the rollout and the relationship. They want an answer today. Decide what you
  do and account for what you are trading. (No framework is named for you on purpose.)
frames:
  - frame_code: lead_with_what_you_refuse_to_do
    frame_detail: State the boundary you will not cross before proposing any action.
    paired_trap: scope_creep_to_please
  - frame_code: protect_the_core_lane
    frame_detail: Keep the promise the core product makes to everyone intact under pressure.
    paired_trap: erode_core_for_one_customer
traps:
  - trap_code: scope_creep_to_please
    trap_detail: Bending the offer to avoid saying no.
  - trap_code: erode_core_for_one_customer
    trap_detail: Special-casing one account in a way that weakens the core promise.
```

```python
# src/retnovation/content_loader.py
from __future__ import annotations

from pathlib import Path

import yaml

from .types import Frame, Rubric, Trap

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"


def _root(root: Path | None) -> Path:
    return root if root is not None else CONTENT_ROOT


def load_map(posture: str, root: Path | None = None) -> tuple[list[str], list[str]]:
    data = yaml.safe_load((_root(root) / "maps" / f"{posture}.yaml").read_text())
    return list(data["process_frames"]), list(data["declarative_seed"])


def load_rubric(name: str, root: Path | None = None) -> Rubric:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=data["mode"],
        binding_constraint=data.get("binding_constraint"),
    )


def load_experience_meta(name: str, root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return {"prompt": data["prompt"], "ledger_ref": data["ledger_ref"], "regime": data["regime"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_content_loader.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/content_loader.py content/ tests/test_content_loader.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: content loader for doctrine maps and rubrics"
```

---

### Task 3: Persistence (SQLite Store)

**Files:**
- Create: `src/retnovation/persistence.py`
- Test: `tests/test_persistence.py`

**Interfaces:**
- Consumes: `types.LearnerState, FrameStrength, Strength, LedgerEntry, NextExperienceSpec, Regime`.
- Produces `class Store`:
  - `Store(db_path: str | Path)` — opens/creates DB and schema.
  - `load_state() -> LearnerState`
  - `save_state(state: LearnerState) -> None` (UPSERT frames; never DELETE)
  - `decay_frame(frame_code:str, new_strength:Strength, new_due:datetime) -> None` (UPDATE only)
  - `add_ledger_entry(entry: LedgerEntry) -> None`; `load_ledger() -> list[LedgerEntry]`
  - `queue_push(spec: NextExperienceSpec) -> None`; `queue_pop() -> NextExperienceSpec | None`
  - `close() -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_persistence.py
from datetime import datetime, timezone

from retnovation.persistence import Store
from retnovation.types import (
    FrameStrength, LearnerState, LedgerEntry, NextExperienceSpec, Regime, Strength,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def test_state_roundtrip(tmp_path):
    s = Store(tmp_path / "t.db")
    st = LearnerState()
    st.frames["protect_the_core_lane"] = FrameStrength(
        strength=Strength.forming, last_seen=_now(), due=_now(), last_evidence="closed under pressure")
    s.save_state(st)
    loaded = Store(tmp_path / "t.db").load_state()
    assert loaded.frames["protect_the_core_lane"].strength is Strength.forming


def test_decay_updates_never_deletes(tmp_path):
    s = Store(tmp_path / "t.db")
    st = LearnerState()
    st.frames["f"] = FrameStrength(strength=Strength.strong, last_seen=_now(), due=_now(),
                                   last_evidence="x")
    s.save_state(st)
    s.decay_frame("f", Strength.forming, _now())
    loaded = s.load_state()
    assert set(loaded.frames) == {"f"}  # row still present
    assert loaded.frames["f"].strength is Strength.forming


def test_ledger_and_queue_fifo(tmp_path):
    s = Store(tmp_path / "t.db")
    s.add_ledger_entry(LedgerEntry(id="veldra:licensing_continuity", owned_problem="..."))
    assert s.load_ledger()[0].id == "veldra:licensing_continuity"
    s.queue_push(NextExperienceSpec(target_frames=["protect_the_core_lane"],
                                    ledger_ref="veldra:licensing_continuity", regime=Regime.open_ended))
    popped = s.queue_pop()
    assert popped.target_frames == ["protect_the_core_lane"]
    assert s.queue_pop() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_persistence.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/persistence.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .types import (
    FrameStrength, LearnerState, LedgerEntry, NextExperienceSpec, Regime, Strength,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
  frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL,
  last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
  id TEXT PRIMARY KEY, owned_problem TEXT NOT NULL, links_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS queue (
  position INTEGER PRIMARY KEY AUTOINCREMENT,
  target_frames_json TEXT NOT NULL, ledger_ref TEXT NOT NULL, regime TEXT NOT NULL);
"""


class Store:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def load_state(self) -> LearnerState:
        st = LearnerState()
        for r in self._db.execute("SELECT * FROM frames"):
            st.frames[r["frame_code"]] = FrameStrength(
                strength=Strength(r["strength"]),
                last_seen=datetime.fromisoformat(r["last_seen"]),
                due=datetime.fromisoformat(r["due"]),
                last_evidence=r["last_evidence"],
            )
        return st

    def save_state(self, state: LearnerState) -> None:
        for code, fs in state.frames.items():
            self._db.execute(
                "INSERT INTO frames(frame_code,strength,last_seen,due,last_evidence) "
                "VALUES(?,?,?,?,?) ON CONFLICT(frame_code) DO UPDATE SET "
                "strength=excluded.strength,last_seen=excluded.last_seen,"
                "due=excluded.due,last_evidence=excluded.last_evidence",
                (code, fs.strength.value, fs.last_seen.isoformat(), fs.due.isoformat(),
                 fs.last_evidence),
            )
        self._db.commit()

    def decay_frame(self, frame_code: str, new_strength: Strength, new_due: datetime) -> None:
        self._db.execute("UPDATE frames SET strength=?, due=? WHERE frame_code=?",
                         (new_strength.value, new_due.isoformat(), frame_code))
        self._db.commit()

    def add_ledger_entry(self, entry: LedgerEntry) -> None:
        self._db.execute(
            "INSERT INTO ledger(id,owned_problem,links_json) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET owned_problem=excluded.owned_problem,"
            "links_json=excluded.links_json",
            (entry.id, entry.owned_problem, json.dumps(entry.links_to_experiences)),
        )
        self._db.commit()

    def load_ledger(self) -> list[LedgerEntry]:
        rows = self._db.execute("SELECT * FROM ledger ORDER BY id")
        return [LedgerEntry(id=r["id"], owned_problem=r["owned_problem"],
                            links_to_experiences=json.loads(r["links_json"])) for r in rows]

    def queue_push(self, spec: NextExperienceSpec) -> None:
        self._db.execute(
            "INSERT INTO queue(target_frames_json,ledger_ref,regime) VALUES(?,?,?)",
            (json.dumps(spec.target_frames), spec.ledger_ref, spec.regime.value))
        self._db.commit()

    def queue_pop(self) -> NextExperienceSpec | None:
        row = self._db.execute("SELECT * FROM queue ORDER BY position LIMIT 1").fetchone()
        if row is None:
            return None
        self._db.execute("DELETE FROM queue WHERE position=?", (row["position"],))
        self._db.commit()
        return NextExperienceSpec(target_frames=json.loads(row["target_frames_json"]),
                                  ledger_ref=row["ledger_ref"], regime=Regime(row["regime"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_persistence.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/persistence.py tests/test_persistence.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: SQLite store with reversible-decay (no-delete) state"
```

---

### Task 4: Model interface + scripted fake

**Files:**
- Create: `src/retnovation/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `types.Experience`.
- Produces:
  - `IntakeClassification(frame_states:dict[str,FrameState], trap_states:dict[str,TrapState])` (pydantic)
  - `ResponseClassification(outcome:Literal["closed","unchanged","regressed"], mechanism_supplied:bool, hard_wrong:bool)` (pydantic)
  - `Model` Protocol: `classify_intake(exp, opening) -> IntakeClassification`; `generate_push(exp, kind, code) -> str`; `classify_response(exp, kind, code, push, response) -> ResponseClassification`
  - `FakeModel(intake: IntakeClassification, responses: dict[str, list[ResponseClassification]])`
  - `AnthropicModel(api_key:str|None=None, model:str="claude-opus-4-8")` — real adapter (NOT exercised by tests).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_model.py
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import FrameState, TrapState


def _exp():  # minimal stand-in; FakeModel ignores it
    return None


def test_fake_model_returns_scripted_intake_and_responses():
    intake = IntakeClassification(
        frame_states={"protect_the_core_lane": FrameState.absent},
        trap_states={"erode_core_for_one_customer": TrapState.not_tripped})
    responses = {"protect_the_core_lane": [
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]}
    m = FakeModel(intake=intake, responses=responses)
    assert m.classify_intake(_exp(), "opening").frame_states["protect_the_core_lane"] is FrameState.absent
    assert isinstance(m.generate_push(_exp(), "frame", "protect_the_core_lane"), str)
    rc = m.classify_response(_exp(), "frame", "protect_the_core_lane", "push", "reply")
    assert rc.outcome == "closed" and rc.mechanism_supplied is True


def test_fake_model_raises_when_script_exhausted():
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={"f": []})
    try:
        m.classify_response(_exp(), "frame", "f", "p", "r")
        raise AssertionError("expected IndexError")
    except IndexError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/model.py
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from .types import Experience, FrameState, TrapState


class IntakeClassification(BaseModel):
    frame_states: dict[str, FrameState]
    trap_states: dict[str, TrapState]


class ResponseClassification(BaseModel):
    outcome: Literal["closed", "unchanged", "regressed"]
    mechanism_supplied: bool
    hard_wrong: bool


@runtime_checkable
class Model(Protocol):
    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification: ...
    def generate_push(self, exp: Experience, kind: str, code: str) -> str: ...
    def classify_response(self, exp: Experience, kind: str, code: str, push: str,
                          response: str) -> ResponseClassification: ...


class FakeModel:
    """Deterministic, scripted model for tests. Pops one response per (code) call."""

    def __init__(self, intake: IntakeClassification,
                 responses: dict[str, list[ResponseClassification]]):
        self._intake = intake
        self._responses = responses

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        return self._intake

    def generate_push(self, exp: Experience, kind: str, code: str) -> str:
        return f"[push:{kind}:{code}]"

    def classify_response(self, exp: Experience, kind: str, code: str, push: str,
                          response: str) -> ResponseClassification:
        return self._responses[code].pop(0)


class AnthropicModel:
    """Real adapter over Claude Opus 4.8. NOT exercised by the dry run.

    Before fleshing out the prompts, consult the claude-api reference for SDK usage.
    The system prompt MUST encode the disband rules: never name the frame, never hand
    the answer, never grade the conclusion; classify only frame/trap deltas + mechanism.
    """

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-8"):
        self._model = model
        self._api_key = api_key
        # Lazy import so tests never need the SDK or network.

    def classify_intake(self, exp: Experience, opening: str) -> IntakeClassification:
        raise NotImplementedError("AnthropicModel.classify_intake: wire in step 1 interactive path")

    def generate_push(self, exp: Experience, kind: str, code: str) -> str:
        raise NotImplementedError("AnthropicModel.generate_push: wire in step 1 interactive path")

    def classify_response(self, exp, kind, code, push, response) -> ResponseClassification:
        raise NotImplementedError("AnthropicModel.classify_response: wire in step 1 interactive path")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_model.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/model.py tests/test_model.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: Model protocol with scripted FakeModel + Opus adapter stub"
```

---

### Task 5: Aim & Core (onboarding)

**Files:**
- Create: `src/retnovation/aim.py`
- Test: `tests/test_aim.py`

**Interfaces:**
- Consumes: `content_loader.load_map`, `types.Aim, Core`.
- Produces: `MAX_PROCESS_DIAL=10`; `aim(posture:str="founder_ceo") -> Aim`; `derive_core(a: Aim, root=None) -> Core`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_aim.py
from retnovation.aim import aim, derive_core, MAX_PROCESS_DIAL


def test_aim_is_founder_ceo_at_max_dial():
    a = aim()
    assert a.posture == "founder_ceo"
    assert a.process_dial == MAX_PROCESS_DIAL
    assert a.content_core is None


def test_derive_core_pulls_frames_from_map():
    core = derive_core(aim())
    assert "protect_the_core_lane" in core.process_frames
    assert "reversible_vs_irreversible" in core.declarative_seed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aim.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/aim.py
from __future__ import annotations

from pathlib import Path

from .content_loader import load_map
from .types import Aim, Core

MAX_PROCESS_DIAL = 10


def aim(posture: str = "founder_ceo") -> Aim:
    return Aim(posture=posture, process_dial=MAX_PROCESS_DIAL, content_core=None)


def derive_core(a: Aim, root: Path | None = None) -> Core:
    frames, seed = load_map(a.posture, root=root)
    return Core(process_frames=frames, declarative_seed=seed, content_core=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aim.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/aim.py tests/test_aim.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: aim and derive_core onboarding from curated map"
```

---

### Task 6: State update + strength estimator

**Files:**
- Create: `src/retnovation/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `types.LearnerState, Assessment, FrameDelta, FrameState, FrameStrength, Strength, TrapOccurrence`.
- Produces: `update_state(state: LearnerState, assessment: Assessment, now: datetime, experience_id: str) -> LearnerState`.
- Estimator rule (3-level heuristic): final frame state `present_reasoned` reached **without any push** for that frame (i.e. already reasoned at intake, surfaced via a delta `absent→present_reasoned` is push-driven) → `strong`; closed under pressure (delta ending `present_reasoned` that appears in `frames_closed_under_pressure`) → `forming`; otherwise (`absent`/`present_asserted` at end, or regressed) → `weak`. Never reads correctness. Tripped traps recorded in `trap_gallery`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from datetime import datetime, timezone

from retnovation.state import update_state
from retnovation.types import (
    Assessment, FrameDelta, FrameState, LearnerState, Push, Strength, StopReason,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _asmt(deltas, closed, traps_pushes=None):
    return Assessment(trajectory=traps_pushes or [], frame_deltas=deltas,
                      frames_closed_under_pressure=closed, hard_wrong_flags=[],
                      stop_reason=StopReason.converged)


def test_closed_under_pressure_becomes_forming():
    a = _asmt([FrameDelta(code="protect_the_core_lane", before=FrameState.absent,
                          after=FrameState.present_reasoned)],
              closed=["protect_the_core_lane"])
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert st.frames["protect_the_core_lane"].strength is Strength.forming


def test_unmoved_absent_frame_becomes_weak():
    a = _asmt([], closed=[])
    # frame present in rubric but never closed -> mark weak via trajectory target
    a.trajectory.append(Push(target_code="lead_with_what_you_refuse_to_do", kind="frame",
                             text="p", response_classification="unchanged"))
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert st.frames["lead_with_what_you_refuse_to_do"].strength is Strength.weak


def test_tripped_trap_recorded_in_gallery():
    a = _asmt([], closed=[])
    a.trajectory.append(Push(target_code="erode_core_for_one_customer", kind="trap",
                             text="p", response_classification="unchanged"))
    st = update_state(LearnerState(), a, _now(), "exp1")
    assert "erode_core_for_one_customer" in st.trap_gallery
    assert st.trap_gallery["erode_core_for_one_customer"][0].experience_id == "exp1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/state.py
from __future__ import annotations

from datetime import datetime

from .types import (
    Assessment, FrameState, FrameStrength, LearnerState, Strength, TrapOccurrence,
)


def update_state(state: LearnerState, assessment: Assessment, now: datetime,
                 experience_id: str) -> LearnerState:
    closed = set(assessment.frames_closed_under_pressure)

    # Frame strengths move on rigor/trajectory evidence only (never correctness).
    final_state: dict[str, FrameState] = {}
    for d in assessment.frame_deltas:
        final_state[d.code] = d.after

    seen_frame_targets = {p.target_code for p in assessment.trajectory if p.kind == "frame"}
    for code in seen_frame_targets | set(final_state):
        if code in closed and final_state.get(code) is FrameState.present_reasoned:
            strength = Strength.forming
        elif final_state.get(code) is FrameState.present_reasoned:
            strength = Strength.strong  # reasoned without needing the closing push
        else:
            strength = Strength.weak
        state.frames[code] = FrameStrength(
            strength=strength, last_seen=now, due=now,
            last_evidence=f"{experience_id}:{final_state.get(code, 'unmoved')}")

    # Trap gallery: any trap target that was pushed and not repaired is logged.
    for p in assessment.trajectory:
        if p.kind == "trap" and p.response_classification != "closed":
            state.trap_gallery.setdefault(p.target_code, []).append(
                TrapOccurrence(experience_id=experience_id, occurred_at=now,
                               detail=p.response_classification))
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/state.py tests/test_state.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: state update with weak/forming/strong estimator (rigor not correctness)"
```

---

### Task 7: Scheduler

**Files:**
- Create: `src/retnovation/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `types.LearnerState, LedgerEntry, NextExperienceSpec, Strength, Regime`.
- Produces: `schedule_next(state: LearnerState, ledger: list[LedgerEntry], now: datetime, regime: Regime = Regime.open_ended) -> NextExperienceSpec`.
- Policy: target the **weakest** frames first (all `weak`, else all `forming`, else the single soonest-`due` `strong`). `ledger_ref` = first ledger entry id (transfer to an owned problem). Never returns empty `target_frames` when any frame exists.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scheduler.py
from datetime import datetime, timezone

from retnovation.scheduler import schedule_next
from retnovation.types import (
    FrameStrength, LearnerState, LedgerEntry, Regime, Strength,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _state(frames):
    st = LearnerState()
    for code, strg in frames.items():
        st.frames[code] = FrameStrength(strength=strg, last_seen=_now(), due=_now(),
                                        last_evidence="")
    return st


def test_weak_frames_are_targeted_first():
    st = _state({"a": Strength.weak, "b": Strength.forming})
    led = [LedgerEntry(id="veldra:licensing_continuity", owned_problem="...")]
    spec = schedule_next(st, led, _now())
    assert spec.target_frames == ["a"]
    assert spec.ledger_ref == "veldra:licensing_continuity"
    assert spec.regime is Regime.open_ended


def test_all_strong_targets_soonest_due():
    st = _state({"a": Strength.strong, "b": Strength.strong})
    led = [LedgerEntry(id="veldra:licensing_continuity", owned_problem="...")]
    spec = schedule_next(st, led, _now())
    assert len(spec.target_frames) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/scheduler.py
from __future__ import annotations

from datetime import datetime

from .types import LearnerState, LedgerEntry, NextExperienceSpec, Regime, Strength


def schedule_next(state: LearnerState, ledger: list[LedgerEntry], now: datetime,
                  regime: Regime = Regime.open_ended) -> NextExperienceSpec:
    ledger_ref = ledger[0].id if ledger else ""
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/scheduler.py tests/test_scheduler.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: scheduler queues next experience (reactivate/transfer/decay)"
```

---

### Task 8: Judgment loop (open-ended assessor) — core path

**Files:**
- Create: `src/retnovation/assessment/__init__.py` (empty package marker for now), `src/retnovation/assessment/judgment_loop.py`
- Test: `tests/test_judgment_loop.py`

**Interfaces:**
- Consumes: `types.Experience, Work, Assessment, Push, FrameDelta, FrameState, TrapState, StopReason, Mode`; `model.Model`.
- Produces: `MAX_PUSHES=6`; `assess(exp: Experience, work: Work, model: Model) -> Assessment`.
- Behavior: one rubric-anchored target per cycle; target order = tripped traps first, then binding-constraint-adjacent absent frames, then remaining absent frames in rubric order. Sharper = `closed` AND `mechanism_supplied`. Disband rules live in the model's prompt; the loop never inspects/echoes the frame name to the student (it passes only `kind,code` to `generate_push`, which returns angle-only text). Stops: `converged` (all frames `present_reasoned`, no trap `tripped`), `bounded_error_violation` (hard_wrong in `bounded_error` mode → record + stop), `budget` (`MAX_PUSHES`), `plateau` (two consecutive pushes moved nothing). `regression` stop is present in the enum but intentionally not triggered here (step 5).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_judgment_loop.py
from retnovation.assessment import judgment_loop
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import (
    Experience, Frame, FrameState, Mode, Rubric, Regime, StopReason, Trap, TrapState, Work,
)


def _exp(mode=Mode.genuinely_open, binding=None):
    rub = Rubric(
        frames=[Frame(frame_code="lead_with_what_you_refuse_to_do", frame_detail="boundary first",
                      paired_trap="scope_creep_to_please"),
                Frame(frame_code="protect_the_core_lane", frame_detail="keep core",
                      paired_trap="erode_core_for_one_customer")],
        traps=[Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
               Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case")],
        mode=mode, binding_constraint=binding)
    return Experience(prompt="...", rubric=rub, ledger_ref="veldra:licensing_continuity",
                      regime=Regime.open_ended)


def _work():
    return Work(opening="here is my reasoning", respond=lambda push: "reply")


def test_cooperative_student_converges():
    intake = IntakeClassification(
        frame_states={"lead_with_what_you_refuse_to_do": FrameState.absent,
                      "protect_the_core_lane": FrameState.absent},
        trap_states={"scope_creep_to_please": TrapState.not_tripped,
                     "erode_core_for_one_customer": TrapState.not_tripped})
    closed = lambda: [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]
    m = FakeModel(intake, {"lead_with_what_you_refuse_to_do": closed(),
                           "protect_the_core_lane": closed()})
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert set(a.frames_closed_under_pressure) == {"lead_with_what_you_refuse_to_do",
                                                   "protect_the_core_lane"}
    # disband rule: no push text contains a literal frame_code
    assert all("protect_the_core_lane" not in p.text for p in a.trajectory)


def test_bounded_error_violation_stops_immediately():
    intake = IntakeClassification(
        frame_states={"lead_with_what_you_refuse_to_do": FrameState.absent,
                      "protect_the_core_lane": FrameState.absent},
        trap_states={"scope_creep_to_please": TrapState.not_tripped,
                     "erode_core_for_one_customer": TrapState.tripped})
    m = FakeModel(intake, {"erode_core_for_one_customer": [
        ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=True)]})
    a = judgment_loop.assess(_exp(mode=Mode.bounded_error, binding="erode_core_for_one_customer"),
                             _work(), m)
    assert a.stop_reason is StopReason.bounded_error_violation
    assert a.hard_wrong_flags == ["erode_core_for_one_customer"]


def test_budget_caps_unproductive_loop():
    intake = IntakeClassification(
        frame_states={"lead_with_what_you_refuse_to_do": FrameState.absent,
                      "protect_the_core_lane": FrameState.absent},
        trap_states={"scope_creep_to_please": TrapState.not_tripped,
                     "erode_core_for_one_customer": TrapState.not_tripped})
    stuck = [ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
             for _ in range(judgment_loop.MAX_PUSHES + 2)]
    m = FakeModel(intake, {"lead_with_what_you_refuse_to_do": list(stuck),
                           "protect_the_core_lane": list(stuck)})
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason in (StopReason.plateau, StopReason.budget)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_judgment_loop.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'retnovation.assessment'`.

- [ ] **Step 3: Write minimal implementation**

First create the empty package marker:

```python
# src/retnovation/assessment/__init__.py
```

Then the loop:

```python
# src/retnovation/assessment/judgment_loop.py
from __future__ import annotations

from ..model import Model
from ..types import (
    Assessment, Experience, FrameDelta, FrameState, Mode, Push, StopReason, TrapState, Work,
)

MAX_PUSHES = 6


def _select_target(exp: Experience, frame_states, trap_states):
    """Tripped traps first, then binding-adjacent absent frames, then remaining absent frames."""
    for t in exp.rubric.traps:
        if trap_states.get(t.trap_code) is TrapState.tripped:
            return ("trap", t.trap_code)
    binding = exp.rubric.binding_constraint
    if binding and frame_states.get(binding) is not None \
            and frame_states[binding] is not FrameState.present_reasoned:
        return ("frame", binding)
    for f in exp.rubric.frames:
        if frame_states.get(f.frame_code) is not FrameState.present_reasoned:
            return ("frame", f.frame_code)
    return None


def _converged(frame_states, trap_states) -> bool:
    frames_ok = all(s is FrameState.present_reasoned for s in frame_states.values())
    traps_ok = all(s is not TrapState.tripped for s in trap_states.values())
    return frames_ok and traps_ok


def assess(exp: Experience, work: Work, model: Model) -> Assessment:
    intake = model.classify_intake(exp, work.opening)
    frame_states = dict(intake.frame_states)
    trap_states = dict(intake.trap_states)

    trajectory: list[Push] = []
    deltas: list[FrameDelta] = []
    closed: list[str] = []
    hard_wrong: list[str] = []
    recent_moved: list[bool] = []
    stop_reason: StopReason | None = None

    while True:
        if _converged(frame_states, trap_states):
            stop_reason = StopReason.converged
            break
        if len(trajectory) >= MAX_PUSHES:
            stop_reason = StopReason.budget
            break
        if len(recent_moved) >= 2 and not recent_moved[-1] and not recent_moved[-2]:
            stop_reason = StopReason.plateau
            break

        target = _select_target(exp, frame_states, trap_states)
        if target is None:
            stop_reason = StopReason.converged
            break
        kind, code = target

        push_text = model.generate_push(exp, kind, code)
        response = work.respond(push_text)
        rc = model.classify_response(exp, kind, code, push_text, response)

        moved = False
        if rc.hard_wrong and exp.rubric.mode is Mode.bounded_error:
            hard_wrong.append(code)
            trajectory.append(Push(target_code=code, kind=kind, text=push_text,
                                   response_classification=rc.outcome))
            stop_reason = StopReason.bounded_error_violation
            break

        if rc.outcome == "closed" and rc.mechanism_supplied:
            if kind == "frame":
                before = frame_states.get(code, FrameState.absent)
                frame_states[code] = FrameState.present_reasoned
                if before is not FrameState.present_reasoned:
                    deltas.append(FrameDelta(code=code, before=before,
                                             after=FrameState.present_reasoned))
                closed.append(code)
            else:
                trap_states[code] = TrapState.repaired
            moved = True

        trajectory.append(Push(target_code=code, kind=kind, text=push_text,
                               response_classification=rc.outcome))
        recent_moved.append(moved)

    return Assessment(trajectory=trajectory, frame_deltas=deltas,
                      frames_closed_under_pressure=closed, hard_wrong_flags=hard_wrong,
                      stop_reason=stop_reason or StopReason.budget)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_judgment_loop.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/assessment/__init__.py src/retnovation/assessment/judgment_loop.py tests/test_judgment_loop.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: judgment loop assessor (one-push-per-cycle, five stops, disband rules)"
```

---

### Task 9: Checkable scorer stub + assessor dispatch

**Files:**
- Create: `src/retnovation/assessment/checkable_scorer.py`
- Modify: `src/retnovation/assessment/__init__.py` (add registry + `get_assessor`)
- Test: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: `judgment_loop.assess`, `types.Regime`.
- Produces: `checkable_scorer.assess(exp, work, model)` → raises `NotImplementedError`; `ASSESSORS: dict[Regime, Callable]`; `get_assessor(regime: Regime) -> Callable`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch.py
import pytest

from retnovation.assessment import get_assessor, ASSESSORS
from retnovation.assessment import judgment_loop
from retnovation.types import Regime


def test_open_ended_dispatches_to_judgment_loop():
    assert get_assessor(Regime.open_ended) is judgment_loop.assess
    assert Regime.open_ended in ASSESSORS


def test_cs_technical_is_registered_but_unimplemented():
    scorer = get_assessor(Regime.cs_technical)
    with pytest.raises(NotImplementedError):
        scorer(None, None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_assessor'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/assessment/checkable_scorer.py
from __future__ import annotations

from ..model import Model
from ..types import Assessment, Experience, Work


def assess(exp: Experience, work: Work, model: Model) -> Assessment:
    raise NotImplementedError("checkable_scorer (cs_technical regime) is built in step 4")
```

```python
# src/retnovation/assessment/__init__.py
from __future__ import annotations

from collections.abc import Callable

from ..types import Regime
from . import checkable_scorer, judgment_loop

ASSESSORS: dict[Regime, Callable] = {
    Regime.open_ended: judgment_loop.assess,
    Regime.cs_technical: checkable_scorer.assess,
}


def get_assessor(regime: Regime) -> Callable:
    return ASSESSORS[regime]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/assessment/checkable_scorer.py src/retnovation/assessment/__init__.py tests/test_dispatch.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: assessor dispatch by regime + cs_technical stub"
```

---

### Task 10: Experience selection

**Files:**
- Create: `src/retnovation/experience.py`
- Test: `tests/test_experience.py`

**Interfaces:**
- Consumes: `content_loader.load_rubric, load_experience_meta`; `types.Core, LearnerState, LedgerEntry, Experience, Regime, NextExperienceSpec`.
- Produces: `FIXED_EXPERIENCE="veldra_licensing_continuity"`; `select_experience(core: Core, state: LearnerState, ledger: list[LedgerEntry], spec: NextExperienceSpec | None = None, root=None) -> Experience`.
- MVP behavior: always loads the one fixed experience from content; if `spec` is given, its `ledger_ref` overrides the rubric default.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_experience.py
from retnovation.aim import aim, derive_core
from retnovation.experience import select_experience, FIXED_EXPERIENCE
from retnovation.types import LearnerState, Regime


def test_select_returns_the_fixed_experience():
    core = derive_core(aim())
    exp = select_experience(core, LearnerState(), ledger=[], spec=None)
    assert exp.regime is Regime.open_ended
    assert exp.ledger_ref == "veldra:licensing_continuity"
    assert exp.prompt.strip()
    assert any(f.frame_code == "protect_the_core_lane" for f in exp.rubric.frames)
    assert FIXED_EXPERIENCE == "veldra_licensing_continuity"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_experience.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/experience.py
from __future__ import annotations

from pathlib import Path

from .content_loader import load_experience_meta, load_rubric
from .types import Core, Experience, LearnerState, LedgerEntry, NextExperienceSpec, Regime

FIXED_EXPERIENCE = "veldra_licensing_continuity"


def select_experience(core: Core, state: LearnerState, ledger: list[LedgerEntry],
                      spec: NextExperienceSpec | None = None,
                      root: Path | None = None) -> Experience:
    rubric = load_rubric(FIXED_EXPERIENCE, root=root)
    meta = load_experience_meta(FIXED_EXPERIENCE, root=root)
    ledger_ref = spec.ledger_ref if spec is not None else meta["ledger_ref"]
    return Experience(prompt=meta["prompt"], rubric=rubric, ledger_ref=ledger_ref,
                      regime=Regime(meta["regime"]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_experience.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/experience.py tests/test_experience.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: select_experience returns the fixed seeded experience"
```

---

### Task 11: Orchestration (run_session)

**Files:**
- Create: `src/retnovation/orchestration.py`
- Test: `tests/test_orchestration.py`

**Interfaces:**
- Consumes: `persistence.Store`; `aim.derive_core` not needed (core passed in); `experience.select_experience`; `assessment.get_assessor`; `state.update_state`; `scheduler.schedule_next`; `model.Model`; `types.Core, Work, Experience, LearnerState, Assessment`.
- Produces:
  - `present_and_collect(exp: Experience) -> Work` (interactive default using `input()`).
  - `run_session(store: Store, core: Core, model: Model, now: datetime, present=present_and_collect) -> tuple[LearnerState, Assessment]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orchestration.py
from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import (
    FrameState, LedgerEntry, NextExperienceSpec, Regime, TrapState, Work,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _fake_model():
    intake = IntakeClassification(
        frame_states={"lead_with_what_you_refuse_to_do": FrameState.absent,
                      "protect_the_core_lane": FrameState.absent},
        trap_states={"scope_creep_to_please": TrapState.not_tripped,
                     "erode_core_for_one_customer": TrapState.not_tripped})
    closed = lambda: [ResponseClassification(outcome="closed", mechanism_supplied=True,
                                             hard_wrong=False)]
    return FakeModel(intake, {"lead_with_what_you_refuse_to_do": closed(),
                              "protect_the_core_lane": closed()})


def test_run_session_closes_one_cycle(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_ledger_entry(LedgerEntry(id="veldra:licensing_continuity", owned_problem="..."))
    store.queue_push(NextExperienceSpec(target_frames=["protect_the_core_lane"],
                                        ledger_ref="veldra:licensing_continuity",
                                        regime=Regime.open_ended))
    core = derive_core(aim())
    fixture = lambda exp: Work(opening="my reasoning", respond=lambda push: "reply")
    state, assessment = run_session(store, core, _fake_model(), _now(), present=fixture)
    assert assessment.trajectory  # something happened
    assert state.frames  # state moved
    assert store.queue_pop() is not None  # a fresh next was queued
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestration.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/retnovation/orchestration.py
from __future__ import annotations

from datetime import datetime
from collections.abc import Callable

from .assessment import get_assessor
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import schedule_next
from .state import update_state
from .types import Assessment, Core, Experience, LearnerState, Work


def present_and_collect(exp: Experience) -> Work:
    print(exp.prompt)
    opening = input("> ")

    def respond(push: str) -> str:
        print(push)
        return input("> ")

    return Work(opening=opening, respond=respond)


def run_session(store: Store, core: Core, model: Model, now: datetime,
                present: Callable[[Experience], Work] = present_and_collect
                ) -> tuple[LearnerState, Assessment]:
    state = store.load_state()
    ledger = store.load_ledger()
    spec = store.queue_pop()
    exp = select_experience(core, state, ledger, spec)
    work = present(exp)
    assessor = get_assessor(exp.regime)
    assessment = assessor(exp, work, model)
    state = update_state(state, assessment, now, exp.ledger_ref)
    store.save_state(state)
    store.queue_push(schedule_next(state, ledger, now, exp.regime))
    return state, assessment
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestration.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add src/retnovation/orchestration.py tests/test_orchestration.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: run_session wires the six links into one cycle"
```

---

### Task 12: Dry-run acceptance test

**Files:**
- Create: `tests/test_dry_run.py`

**Interfaces:**
- Consumes: everything above. No new source code (this proves the spec's acceptance criteria).

- [ ] **Step 1: Write the acceptance test**

```python
# tests/test_dry_run.py
"""Loop v0.1 dry run: the six links close end-to-end with no manual stitching."""
from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.types import (
    FrameState, LedgerEntry, NextExperienceSpec, Regime, StopReason, TrapState, Work,
)


def _now():
    return datetime(2026, 6, 22, tzinfo=timezone.utc)


def _cooperative_model():
    intake = IntakeClassification(
        frame_states={"lead_with_what_you_refuse_to_do": FrameState.absent,
                      "protect_the_core_lane": FrameState.absent},
        trap_states={"scope_creep_to_please": TrapState.not_tripped,
                     "erode_core_for_one_customer": TrapState.not_tripped})
    closed = lambda: [ResponseClassification(outcome="closed", mechanism_supplied=True,
                                             hard_wrong=False)]
    return FakeModel(intake, {"lead_with_what_you_refuse_to_do": closed(),
                              "protect_the_core_lane": closed()})


def test_dry_run_closes_the_loop(tmp_path):
    # Arrange: a learner who opens to a queued next experience on an owned problem.
    store = Store(tmp_path / "dryrun.db")
    store.add_ledger_entry(LedgerEntry(
        id="veldra:licensing_continuity",
        owned_problem="A customer contract ambiguity forces a same-day call."))
    store.queue_push(NextExperienceSpec(
        target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
        ledger_ref="veldra:licensing_continuity", regime=Regime.open_ended))
    core = derive_core(aim())

    student_replies = iter(["I refuse to weaken the core promise; here is the mechanism...",
                            "and I hold the core lane by..."])
    fixture = lambda exp: Work(opening="my opening reasoning",
                               respond=lambda push: next(student_replies, "..."))

    # Act: run exactly one session, no manual stitching between links.
    state, assessment = run_session(store, core, _cooperative_model(), _now(), present=fixture)

    # Assert the four acceptance criteria from the spec.
    # 1) experience came off the queue (queue had been consumed before re-queue)
    # 2) judgment loop produced a trajectory + deltas tracing to rubric codes
    assert assessment.trajectory
    assert assessment.stop_reason is StopReason.converged
    assert all(d.code in {"lead_with_what_you_refuse_to_do", "protect_the_core_lane"}
               for d in assessment.frame_deltas)
    # 3) at least one frame strength moved in persisted state
    reloaded = Store(tmp_path / "dryrun.db").load_state()
    assert reloaded.frames
    # 4) the queue holds a fresh NextExperienceSpec
    assert reloaded_next(tmp_path) is not None


def reloaded_next(tmp_path):
    return Store(tmp_path / "dryrun.db").queue_pop()
```

- [ ] **Step 2: Run the full suite**

Run: `pytest -v`
Expected: PASS (all tests, including `test_dry_run_closes_the_loop`).

- [ ] **Step 3: Commit**

```bash
git -C /Users/a14808/Documents/Retnovation add tests/test_dry_run.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "test: dry run closes the six-link loop end-to-end"
```

---

### Task 13: CLI entrypoint

**Files:**
- Create: `src/retnovation/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `aim`, `persistence.Store`, `orchestration.run_session`, `model.AnthropicModel`.
- Produces: `build_store(db_path) -> Store` (seeds the fixed ledger + an initial queued spec if empty); `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from retnovation.cli import build_store
from retnovation.types import LedgerEntry


def test_build_store_seeds_ledger_and_queue(tmp_path):
    store = build_store(tmp_path / "cli.db")
    assert any(e.id == "veldra:licensing_continuity" for e in store.load_ledger())
    assert store.queue_pop() is not None  # an initial experience is queued
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

First add a non-consuming queue count to `persistence.py` (the seed check must not consume the queue):

```python
    def queue_len(self) -> int:
        return self._db.execute("SELECT COUNT(*) AS n FROM queue").fetchone()["n"]
```

Then write the CLI, using `queue_len()` (not the consuming `queue_pop()`) for the seed check:

```python
# src/retnovation/cli.py
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .aim import aim, derive_core
from .model import AnthropicModel
from .orchestration import run_session
from .persistence import Store
from .types import LedgerEntry, NextExperienceSpec, Regime

DEFAULT_DB = Path("data/retnovation.db")
_SEED_PROBLEM = "A customer contract ambiguity forces a same-day call (sanitized seed)."


def build_store(db_path: str | Path = DEFAULT_DB) -> Store:
    store = Store(db_path)
    if not store.load_ledger():
        store.add_ledger_entry(LedgerEntry(id="veldra:licensing_continuity",
                                           owned_problem=_SEED_PROBLEM))
    if store.queue_len() == 0:
        store.queue_push(NextExperienceSpec(
            target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
            ledger_ref="veldra:licensing_continuity", regime=Regime.open_ended))
    return store


def main(argv: list[str] | None = None) -> int:
    store = build_store()
    core = derive_core(aim())
    model = AnthropicModel()
    state, assessment = run_session(store, core, model, datetime.now(timezone.utc))
    print(f"stop_reason={assessment.stop_reason.value} frames_moved={len(state.frames)}")
    return 0
```

Add to `tests/test_persistence.py`:

```python
def test_queue_len_is_non_consuming(tmp_path):
    from retnovation.types import NextExperienceSpec, Regime
    s = Store(tmp_path / "q.db")
    assert s.queue_len() == 0
    s.queue_push(NextExperienceSpec(target_frames=["a"], ledger_ref="x", regime=Regime.open_ended))
    assert s.queue_len() == 1
    assert s.queue_len() == 1  # still there
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py tests/test_persistence.py -v`
Expected: PASS

- [ ] **Step 5: Final full-suite green + commit**

```bash
ruff format . && ruff check . && pytest -v
git -C /Users/a14808/Documents/Retnovation add src/retnovation/cli.py src/retnovation/persistence.py tests/test_cli.py tests/test_persistence.py docs/DEVLOG.md
git -C /Users/a14808/Documents/Retnovation commit -m "feat: CLI entrypoint + non-consuming queue_len; seed fixed experience"
```

---

## Self-Review

**1. Spec coverage:**
- §3 types → Task 1. §4 modules → Tasks 2–13. §5 persistence (no-delete decay) → Task 3.
  §6 dispatch + judgment loop → Tasks 8, 9. §7 state + estimator → Task 6. §8 scheduler →
  Task 7. §9 orchestration → Task 11. §10 fixed experience + content → Tasks 2, 10.
  §11 acceptance dry run → Task 12. §12 doctrine guardrails: reversible decay (Task 3),
  rigor-not-correctness (Task 6), disband rules (Task 8), doctrine-as-data (Task 2),
  unlabeled prompt (Task 2 YAML). §13 gaps: checkable_scorer stub (Task 9), AnthropicModel
  not exercised (Task 4). **No gaps.**

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". Task 13 flags a
real side-effect bug in the first draft and fixes it inline with a method + test — that is a
correction, not a placeholder.

**3. Type consistency:** `assess(exp, work, model)` is used identically in Tasks 8, 9, 11, 12.
`update_state(state, assessment, now, experience_id)` matches Tasks 6 and 11.
`schedule_next(state, ledger, now, regime)` matches Tasks 7 and 11. `select_experience(core,
state, ledger, spec, root)` matches Tasks 10 and 11. `Store` method names (`save_state`,
`decay_frame`, `add_ledger_entry`, `load_ledger`, `queue_push`, `queue_pop`, `queue_len`)
are consistent across Tasks 3, 11, 13. `FrameDelta.code` (not `frame_code`) is used
consistently in types, state, and judgment_loop. Enums referenced by the same names throughout.

One known follow-up for execution: in `judgment_loop._select_target`, traps are surfaced by
intake `tripped` state; the cooperative-student test never trips a trap, so the trap branch is
exercised only by the bounded-error test. That is intended for step 1.
