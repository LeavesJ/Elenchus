# Cartographer MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app where the founder runs the clean-room friction-dialogue end-to-end through the *real, untouched* judgment-loop engine, and sees a single honest "nascent seed" of their judgment-world afterward.

**Architecture:** A thin **FastAPI** layer drives the engine via a **worker-bridge** (option A): each session runs the real `run_session` in a daemon thread whose `present`/`decide`/`respond` seams block on per-session queues fed by HTTP — so the engine is byte-identical and the unprompted-read is computed by unchanged code. A new pure `terrain.py` (`project_terrain` + a per-region non-invertibility guard) produces the post-session reveal; at user-zero every region gates to a seed. A minimal static frontend renders the dialogue (no terrain/labels during the read) and the seed (only after the read is locked).

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI + uvicorn (new `web` extra), pytest + `fastapi.testclient` (httpx). Real model: `AnthropicModel`; tests use `FakeModel`.

**Spec:** `docs/superpowers/specs/2026-06-28-uiux-cartographer-design.md` (committed `9c5d168`), §7–§8 + §4b/§4c/§5/§8a.

## Global Constraints

- **Engine is untouched.** No edits to `orchestration.py`, `assessment/`, `policy.py`, `state.py`, `persistence.py`. New code only: `terrain.py`, `web/`, types in `types.py`, tests.
- **L-13 surface invariant:** dialogue payloads (`menu`/`problem`/`push`) MUST contain no `frame_code` and no terrain; the terrain seed appears ONLY in the post-converge `done` payload. (`menu` = `ledger_ref`s; `problem` = `exp.prompt`; `push` = instructor probe text.)
- **Non-invertibility guard:** a region renders only with **≥2 distinct frames across ≥2 distinct problems** (`min_frames=2`, `min_problems=2`, calibration params); else it is a `seed`.
- **Worker uses its own `Store`** built inside the thread (sqlite `check_same_thread`).
- **Tests:** `PYTHONPATH=src .venv/bin/pytest -q`. The `@live` browser dogfood is a gated MANUAL step (Task 7), not automated.
- **Pre-commit (docs/lessons.md):** `.venv/bin/ruff format .` → `.venv/bin/ruff check .` → suite green → stage explicit paths only → **no `Co-Authored-By`** → confidentiality gate empty (`git ls-files | grep -iE 'berkeley|guidebook|...'`).
- **Shared test helpers:** put `_fake` (the scripted `FakeModel`) and `_steer` in `tests/conftest.py` (the repo already uses conftest) so both `test_session_runner.py` and `test_web_api.py` reuse them — do NOT `from tests.test_x import ...` across test modules (fragile collection-order dependency).

## File Structure

- **Modify** `src/retnovation/types.py` — add `RegionRender`, `Region`, `TerrainView`.
- **Create** `src/retnovation/terrain.py` — pure: `region_clears_guard`, `project_terrain`.
- **Create** `src/retnovation/web/__init__.py`, `web/session_runner.py` (worker-bridge), `web/app.py` (FastAPI), `web/__main__.py` (uvicorn launch), `web/static/index.html` (frontend).
- **Modify** `pyproject.toml` — add a `web` optional-dependency extra.
- **Create** `tests/test_terrain.py`, `tests/test_session_runner.py`, `tests/test_web_api.py`.

---

### Task 1: Terrain types + the non-invertibility guard

**Files:** Modify `src/retnovation/types.py` (after the `ProbeResult` block); Create `src/retnovation/terrain.py`; Test `tests/test_terrain.py`.

**Interfaces:**
- Produces: `RegionRender` (`"seed"|"rendered"`); `Region(region_id:str, frame_codes:list[str], problems:list[str], vitality:float|None, render:RegionRender)`; `TerrainView(regions:list[Region])`; `region_clears_guard(frame_codes:set[str], problems:set[str], *, min_frames:int=2, min_problems:int=2) -> bool`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_terrain.py`:

```python
from retnovation.terrain import region_clears_guard


def test_guard_refuses_single_frame_region():
    assert region_clears_guard({"embed"}, {"P1", "P2"}) is False  # 1 frame < 2


def test_guard_refuses_single_problem_region():
    assert region_clears_guard({"embed", "choose_failure"}, {"P1"}) is False  # 1 problem < 2


