# Diagnostic Progression — Project 1: Learner-Model Substrate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the learner-model substrate so a frame's strength is an *earned, derived* function of persistent evidence on a storage-keyed staleness clock — making `strong` reachable, decay automatic, and the trap gallery persisted — with **no selection-behavior change** (the existing scheduler keeps reading `fs.strength`).

**Architecture:** `FrameStrength` stores only *storage strength* (`evidence_count`, `breadth`, `unprompted_breadth`, `last_seen`, `last_evidence`); `strength` and `due` become *derived* (computed from storage + `now`) via pure functions whose staleness clock keys to the storage tier, never the displayed bucket. The estimator writes only storage; `load_state(now)` derives the buckets; `decay_frame` is deleted; `trap_gallery` is persisted. Same-session reads (staleness 0) reproduce today's buckets, so the existing scheduler/state tests stay green.

**Tech Stack:** Python 3.12, Pydantic v2, sqlite3, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-06-24-diagnostic-progression-design.md` (rev. 2). This plan implements **Project 1 only** (§10.1); Projects 2 (value-function policy) and 3 (receipt surface) are separate plans.

**Branch:** create `diagnostic-progression-substrate` off `main` before Task 1. `main` is ~48 commits ahead of `origin/main`; **do not push**.

## Global Constraints

Every task implicitly includes these:

- **Storage vs. retrieval strength (the load-bearing pin, spec §6/§14).** Persist only storage:
  `evidence_count`, `breadth`, `unprompted_breadth`, `last_seen`, `last_evidence`. `strength`/`due` are
  derived from storage + `now`. **The staleness clock (the `due` interval, the decay step, the
  uncertainty staleness-term) keys to the storage tier (`evidence_count`/`unprompted_breadth`), NEVER the
  displayed/decayed bucket.** A well-earned frame keeps its long interval as it decays (reviewed *less*,
  not more) and springs back on one re-exposure.
- **Served-path boundary (spec §14.2).** `load_state` derives and `update_state` writes only storage —
  the **served paths never set `strength` directly**. Direct `FrameStrength(strength=…)` construction
  stays open for tests only (the shim seam).
- **No behavior change / shim.** The scheduler is untouched and still reads `fs.strength`. Same-session
  reads (staleness 0) must reproduce today's reachable buckets, so every existing
  state/scheduler/orchestration/dry-run test stays green.
- **Earned `strong` bar (spec §6).** `strong` requires unprompted `present_reasoned` on ≥2 distinct
  problems (`len(unprompted_breadth) >= 2`); `forming` = engaged with a mechanism ≥1 time
  (`evidence_count >= 1`, incl. closed-under-pressure); `weak` otherwise.
- **Conclusion-agnostic.** No new signal reads a conclusion; strength moves on rigor/trajectory evidence
  only.
- **TDD.** Failing test first, run RED, implement, run GREEN, full suite, commit.
- **Per-commit gate** (all clean before commit): `.venv/bin/ruff format .`; `.venv/bin/ruff check .`;
  `PYTHONPATH=src .venv/bin/pytest -q`; confidentiality
  `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'`
  empty; `git status --short` shows no `data/` staged; `docs/DEVLOG.md` updated in the same commit;
  explicit-path `git add` only; **no `Co-Authored-By` trailer**.
- **Staleness thresholds** live as named module constants in `state.py` this project
  (`_INTERVAL_DAYS = {weak:1, forming:7, strong:30}`), with a comment that they move to
  `content/cadence/progression.yaml` in Project 2. Not hardcoded magic — named and centralized.

Baseline before Task 1: **124 passed, 3 skipped**, ruff clean.

---

### Task 1: `FrameStrength` storage fields

**Files:**
- Modify: `src/retnovation/types.py:193-197` (the `FrameStrength` model)
- Test: `tests/test_types.py` (append)

**Interfaces:**
- Produces: `FrameStrength` gains `evidence_count: int = 0`, `breadth: set[str] = {}`,
  `unprompted_breadth: set[str] = {}`; `strength`/`due`/`last_seen`/`last_evidence` unchanged. Existing
  positional/keyword construction `FrameStrength(strength=…, last_seen=…, due=…, last_evidence=…)` still
  works (new fields default).

- [ ] **Step 1: Write the failing test** — append to `tests/test_types.py`:

