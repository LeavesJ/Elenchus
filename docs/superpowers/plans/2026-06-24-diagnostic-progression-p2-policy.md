# Diagnostic Progression — Project 2: Value-Function Policy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder `weak>forming>strong` scheduler with a diagnostic value-function policy that scores `(frame, experience)` candidates over the Project-1 learner state, picks the next experience by `argmax` (diagnose / consolidate / deploy, minus a cold-start integration-readiness penalty), and logs a full decomposition (the validation surface).

**Architecture:** A pure, injectable value function (`policy.select_next`) scores every `(frame f, experience e)` candidate; `scheduler.schedule_next`'s `open_ended` branch loads the library + `progression.yaml` and delegates to it; the selector runs the *exact* experience the policy scored; the decision + receipt are written to a new `selection_log`. `cs_technical` is byte-stable. Orchestration stays queue-based; the interactive surface is Project 3.

**Tech Stack:** Python 3.12, Pydantic v2, sqlite3, pytest, ruff, PyYAML.

**Spec:** `docs/superpowers/specs/2026-06-24-diagnostic-progression-design.md` §7, §16 (rev. with external review r2). Project 2 only; Project 3 (interactive surface + core promote/demote) is a separate plan.

**Branch:** create `diagnostic-progression-policy` off `main` before Task 1. `main` is far ahead of `origin/main`; **do not push**.

## Global Constraints

- **Candidate = `(frame, experience)`** (§16 r2); `problem = e.ledger_ref` derived. The penalty (`max` over `e.rubric.frames`) and the served artifact are per-experience; per-frame attribution preserved (score per frame).
- **Score:** `V(f,e) = wU·uncertainty(f) + wR·retention_due(f) + wT·transfer_opportunity(f,e) − wL·max_constituent_uncertainty(e)`. `argmax`, tie-break **`(constituent_count asc, frame_id, problem, experience_id)`** — deterministic, no randomness.
- **Drives:** `uncertainty(f)` = `state.frame_uncertainty(...)`, `1.0` for an unseen frame. `retention_due(f)` = `clamp((staleness−interval)/interval, 0, 1)` on the storage-keyed interval, `0` for unearned (`evidence_count==0`). `transfer_opportunity(f,e)` = `1.0` iff `f` is `forming` and `e.ledger_ref ∉ breadth(f)`, else `0`. Penalty = `max(uncertainty(g) for g in e.rubric.frames)`.
- **Default weights** (`content/cadence/progression.yaml`): `wU=1.0, wR=1.0, wT=1.5, wL=0.5`; `θ_located=0.5`.
- **Content gap (static predicate):** `f` is unlocatable-in-isolation iff no experience containing `f` has all its **other** frames located, where `located(g) ≜ uncertainty(g) ≤ θ_located` and a single-frame experience is trivially a home. Logged; the policy still serves the best candidate. No scorer escape hatch.
- **`_INTERVAL_DAYS` stays in `state.py`** (refines §16: avoid churning the Project-1 `derive_*` signatures); exposed via `state.frame_interval_days`. `progression.yaml` holds only the new weights + `θ_located`.
- **No behavior change to `cs_technical`** (SM2-lite) or its tests. The judgment loop, the Project-1 substrate, and `frame_uncertainty` are reused unchanged.
- **TDD; every commit leaves the full suite green.** Per-commit gate: `.venv/bin/ruff format .`; `.venv/bin/ruff check .`; `PYTHONPATH=src .venv/bin/pytest -q`; confidentiality grep empty; `git status --short` shows no `data/` staged; `docs/DEVLOG.md` updated in the same commit; explicit-path `git add`; **no `Co-Authored-By`**.
- **Core-path review** (`scheduler`, `policy`, `generator`, `persistence`, `orchestration`, `types`): whole-branch adversarial review before finishing.

Baseline before Task 1: **137 passed, 3 skipped**, ruff clean.

**Task order is dependency-clean and every commit is green:** types → config → policy (pure) → selector → persistence (all additive) → the single atomic integration task that swaps `schedule_next`'s return type and updates every caller at once → controller review.

---

### Task 1: types — `NextExperienceSpec.experience_id` + `SelectionReceipt`

**Files:** Modify `src/retnovation/types.py` (`NextExperienceSpec` :239-244; add `SelectionReceipt`). Test `tests/test_types.py` (append).