def test_guard_clears_two_by_two():
    assert region_clears_guard({"embed", "choose_failure"}, {"P1", "P2"}) is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_terrain.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'retnovation.terrain'`.

- [ ] **Step 3: Add the types** to `src/retnovation/types.py` (after the `ProbeResult` class):

```python
class RegionRender(str, Enum):
    seed = "seed"
    rendered = "rendered"


class Region(BaseModel):
    region_id: str
    frame_codes: list[str]  # author-side membership — STRIPPED from the learner-facing view (L-13)
    problems: list[str]
    vitality: float | None  # None when render == seed (sub-threshold; nothing to decode)
    render: RegionRender


class TerrainView(BaseModel):
    regions: list[Region]

    def learner_view(self) -> list[dict]:
        # L-13: never expose frame_codes to the learner; only an opaque id + render + (coarse) vitality
        return [
            {"region_id": r.region_id, "render": r.render.value, "vitality": r.vitality}
            for r in self.regions
        ]
```

- [ ] **Step 4: Create `src/retnovation/terrain.py`**:

```python
from __future__ import annotations


def region_clears_guard(
    frame_codes: set[str], problems: set[str], *, min_frames: int = 2, min_problems: int = 2
) -> bool:
    """Per-region non-invertibility gate (§4b): a region may render decodable vitality only when it
    draws on enough distinct frames across enough distinct problems that brightness cannot be read
    back to one move. Below threshold the region stays a seed."""
    return len(frame_codes) >= min_frames and len(problems) >= min_problems
```

- [ ] **Step 5: Run to verify pass + commit**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_terrain.py -q` → PASS.
```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/types.py src/retnovation/terrain.py tests/test_terrain.py
git commit -m "feat(terrain): Region/TerrainView types + per-region non-invertibility guard"
```

> **Reviewer:** OPUS — confirm the guard encodes exactly the two thresholds and `learner_view` strips `frame_codes`.

---

### Task 2: `project_terrain` (lossy clustering + per-region gating)

**Files:** Modify `src/retnovation/terrain.py`; Test `tests/test_terrain.py`.

**Interfaces:**
- Consumes: `region_clears_guard`, `Region`, `TerrainView`, `RegionRender`; `LearnerState`/`FrameStrength` (from `types.py`).
- Produces: `project_terrain(state: LearnerState, now: datetime, *, min_frames:int=2, min_problems:int=2) -> TerrainView`.

Clustering rule (MVP, deterministic): frames are nodes; two frames are connected if their `breadth` sets share any problem; each connected component is a region. A region's `problems` = the union of its frames' `breadth`; its `frame_codes` = the component. `region_clears_guard` decides `rendered` vs `seed`. Vitality (rendered only) = mean derived strength of member frames, mapped to `[0,1]` via `{weak:0.2, forming:0.6, strong:1.0}`; `None` for seeds. `region_id` = a stable hash of the sorted frame_codes (opaque; not a move name).

- [ ] **Step 1: Write the failing test** — append to `tests/test_terrain.py`:

```python
from datetime import datetime, timezone
from retnovation.terrain import project_terrain
from retnovation.types import FrameStrength, LearnerState, RegionRender, Strength, TerrainView

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _fs(strength, breadth):
    return FrameStrength(
        strength=strength, last_seen=NOW, due=NOW, last_evidence="x",
        evidence_count=len(breadth), breadth=set(breadth), unprompted_breadth=set(breadth),
    )


def test_user_zero_single_frame_is_a_seed():
    # embed alone across 2 problems: 1 frame < min_frames -> seed, vitality None, frame_codes hidden in learner_view
    state = LearnerState(frames={"embed": _fs(Strength.strong, ["P1", "P2"])})
    view = project_terrain(state, NOW)
    assert isinstance(view, TerrainView) and len(view.regions) == 1
    assert view.regions[0].render is RegionRender.seed
    assert view.regions[0].vitality is None
    assert "frame_codes" not in view.learner_view()[0]


def test_two_frames_two_problems_renders_a_non_invertible_region():
    # embed + choose_failure sharing problems -> one region, >=2 frames across >=2 problems -> rendered
    state = LearnerState(frames={
        "embed": _fs(Strength.strong, ["P1", "P2"]),
        "choose_failure": _fs(Strength.forming, ["P1"]),
    })
    view = project_terrain(state, NOW)
    assert len(view.regions) == 1
    r = view.regions[0]
    assert r.render is RegionRender.rendered
    assert set(r.frame_codes) == {"embed", "choose_failure"}  # vitality draws on >1 frame (non-invertible)
    assert r.vitality is not None and 0.0 <= r.vitality <= 1.0


def test_disjoint_frames_form_separate_regions():
    state = LearnerState(frames={
        "a": _fs(Strength.forming, ["P1"]),
        "b": _fs(Strength.forming, ["P9"]),
    })
    view = project_terrain(state, NOW)
    assert len(view.regions) == 2  # no shared problem -> two components, both seeds
    assert all(r.render is RegionRender.seed for r in view.regions)
```