```python
def test_frame_strength_storage_fields_default_empty():
    from datetime import datetime, timezone
    from retnovation.types import FrameStrength, Strength

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    fs = FrameStrength(strength=Strength.weak, last_seen=now, due=now, last_evidence="")
    assert fs.evidence_count == 0
    assert fs.breadth == set()
    assert fs.unprompted_breadth == set()
    fs2 = FrameStrength(
        strength=Strength.strong, last_seen=now, due=now, last_evidence="x",
        evidence_count=3, breadth={"veldra:a", "veldra:b"}, unprompted_breadth={"veldra:a", "veldra:b"},
    )
    assert fs2.evidence_count == 3 and fs2.breadth == {"veldra:a", "veldra:b"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py::test_frame_strength_storage_fields_default_empty -q`
Expected: FAIL — `FrameStrength` rejects `evidence_count`/`breadth`/`unprompted_breadth` (unknown fields).

- [ ] **Step 3: Add the fields** — in `src/retnovation/types.py`, replace the `FrameStrength` class:

```python
class FrameStrength(BaseModel):
    strength: Strength  # DERIVED on read (storage-keyed clock); kept settable for tests/back-compat
    last_seen: datetime
    due: datetime  # DERIVED on read
    last_evidence: str
    evidence_count: int = 0  # total mechanism-engagements (unprompted OR closed-under-pressure)
    breadth: set[str] = Field(default_factory=set)  # problems engaged with a mechanism (forming+; transfer uses this)
    unprompted_breadth: set[str] = Field(default_factory=set)  # subset: problems with an UNPROMPTED present_reasoned (the strong bar)
```

(`Field` is already imported at `types.py:8`.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P1 Task 1 — FrameStrength storage fields (evidence_count, breadth, unprompted_breadth); 125/3."
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): FrameStrength storage fields for derived strength"
```
Expected suite: 125 passed, 3 skipped.

---

### Task 2: derivation functions on the storage-keyed clock

**Files:**
- Modify: `src/retnovation/state.py` (add the derivation functions + constants near the top, after imports)
- Test: `tests/test_state.py` (append)

**Interfaces:**
- Consumes: `FrameStrength` storage fields (Task 1).
- Produces, in `src/retnovation/state.py`:
  - `derive_strength(evidence_count: int, unprompted_breadth: set[str], last_seen: datetime, now: datetime) -> Strength`
  - `derive_due(evidence_count: int, unprompted_breadth: set[str], last_seen: datetime) -> datetime`
  - `frame_uncertainty(evidence_count: int, breadth: set[str], unprompted_breadth: set[str], last_seen: datetime, now: datetime) -> float` (in `[0,1]`)
  - module constant `_INTERVAL_DAYS: dict[Strength, int] = {weak:1, forming:7, strong:30}`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_state.py`:

```python
def test_storage_tier_strong_needs_two_unprompted_problems():
    from datetime import datetime, timezone
    from retnovation.state import derive_strength
    from retnovation.types import Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # 1 unprompted problem → forming (not strong yet)
    assert derive_strength(1, {"veldra:a"}, t0, t0) is Strength.forming
    # 2 distinct unprompted problems → strong (reachable)
    assert derive_strength(2, {"veldra:a", "veldra:b"}, t0, t0) is Strength.strong
    # engaged but never unprompted (closed-under-pressure only) → forming
    assert derive_strength(2, set(), t0, t0) is Strength.forming
    # no engagement → weak
    assert derive_strength(0, set(), t0, t0) is Strength.weak


def test_derive_strength_decays_one_bucket_then_springs_back():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import derive_strength
    from retnovation.types import Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    strong_args = (2, {"veldra:a", "veldra:b"})  # storage tier = strong, interval 30d
    assert derive_strength(*strong_args, t0, t0) is Strength.strong  # fresh
    assert derive_strength(*strong_args, t0, t0 + timedelta(days=40)) is Strength.forming  # decayed one bucket
    # re-exposure: last_seen advances, storage unchanged → springs back
    assert derive_strength(*strong_args, t0 + timedelta(days=40), t0 + timedelta(days=40)) is Strength.strong


def test_due_keys_to_storage_tier_not_the_decayed_bucket():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import derive_due

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    strong_due = derive_due(2, {"veldra:a", "veldra:b"}, t0)
    forming_due = derive_due(1, {"veldra:a"}, t0)
    # the well-earned (strong-storage) frame comes due LATER, i.e. is reviewed less, not more, as it decays
    assert strong_due == t0 + timedelta(days=30)
    assert forming_due == t0 + timedelta(days=7)
    assert strong_due > forming_due


def test_frame_uncertainty_monotone():
    from datetime import datetime, timedelta, timezone
    from retnovation.state import frame_uncertainty

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # more evidence → less uncertain
    assert frame_uncertainty(1, {"a"}, set(), t0, t0) > frame_uncertainty(5, {"a"}, set(), t0, t0)
    # broader → less uncertain
    assert frame_uncertainty(2, {"a"}, set(), t0, t0) > frame_uncertainty(2, {"a", "b"}, set(), t0, t0)
    # staler → more uncertain
    assert frame_uncertainty(2, {"a", "b"}, {"a", "b"}, t0, t0) < frame_uncertainty(
        2, {"a", "b"}, {"a", "b"}, t0, t0 + timedelta(days=20)
    )
    u = frame_uncertainty(1, {"a"}, set(), t0, t0)
    assert 0.0 <= u <= 1.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_state.py -q -k "storage_tier or decays or due_keys or uncertainty_monotone"`