**Interfaces:** Produces `NextExperienceSpec(..., experience_id: str | None = None)` and `SelectionReceipt(frame, problem, experience_id, drive, scores: dict[str,float], runner_up_drive: str | None, margin: float, content_gaps: list[str], created_at: datetime)`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_types.py`:

```python
def test_next_experience_spec_carries_experience_id_default_none():
    from retnovation.types import NextExperienceSpec, Regime

    s = NextExperienceSpec(target_frames=["f"], ledger_ref="veldra:x", regime=Regime.open_ended)
    assert s.experience_id is None
    s2 = NextExperienceSpec(
        target_frames=["f"], ledger_ref="veldra:x", regime=Regime.open_ended, experience_id="license_continuity"
    )
    assert s2.experience_id == "license_continuity"


def test_selection_receipt_shape():
    from datetime import datetime, timezone
    from retnovation.types import SelectionReceipt

    r = SelectionReceipt(
        frame="lead_with_what_you_refuse_to_do", problem="veldra:license_fork_risk",
        experience_id="license_continuity", drive="diagnose",
        scores={"uncertainty": 1.0, "retention": 0.0, "transfer": 0.0, "penalty": 1.0, "V": 0.5},
        runner_up_drive=None, margin=0.5, content_gaps=["commit_under_the_deadline"],
        created_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
    )
    assert r.drive == "diagnose" and r.scores["V"] == 0.5 and r.content_gaps == ["commit_under_the_deadline"]
```

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q -k "experience_id or selection_receipt"` → FAIL (unknown field / undefined).

- [ ] **Step 3: Implement** — in `types.py` add `experience_id` to `NextExperienceSpec`:

```python
class NextExperienceSpec(BaseModel):
    target_frames: list[str]
    ledger_ref: str
    regime: Regime
    experience_id: str | None = None  # the exact (frame, experience) the policy scored; None for the legacy seed
```

and add `SelectionReceipt` after it:

```python
class SelectionReceipt(BaseModel):
    frame: str
    problem: str
    experience_id: str
    drive: str
    scores: dict[str, float]
    runner_up_drive: str | None
    margin: float
    content_gaps: list[str]
    created_at: datetime
```

- [ ] **Step 4: GREEN + full suite** — `PYTHONPATH=src .venv/bin/pytest -q` → 139 passed, 3 skipped.

- [ ] **Step 5: Gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P2 Task 1 — NextExperienceSpec.experience_id + SelectionReceipt; 139/3."
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): NextExperienceSpec.experience_id + SelectionReceipt"
```

---

### Task 2: config — `progression.yaml`, `load_progression`, `state.frame_interval_days`

**Files:** Create `content/cadence/progression.yaml`. Modify `src/retnovation/content_loader.py` (`load_progression`) and `src/retnovation/state.py` (`frame_interval_days`). Test `tests/test_content_loader.py`, `tests/test_state.py` (append).

**Interfaces:** `content_loader.load_progression(root=None) -> dict` = `{"wU","wR","wT","wL","theta_located"}` (floats). `state.frame_interval_days(evidence_count: int, unprompted_breadth: set[str]) -> int` = the storage-tier interval in days.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_content_loader.py`:

```python
def test_load_progression_returns_weights_and_threshold():
    from retnovation.content_loader import load_progression

    p = load_progression()
    assert p["wU"] == 1.0 and p["wR"] == 1.0 and p["wT"] == 1.5 and p["wL"] == 0.5
    assert p["theta_located"] == 0.5
```

and to `tests/test_state.py`:

```python
def test_frame_interval_days_keys_to_storage_tier():
    from retnovation.state import frame_interval_days

    assert frame_interval_days(0, set()) == 1          # weak
    assert frame_interval_days(1, set()) == 7          # forming
    assert frame_interval_days(2, {"a", "b"}) == 30    # strong (2 unprompted problems)
```

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py tests/test_state.py -q -k "progression or interval_days"` → FAIL (undefined).

- [ ] **Step 3: Create `content/cadence/progression.yaml`**:

```yaml
# Diagnostic-progression value-function config (doctrine-as-data). Dogfood-tunable.
weights:
  wU: 1.0   # diagnose (reduce uncertainty)
  wR: 1.0   # consolidate (retention due)
  wT: 1.5   # deploy (transfer) — preempts consolidate by design (the signature move)
  wL: 0.5   # cold-start integration-readiness penalty (< wU so cold start still serves)