- [ ] **Step 2: Run to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_terrain.py -q -k project or seed or region` → FAIL (`cannot import name 'project_terrain'`).

- [ ] **Step 3: Implement `project_terrain`** — append to `src/retnovation/terrain.py`:

```python
from datetime import datetime

from .types import LearnerState, Region, RegionRender, Strength, TerrainView

_VITALITY = {Strength.weak: 0.2, Strength.forming: 0.6, Strength.strong: 1.0}


def _components(frames: dict) -> list[list[str]]:
    """Connected components of frames linked by a shared problem (ledger_ref in breadth)."""
    codes = sorted(frames)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in codes:
        if start in seen:
            continue
        stack, comp = [start], []
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            comp.append(c)
            for other in codes:
                if other not in seen and frames[c].breadth & frames[other].breadth:
                    stack.append(other)
        comps.append(sorted(comp))
    return comps


def project_terrain(
    state: LearnerState, now: datetime, *, min_frames: int = 2, min_problems: int = 2
) -> TerrainView:
    regions: list[Region] = []
    for comp in _components(state.frames):
        problems: set[str] = set()
        for c in comp:
            problems |= state.frames[c].breadth
        clears = region_clears_guard(
            set(comp), problems, min_frames=min_frames, min_problems=min_problems
        )
        vitality = (
            sum(_VITALITY[state.frames[c].strength] for c in comp) / len(comp) if clears else None
        )
        regions.append(
            Region(
                region_id=f"r{abs(hash(tuple(comp))) % 100000:05d}",
                frame_codes=comp,
                problems=sorted(problems),
                vitality=vitality,
                render=RegionRender.rendered if clears else RegionRender.seed,
            )
        )
    return regions_to_view(regions)


def regions_to_view(regions: list[Region]) -> TerrainView:
    return TerrainView(regions=sorted(regions, key=lambda r: r.region_id))
```

> Note: `region_id` uses `hash()` which is process-salted; that is fine (ids are opaque and per-response). If a stable id is ever needed, switch to `hashlib`. Not required for the MVP.

- [ ] **Step 4: Run to verify pass + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/terrain.py tests/test_terrain.py
git commit -m "feat(terrain): project_terrain — lossy clustering + per-region gating to seed/rendered"
```

> **Reviewer:** OPUS — confirm: every `rendered` region clears the guard (no sub-threshold region renders vitality); vitality of a rendered region is a function of ≥2 frames (non-invertible); `learner_view` never leaks `frame_codes`; user-zero (1 frame) → seed.

---

### Task 3: `web` deps + FastAPI skeleton + static serving

**Files:** Modify `pyproject.toml`; Create `src/retnovation/web/__init__.py`, `src/retnovation/web/app.py`, `src/retnovation/web/static/index.html` (placeholder body for now); Test `tests/test_web_api.py`.

- [ ] **Step 1: Add the `web` extra** to `pyproject.toml` under `[project.optional-dependencies]`:

```toml
web = ["fastapi>=0.110", "uvicorn>=0.29", "httpx>=0.27"]
```

Then install: `.venv/bin/pip install -e ".[web]"` (expected: installs fastapi, uvicorn, httpx, starlette).

- [ ] **Step 2: Write the failing test** — create `tests/test_web_api.py`:

```python
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from retnovation.web.app import create_app


def test_health_ok():
    client = TestClient(create_app(db_path=":memory:", model_factory=None))
    assert client.get("/api/health").json() == {"ok": True}
```

- [ ] **Step 3: Run to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py -q` → FAIL (`No module named 'retnovation.web.app'`).

- [ ] **Step 4: Create the skeleton** — `src/retnovation/web/__init__.py` (empty), and `src/retnovation/web/app.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC = Path(__file__).parent / "static"


def create_app(db_path: str, model_factory=None) -> FastAPI:
    app = FastAPI(title="Retnovation — Cartographer MVP")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app
```

Create `src/retnovation/web/static/index.html` with a minimal body (`<!doctype html><title>Cartographer</title><h1>Cartographer</h1>`) — fleshed out in Task 6.

- [ ] **Step 5: Run to verify pass + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add pyproject.toml src/retnovation/web/__init__.py src/retnovation/web/app.py src/retnovation/web/static/index.html tests/test_web_api.py
git commit -m "feat(web): FastAPI skeleton — web extra, health, static serving"
```

---

### Task 4: The session runner (worker-bridge)

**Files:** Create `src/retnovation/web/session_runner.py`; Test `tests/test_session_runner.py`.

**Interfaces:**
- Consumes: `run_session` (orchestration), `build_store` (cli), `aim`+`derive_core` (aim), `Work`/`Selection`/`Outcome`/`Proposal` (types).
- Produces: `SessionRegistry(db_path:str, model_factory:Callable[[], Model])` with `start(session_id, now=None) -> tuple[str, dict]` and `step(session_id, value) -> tuple[str, dict]`. Emission tag ∈ `{"menu","problem","push","done","error"}`.

- [ ] **Step 1: Write the failing test (bridge-transparency equivalence)** — create `tests/test_session_runner.py`:

```python
from datetime import datetime, timezone

from retnovation.aim import aim, derive_core
from retnovation.assessment.judgment_loop import assess
from retnovation.cli import build_store
from retnovation.content_loader import load_experience
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.orchestration import run_session
from retnovation.types import FrameState, Outcome, Regime, Selection, TrapState, Work
from retnovation.web.session_runner import SessionRegistry

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _fake():
    intake = IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={"deferred_the_one_time_choice": TrapState.not_tripped,
                     "assumed_the_happy_path": TrapState.not_tripped},
    )
    closed = [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
              for _ in range(4)]
    return FakeModel(intake, {"choose_the_failure_default_deliberately": closed})


def _steer(eid):
    def decide(proposal):
        for spec, receipt in proposal.candidates:
            if spec.experience_id == eid:
                top_spec, top_rcpt = proposal.top
                return Selection(proposed_receipt=top_rcpt, chosen_spec=spec, chosen_receipt=receipt,
                                 outcome=Outcome.accepted if spec is top_spec else Outcome.redirected)
        raise AssertionError(eid)
    return decide


def test_runner_assessment_equals_direct_run_session(tmp_path):
    # direct run_session with synchronous scripted callbacks
    db1 = build_store(str(tmp_path / "a.db"))
    core = derive_core(aim())
    direct_state, direct_assess = run_session(
        db1, core, _fake(), NOW, regime=Regime.open_ended,
        present=lambda exp: Work(opening="reasoning that already holds the move",
                                 respond=lambda push: "mechanism"),
        decide=_steer("irreversible_anchor"), decide_core=lambda c: [],
    )
    # same inputs via the runner's queue bridge
    reg = SessionRegistry(str(tmp_path / "b.db"), model_factory=_fake)
    tag, _ = reg.start("s1", now=NOW)
    assert tag == "menu"
    # choose irreversible_anchor by ledger_ref
    idx = _, = [0]  # placeholder; resolved below
    menu = reg.menu_index("s1", "veldra:embedded_anchor_lock_in")
    tag, _ = reg.step("s1", menu)
    assert tag == "problem"
    tag, data = reg.step("s1", "reasoning that already holds the move")
    while tag == "push":
        tag, data = reg.step("s1", "mechanism")
    assert tag == "done"
    runner_assess = data["assessment"]
    assert runner_assess.model_dump() == direct_assess.model_dump()  # byte-identical -> bridge transparent
```