Expected: FAIL — `ImportError: cannot import name 'derive_strength'` (functions don't exist).

- [ ] **Step 3: Implement the derivation** — in `src/retnovation/state.py`, add after the imports (before `update_state`), and add `timedelta` to the existing `from datetime import` line:

```python
# Storage-keyed staleness clock. The interval is a function of the persistent STORAGE tier
# (evidence_count / unprompted_breadth), never the displayed/decayed bucket — acyclic and §5-faithful.
# Moves to content/cadence/progression.yaml in Project 2.
_INTERVAL_DAYS: dict[Strength, int] = {Strength.weak: 1, Strength.forming: 7, Strength.strong: 30}
_STEP_DOWN: dict[Strength, Strength] = {
    Strength.strong: Strength.forming,
    Strength.forming: Strength.weak,
    Strength.weak: Strength.weak,
}


def _storage_tier(evidence_count: int, unprompted_breadth: set[str]) -> Strength:
    if len(unprompted_breadth) >= 2:
        return Strength.strong  # unprompted on >=2 distinct problems: repeated AND cross-context
    if evidence_count >= 1:
        return Strength.forming  # engaged with a mechanism at least once (incl. closed-under-pressure)
    return Strength.weak


def _staleness_days(last_seen: datetime, now: datetime) -> float:
    return max(0.0, (now - last_seen).total_seconds() / 86400.0)


def derive_strength(
    evidence_count: int, unprompted_breadth: set[str], last_seen: datetime, now: datetime
) -> Strength:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    if _staleness_days(last_seen, now) <= _INTERVAL_DAYS[tier]:
        return tier
    return _STEP_DOWN[tier]  # decayed one bucket; the interval below stays keyed to `tier` (storage)


def derive_due(evidence_count: int, unprompted_breadth: set[str], last_seen: datetime) -> datetime:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    return last_seen + timedelta(days=_INTERVAL_DAYS[tier])


def frame_uncertainty(
    evidence_count: int,
    breadth: set[str],
    unprompted_breadth: set[str],
    last_seen: datetime,
    now: datetime,
) -> float:
    tier = _storage_tier(evidence_count, unprompted_breadth)
    evidence_term = 1.0 / (1.0 + evidence_count)
    breadth_term = 0.0 if len(breadth) >= 2 else 1.0
    staleness_term = min(1.0, _staleness_days(last_seen, now) / _INTERVAL_DAYS[tier])
    return max(0.0, min(1.0, (evidence_term + breadth_term + staleness_term) / 3.0))
```

The existing `from datetime import datetime, timedelta` at `state.py:4` already imports `timedelta` — confirm; if only `datetime` is imported, add `timedelta`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_state.py -q`
Expected: PASS (existing state tests + 4 new).

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P1 Task 2 — derive_strength/derive_due/frame_uncertainty on the storage-keyed clock; 129/3."
git add src/retnovation/state.py tests/test_state.py docs/DEVLOG.md
git commit -m "feat(state): derived strength/due/uncertainty on the storage-keyed staleness clock"
```
Expected suite: 129 passed, 3 skipped.

---

### Task 3: estimator redesign — write storage, anchored to the problem

**Files:**
- Modify: `src/retnovation/state.py:20-58` (`update_state`) and `:61-96` (`update_state_checkable` signature + `STATE_UPDATERS`)
- Modify: `src/retnovation/orchestration.py:41` (pass `exp.ledger_ref`)
- Test: `tests/test_state.py` (append + update existing call sites), `tests/test_sharper_grader.py:86` (update call)

**Interfaces:**
- Consumes: `derive_strength`/`derive_due` (Task 2), `FrameStrength` storage (Task 1).
- Produces: `update_state(state, assessment, now, experience_id, ledger_ref)` — new required `ledger_ref`
  param; writes `evidence_count`/`breadth`/`unprompted_breadth`/`last_seen` and the derived
  `strength`/`due`. `update_state_checkable(state, assessment, now, experience_id, ledger_ref, spacing=None)`
  accepts + ignores `ledger_ref`. Both stay registered in `STATE_UPDATERS` and are called with the same
  5 positional args.

- [ ] **Step 1: Write the failing tests + update existing calls** — in `tests/test_state.py`, update the
  three existing `update_state(LearnerState(), a, _now(), "exp1")` calls (lines ~40, 55, 69) to add a
  ledger_ref: `update_state(LearnerState(), a, _now(), "exp1", "veldra:p1")`. Then append:

```python
def test_strong_reachable_across_two_problems():
    from datetime import datetime, timezone
    from retnovation.model import IntakeClassification, ResponseClassification  # noqa: F401
    from retnovation.state import update_state
    from retnovation.types import (
        Assessment, FrameDelta, FrameState, LearnerState, Push, StopReason, Strength,
    )

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)

    def _unprompted(code):
        # an unprompted present_reasoned: a delta to present_reasoned, NOT in frames_closed_under_pressure
        return Assessment(
            trajectory=[Push(target_code=code, kind="frame", text="t", response_classification="closed", response="r")],
            frame_deltas=[FrameDelta(code=code, before=FrameState.absent, after=FrameState.present_reasoned)],
            frames_closed_under_pressure=[],
            hard_wrong_flags=[],
            stop_reason=StopReason.converged,
        )

    st = LearnerState()
    st = update_state(st, _unprompted("f"), now, "exp1", "veldra:p1")
    assert st.frames["f"].strength is Strength.forming  # one problem only
    st = update_state(st, _unprompted("f"), now, "exp2", "veldra:p2")
    assert st.frames["f"].unprompted_breadth == {"veldra:p1", "veldra:p2"}
    assert st.frames["f"].strength is Strength.strong  # two distinct problems, unprompted


def test_closed_under_pressure_is_forming_not_strong():
    from datetime import datetime, timezone
    from retnovation.state import update_state
    from retnovation.types import (
        Assessment, FrameDelta, FrameState, LearnerState, Push, StopReason, Strength,
    )

    now = datetime(2026, 6, 24, tzinfo=timezone.utc)
    a = Assessment(
        trajectory=[Push(target_code="f", kind="frame", text="t", response_classification="closed", response="r")],
        frame_deltas=[FrameDelta(code="f", before=FrameState.absent, after=FrameState.present_reasoned)],
        frames_closed_under_pressure=["f"],  # needed the push
        hard_wrong_flags=[],
        stop_reason=StopReason.converged,
    )
    st = update_state(LearnerState(), a, now, "exp1", "veldra:p1")
    assert st.frames["f"].strength is Strength.forming
    assert st.frames["f"].breadth == {"veldra:p1"}
    assert st.frames["f"].unprompted_breadth == set()  # closed-under-pressure does NOT earn strong-grade
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_state.py -q -k "strong_reachable or closed_under_pressure_is_forming"`
Expected: FAIL — `update_state()` takes 4 positional args, the new calls pass 5 (`TypeError`), and
`unprompted_breadth` is never populated.

- [ ] **Step 3: Rewrite `update_state` and the registry** — in `src/retnovation/state.py`, replace
  `update_state` (lines 20-58):

```python
def update_state(
    state: LearnerState, assessment: Assessment, now: datetime, experience_id: str, ledger_ref: str
) -> LearnerState:
    closed = set(assessment.frames_closed_under_pressure)
    final_state: dict[str, FrameState] = {d.code: d.after for d in assessment.frame_deltas}
    seen_frame_targets = {p.target_code for p in assessment.trajectory if p.kind == "frame"}

    for code in seen_frame_targets | set(final_state):
        prev = state.frames.get(code)
        evidence_count = prev.evidence_count if prev else 0
        breadth = set(prev.breadth) if prev else set()
        unprompted_breadth = set(prev.unprompted_breadth) if prev else set()
        fstate = final_state.get(code)
        if fstate is FrameState.present_reasoned:
            evidence_count += 1
            breadth.add(ledger_ref)
            if code not in closed:
                unprompted_breadth.add(ledger_ref)  # reasoned WITHOUT a closing push → strong-grade
        evidence = fstate.value if fstate is not None else "unmoved"
        state.frames[code] = FrameStrength(
            strength=derive_strength(evidence_count, unprompted_breadth, now, now),
            last_seen=now,
            due=derive_due(evidence_count, unprompted_breadth, now),
            last_evidence=f"{experience_id}:{evidence}",
            evidence_count=evidence_count,
            breadth=breadth,
            unprompted_breadth=unprompted_breadth,
        )

    for p in assessment.trajectory:
        if p.kind == "trap" and p.response_classification != "closed":
            state.trap_gallery.setdefault(p.target_code, []).append(
                TrapOccurrence(
                    experience_id=experience_id, occurred_at=now, detail=p.response_classification
                )
            )
    return state
```

Update `update_state_checkable` (line 61) to accept the new positional `ledger_ref` (ignored), keeping
`spacing` last and keyword-defaulted:

```python
def update_state_checkable(
    state: LearnerState,
    assessment: CheckableAssessment,
    now: datetime,
    experience_id: str,
    ledger_ref: str,
    spacing: dict | None = None,
) -> LearnerState:
```

(`Strength`, `FrameState`, `FrameStrength`, `TrapOccurrence` are already imported at the top of
`state.py`.)

- [ ] **Step 4: Thread `ledger_ref` at the call site** — in `src/retnovation/orchestration.py` line 41:

```python
    state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id, exp.ledger_ref)
```

- [ ] **Step 5: Update the other direct caller** — in `tests/test_sharper_grader.py` line 86, add the
  ledger_ref arg:

```python
    st = update_state(LearnerState(), audited, datetime(2026, 6, 23, tzinfo=timezone.utc), "x", "veldra:p")
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_state.py tests/test_sharper_grader.py tests/test_orchestration.py tests/test_dry_run.py -q`
Expected: PASS — the two new tests, the preserved `forming`/`weak` assertions (`test_state.py`), the
sharper-grader guard, and the full open-ended loop (orchestration/dry-run feed `exp.ledger_ref`).

- [ ] **Step 7: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "P1 Task 3 — estimator writes storage anchored to ledger_ref; strong reachable across 2 problems; 131/3."
git add src/retnovation/state.py src/retnovation/orchestration.py tests/test_state.py tests/test_sharper_grader.py docs/DEVLOG.md
git commit -m "feat(state): estimator writes evidence/breadth anchored to the problem; strong reachable"
```
Expected suite: 131 passed, 3 skipped.

---

### Task 4: persistence — derive on load, migrate, delete `decay_frame`

**Files:**
- Modify: `src/retnovation/persistence.py` (`_SCHEMA` :20-35, `__init__` migration :45-48, `load_state` :53-68, `save_state` :70-92, delete `decay_frame` :94-99)
- Modify: `src/retnovation/orchestration.py:34` (`load_state(now)`)
- Modify: callers `tests/test_dry_run.py:132`, `tests/test_cs_dry_run.py:45`, `tests/test_cli.py:18`
- Test: `tests/test_persistence.py` (update: drop the `decay_frame` test, add migration + derive tests)

**Interfaces:**
- Consumes: `derive_strength`/`derive_due` (Task 2), `FrameStrength` storage (Task 1).
- Produces: `Store.load_state(now: datetime) -> LearnerState` — derives `strength`/`due` from stored
  storage + `now`; `Store.save_state(state)` persists the storage fields (+ a `strength`/`due` snapshot);
  `decay_frame` removed. New `frames` columns `evidence_count`, `breadth_json`, `unprompted_breadth_json`
  (guarded migration).

- [ ] **Step 1: Write the failing tests** — in `tests/test_persistence.py`: (a) update existing
  `load_state()` calls (lines 28, 40, 78, 86) to `load_state(_now())`; (b) **delete** the
  `decay_frame` test (the one calling `s.decay_frame(...)`, ~lines 33-42); (c) append:

```python
def test_storage_fields_round_trip_and_strength_derives(tmp_path):
    from datetime import datetime, timedelta, timezone
    from retnovation.persistence import Store
    from retnovation.types import FrameStrength, LearnerState, Strength

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    s = Store(tmp_path / "p.db")
    st = LearnerState()
    st.frames["f"] = FrameStrength(
        strength=Strength.strong, last_seen=t0, due=t0 + timedelta(days=30), last_evidence="exp:reasoned",
        evidence_count=2, breadth={"veldra:a", "veldra:b"}, unprompted_breadth={"veldra:a", "veldra:b"},
    )
    s.save_state(st)
    # fresh read at t0 → strong (staleness 0); read 40d later → decayed to forming, storage intact
    fresh = Store(tmp_path / "p.db").load_state(t0)
    assert fresh.frames["f"].strength is Strength.strong
    assert fresh.frames["f"].unprompted_breadth == {"veldra:a", "veldra:b"}
    decayed = Store(tmp_path / "p.db").load_state(t0 + timedelta(days=40))
    assert decayed.frames["f"].strength is Strength.forming
    assert decayed.frames["f"].evidence_count == 2  # storage never lost


def test_old_db_without_new_columns_migrates(tmp_path):
    import sqlite3
    from datetime import datetime, timezone
    from retnovation.persistence import Store

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    # simulate a pre-migration frames table (no evidence_count/breadth columns)
    db = tmp_path / "old.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE frames (frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL, "
        "last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL)"
    )
    con.execute(
        "INSERT INTO frames VALUES ('f','forming',?,?,'old')",
        (t0.isoformat(), t0.isoformat()),
    )
    con.commit()
    con.close()
    loaded = Store(db).load_state(t0)  # __init__ migrates, load derives
    assert loaded.frames["f"].evidence_count == 0  # old row → no storage evidence
    assert loaded.frames["f"].breadth == set()
    from retnovation.types import Strength
    assert loaded.frames["f"].strength is Strength.weak  # derived from zero evidence