theta_located: 0.5   # a frame g is "located" when uncertainty(g) <= this
```

- [ ] **Step 4: Implement `load_progression`** — in `content_loader.py` (mirroring `load_spacing`):

```python
def load_progression(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "cadence" / "progression.yaml").read_text())
    w = data["weights"]
    return {
        "wU": float(w["wU"]), "wR": float(w["wR"]), "wT": float(w["wT"]), "wL": float(w["wL"]),
        "theta_located": float(data["theta_located"]),
    }
```

- [ ] **Step 5: Implement `frame_interval_days`** — in `state.py` (reuses `_storage_tier` + `_INTERVAL_DAYS` already in this module):

```python
def frame_interval_days(evidence_count: int, unprompted_breadth: set[str]) -> int:
    return _INTERVAL_DAYS[_storage_tier(evidence_count, unprompted_breadth)]
```

- [ ] **Step 6: GREEN + full suite** — `PYTHONPATH=src .venv/bin/pytest -q` → 141 passed, 3 skipped.

- [ ] **Step 7: Gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P2 Task 2 — progression.yaml + load_progression + state.frame_interval_days; 141/3."
git add content/cadence/progression.yaml src/retnovation/content_loader.py src/retnovation/state.py tests/test_content_loader.py tests/test_state.py docs/DEVLOG.md
git commit -m "feat(content): progression.yaml weights + load_progression + frame_interval_days"
```

---

### Task 3: `policy.py` — the value function (the heart)

**Files:** Create `src/retnovation/policy.py`. Test `tests/test_policy.py` (create).

**Interfaces:** Consumes `state.frame_uncertainty`, `state.frame_interval_days` (Task 2); `SelectionReceipt`, `NextExperienceSpec` (Task 1). Produces `policy.select_next(state: LearnerState, experiences: list[Experience], config: dict, now: datetime) -> tuple[NextExperienceSpec, SelectionReceipt]` — pure (no I/O), deterministic; `experiences` are the open_ended candidates.

- [ ] **Step 1: Write the failing tests** — create `tests/test_policy.py`:

```python
from datetime import datetime, timedelta, timezone

from retnovation.policy import select_next
from retnovation.types import (
    Experience, Frame, FrameStrength, LearnerState, Mode, Regime, Rubric, Strength,
)

NOW = datetime(2026, 6, 24, tzinfo=timezone.utc)
CFG = {"wU": 1.0, "wR": 1.0, "wT": 1.5, "wL": 0.5, "theta_located": 0.5}


def _exp(eid, ref, frames):
    rub = Rubric(
        frames=[Frame(frame_code=c, frame_detail="d") for c in frames], traps=[], mode=Mode.genuinely_open
    )
    return Experience(experience_id=eid, prompt="p", rubric=rub, ledger_ref=ref, regime=Regime.open_ended)


def _forming(ref, now=NOW):
    return FrameStrength(
        strength=Strength.forming, last_seen=now, due=now, last_evidence="x",
        evidence_count=1, breadth={ref}, unprompted_breadth={ref},
    )


def test_cold_start_serves_lowest_load_experience_first():
    exps = [_exp("cap", "veldra:p1", ["a", "b", "c"]), _exp("iso", "veldra:p2", ["z"])]
    spec, receipt = select_next(LearnerState(), exps, CFG, NOW)
    assert receipt.experience_id == "iso"  # lowest constituent_count wins the V tie
    assert spec.experience_id == "iso" and spec.ledger_ref == "veldra:p2" and spec.target_frames == ["z"]


def test_transfer_fires_for_forming_frame_on_a_new_problem():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1")
    exps = [_exp("e1", "veldra:p1", ["lead", "other1"]), _exp("e2", "veldra:p2", ["lead", "other2"])]
    spec, receipt = select_next(st, exps, CFG, NOW)
    assert receipt.frame == "lead" and receipt.problem == "veldra:p2" and receipt.drive == "deploy"


def test_retention_fires_only_when_overdue_on_the_storage_clock():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1", now=NOW - timedelta(days=10))  # forming interval 7d -> overdue
    spec, receipt = select_next(st, [_exp("e1", "veldra:p1", ["lead"])], CFG, NOW)
    assert receipt.scores["retention"] > 0.0


def test_content_gap_logged_for_frame_with_no_isolated_home():
    spec, receipt = select_next(LearnerState(), [_exp("e1", "veldra:p1", ["a", "b"])], CFG, NOW)
    assert "a" in receipt.content_gaps and "b" in receipt.content_gaps


def test_two_experiences_sharing_a_pair_pick_lower_load():
    e_iso = _exp("e_iso", "veldra:p1", ["lead"])
    e_cap = _exp("e_cap", "veldra:p1", ["lead", "x", "y"])
    spec, receipt = select_next(LearnerState(), [e_cap, e_iso], CFG, NOW)
    assert receipt.experience_id == "e_iso"  # lower constituent_count breaks the V tie
```

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_policy.py -q` → FAIL (undefined).

- [ ] **Step 3: Implement `src/retnovation/policy.py`**:

```python
from __future__ import annotations