> The test uses a helper `menu_index(session_id, ledger_ref)` for ergonomics; implement it on `SessionRegistry`. (It reads the last menu emission and returns the index of that ledger_ref.)

- [ ] **Step 2: Run to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_session_runner.py -q` → FAIL (`No module named 'retnovation.web.session_runner'`).

- [ ] **Step 3: Implement the runner** — `src/retnovation/web/session_runner.py`:

```python
from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from ..aim import aim, derive_core
from ..cli import build_store
from ..orchestration import run_session
from ..types import Outcome, Regime, Selection, Work


class _Channel:
    def __init__(self):
        self.to_worker: queue.Queue = queue.Queue()
        self.from_worker: queue.Queue = queue.Queue()
        self.last_menu: list[str] = []


class SessionRegistry:
    def __init__(self, db_path: str, model_factory: Callable[[], object]):
        self._db_path = db_path
        self._model_factory = model_factory
        self._ch: dict[str, _Channel] = {}
        self._lock = threading.Lock()

    def start(self, session_id: str, now: datetime | None = None) -> tuple[str, dict]:
        now = now or datetime.now(timezone.utc)
        ch = _Channel()
        with self._lock:
            self._ch[session_id] = ch

        def worker():
            store = build_store(self._db_path)
            try:
                core = derive_core(aim())
                model = self._model_factory()

                def decide(proposal):
                    menu = proposal.problem_menu()
                    ch.from_worker.put(("menu", {"problems": [s.ledger_ref for s, _ in menu]}))
                    idx = ch.to_worker.get()
                    spec, receipt = menu[idx]
                    top_spec, top_rcpt = proposal.top
                    return Selection(
                        proposed_receipt=top_rcpt, chosen_spec=spec, chosen_receipt=receipt,
                        outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                    )

                def present(exp):
                    ch.from_worker.put(("problem", {"prompt": exp.prompt, "ledger_ref": exp.ledger_ref}))
                    opening = ch.to_worker.get()

                    def respond(push):
                        ch.from_worker.put(("push", {"text": push}))
                        return ch.to_worker.get()

                    return Work(opening=opening, respond=respond)

                state, assessment = run_session(
                    store, core, model, now, regime=Regime.open_ended,
                    present=present, decide=decide, decide_core=lambda c: [],
                )
                ch.from_worker.put(("done", {"state": state, "assessment": assessment}))
            except Exception as e:  # surface, never hang the client
                ch.from_worker.put(("error", {"message": repr(e)}))
            finally:
                store.close()

        threading.Thread(target=worker, daemon=True).start()
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
        return tag, data

    def step(self, session_id: str, value) -> tuple[str, dict]:
        ch = self._ch[session_id]
        ch.to_worker.put(value)
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
        return tag, data

    def menu_index(self, session_id: str, ledger_ref: str) -> int:
        return self._ch[session_id].last_menu.index(ledger_ref)
```

- [ ] **Step 4: Run to verify pass + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/web/session_runner.py tests/test_session_runner.py
git commit -m "feat(web): session runner — worker-bridge over the untouched engine (byte-identical)"
```

> **Reviewer:** OPUS — this is the load-bearing surface for the unprompted-read. Confirm: the engine is unmodified; the bridge delivers every push/reply in order without drop/reorder; the equivalence test proves `done.assessment == direct run_session.assessment` byte-for-byte; the worker builds its own `Store` in-thread; an engine exception becomes an `error` emission (never a client hang).

---

### Task 5: API endpoints (the stepper over HTTP) + L-13 surface test

**Files:** Modify `src/retnovation/web/app.py`; Test `tests/test_web_api.py`.

**Interfaces:**
- Consumes: `SessionRegistry`, `project_terrain`, `TerrainView`.
- Produces endpoints: `POST /api/session` → `{kind, ...}`; `POST /api/session/{sid}/choose` `{index|ledger_ref}`; `POST /api/session/{sid}/open` `{text}`; `POST /api/session/{sid}/reply` `{text}`. Each returns `{"kind": "menu"|"problem"|"push"|"done"|"error", ...}`; `done` carries `{"terrain": [...learner_view...]}`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_web_api.py`:

```python
import itertools
from retnovation.web import session_runner as sr_mod
# reuse the fake from the runner test module
from tests.test_session_runner import _fake