def test_decay_frame_is_gone(tmp_path):
    from retnovation.persistence import Store

    assert not hasattr(Store(tmp_path / "x.db"), "decay_frame")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py -q -k "storage_fields or old_db or decay_frame_is_gone"`
Expected: FAIL — `load_state()` takes no `now`; new columns absent; `decay_frame` still present.

- [ ] **Step 3: Migrate the schema** — in `src/retnovation/persistence.py`, extend the `frames` table in
  `_SCHEMA` (so fresh DBs get the columns) and add a guarded migration in `__init__` after the existing
  `scene_json` guard:

In `_SCHEMA`, change the `frames` table to:
```python
CREATE TABLE IF NOT EXISTS frames (
  frame_code TEXT PRIMARY KEY, strength TEXT NOT NULL,
  last_seen TEXT NOT NULL, due TEXT NOT NULL, last_evidence TEXT NOT NULL,
  evidence_count INTEGER NOT NULL DEFAULT 0, breadth_json TEXT, unprompted_breadth_json TEXT);
```
In `__init__`, after the `scene_json` block (line 48), add:
```python
        fcols = {r["name"] for r in self._db.execute("PRAGMA table_info(frames)")}
        for col, decl in (
            ("evidence_count", "INTEGER NOT NULL DEFAULT 0"),
            ("breadth_json", "TEXT"),
            ("unprompted_breadth_json", "TEXT"),
        ):
            if col not in fcols:
                self._db.execute(f"ALTER TABLE frames ADD COLUMN {col} {decl}")
        self._db.commit()