from datetime import datetime

from .state import frame_interval_days, frame_uncertainty
from .types import Experience, LearnerState, NextExperienceSpec, Regime, SelectionReceipt, Strength


def _uncertainty(state: LearnerState, code: str, now: datetime) -> float:
    fs = state.frames.get(code)
    if fs is None:
        return 1.0  # never seen -> maximally uncertain (cold start)
    return frame_uncertainty(fs.evidence_count, fs.breadth, fs.unprompted_breadth, fs.last_seen, now)


def _retention_due(state: LearnerState, code: str, now: datetime) -> float:
    fs = state.frames.get(code)
    if fs is None or fs.evidence_count == 0:
        return 0.0
    interval = frame_interval_days(fs.evidence_count, fs.unprompted_breadth)
    staleness = max(0.0, (now - fs.last_seen).total_seconds() / 86400.0)
    return max(0.0, min(1.0, (staleness - interval) / interval))


def _transfer(state: LearnerState, code: str, problem: str) -> float:
    fs = state.frames.get(code)
    if fs is None or fs.strength is not Strength.forming:
        return 0.0
    return 1.0 if problem not in fs.breadth else 0.0


def _located(state: LearnerState, code: str, now: datetime, theta: float) -> bool:
    return _uncertainty(state, code, now) <= theta


def _content_gaps(state, experiences, now, theta):
    all_frames = set()
    for e in experiences:
        all_frames.update(f.frame_code for f in e.rubric.frames)
    gaps = []
    for f in sorted(all_frames):
        homed = False
        for e in experiences:
            codes = [x.frame_code for x in e.rubric.frames]
            if f not in codes:
                continue
            if all(_located(state, c, now, theta) for c in codes if c != f):
                homed = True
                break
        if not homed:
            gaps.append(f)
    return gaps


def select_next(state, experiences, config, now):
    wU, wR, wT, wL = config["wU"], config["wR"], config["wT"], config["wL"]
    theta = config["theta_located"]

    best = None  # (sort_key, frame, exp, terms, V, penalty)
    for e in experiences:
        penalty = max((_uncertainty(state, g.frame_code, now) for g in e.rubric.frames), default=0.0)
        load = len(e.rubric.frames)
        for fr in e.rubric.frames:
            f = fr.frame_code
            terms = {
                "diagnose": wU * _uncertainty(state, f, now),
                "consolidate": wR * _retention_due(state, f, now),
                "deploy": wT * _transfer(state, f, e.ledger_ref),
            }
            V = terms["diagnose"] + terms["consolidate"] + terms["deploy"] - wL * penalty
            sort_key = (-V, load, f, e.ledger_ref, e.experience_id)
            if best is None or sort_key < best[0]:
                best = (sort_key, f, e, terms, V, penalty)

    _, frame, exp, terms, V, penalty = best
    ranked = sorted(terms.items(), key=lambda kv: -kv[1])
    drive = ranked[0][0]
    runner_up_drive = ranked[1][0] if len(ranked) > 1 and ranked[1][1] > 0 else None
    margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)

    spec = NextExperienceSpec(
        target_frames=[frame], ledger_ref=exp.ledger_ref, regime=Regime.open_ended,
        experience_id=exp.experience_id,
    )
    receipt = SelectionReceipt(
        frame=frame, problem=exp.ledger_ref, experience_id=exp.experience_id, drive=drive,
        scores={
            "uncertainty": terms["diagnose"] / wU if wU else 0.0,
            "retention": terms["consolidate"] / wR if wR else 0.0,
            "transfer": terms["deploy"] / wT if wT else 0.0,
            "penalty": penalty, "V": V,
        },
        runner_up_drive=runner_up_drive, margin=margin,
        content_gaps=_content_gaps(state, experiences, now, theta), created_at=now,
    )
    return spec, receipt