def _client():
    return TestClient(create_app(db_path="file:webtest?mode=memory&cache=shared", model_factory=_fake))


def test_full_session_and_l13_surface(tmp_path):
    app = create_app(db_path=str(tmp_path / "w.db"), model_factory=_fake)
    client = TestClient(app)
    seen_texts = []

    r = client.post("/api/session").json()
    assert r["kind"] == "menu"
    seen_texts.append(str(r["problems"]))
    r = client.post("/api/session/s/choose", json={"ledger_ref": "veldra:embedded_anchor_lock_in"}).json()
    assert r["kind"] == "problem"
    seen_texts.append(r["prompt"])
    r = client.post("/api/session/s/open", json={"text": "reasoning that already holds the move"}).json()
    while r["kind"] == "push":
        seen_texts.append(r["text"])
        r = client.post("/api/session/s/reply", json={"text": "mechanism"}).json()
    assert r["kind"] == "done"
    assert "terrain" in r and isinstance(r["terrain"], list)
    # L-13: no frame_code, and no terrain, ever appeared in a dialogue payload
    for blob in seen_texts:
        assert "embed_credentials_as_a_list" not in blob
        assert "choose_the_failure_default_deliberately" not in blob
    # terrain entries are learner_view (no frame_codes)
    for region in r["terrain"]:
        assert "frame_codes" not in region
```

> The endpoints use a single fixed session id per `create_app` instance for the MVP (one user); `{sid}` is accepted but the registry keys on a constant. If you prefer real ids, return an `id` from `POST /api/session` and thread it — but one-user-one-session is in scope; keep it simple.

- [ ] **Step 2: Run to verify fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py -q -k full_session` → FAIL (404 / missing endpoints).

- [ ] **Step 3: Implement the endpoints** — extend `create_app` in `src/retnovation/web/app.py`:

```python
from pydantic import BaseModel
from .session_runner import SessionRegistry
from ..terrain import project_terrain

_SID = "single"  # one user, one session (MVP)


class _Choice(BaseModel):
    index: int | None = None
    ledger_ref: str | None = None


class _Text(BaseModel):
    text: str


def _emit(reg: SessionRegistry, tag: str, data: dict) -> dict:
    if tag == "done":
        view = project_terrain(data["state"], data["state"].frames and __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        return {"kind": "done", "terrain": view.learner_view()}
    if tag == "menu":
        return {"kind": "menu", "problems": data["problems"]}
    if tag == "problem":
        return {"kind": "problem", "prompt": data["prompt"], "ledger_ref": data["ledger_ref"]}
    if tag == "push":
        return {"kind": "push", "text": data["text"]}
    return {"kind": "error", "message": data.get("message", "")}
```

Add inside `create_app` (after the registry is constructed — construct it there: `reg = SessionRegistry(db_path, model_factory or (lambda: _default_model()))`):

```python
    @app.post("/api/session")
    def start():
        return _emit(reg, *reg.start(_SID))

    @app.post("/api/session/{sid}/choose")
    def choose(sid: str, body: _Choice):
        idx = body.index if body.index is not None else reg.menu_index(_SID, body.ledger_ref)
        return _emit(reg, *reg.step(_SID, idx))

    @app.post("/api/session/{sid}/open")
    def open_read(sid: str, body: _Text):
        return _emit(reg, *reg.step(_SID, body.text))

    @app.post("/api/session/{sid}/reply")
    def reply(sid: str, body: _Text):
        return _emit(reg, *reg.step(_SID, body.text))
```

Where `_default_model` lazily builds `AnthropicModel` (so tests passing a `model_factory` never import the SDK):

```python
def _default_model():
    from ..model import AnthropicModel
    return AnthropicModel()
```

> Clean up the `_emit` "done" branch: compute `now = datetime.now(timezone.utc)` with a normal import at the top of `app.py` (`from datetime import datetime, timezone`) rather than the inline `__import__` shown above — that inline form is illustrative; the implementer must use the clean import. `project_terrain(data["state"], now)`.