```

- [ ] **Step 4: Derive on load, persist storage on save, delete `decay_frame`** — replace `load_state`
  (lines 53-68) and `save_state` (lines 70-92), and delete `decay_frame` (lines 94-99):

```python
    def load_state(self, now: datetime) -> LearnerState:
        from .state import derive_due, derive_strength

        st = LearnerState()
        for r in self._db.execute("SELECT * FROM frames"):
            breadth = set(json.loads(r["breadth_json"])) if r["breadth_json"] else set()
            unprompted = (
                set(json.loads(r["unprompted_breadth_json"])) if r["unprompted_breadth_json"] else set()
            )
            evidence_count = r["evidence_count"] or 0
            last_seen = datetime.fromisoformat(r["last_seen"])
            st.frames[r["frame_code"]] = FrameStrength(
                strength=derive_strength(evidence_count, unprompted, last_seen, now),
                last_seen=last_seen,
                due=derive_due(evidence_count, unprompted, last_seen),
                last_evidence=r["last_evidence"],
                evidence_count=evidence_count,
                breadth=breadth,
                unprompted_breadth=unprompted,
            )
        for r in self._db.execute("SELECT * FROM concepts"):
            st.declarative_seed[r["concept"]] = SpacedItem(
                concept=r["concept"],
                due=datetime.fromisoformat(r["due"]),
                interval_days=r["interval_days"],
            )
        return st

    def save_state(self, state: LearnerState) -> None:
        for code, fs in state.frames.items():
            self._db.execute(
                "INSERT INTO frames(frame_code,strength,last_seen,due,last_evidence,"
                "evidence_count,breadth_json,unprompted_breadth_json) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(frame_code) DO UPDATE SET strength=excluded.strength,"
                "last_seen=excluded.last_seen,due=excluded.due,last_evidence=excluded.last_evidence,"
                "evidence_count=excluded.evidence_count,breadth_json=excluded.breadth_json,"
                "unprompted_breadth_json=excluded.unprompted_breadth_json",
                (
                    code,
                    fs.strength.value,  # snapshot only — load_state re-derives; never read back as authority
                    fs.last_seen.isoformat(),
                    fs.due.isoformat(),
                    fs.last_evidence,
                    fs.evidence_count,
                    json.dumps(sorted(fs.breadth)),
                    json.dumps(sorted(fs.unprompted_breadth)),
                ),
            )
        for concept, si in state.declarative_seed.items():
            self._db.execute(
                "INSERT INTO concepts(concept,due,interval_days) VALUES(?,?,?) "
                "ON CONFLICT(concept) DO UPDATE SET due=excluded.due, "
                "interval_days=excluded.interval_days",
                (concept, si.due.isoformat(), si.interval_days),
            )
        self._db.commit()