```

- [ ] **Step 4: GREEN** — `PYTHONPATH=src .venv/bin/pytest tests/test_policy.py -q` → 5 passed.

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P2 Task 3 — policy.select_next value function (drives, argmax + constituent-count tie-break, content-gap predicate, receipt); 146/3."
git add src/retnovation/policy.py tests/test_policy.py docs/DEVLOG.md
git commit -m "feat(policy): value-function select_next over (frame, experience) candidates"
```
Expected suite: 146 passed, 3 skipped. (`policy` is pure and not yet wired into `schedule_next` — additive, suite stays green.)

---

### Task 4: selector honors `experience_id`

**Files:** Modify `src/retnovation/generator.py:165-175` (`select_open_ended`). Test `tests/test_generator.py` (append).

**Interfaces:** Consumes `NextExperienceSpec.experience_id` (Task 1) + `content_loader.load_experience`. Produces `select_open_ended(...)` — when `spec.experience_id` is set, returns exactly that experience; else the legacy coverage ranking (the `build_store` seed has no `experience_id`).

- [ ] **Step 1: Write the failing test** — append to `tests/test_generator.py`:

```python
def test_select_open_ended_honors_experience_id():
    from retnovation.generator import select_open_ended
    from retnovation.types import NextExperienceSpec, Regime

    spec = NextExperienceSpec(
        target_frames=["commit_under_the_deadline"], ledger_ref="veldra:license_fork_risk",
        regime=Regime.open_ended, experience_id="license_continuity",
    )
    exp = select_open_ended(None, None, [], [], spec)
    assert exp.experience_id == "license_continuity"
```

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_generator.py -q -k honors_experience_id` → FAIL (ignores experience_id).

- [ ] **Step 3: Implement** — update `select_open_ended` (add `load_experience` to the `from .content_loader import ...` block if absent):

```python
def select_open_ended(core, state, ledger, corpus, spec, root=None) -> Experience:
    if spec is not None and spec.experience_id is not None:
        return load_experience(spec.experience_id, root)  # the exact (frame, experience) the policy scored
    gated = [(e, r) for (e, r) in load_gated_library(corpus, root) if e.regime is Regime.open_ended]
    if not gated:
        raise GateError("no shippable open_ended experience in the library")
    target = spec.target_frames if spec is not None else []
    ranked = sorted(
        gated, key=lambda er: (-_coverage(er[0], target), len(er[1].downgrades), er[0].experience_id)
    )
    return ranked[0][0]
```

- [ ] **Step 4: GREEN + full suite** — `PYTHONPATH=src .venv/bin/pytest -q` → 147 passed, 3 skipped. (The selector now honors `experience_id`; nothing produces one yet — additive, suite green.)

- [ ] **Step 5: Gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P2 Task 4 — select_open_ended runs the exact experience_id (legacy coverage fallback for the seed); 147/3."
git add src/retnovation/generator.py tests/test_generator.py docs/DEVLOG.md
git commit -m "feat(generator): select_open_ended honors spec.experience_id"
```

---

### Task 5: persistence — `selection_log` + queue `experience_id`

**Files:** Modify `src/retnovation/persistence.py` (`_SCHEMA`, `__init__` migration, `queue_push`/`queue_pop`, add `log_selection`). Test `tests/test_persistence.py` (append).

**Interfaces:** Consumes `NextExperienceSpec.experience_id`, `SelectionReceipt` (Task 1). Produces `queue_push`/`queue_pop` round-trip `experience_id`; `Store.log_selection(receipt) -> None`; a `selection_log` table.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_persistence.py`:

```python
def test_queue_round_trips_experience_id(tmp_path):
    from retnovation.persistence import Store
    from retnovation.types import NextExperienceSpec, Regime

    s = Store(tmp_path / "q.db")
    s.queue_push(NextExperienceSpec(
        target_frames=["f"], ledger_ref="veldra:x", regime=Regime.open_ended, experience_id="license_continuity"
    ))
    assert s.queue_pop().experience_id == "license_continuity"