- [ ] **Step 4: Run to verify pass + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/web/app.py tests/test_web_api.py
git commit -m "feat(web): stepper endpoints + L-13 surface (no frame_code/terrain in dialogue; seed only at done)"
```

> **Reviewer:** OPUS — the doctrine surface. Confirm: no `menu`/`problem`/`push` payload can contain a `frame_code` or terrain; the terrain (`learner_view`, no `frame_codes`) appears ONLY in `done`; the L-13 test actually exercises a full session and would fail if a frame name leaked.

---

### Task 6: Minimal frontend (clean room + seed reveal)

**Files:** Rewrite `src/retnovation/web/static/index.html` (self-contained HTML/CSS/JS).

- [ ] **Step 1: Write the frontend** — replace `src/retnovation/web/static/index.html` with:

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cartographer</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;background:#0a0f1c;color:#e8eef7;font:16px/1.55 ui-sans-serif,system-ui,sans-serif}
  main{max-width:720px;margin:0 auto;padding:32px 20px}
  h1{font:600 20px/1 Georgia,serif;color:#9fb2cc;margin:0 0 24px}
  .prompt{background:#0f1a2b;border:1px solid #1b2b44;border-radius:12px;padding:18px 20px;margin:14px 0}
  .push{color:#5eead4;margin:18px 0 8px}
  textarea{width:100%;box-sizing:border-box;background:#0f1a2b;color:#e8eef7;border:1px solid #1b2b44;
    border-radius:10px;padding:12px;font:inherit;min-height:90px;resize:vertical}
  button{margin-top:10px;background:#155e63;color:#e8eef7;border:0;border-radius:9px;padding:10px 18px;
    font:inherit;cursor:pointer}
  button:hover{background:#1f7a80}
  .menu button{display:block;width:100%;text-align:left;margin:6px 0;background:#0f1a2b;border:1px solid #1b2b44}
  #seed{display:flex;align-items:center;gap:14px;margin-top:24px}
  #seed svg{flex:0 0 auto}
  .muted{color:#8aa0bf;font-size:13px}
</style></head>
<body><main>
  <h1>your terrain begins</h1>
  <div id="app"></div>
</main>
<script>
const app = document.getElementById('app');
const post = (url, body) => fetch(url, {method:'POST', headers:{'content-type':'application/json'},
  body: body?JSON.stringify(body):null}).then(r=>r.json());

function el(html){const d=document.createElement('div'); d.innerHTML=html; return d.firstElementChild;}

async function start(){
  const r = await post('/api/session');
  renderMenu(r.problems);
}
function renderMenu(problems){
  app.innerHTML = '<div class="muted">Choose a problem to work. You are never told the move to make.</div>';
  const m = el('<div class="menu"></div>');
  problems.forEach((p,i)=>{ const b=el(`<button>${p}</button>`); b.onclick=()=>choose(i); m.appendChild(b); });
  app.appendChild(m);
}
async function choose(index){
  const r = await post('/api/session/single/choose', {index});
  renderProblem(r.prompt);
}
function renderProblem(prompt){
  app.innerHTML='';
  app.appendChild(el(`<div class="prompt">${prompt.replace(/</g,'&lt;')}</div>`));
  const ta=el('<textarea placeholder="Reason it through. Decide, and account for the trade-offs."></textarea>');
  const btn=el('<button>Submit</button>');
  btn.onclick=async()=>{ const r=await post('/api/session/single/open',{text:ta.value}); advance(r); };
  app.appendChild(ta); app.appendChild(btn);
}
function advance(r){
  if(r.kind==='push') return renderPush(r.text);
  if(r.kind==='done') return renderSeed(r.terrain);
  app.appendChild(el(`<div class="muted">error: ${r.message||''}</div>`));
}
function renderPush(text){
  app.appendChild(el(`<div class="push">${text.replace(/</g,'&lt;')}</div>`));
  const ta=el('<textarea placeholder="Respond."></textarea>');
  const btn=el('<button>Reply</button>');
  btn.onclick=async()=>{ ta.disabled=true; btn.disabled=true;
    const r=await post('/api/session/single/reply',{text:ta.value}); advance(r); };
  app.appendChild(ta); app.appendChild(btn);
}
function renderSeed(terrain){
  const rendered = terrain.filter(t=>t.render==='rendered').length;
  const note = rendered ? `${rendered} region${rendered>1?'s':''} took shape.`
                        : 'A seed was planted. Your world is too young to read yet — it grows as you work more problems.';
  app.innerHTML = `<div class="muted">The read is locked. Now — your terrain:</div>
    <div id="seed"><svg width="80" height="80" viewBox="0 0 80 80">
      <circle cx="40" cy="40" r="6" fill="#5eead4"></circle>
      <circle cx="40" cy="40" r="16" fill="none" stroke="#5eead4" stroke-opacity="0.35"></circle>
    </svg><div>${note}</div></div>`;
}
start();
</script></body></html>
```