```

- [ ] **Step 5: Thread `now` into the remaining callers**:
  - `src/retnovation/orchestration.py:34`: `state = store.load_state(now)`
  - `tests/test_dry_run.py:132`: `Store(tmp_path / "dryrun.db").load_state(NOW)` (use the test's existing
    `now`/fixed datetime; if none in scope, add `from datetime import datetime, timezone` and a
    `NOW = datetime(2026, 6, 24, tzinfo=timezone.utc)`)
  - `tests/test_cs_dry_run.py:45`: same — `.load_state(NOW)` with a fixed datetime in scope
  - `tests/test_cli.py:18`: pass a fixed `now` — `store.load_state(datetime(2026, 6, 24, tzinfo=timezone.utc))`
    (add the import if absent). If the cli path under test constructs `select_experience(...)`, the
    `load_state(now)` is the only change there.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py tests/test_dry_run.py tests/test_cs_dry_run.py tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 7: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git status --short   # confirm no data/ staged
# DEVLOG: "P1 Task 4 — persistence: load_state(now) derives, storage columns + guarded migration, decay_frame deleted; 133/3."
git add src/retnovation/persistence.py src/retnovation/orchestration.py tests/test_persistence.py tests/test_dry_run.py tests/test_cs_dry_run.py tests/test_cli.py docs/DEVLOG.md
git commit -m "feat(persistence): derive strength on load, storage columns + migration, drop decay_frame"
```
Expected suite: 133 passed, 3 skipped.