def test_log_selection_round_trips(tmp_path):
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import SelectionReceipt

    s = Store(tmp_path / "log.db")
    s.log_selection(SelectionReceipt(
        frame="lead", problem="veldra:x", experience_id="license_continuity", drive="deploy",
        scores={"V": 1.5}, runner_up_drive="diagnose", margin=0.5, content_gaps=["g"],
        created_at=datetime(2026, 6, 24, tzinfo=timezone.utc),
    ))
    rows = list(s._db.execute("SELECT frame, experience_id, drive FROM selection_log"))
    assert rows[0]["frame"] == "lead" and rows[0]["experience_id"] == "license_continuity" and rows[0]["drive"] == "deploy"
```

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py -q -k "experience_id or log_selection"` → FAIL.

- [ ] **Step 3: Schema + migration** — extend `_SCHEMA`'s `queue` table and add `selection_log`:

```python
CREATE TABLE IF NOT EXISTS queue (
  position INTEGER PRIMARY KEY AUTOINCREMENT,
  target_frames_json TEXT NOT NULL, ledger_ref TEXT NOT NULL, regime TEXT NOT NULL,
  experience_id TEXT);
CREATE TABLE IF NOT EXISTS selection_log (
  created_at TEXT NOT NULL, frame TEXT NOT NULL, problem TEXT NOT NULL, experience_id TEXT NOT NULL,
  drive TEXT NOT NULL, scores_json TEXT NOT NULL, runner_up_drive TEXT, margin REAL NOT NULL,
  content_gaps_json TEXT NOT NULL);
```

In `__init__`, after the `frames` column guard, add the guarded `queue.experience_id` migration:
```python
        qcols = {r["name"] for r in self._db.execute("PRAGMA table_info(queue)")}
        if "experience_id" not in qcols:
            self._db.execute("ALTER TABLE queue ADD COLUMN experience_id TEXT")
        self._db.commit()
```

- [ ] **Step 4: queue round-trip + `log_selection`** — update `queue_push`/`queue_pop` (thread `experience_id`) and add `log_selection` (add `SelectionReceipt` to the top `from .types import (...)` block):

```python
    def queue_push(self, spec: NextExperienceSpec) -> None:
        self._db.execute(
            "INSERT INTO queue(target_frames_json,ledger_ref,regime,experience_id) VALUES(?,?,?,?)",
            (json.dumps(spec.target_frames), spec.ledger_ref, spec.regime.value, spec.experience_id),
        )
        self._db.commit()

    def queue_pop(self) -> NextExperienceSpec | None:
        row = self._db.execute("SELECT * FROM queue ORDER BY position LIMIT 1").fetchone()
        if row is None:
            return None
        self._db.execute("DELETE FROM queue WHERE position=?", (row["position"],))
        self._db.commit()
        return NextExperienceSpec(
            target_frames=json.loads(row["target_frames_json"]), ledger_ref=row["ledger_ref"],
            regime=Regime(row["regime"]), experience_id=row["experience_id"],
        )

    def log_selection(self, receipt: SelectionReceipt) -> None:
        self._db.execute(
            "INSERT INTO selection_log(created_at,frame,problem,experience_id,drive,scores_json,"
            "runner_up_drive,margin,content_gaps_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                receipt.created_at.isoformat(), receipt.frame, receipt.problem, receipt.experience_id,
                receipt.drive, json.dumps(receipt.scores), receipt.runner_up_drive, receipt.margin,
                json.dumps(receipt.content_gaps),
            ),
        )
        self._db.commit()
```

- [ ] **Step 5: GREEN + full suite** — `PYTHONPATH=src .venv/bin/pytest -q` → 149 passed, 3 skipped. (`experience_id` is nullable → existing queue round-trips unaffected.)