- [ ] **Step 2: Verify it serves** — Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py::test_health_ok -q` (the `/` route + static mount already covered by Task 3) and confirm no import breakage. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/web/static/index.html
git commit -m "feat(web): minimal clean-room frontend + nascent-seed reveal"
```

> **Reviewer:** sonnet — confirm the frontend never requests/shows terrain during the dialogue (seed only on `done`), escapes user/prompt text, and matches the API shape.

---

### Task 7: Launch entry, DEVLOG, whole-branch review, gated dogfood

**Files:** Create `src/retnovation/web/__main__.py`; Modify `docs/DEVLOG.md`.

- [ ] **Step 1: Launch entry** — `src/retnovation/web/__main__.py`:

```python
from __future__ import annotations

from pathlib import Path

from .app import create_app

DB = str(Path(__file__).resolve().parents[3] / "data" / "retnovation.db")
app = create_app(db_path=DB)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

Run check (no server): `PYTHONPATH=src .venv/bin/python -c "import retnovation.web.__main__"` → no error.

- [ ] **Step 2: Full gates**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf|content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$' || echo "GATE EMPTY"
```

- [ ] **Step 3: OPUS whole-branch review** over the full diff vs the spec + lessons. Checklist: engine untouched; bridge byte-identical (equivalence test); L-13 surface (no frame_code/terrain in dialogue, seed only at done); per-region guard correct + user-zero → seed; `learner_view` strips frame_codes; deps added cleanly; no `Co-Authored-By`; no confidential paths. Fold findings.

- [ ] **Step 4: DEVLOG + commit** — prepend a `## 2026-06-29 — Cartographer MVP built` entry (components, the worker-bridge choice, the guard, the L-13 surface, suite counts). Then:
```bash
git add docs/DEVLOG.md
git commit -m "docs: DEVLOG — Cartographer MVP built"
```

- [ ] **Step 5: MANUAL gated dogfood (with the user, spends Opus tokens)** — `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m retnovation.web`, open `http://127.0.0.1:8000`, run one real session, confirm the clean-room dialogue works end-to-end and the seed appears only after converge. Record the dogfood finding in DEVLOG + memory.

---

## Self-Review (completed by author)

- **Spec coverage:** worker-bridge stepper §7 (Task 4); clean-room dialogue end-to-end §8 (Tasks 4–6); `terrain_projection` + per-region guard §4b (Tasks 1–2); nascent seed §8 (Tasks 2,5,6); L-13 clean-room/reveal-after surface §4 (Task 5); bridge-transparency equivalence test (the §7 "stepper-equivalence", reframed per option A) (Task 4); medium = local web app §7 (Tasks 3–7). Out-of-scope (rich 3D terrain, trails, decay/rebound animation, positioning) correctly absent.
- **Placeholder scan:** the only deferred numerals are DEVLOG suite counts (filled from observed output); the `_emit` inline `__import__` is explicitly flagged for cleanup to a normal import in Step 3's note. No "TBD"/"handle edge cases".
- **Type consistency:** `region_clears_guard`, `project_terrain`, `Region`/`TerrainView`/`RegionRender`/`learner_view`, `SessionRegistry.start/step/menu_index`, emission tags `menu|problem|push|done|error`, `create_app(db_path, model_factory)` used identically across tasks/tests.
- **Note for the builder:** the `_emit` "done" branch in Task 5 Step 3 shows an inline `__import__` only to keep the snippet local — replace with `from datetime import datetime, timezone` at module top and `project_terrain(data["state"], datetime.now(timezone.utc))`.