---

### Task 5: persist the trap gallery

**Files:**
- Modify: `src/retnovation/persistence.py` (`_SCHEMA` add `trap_gallery` table; `load_state` reads it; `save_state` writes it)
- Test: `tests/test_persistence.py` (append)

**Interfaces:**
- Consumes: `load_state(now)`/`save_state` (Task 4); `TrapOccurrence` (`types.py`).
- Produces: `state.trap_gallery` (`dict[str, list[TrapOccurrence]]`) survives save/load. `save_state`
  rewrites the whole gallery (delete-then-insert, idempotent); `load_state` groups rows by trap code.

- [ ] **Step 1: Write the failing test** — append to `tests/test_persistence.py`:

```python
def test_trap_gallery_round_trips_and_is_idempotent(tmp_path):
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import LearnerState, TrapOccurrence

    t0 = datetime(2026, 6, 24, tzinfo=timezone.utc)
    s = Store(tmp_path / "tg.db")
    st = LearnerState()
    st.trap_gallery["scope_creep_to_please"] = [
        TrapOccurrence(experience_id="exp1", occurred_at=t0, detail="unchanged"),
        TrapOccurrence(experience_id="exp2", occurred_at=t0, detail="regressed"),
    ]
    s.save_state(st)
    s.save_state(st)  # second save must not duplicate
    loaded = Store(tmp_path / "tg.db").load_state(t0)
    occ = loaded.trap_gallery["scope_creep_to_please"]
    assert len(occ) == 2
    assert {o.experience_id for o in occ} == {"exp1", "exp2"}
    assert {o.detail for o in occ} == {"unchanged", "regressed"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py::test_trap_gallery_round_trips_and_is_idempotent -q`
Expected: FAIL — `trap_gallery` isn't persisted; `loaded.trap_gallery` is empty (`KeyError`).

- [ ] **Step 3: Add the table + read/write** — in `src/retnovation/persistence.py`:

Add to `_SCHEMA`:
```python
CREATE TABLE IF NOT EXISTS trap_gallery (
  trap_code TEXT NOT NULL, experience_id TEXT NOT NULL, occurred_at TEXT NOT NULL, detail TEXT NOT NULL);
```
Add `TrapOccurrence` to the `from .types import (...)` block at the top.