- [ ] **Step 6: Gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git status --short   # no data/ staged
# DEVLOG: "P2 Task 5 — selection_log table + log_selection; queue carries experience_id (guarded migration); 149/3."
git add src/retnovation/persistence.py tests/test_persistence.py docs/DEVLOG.md
git commit -m "feat(persistence): selection_log + queue experience_id"
```

---

### Task 6: integration — `schedule_next` → policy, `run_session` logs the receipt (atomic, suite green)

**Files:** Modify `src/retnovation/scheduler.py` (rewrite `schedule_next`), `src/retnovation/orchestration.py:43`, and the direct `schedule_next` callers/expectations in `tests/test_scheduler.py`, `tests/test_dry_run.py`, `tests/test_cs_dry_run.py`, `tests/test_orchestration.py`, `tests/test_cli.py` — **all in one task** so the return-type change never leaves the suite red.

**Interfaces:** Consumes `policy.select_next` (Task 3), `content_loader.load_library`/`load_progression` (Task 2), `Store.log_selection` (Task 5), the `experience_id`-honoring selector (Task 4). Produces `schedule_next(state, ledger, now, regime=Regime.open_ended, *, root=None) -> tuple[NextExperienceSpec, SelectionReceipt | None]`; `run_session` queues the spec and logs the receipt (open_ended only).

- [ ] **Step 1: Write/rewrite the failing tests.**
  - In `tests/test_scheduler.py`: delete `test_weak_frames_are_targeted_first` and `test_all_strong_targets_soonest_due` (they assert the removed placeholder); change every cs `spec = schedule_next(...)` to `spec, _ = schedule_next(...)`; add:

```python
def test_open_ended_uses_the_value_function_over_real_content():
    st = LearnerState()
    led = [LedgerEntry(id="veldra:license_fork_risk", owned_problem="...")]
    spec, receipt = schedule_next(st, led, _now())
    assert spec.regime is Regime.open_ended
    assert spec.experience_id is not None and spec.experience_id == receipt.experience_id
    assert spec.target_frames == [receipt.frame] and receipt.scores["V"] >= 0.0
```

  - In `tests/test_orchestration.py`: append a log-assertion test modeled on the file's existing `test_run_session_closes_one_cycle` (same store/core/FakeModel setup), then assert `len(list(store._db.execute("SELECT * FROM selection_log"))) == 1` after `run_session`.

- [ ] **Step 2: Run RED** — `PYTHONPATH=src .venv/bin/pytest tests/test_scheduler.py -q` → FAIL (placeholder branch + non-tuple return).

- [ ] **Step 3: Rewrite `src/retnovation/scheduler.py`**:

```python
from __future__ import annotations

from datetime import datetime

from .content_loader import load_library, load_progression
from .policy import select_next
from .types import LearnerState, LedgerEntry, NextExperienceSpec, Regime, SelectionReceipt


def schedule_next(
    state: LearnerState, ledger: list[LedgerEntry], now: datetime,
    regime: Regime = Regime.open_ended, *, root=None,
) -> tuple[NextExperienceSpec, SelectionReceipt | None]:
    if regime is Regime.cs_technical:
        ledger_ref = ledger[0].id if ledger else ""
        items = state.declarative_seed
        due = sorted((c for c, si in items.items() if si.due <= now), key=lambda c: (items[c].due, c))
        if due:
            targets = due
        elif items:
            targets = [min(items.items(), key=lambda kv: (kv[1].due, kv[0]))[0]]
        else:
            targets = []
        return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime), None

    experiences = [e for e in load_library(root) if e.regime is Regime.open_ended]
    return select_next(state, experiences, load_progression(root), now)
```

- [ ] **Step 4: Wire `run_session`** — in `src/retnovation/orchestration.py`, replace line 43:

```python
    next_spec, receipt = schedule_next(state, ledger, now, exp.regime)
    if receipt is not None:
        store.log_selection(receipt)
    store.queue_push(next_spec)
```

- [ ] **Step 5: Fix the remaining callers/expectations.** In `tests/test_dry_run.py`, `tests/test_cs_dry_run.py`, `tests/test_cli.py`, `tests/test_orchestration.py`: unpack any direct `schedule_next(...)` to `spec, _ = ...`. Where an open_ended dry-run/cli test pinned a specific selected experience under the old placeholder, relax it to the value-function behavior (assert `assessment.stop_reason` / non-empty `state.frames` / a `selection_log` row, not a hard-coded experience id — the policy may pick a different experience than the placeholder did).

- [ ] **Step 6: GREEN — full suite** — `PYTHONPATH=src .venv/bin/pytest -q` → all green (~151 passed, 3 skipped; exact count depends on the tests touched). The value-function policy is now wired end-to-end.

- [ ] **Step 7: Gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git status --short   # no data/ staged
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo CLEAN
# DEVLOG: "P2 Task 6 — schedule_next dispatches open_ended to the value function (returns (spec, receipt)); run_session logs the receipt + queues the spec; cs byte-stable; placeholder removed; suite green. Project 2 policy complete."
git add src/retnovation/scheduler.py src/retnovation/orchestration.py tests/test_scheduler.py tests/test_dry_run.py tests/test_cs_dry_run.py tests/test_orchestration.py tests/test_cli.py docs/DEVLOG.md
git commit -m "feat(scheduler): value-function policy wired end-to-end; run_session logs the receipt"
```

---

### Task 7: whole-branch adversarial review + finish (CONTROLLER — not an implementer subagent)

- [ ] **Step 1: Dispatch an independent opus whole-branch review** of `git diff main...HEAD` against §7/§16 and these risks:
  - **Candidate = `(frame, experience)`:** the penalty (`max` over `e.rubric.frames`), the served artifact (selector runs `spec.experience_id`), and the receipt all describe the SAME `e`; a `(frame, problem)` with two homes scores each `(f,e)` distinctly and picks the lower-load one.
  - **Tie-break `(constituent_count asc, frame_id, problem, experience_id)`:** cold-start serves the lowest-load experience first (intro-arc at the first pick), fully deterministic.
  - **Drives:** uncertainty reuses `frame_uncertainty` (unseen→1.0); retention keys to `frame_interval_days` and fires only when overdue + earned; transfer only for `forming` + new problem; penalty = `max` constituent uncertainty.
  - **Content-gap static predicate** is the one implemented (no runtime "dominated by penalty"); the policy still serves.
  - **`cs_technical` byte-stable;** the placeholder shim is fully removed; `_INTERVAL_DAYS` stays in `state.py`.
  - **Persistence:** `selection_log` + `queue.experience_id` migration is guarded (old DBs migrate); nothing under `data/` staged.
  - **Determinism:** no `Math.random`/`datetime.now` inside `policy` (now is injected); the receipt's per-term scores are the un-weighted drive values.
- [ ] **Step 2: Address findings** as additive fixes (own commits, same gate); re-run the full suite.
- [ ] **Step 3: Finish** — `superpowers:finishing-a-development-branch` to merge `diagnostic-progression-policy` into `main`. **Do not push** unless asked. Update the `retnovation-commitment-frame-gap` memory's progression thread: "Project 2 (value-function policy) landed; Project 3 (interactive surface + core promote/demote) pending."

---

## Self-Review

**Spec coverage (§16):** candidate `(frame, experience)` + derived problem → T3 (policy) + T1 (spec.experience_id); 4 drive formulas → T3; score + default weights + constituent-count tie-break → T3 + T2; static content-gap predicate (`θ_located`) → T3 + T2; selector honors the scored experience → T4; `progression.yaml` + `load_progression` (and `_INTERVAL_DAYS` stays in `state.py`, refining §16) → T2; `selection_log` (decision + receipt incl. `experience_id`, queue-time) → T5 + T6; remove the shim, `cs_technical` byte-stable → T6; all testing items (each drive, cold-start tie-break, transfer, retention, penalty, content-gap, two-homes, selector, log) → T3–T6. ✓

**Placeholder scan:** the one implementer-fill is T6 Step 1's orchestration log-assert test (it must mirror this file's existing `test_run_session_closes_one_cycle` harness, which the plan can't reproduce blind) — flagged with the exact assertion. T6 Step 5 says "relax pinned-experience expectations to value-function behavior" — concrete (assert stop_reason / state.frames / a selection_log row, not a hard-coded id). All code steps carry complete code.

**Type consistency:** `select_next(state, experiences, config, now) -> (NextExperienceSpec, SelectionReceipt)` (T3) consumed by `schedule_next(...) -> (spec, receipt|None)` (T6); `SelectionReceipt` fields identical across T1/T3/T5; `frame_interval_days`/`frame_uncertainty`/`load_progression` signatures match T2/T3; `spec.experience_id` flows types→policy→generator→persistence→scheduler consistently. **Every commit leaves the full suite green** (T1–T5 additive; T6 the single atomic return-type swap).