In `save_state`, before `self._db.commit()`, rewrite the gallery (delete-then-insert is idempotent):
```python
        self._db.execute("DELETE FROM trap_gallery")
        for trap_code, occurrences in state.trap_gallery.items():
            for o in occurrences:
                self._db.execute(
                    "INSERT INTO trap_gallery(trap_code,experience_id,occurred_at,detail) "
                    "VALUES(?,?,?,?)",
                    (trap_code, o.experience_id, o.occurred_at.isoformat(), o.detail),
                )
```

In `load_state`, before `return st`, read the gallery:
```python
        for r in self._db.execute("SELECT * FROM trap_gallery ORDER BY occurred_at, experience_id"):
            st.trap_gallery.setdefault(r["trap_code"], []).append(
                TrapOccurrence(
                    experience_id=r["experience_id"],
                    occurred_at=datetime.fromisoformat(r["occurred_at"]),
                    detail=r["detail"],
                )
            )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git status --short   # confirm no data/ staged
# DEVLOG: "P1 Task 5 — persist trap_gallery (delete+reinsert, idempotent); 134/3. Project 1 substrate complete."
git add src/retnovation/persistence.py tests/test_persistence.py docs/DEVLOG.md
git commit -m "feat(persistence): persist the trap gallery"
```
Expected suite: 134 passed, 3 skipped.

---

### Task 6: whole-branch adversarial review + finish (CONTROLLER — not an implementer subagent)

- [ ] **Step 1: Dispatch an independent opus whole-branch review** of `git diff main...HEAD` against the
  spec (§6, §7 retention/decay, §14) and these risks:
  - **Storage-keyed clock:** confirm `derive_due` and the decay step and the `frame_uncertainty`
    staleness-term all key to `_storage_tier(evidence_count, unprompted_breadth)`, never the displayed
    bucket — acyclic, no continuous-review pathology (a decayed strong-storage frame comes due no sooner
    than a thin frame).
  - **Served-path boundary:** `load_state` derives and `update_state` writes only storage; neither sets
    `strength` from outside the derivation. Direct construction remains only in tests.
  - **Shim / no behavior change:** at staleness 0 the derived buckets reproduce the old reachable cases;
    the scheduler is untouched; every prior test passes.
  - **`strong` reachable** (2 unprompted problems) and **`forming`** for closed-under-pressure (the
    `test_state` parity).
  - **Migration:** fresh DB and old (pre-column) DB both load; old rows → evidence 0 → derived weak.
  - **Confidentiality:** `git ls-files` confidential grep empty; `data/` untracked.
- [ ] **Step 2: Address findings** as additive fixes (own commits, same gate); re-run the full suite.
- [ ] **Step 3: Finish** — invoke `superpowers:finishing-a-development-branch` to merge
  `diagnostic-progression-substrate` into `main`. **Do not push** unless the user asks. Update the
  `retnovation-commitment-frame-gap` memory's progression thread to "substrate (Project 1) landed; policy
  + receipt surface (Projects 2–3) pending."

---

## Self-Review

**Spec coverage (Project 1, §10.1):**
- `FrameStrength` storage extension → Task 1. ✓
- `derive_strength`/`frame_uncertainty` on the storage-keyed clock (§6, §14.1) → Task 2. ✓
- Estimator writes evidence/breadth/last_seen anchored to the problem; `strong` reachable → Task 3. ✓
- Schema migration; `load_state(now)` derives; `decay_frame` deleted → Task 4. ✓
- Persisted `trap_gallery` → Task 5. ✓
- Legacy shim (no behavior change; existing tests green at staleness 0) → verified across Tasks 3–5 and in
  the Task 6 review. ✓
- Served-path boundary (§14.2) → enforced in Tasks 3–4 (only storage written; strength derived), checked
  in Task 6. ✓
- The two orchestration touches (`now`→`load_state`, `exp.ledger_ref`→`update_state`) are read-parameter
  threading, no mutation/sweep — consistent with §10.1's "no state mutation for decay." (The spec said
  "only orchestration touch is `now`"; the `ledger_ref` thread is the second, needed for breadth — noted.)

**Placeholder scan:** none — every step shows complete code and exact commands.

**Type consistency:** `derive_strength(evidence_count, unprompted_breadth, last_seen, now)`,
`derive_due(evidence_count, unprompted_breadth, last_seen)`, `frame_uncertainty(evidence_count, breadth,
unprompted_breadth, last_seen, now)`, `update_state(state, assessment, now, experience_id, ledger_ref)`,
`load_state(now)` are used identically across Tasks 2–5 and the tests. `unprompted_breadth`/`breadth`/
`evidence_count` field names match Task 1 throughout. `_INTERVAL_DAYS` keys are `Strength` members.
