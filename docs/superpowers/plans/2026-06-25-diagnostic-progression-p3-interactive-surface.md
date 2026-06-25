# Diagnostic Progression — Project 3 (Interactive Surface) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the diagnostic-progression engine interactive and live — the `open_ended` policy proposes from fresh state at session start, the learner accepts or redirects at the *problem* level (never seeing a frame), the full frame-level decomposition goes to an async author log, and an advisory core promote/demote pass surfaces crystallization candidates.

**Architecture:** Regime becomes an explicit `run_session` parameter. The `open_ended` path ignores the queue and proposes from live state via the value function (now returning the full ranking); `cs_technical` stays queue-driven and behaviorally byte-stable. Two audiences are split: a learner-facing problem-level menu (no `frame_code`) and an author-facing frame-level receipt written to `selection_log`. Promote/demote keys to the experience library's `ledger_ref` back-pointer (exogenous), logs advisory verdicts, and mutates nothing.

**Tech Stack:** Python 3, pydantic v2, SQLite (stdlib `sqlite3`), pytest, ruff, PyYAML.

**Spec:** `docs/superpowers/specs/2026-06-24-diagnostic-progression-design.md` §17 (and §6–§10). Read §17.1–§17.6 before starting.

## Global Constraints

- Tests run with `PYTHONPATH=src .venv/bin/pytest -q` (no pytest pythonpath is configured). Baseline is **150 passed / 3 skipped**; the 3 skips are `@pytest.mark.live`. **Every commit must leave the suite green.**
- Before every commit: `.venv/bin/ruff format .` then `.venv/bin/ruff check .` (both clean).
- Stage **explicit paths only** — never `git add -A`, never `-f` on a gitignored path (L-7). Reports/scratch under `.superpowers/sdd/` are never committed.
- **No `Co-Authored-By` trailer** on any commit (`.claude/CLAUDE.md`).
- Confidential-docs gate must stay empty: `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` → no output. `data/` stays untracked.
- **Doctrine (binding):** conclusion-agnostic — no surface, receipt, or predicate reads a conclusion (§3, L-4). The judgment loop and the `cs_technical` path are **byte-stable** (no behavior change). Doctrine thresholds live in `content/cadence/progression.yaml`, never hardcoded in `src/` (L-1).
- **L-8:** every schema change works on a fresh DB **and** migrates an old one; add a fresh-DB + old-DB regression test for each.
- **L-10:** the orchestration seam swap (Task 8) changes `run_session`, removes `schedule_next`/old `log_selection`, and rewrites **six** test/seed sites (orchestration, dry_run, cs_dry_run, cli, scheduler, persistence) — all in **one commit**, suite green.
- Core-path files (`scheduler`, `state`, `types`, `persistence`, `orchestration`, `policy`): an independent adversarial review runs before the branch is declared complete (`docs/lessons.md` "Before Declaring a Change Complete").

## File Structure

- `src/retnovation/types.py` — **modify**: add `Outcome`/`CoreKind` enums, `RankedCandidate`-shaped tuples used as `list[tuple[NextExperienceSpec, SelectionReceipt]]`, `Proposal` + `Selection` (dataclasses, mirroring `Work`), `CoreCandidate` + `CoreVerdict` (pydantic).
- `src/retnovation/policy.py` — **modify**: `select_next` returns the full ranked `list[tuple[spec, receipt]]`; cross-drive runner-up; `_retention_due` → public `retention_due`.
- `src/retnovation/crystallization.py` — **create**: `crystallization_candidates(...)` + the ledger-referenced predicate.
- `src/retnovation/surface.py` — **create**: pure formatters `format_receipt` (author/log) + `format_problem_menu` (learner; no `frame_code`).
- `src/retnovation/scheduler.py` — **modify**: add `propose_open_ended` + `schedule_cs`; (Task 8) remove `schedule_next`.
- `src/retnovation/orchestration.py` — **modify** (Task 8): `run_session` explicit-regime restructure; default `decide`/`decide_core` CLI callbacks.
- `src/retnovation/persistence.py` — **modify**: `selection_log` decision columns + `log_decision`; `core_decision_log` + `log_core_decision`.
- `src/retnovation/cli.py` — **modify** (Task 8): drop the dead `open_ended` queue seed; `main` passes the new defaults.
- `src/retnovation/content_loader.py` — **modify**: `load_progression` gains `theta_ledger_refs`.
- `content/cadence/progression.yaml` — **modify**: add `theta_ledger_refs`.
- Tests: `tests/test_types.py`, `tests/test_policy.py`, `tests/test_surface.py` (new), `tests/test_crystallization.py` (new), `tests/test_scheduler.py`, `tests/test_persistence.py`, `tests/test_orchestration.py`, `tests/test_cli.py`, `tests/test_dry_run.py`, `tests/test_cs_dry_run.py`.

---

### Task 1: New surface/decision types

**Files:**
- Modify: `src/retnovation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Consumes: existing `NextExperienceSpec`, `SelectionReceipt` (types.py).
- Produces:
  - `class Outcome(str, Enum): accepted = "accepted"; redirected = "redirected"`
  - `class CoreKind(str, Enum): promote = "promote"; demote = "demote"`
  - `@dataclass class Proposal: candidates: list[tuple[NextExperienceSpec, SelectionReceipt]]`; `@property top -> tuple[...]`; `problem_menu() -> list[tuple[NextExperienceSpec, SelectionReceipt]]` (first/best candidate per `ledger_ref`, rank order preserved).
  - `@dataclass class Selection: proposed_receipt: SelectionReceipt; chosen_spec: NextExperienceSpec; chosen_receipt: SelectionReceipt; outcome: Outcome`
  - `class CoreCandidate(BaseModel): kind: CoreKind; target: str; rationale: str`
  - `class CoreVerdict(BaseModel): candidate: CoreCandidate; outcome: str  # "accepted" | "rejected"`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_types.py`:

```python
def test_proposal_top_and_problem_menu_dedup():
    from retnovation.types import NextExperienceSpec, Proposal, Regime, SelectionReceipt
    from datetime import datetime, timezone

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)

    def mk(frame, ref, eid):
        spec = NextExperienceSpec(
            target_frames=[frame], ledger_ref=ref, regime=Regime.open_ended, experience_id=eid
        )
        rc = SelectionReceipt(
            frame=frame, problem=ref, experience_id=eid, drive="diagnose",
            scores={"V": 0.5}, runner_up_drive=None, margin=0.0, content_gaps=[], created_at=now,
        )
        return (spec, rc)

    p = Proposal(candidates=[mk("a", "veldra:p1", "e1"), mk("b", "veldra:p1", "e2"),
                             mk("c", "veldra:p2", "e3")])
    assert p.top[0].experience_id == "e1"
    menu = p.problem_menu()
    assert [s.ledger_ref for s, _ in menu] == ["veldra:p1", "veldra:p2"]  # deduped, rank order
    assert menu[0][0].experience_id == "e1"  # best candidate per problem kept


def test_core_candidate_and_verdict_roundtrip():
    from retnovation.types import CoreCandidate, CoreKind, CoreVerdict

    c = CoreCandidate(kind=CoreKind.demote, target="orphan_frame", rationale="no evidence, unreferenced")
    v = CoreVerdict(candidate=c, outcome="rejected")
    assert v.candidate.kind is CoreKind.demote and v.outcome == "rejected"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q`
Expected: FAIL with `ImportError`/`cannot import name 'Proposal'`.

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/types.py`, the file already imports `dataclass` (used by `Work`) and `Enum`. Add the enums near the other enums (after `class Strength`), and add the dataclasses/models near the end (after `SelectionReceipt`, before/after `Work`):

```python
class Outcome(str, Enum):
    accepted = "accepted"
    redirected = "redirected"


class CoreKind(str, Enum):
    promote = "promote"
    demote = "demote"
```

```python
class CoreCandidate(BaseModel):
    kind: CoreKind
    target: str
    rationale: str


class CoreVerdict(BaseModel):
    candidate: CoreCandidate
    outcome: str  # "accepted" | "rejected"


@dataclass
class Proposal:
    # ranked best-first; each entry is the (spec, receipt) the policy scored
    candidates: list[tuple[NextExperienceSpec, SelectionReceipt]]

    @property
    def top(self) -> tuple[NextExperienceSpec, SelectionReceipt]:
        return self.candidates[0]

    def problem_menu(self) -> list[tuple[NextExperienceSpec, SelectionReceipt]]:
        # learner-facing projection: best-ranked candidate per owned problem, rank order preserved
        seen: set[str] = set()
        out: list[tuple[NextExperienceSpec, SelectionReceipt]] = []
        for spec, receipt in self.candidates:
            if spec.ledger_ref in seen:
                continue
            seen.add(spec.ledger_ref)
            out.append((spec, receipt))
        return out


@dataclass
class Selection:
    proposed_receipt: SelectionReceipt
    chosen_spec: NextExperienceSpec
    chosen_receipt: SelectionReceipt
    outcome: Outcome
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/types.py tests/test_types.py
git commit -m "feat(types): P3 surface/decision types (Proposal, Selection, CoreCandidate)"
```

---

### Task 2: `theta_ledger_refs` config (doctrine-as-data)

**Files:**
- Modify: `content/cadence/progression.yaml`
- Modify: `src/retnovation/content_loader.py:110-119` (`load_progression`)
- Test: `tests/test_content_loader.py`

**Interfaces:**
- Produces: `load_progression(root)` dict gains key `"theta_ledger_refs": int` (default value `2`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_content_loader.py`:

```python
def test_load_progression_has_theta_ledger_refs():
    from retnovation.content_loader import load_progression

    cfg = load_progression()
    assert cfg["theta_ledger_refs"] == 2
    assert isinstance(cfg["theta_ledger_refs"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py::test_load_progression_has_theta_ledger_refs -q`
Expected: FAIL with `KeyError: 'theta_ledger_refs'`.

- [ ] **Step 3: Write minimal implementation**

Append to `content/cadence/progression.yaml`:

```yaml
theta_ledger_refs: 2   # promote candidate: a decayed frame referenced across >= this many active problems
```

In `src/retnovation/content_loader.py`, extend the `load_progression` return dict:

```python
    return {
        "wU": float(w["wU"]),
        "wR": float(w["wR"]),
        "wT": float(w["wT"]),
        "wL": float(w["wL"]),
        "theta_located": float(data["theta_located"]),
        "theta_ledger_refs": int(data["theta_ledger_refs"]),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q`
Expected: PASS. (Existing `select_next`/policy callers ignore the extra key — suite stays green.)

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add content/cadence/progression.yaml src/retnovation/content_loader.py tests/test_content_loader.py
git commit -m "feat(config): progression.yaml theta_ledger_refs (promote threshold)"
```

---

### Task 3: Persistence — decision columns + `core_decision_log`

**Files:**
- Modify: `src/retnovation/persistence.py` (`_SCHEMA`, `__init__` migration, add `log_decision` + `log_core_decision`)
- Test: `tests/test_persistence.py`

**Interfaces:**
- Consumes: `Selection`, `CoreVerdict` (Task 1).
- Produces:
  - `selection_log` gains `outcome TEXT, chosen_frame TEXT, chosen_problem TEXT, chosen_experience_id TEXT` (PRAGMA-guarded `ADD COLUMN`).
  - `Store.log_decision(self, selection: Selection) -> None` — writes proposed-receipt columns (from `selection.proposed_receipt`) + `outcome` + `chosen_*` (from `selection.chosen_receipt`).
  - `core_decision_log(created_at TEXT, kind TEXT, target TEXT, rationale TEXT, outcome TEXT)` + `Store.log_core_decision(self, verdict: CoreVerdict, now: datetime) -> None`.
- The existing `log_selection(receipt)` stays until Task 8 (still used by current `run_session`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_persistence.py`:

```python
def test_selection_log_decision_columns_fresh_and_old_db(tmp_path):
    import sqlite3
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import (
        NextExperienceSpec, Outcome, Regime, SelectionReceipt, Selection,
    )

    # old DB: selection_log WITHOUT the new columns
    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.executescript(
        "CREATE TABLE selection_log (created_at TEXT NOT NULL, frame TEXT NOT NULL, "
        "problem TEXT NOT NULL, experience_id TEXT NOT NULL, drive TEXT NOT NULL, "
        "scores_json TEXT NOT NULL, runner_up_drive TEXT, margin REAL NOT NULL, "
        "content_gaps_json TEXT NOT NULL);"
    )
    con.commit()
    con.close()

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    for path in (old, tmp_path / "fresh.db"):
        store = Store(path)  # migration must not raise
        cols = {r["name"] for r in store._db.execute("PRAGMA table_info(selection_log)")}
        assert {"outcome", "chosen_frame", "chosen_problem", "chosen_experience_id"} <= cols

        def rc(frame, ref, eid):
            return SelectionReceipt(
                frame=frame, problem=ref, experience_id=eid, drive="deploy",
                scores={"V": 0.7}, runner_up_drive="diagnose", margin=0.2,
                content_gaps=[], created_at=now,
            )

        sel = Selection(
            proposed_receipt=rc("lead", "veldra:p1", "e1"),
            chosen_spec=NextExperienceSpec(
                target_frames=["lead"], ledger_ref="veldra:p2",
                regime=Regime.open_ended, experience_id="e2"),
            chosen_receipt=rc("lead", "veldra:p2", "e2"),
            outcome=Outcome.redirected,
        )
        store.log_decision(sel)
        row = store._db.execute("SELECT * FROM selection_log").fetchone()
        assert row["frame"] == "lead" and row["experience_id"] == "e1"  # proposed
        assert row["outcome"] == "redirected"
        assert row["chosen_problem"] == "veldra:p2" and row["chosen_experience_id"] == "e2"
        store.close()


def test_core_decision_log_roundtrip(tmp_path):
    from datetime import datetime, timezone
    from retnovation.persistence import Store
    from retnovation.types import CoreCandidate, CoreKind, CoreVerdict

    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    store = Store(tmp_path / "c.db")
    v = CoreVerdict(
        candidate=CoreCandidate(kind=CoreKind.promote, target="protect", rationale="decayed, broad"),
        outcome="accepted",
    )
    store.log_core_decision(v, now)
    row = store._db.execute("SELECT * FROM core_decision_log").fetchone()
    assert row["kind"] == "promote" and row["target"] == "protect" and row["outcome"] == "accepted"
    store.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py -q`
Expected: FAIL (`log_decision`/`log_core_decision` missing; new columns absent).

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/persistence.py` `_SCHEMA`, add the `core_decision_log` table (the `selection_log` `CREATE` keeps the original 9 columns — the new ones are added by guarded `ALTER`):

```python
CREATE TABLE IF NOT EXISTS core_decision_log (
  created_at TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL,
  rationale TEXT NOT NULL, outcome TEXT NOT NULL);
```

In `Store.__init__`, after the `queue` migration block, add the `selection_log` migration:

```python
        scols = {r["name"] for r in self._db.execute("PRAGMA table_info(selection_log)")}
        for col in ("outcome", "chosen_frame", "chosen_problem", "chosen_experience_id"):
            if col not in scols:
                self._db.execute(f"ALTER TABLE selection_log ADD COLUMN {col} TEXT")
        self._db.commit()
```

Add the two writer methods (near `log_selection`):

```python
    def log_decision(self, selection: Selection) -> None:
        p = selection.proposed_receipt
        c = selection.chosen_receipt
        self._db.execute(
            "INSERT INTO selection_log(created_at,frame,problem,experience_id,drive,scores_json,"
            "runner_up_drive,margin,content_gaps_json,outcome,chosen_frame,chosen_problem,"
            "chosen_experience_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                p.created_at.isoformat(), p.frame, p.problem, p.experience_id, p.drive,
                json.dumps(p.scores), p.runner_up_drive, p.margin, json.dumps(p.content_gaps),
                selection.outcome.value, c.frame, c.problem, c.experience_id,
            ),
        )
        self._db.commit()

    def log_core_decision(self, verdict: CoreVerdict, now: datetime) -> None:
        self._db.execute(
            "INSERT INTO core_decision_log(created_at,kind,target,rationale,outcome) "
            "VALUES(?,?,?,?,?)",
            (
                now.isoformat(), verdict.candidate.kind.value, verdict.candidate.target,
                verdict.candidate.rationale, verdict.outcome,
            ),
        )
        self._db.commit()
```

Add `CoreVerdict`, `Selection` to the `from .types import (...)` block at the top of `persistence.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_persistence.py -q`
Expected: PASS. Then full suite: `PYTHONPATH=src .venv/bin/pytest -q` → still green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/persistence.py tests/test_persistence.py
git commit -m "feat(persistence): selection_log decision columns + core_decision_log (guarded migrations)"
```

---

### Task 4: Policy — `select_next` returns the full ranking; cross-drive runner-up; public `retention_due`

**Files:**
- Modify: `src/retnovation/policy.py`
- Modify: `src/retnovation/scheduler.py:32-33` (open_ended branch: take `[0]` so its tuple contract is unchanged)
- Test: `tests/test_policy.py`

**Interfaces:**
- Produces:
  - `select_next(state, experiences, config, now) -> list[tuple[NextExperienceSpec, SelectionReceipt]]` (best-first; raises `ValueError` if no candidates). `[0]` is the winner.
  - `retention_due(state, code, now) -> float` (public; the old private `_retention_due`).
  - Receipt `runner_up_drive`/`margin` are now **cross-candidate, different-drive**: for candidate `c`, runner-up = the highest-`V` candidate whose dominant drive ≠ `c`'s; `margin = V(c) − V(runner-up)`; `None`/`0.0` if no different-drive candidate exists (cold start).
- Consumes: `state.frame_uncertainty`, `state.frame_interval_days` (state.py, unchanged).

- [ ] **Step 1: Write the failing tests**

Replace the existing `select_next` call-sites in `tests/test_policy.py` with the list form, and add the new behavior tests. Edit the existing tests to unpack `[0]`:

```python
def test_cold_start_serves_lowest_load_experience_first():
    exps = [_exp("cap", "veldra:p1", ["a", "b", "c"]), _exp("iso", "veldra:p2", ["z"])]
    spec, receipt = select_next(LearnerState(), exps, CFG, NOW)[0]
    assert receipt.experience_id == "iso"
    assert (spec.experience_id == "iso" and spec.ledger_ref == "veldra:p2"
            and spec.target_frames == ["z"])


def test_transfer_fires_for_forming_frame_on_a_new_problem():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1")
    exps = [_exp("e1", "veldra:p1", ["lead", "other1"]), _exp("e2", "veldra:p2", ["lead", "other2"])]
    spec, receipt = select_next(st, exps, CFG, NOW)[0]
    assert receipt.frame == "lead" and receipt.problem == "veldra:p2" and receipt.drive == "deploy"


def test_retention_fires_only_when_overdue_on_the_storage_clock():
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1", now=NOW - timedelta(days=10))
    spec, receipt = select_next(st, [_exp("e1", "veldra:p1", ["lead"])], CFG, NOW)[0]
    assert receipt.scores["retention"] > 0.0


def test_content_gap_logged_for_frame_with_no_isolated_home():
    spec, receipt = select_next(LearnerState(), [_exp("e1", "veldra:p1", ["a", "b"])], CFG, NOW)[0]
    assert "a" in receipt.content_gaps and "b" in receipt.content_gaps


def test_two_experiences_sharing_a_pair_pick_lower_load():
    e_iso = _exp("e_iso", "veldra:p1", ["lead"])
    e_cap = _exp("e_cap", "veldra:p1", ["lead", "x", "y"])
    ranked = select_next(LearnerState(), [e_cap, e_iso], CFG, NOW)
    assert ranked[0][1].experience_id == "e_iso"


def test_select_next_returns_full_ranking():
    exps = [_exp("cap", "veldra:p1", ["a", "b", "c"]), _exp("iso", "veldra:p2", ["z"])]
    ranked = select_next(LearnerState(), exps, CFG, NOW)
    assert len(ranked) == 4  # (a,cap),(b,cap),(c,cap),(z,iso)
    assert ranked[0][1].experience_id == "iso"  # best first


def test_runner_up_is_best_candidate_of_a_different_drive():
    # 'lead' forming on p1 -> deploy candidate on p2; a fresh frame -> diagnose candidate.
    st = LearnerState()
    st.frames["lead"] = _forming("veldra:p1")
    exps = [_exp("e2", "veldra:p2", ["lead"]), _exp("e3", "veldra:p3", ["fresh"])]
    spec, receipt = select_next(st, exps, CFG, NOW)[0]
    assert receipt.drive == "deploy"
    assert receipt.runner_up_drive == "diagnose"  # a DIFFERENT drive, not 'deploy' again
    assert receipt.margin > 0.0


def test_runner_up_none_at_uniform_cold_start():
    # all candidates are 'diagnose' (cold start) -> no different-drive runner-up
    exps = [_exp("a", "veldra:p1", ["x"]), _exp("b", "veldra:p2", ["y"])]
    spec, receipt = select_next(LearnerState(), exps, CFG, NOW)[0]
    assert receipt.drive == "diagnose"
    assert receipt.runner_up_drive is None and receipt.margin == 0.0


def test_select_next_raises_on_empty_experiences():
    import pytest

    with pytest.raises(ValueError):
        select_next(LearnerState(), [], CFG, NOW)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_policy.py -q`
Expected: FAIL (`select_next(...)[0]` — current `select_next` returns a tuple, not a list, so subscripting `[0]` yields the spec, not a `(spec, receipt)` pair → unpack error; and the new runner-up tests fail).

- [ ] **Step 3: Write minimal implementation**

Rewrite `src/retnovation/policy.py`. Rename `_retention_due` → `retention_due` (public; update the internal call in the terms dict), and replace `select_next` with a ranked version that computes the cross-drive runner-up after scoring all candidates:

```python
def retention_due(state: LearnerState, code: str, now: datetime) -> float:
    fs = state.frames.get(code)
    if fs is None or fs.evidence_count == 0:
        return 0.0
    interval = frame_interval_days(fs.evidence_count, fs.unprompted_breadth)
    staleness = max(0.0, (now - fs.last_seen).total_seconds() / 86400.0)
    return max(0.0, min(1.0, (staleness - interval) / interval))
```

```python
def select_next(
    state: LearnerState, experiences: list[Experience], config: dict, now: datetime
) -> list[tuple[NextExperienceSpec, SelectionReceipt]]:
    wU, wR, wT, wL = config["wU"], config["wR"], config["wT"], config["wL"]
    theta = config["theta_located"]
    gaps = _content_gaps(state, experiences, now, theta)

    scored = []  # each: dict with sort_key, frame, exp, drive, V, terms, penalty
    for e in experiences:
        penalty = max(
            (_uncertainty(state, g.frame_code, now) for g in e.rubric.frames), default=0.0
        )
        load = len(e.rubric.frames)
        for fr in e.rubric.frames:
            f = fr.frame_code
            terms = {
                "diagnose": wU * _uncertainty(state, f, now),
                "consolidate": wR * retention_due(state, f, now),
                "deploy": wT * _transfer(state, f, e.ledger_ref),
            }
            V = terms["diagnose"] + terms["consolidate"] + terms["deploy"] - wL * penalty
            drive = max(terms.items(), key=lambda kv: kv[1])[0]
            scored.append(
                {
                    "sort_key": (-V, load, f, e.ledger_ref, e.experience_id),
                    "frame": f, "exp": e, "drive": drive, "V": V,
                    "terms": terms, "penalty": penalty,
                }
            )

    if not scored:
        raise ValueError("no (frame, experience) candidates to score")
    scored.sort(key=lambda c: c["sort_key"])

    ranked: list[tuple[NextExperienceSpec, SelectionReceipt]] = []
    for c in scored:
        others = [o for o in scored if o["drive"] != c["drive"]]
        if others:
            best_other = max(others, key=lambda o: o["V"])
            runner_up_drive = best_other["drive"]
            margin = c["V"] - best_other["V"]
        else:
            runner_up_drive, margin = None, 0.0
        e, f, terms = c["exp"], c["frame"], c["terms"]
        spec = NextExperienceSpec(
            target_frames=[f], ledger_ref=e.ledger_ref,
            regime=Regime.open_ended, experience_id=e.experience_id,
        )
        receipt = SelectionReceipt(
            frame=f, problem=e.ledger_ref, experience_id=e.experience_id, drive=c["drive"],
            scores={
                "uncertainty": terms["diagnose"] / wU if wU else 0.0,
                "retention": terms["consolidate"] / wR if wR else 0.0,
                "transfer": terms["deploy"] / wT if wT else 0.0,
                "penalty": c["penalty"], "V": c["V"],
            },
            runner_up_drive=runner_up_drive, margin=margin,
            content_gaps=gaps, created_at=now,
        )
        ranked.append((spec, receipt))
    return ranked
```

In `src/retnovation/scheduler.py`, the `open_ended` branch must keep returning a single `(spec, receipt)` tuple (its callers don't change until Task 8). Change line 33:

```python
    experiences = [e for e in load_library(root) if e.regime is Regime.open_ended]
    return select_next(state, experiences, load_progression(root), now)[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_policy.py tests/test_scheduler.py -q`
Expected: PASS (test_scheduler unchanged — `schedule_next` still returns a tuple). Then full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/policy.py src/retnovation/scheduler.py tests/test_policy.py
git commit -m "feat(policy): select_next returns full ranking; cross-drive runner-up; public retention_due"
```

---

### Task 5: Surface formatters (learner vs author)

**Files:**
- Create: `src/retnovation/surface.py`
- Test: `tests/test_surface.py`

**Interfaces:**
- Consumes: `Proposal` (Task 1), `SelectionReceipt`.
- Produces:
  - `format_receipt(receipt: SelectionReceipt) -> str` — author/log-facing; names drive + cross-drive runner-up + margin; reads sensibly at margin ≈ 0 / `None` runner-up; appends content gaps.
  - `format_problem_menu(proposal: Proposal) -> str` — learner-facing; numbered owned-problem rows by `ledger_ref`; **never contains a `frame_code` or a drive name**.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_surface.py`:

```python
from datetime import datetime, timezone

from retnovation.surface import format_problem_menu, format_receipt
from retnovation.types import NextExperienceSpec, Proposal, Regime, SelectionReceipt

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)


def _rc(frame, ref, eid, drive, ru, margin, gaps=None):
    return SelectionReceipt(
        frame=frame, problem=ref, experience_id=eid, drive=drive,
        scores={"V": 0.7}, runner_up_drive=ru, margin=margin,
        content_gaps=gaps or [], created_at=NOW,
    )


def test_format_receipt_names_drive_runner_up_and_margin():
    s = format_receipt(_rc("lead", "veldra:lic", "e1", "deploy", "consolidate", 0.12))
    assert "DEPLOY" in s and "lead" in s and "veldra:lic" in s
    assert "0.12" in s and "CONSOLIDATE" in s


def test_format_receipt_reads_sensibly_with_no_runner_up():
    s = format_receipt(_rc("a", "veldra:p1", "e1", "diagnose", None, 0.0))
    assert "DEPLOY" not in s and "over" not in s  # no false "decisive over X"
    assert "DIAGNOSE" in s


def test_format_receipt_lists_content_gaps():
    s = format_receipt(_rc("a", "veldra:p1", "e1", "diagnose", None, 0.0, gaps=["a", "b"]))
    assert "a" in s and "b" in s and "gap" in s.lower()


def test_problem_menu_never_names_a_frame():
    def mk(frame, ref, eid):
        spec = NextExperienceSpec(
            target_frames=[frame], ledger_ref=ref, regime=Regime.open_ended, experience_id=eid)
        return (spec, _rc(frame, ref, eid, "deploy", "diagnose", 0.2))

    p = Proposal(candidates=[mk("lead_with_what_you_refuse_to_do", "veldra:lic", "e1"),
                             mk("protect_the_core_lane", "veldra:price", "e2")])
    menu = format_problem_menu(p)
    assert "veldra:lic" in menu and "veldra:price" in menu
    # the gating guard: no frame_code, no drive, leaks to the learner
    for leak in ("lead_with_what_you_refuse_to_do", "protect_the_core_lane",
                 "deploy", "diagnose", "DEPLOY"):
        assert leak not in menu
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_surface.py -q`
Expected: FAIL with `ModuleNotFoundError: retnovation.surface`.

- [ ] **Step 3: Write minimal implementation**

Create `src/retnovation/surface.py`:

```python
from __future__ import annotations

from .types import Proposal, SelectionReceipt

_DRIVE_LABEL = {"diagnose": "DIAGNOSE", "consolidate": "CONSOLIDATE", "deploy": "DEPLOY"}


def _label(drive: str) -> str:
    return _DRIVE_LABEL.get(drive, drive.upper())


def format_receipt(receipt: SelectionReceipt) -> str:
    """Author/log-facing: the full frame-level decomposition. NEVER shown to the learner
    pre-experience (it names the frame — §17.1)."""
    head = f"{_label(receipt.drive)} -> {receipt.frame} on {receipt.problem}"
    if receipt.runner_up_drive is not None and receipt.margin > 1e-9:
        head += f" (margin {receipt.margin:.2f} over {_label(receipt.runner_up_drive)})"
    else:
        head += " (uncontested / cold start)"
    if receipt.content_gaps:
        head += f" [content gaps: {', '.join(receipt.content_gaps)}]"
    return head


def format_problem_menu(proposal: Proposal) -> str:
    """Learner-facing: owned problems only. Must NOT name a frame or a drive (§17.1) — the move
    the learner has to work out stays withheld; the experience prompt is the only context shown."""
    lines = ["Next up:"]
    for i, (spec, _receipt) in enumerate(proposal.problem_menu(), start=1):
        lines.append(f"  {i}. {spec.ledger_ref}")
    lines.append("Press Enter to start #1, or type a number to switch problem.")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_surface.py -q`
Expected: PASS. Full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/surface.py tests/test_surface.py
git commit -m "feat(surface): learner problem-menu (no frame_code) + author receipt formatters"
```

---

### Task 6: Crystallization — advisory promote/demote candidates

**Files:**
- Create: `src/retnovation/crystallization.py`
- Test: `tests/test_crystallization.py`

**Interfaces:**
- Consumes: `policy.retention_due` (Task 4), `Experience`/`LedgerEntry`/`Core`/`LearnerState`, `CoreCandidate`/`CoreKind` (Task 1), `config["theta_ledger_refs"]` (Task 2).
- Produces: `crystallization_candidates(state, core, ledger, experiences, now, config) -> list[CoreCandidate]`.
- Predicate **ledger-referenced(f)** ≜ some `e` in `experiences` with `e.ledger_ref ∈ {entry.id for entry in ledger}` has `f ∈ e.rubric.frames`. Uses `Experience.ledger_ref` (populated), **not** `LedgerEntry.links_to_experiences` (empty in prod — L-9), **not** `breadth` (endogenous).
  - **Demote:** core `process_frame` with `evidence_count == 0` (or absent from `state.frames`) **and not** ledger-referenced.
  - **Promote:** a `state.frames` frame with `retention_due(...) > 0` **and** referenced across `≥ theta_ledger_refs` distinct active problems.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_crystallization.py`:

```python
from datetime import datetime, timedelta, timezone

from retnovation.crystallization import crystallization_candidates
from retnovation.types import (
    Core, CoreKind, Experience, Frame, FrameStrength, LearnerState, LedgerEntry, Mode,
    Regime, Rubric, Strength,
)

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)
CFG = {"theta_ledger_refs": 2}


def _exp(eid, ref, frames):
    return Experience(
        experience_id=eid, prompt="p", ledger_ref=ref, regime=Regime.open_ended,
        rubric=Rubric(frames=[Frame(frame_code=c, frame_detail="d") for c in frames],
                      traps=[], mode=Mode.genuinely_open),
    )


def _core(frames):
    return Core(process_frames=frames, declarative_seed=[], content_core=None)


def test_demote_orphan_core_frame():
    # 'ghost' is a core frame, zero evidence, in NO active-problem experience -> demote
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x")]
    exps = [_exp("e1", "veldra:p1", ["lead"])]
    cands = crystallization_candidates(core=_core(["lead", "ghost"]), state=LearnerState(),
                                       ledger=ledger, experiences=exps, now=NOW, config=CFG)
    demotes = [c for c in cands if c.kind is CoreKind.demote]
    assert [c.target for c in demotes] == ["ghost"]  # 'lead' is referenced -> not demoted


def test_no_demote_when_frame_referenced_even_if_unseen():
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x")]
    exps = [_exp("e1", "veldra:p1", ["lead"])]  # 'lead' referenced by an active problem
    cands = crystallization_candidates(core=_core(["lead"]), state=LearnerState(),
                                       ledger=ledger, experiences=exps, now=NOW, config=CFG)
    assert not [c for c in cands if c.kind is CoreKind.demote]


def test_promote_decayed_frame_referenced_across_problems():
    st = LearnerState()
    # forming (interval 7d), last seen 10d ago -> retention_due > 0 (decayed)
    st.frames["lead"] = FrameStrength(
        strength=Strength.forming, last_seen=NOW - timedelta(days=10), due=NOW,
        last_evidence="x", evidence_count=1, breadth={"veldra:p1"}, unprompted_breadth=set())
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x"),
              LedgerEntry(id="veldra:p2", owned_problem="y")]
    exps = [_exp("e1", "veldra:p1", ["lead"]), _exp("e2", "veldra:p2", ["lead"])]  # 2 problems
    cands = crystallization_candidates(core=_core(["lead"]), state=st, ledger=ledger,
                                       experiences=exps, now=NOW, config=CFG)
    promotes = [c for c in cands if c.kind is CoreKind.promote]
    assert [c.target for c in promotes] == ["lead"]


def test_no_promote_when_not_decayed():
    st = LearnerState()
    st.frames["lead"] = FrameStrength(
        strength=Strength.forming, last_seen=NOW, due=NOW, last_evidence="x",
        evidence_count=1, breadth={"veldra:p1"}, unprompted_breadth=set())
    ledger = [LedgerEntry(id="veldra:p1", owned_problem="x"),
              LedgerEntry(id="veldra:p2", owned_problem="y")]
    exps = [_exp("e1", "veldra:p1", ["lead"]), _exp("e2", "veldra:p2", ["lead"])]
    cands = crystallization_candidates(core=_core(["lead"]), state=st, ledger=ledger,
                                       experiences=exps, now=NOW, config=CFG)
    assert not [c for c in cands if c.kind is CoreKind.promote]


def test_empty_when_nothing_qualifies():
    cands = crystallization_candidates(core=_core([]), state=LearnerState(), ledger=[],
                                       experiences=[], now=NOW, config=CFG)
    assert cands == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_crystallization.py -q`
Expected: FAIL with `ModuleNotFoundError: retnovation.crystallization`.

- [ ] **Step 3: Write minimal implementation**

Create `src/retnovation/crystallization.py`:

```python
from __future__ import annotations

from datetime import datetime

from .policy import retention_due
from .types import CoreCandidate, CoreKind, Core, Experience, LearnerState, LedgerEntry


def _active_problem_frames(
    ledger: list[LedgerEntry], experiences: list[Experience]
) -> dict[str, set[str]]:
    """frame_code -> set of active owned problems whose experiences carry it (exogenous signal:
    Experience.ledger_ref into the ledger, NOT LedgerEntry.links_to_experiences which is empty in
    production, NOT breadth which is endogenous)."""
    active = {entry.id for entry in ledger}
    out: dict[str, set[str]] = {}
    for e in experiences:
        if e.ledger_ref not in active or e.rubric is None:
            continue
        for fr in e.rubric.frames:
            out.setdefault(fr.frame_code, set()).add(e.ledger_ref)
    return out


def crystallization_candidates(
    state: LearnerState,
    core: Core,
    ledger: list[LedgerEntry],
    experiences: list[Experience],
    now: datetime,
    config: dict,
) -> list[CoreCandidate]:
    theta = config["theta_ledger_refs"]
    refs = _active_problem_frames(ledger, experiences)
    out: list[CoreCandidate] = []

    # Demote: core process frame, no evidence, not referenced by any active problem.
    for f in core.process_frames:
        fs = state.frames.get(f)
        untouched = fs is None or fs.evidence_count == 0
        if untouched and f not in refs:
            out.append(
                CoreCandidate(
                    kind=CoreKind.demote, target=f,
                    rationale="no evidence and unreferenced by the active ledger",
                )
            )

    # Promote: a frame that has decayed AND keeps surfacing across active problems.
    for f, fs in state.frames.items():
        if retention_due(state, f, now) > 0.0 and len(refs.get(f, set())) >= theta:
            out.append(
                CoreCandidate(
                    kind=CoreKind.promote, target=f,
                    rationale=f"decayed and referenced across {len(refs[f])} active problems",
                )
            )
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_crystallization.py -q`
Expected: PASS. Full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/crystallization.py tests/test_crystallization.py
git commit -m "feat(crystallization): advisory promote/demote candidates keyed to the active ledger"
```

---

### Task 7: Scheduler — `propose_open_ended` + `schedule_cs` (additive)

**Files:**
- Modify: `src/retnovation/scheduler.py` (add two functions; leave `schedule_next` in place for now)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces:
  - `propose_open_ended(state, experiences, config, now) -> Proposal` — `Proposal(candidates=select_next(state, experiences, config, now))`.
  - `schedule_cs(state, ledger, now) -> NextExperienceSpec` — the existing cs SM2-lite logic (the current `schedule_next` `cs_technical` branch), returning the spec only (cs never produces a receipt).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py`:

```python
def test_propose_open_ended_returns_ranked_proposal():
    from retnovation.scheduler import propose_open_ended
    from retnovation.content_loader import load_library, load_progression

    exps = [e for e in load_library() if e.regime.value == "open_ended"]
    prop = propose_open_ended(LearnerState(), exps, load_progression(), _now())
    assert len(prop.candidates) >= 1
    assert prop.top[0].regime is Regime.open_ended
    assert prop.top[0].experience_id == prop.top[1].experience_id


def test_schedule_cs_targets_due_concepts_first():
    from datetime import timedelta
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state({"overdue": (now - timedelta(days=1), 1), "future": (now + timedelta(days=5), 4)})
    spec = schedule_cs(st, [], now)
    assert spec.target_frames == ["overdue"] and spec.regime is Regime.cs_technical
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_scheduler.py -q`
Expected: FAIL (`cannot import name 'propose_open_ended'` / `'schedule_cs'`).

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/scheduler.py`, add imports (`Proposal`) and the two functions. Extract `schedule_cs` from the existing `cs_technical` branch:

```python
def schedule_cs(state: LearnerState, ledger: list[LedgerEntry], now: datetime) -> NextExperienceSpec:
    ledger_ref = ledger[0].id if ledger else ""
    items = state.declarative_seed
    due = sorted((c for c, si in items.items() if si.due <= now), key=lambda c: (items[c].due, c))
    if due:
        targets = due
    elif items:
        targets = [min(items.items(), key=lambda kv: (kv[1].due, kv[0]))[0]]
    else:
        targets = []
    return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=Regime.cs_technical)


def propose_open_ended(
    state: LearnerState, experiences: list[Experience], config: dict, now: datetime
) -> Proposal:
    return Proposal(candidates=select_next(state, experiences, config, now))
```

Add `Experience`, `Proposal` to the `from .types import (...)` block in `scheduler.py`. (`schedule_next` stays untouched in this task — Task 8 removes it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_scheduler.py -q`
Expected: PASS. Full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/scheduler.py tests/test_scheduler.py
git commit -m "feat(scheduler): propose_open_ended (ranked Proposal) + schedule_cs"
```

---

### Task 8: Orchestration integration (the L-10 atomic seam swap)

**Files:**
- Modify: `src/retnovation/orchestration.py` (rewrite `run_session`; add `decide_cli`/`decide_core_cli`)
- Modify: `src/retnovation/scheduler.py` (remove `schedule_next` + deterministic import cleanup)
- Modify: `src/retnovation/persistence.py` (remove old `log_selection(receipt)`; drop the now-unused `SelectionReceipt` import)
- Modify: `src/retnovation/cli.py` (`build_store` drops the `open_ended` seed; `main` passes `regime=Regime.open_ended` explicitly)
- Modify (rewrite affected assertions): `tests/test_orchestration.py`, `tests/test_dry_run.py`, `tests/test_cs_dry_run.py`, `tests/test_cli.py`, `tests/test_scheduler.py`, **`tests/test_persistence.py`** (drop `test_log_selection_round_trips`)
- **One commit, suite green** (L-10 — six test/seed sites).

> **Why steering matters (verified):** removing the queue seed means the `open_ended` path proposes from
> live **cold-start** state. Over the real library the deterministic tie-break ranks experience
> `decision_under_stakes` / frame `choose_the_failure_default_deliberately` **first** — which the test
> `FakeModel`s do NOT script (→ `KeyError`). So every rewritten `open_ended` `run_session` test must
> **steer selection to `license_continuity`** via a `decide` fixture that redirects to the
> `veldra:license_fork_risk` problem (and this doubles as the redirect-path test). Do not rely on an
> `accept` fixture landing on a scripted experience.

**Interfaces:**
- Produces:
  - `decide_cli(proposal: Proposal) -> Selection` — prints `format_problem_menu`, reads input; blank/`1` = accept `proposal.top`; a valid number `n` = redirect to `problem_menu()[n-1]`'s candidate; invalid input re-prompts.
  - `decide_core_cli(candidates: list[CoreCandidate]) -> list[CoreVerdict]` — prints each candidate (author-facing — frame names allowed here), reads `y`/`n`, returns verdicts.
  - `run_session(store, core, model, now, *, regime=Regime.open_ended, present=present_and_collect, decide=decide_cli, decide_core=decide_core_cli) -> tuple[LearnerState, Assessment | CheckableAssessment]`.
- Consumes: `propose_open_ended`, `schedule_cs` (Task 7); `crystallization_candidates` (Task 6); `Store.log_decision`/`log_core_decision` (Task 3); `format_problem_menu` (Task 5).

- [ ] **Step 1: Rewrite the orchestration tests (the spec's new behavior)**

**`tests/test_orchestration.py`** — add a module-level steering fixture, rewrite both `run_session` tests to use it (drop the `queue_push` of an open_ended spec and the "a fresh next was queued" assertion), and add a `decide_cli` unit test for the accept/redirect branches:

```python
def _to_license(proposal):
    # Steer to the scripted license_continuity problem (cold-start top is decision_under_stakes,
    # whose frames the FakeModel does not script). Doubles as the redirect-path test.
    from retnovation.types import Outcome, Selection

    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.problem_menu():
        if spec.ledger_ref == "veldra:license_fork_risk":
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(proposed_receipt=top_receipt, chosen_spec=spec,
                             chosen_receipt=receipt, outcome=outcome)
    raise AssertionError("license_fork_risk not in the proposal")


def test_run_session_closes_one_cycle(tmp_path):
    store = Store(tmp_path / "t.db")
    for ref in ("veldra:license_fork_risk", "veldra:concentrated_market_pricing_power",
                "veldra:first_customer_proof_loop"):
        store.add_ledger_entry(LedgerEntry(id=ref, owned_problem="..."))
        store.upsert_corpus(CorpusEntry(ledger_ref=ref, domain="founder_ceo", why_owned="stakes",
                                        unlabeled="unlabeled", provenance="synthetic-test",
                                        corpus_pointers=[]))
    core = derive_core(aim())

    def fixture(exp):
        return Work(opening="my reasoning", respond=lambda push: "reply")  # noqa: E731

    state, assessment = run_session(store, core, _fake_model(), _now(),
                                    present=fixture, decide=_to_license, decide_core=lambda c: [])
    assert assessment.trajectory and state.frames
    assert any("license_continuity" in fs.last_evidence for fs in state.frames.values())
    rows = list(store._db.execute("SELECT * FROM selection_log"))
    assert len(rows) == 1 and rows[0]["chosen_problem"] == "veldra:license_fork_risk"
    assert store.queue_len() == 0  # open_ended path does not queue


def test_run_session_logs_selection_receipt(tmp_path):
    store = Store(tmp_path / "t2.db")
    for ref in ("veldra:license_fork_risk", "veldra:concentrated_market_pricing_power",
                "veldra:first_customer_proof_loop"):
        store.add_ledger_entry(LedgerEntry(id=ref, owned_problem="..."))
        store.upsert_corpus(CorpusEntry(ledger_ref=ref, domain="founder_ceo", why_owned="stakes",
                                        unlabeled="unlabeled", provenance="synthetic-test",
                                        corpus_pointers=[]))
    core = derive_core(aim())

    def fixture(exp):
        return Work(opening="my reasoning", respond=lambda push: "reply")  # noqa: E731

    run_session(store, core, _fake_model(), _now(),
                present=fixture, decide=_to_license, decide_core=lambda c: [])
    rows = list(store._db.execute("SELECT * FROM selection_log"))
    assert len(rows) == 1
    assert rows[0]["chosen_experience_id"] == "license_continuity"
    assert rows[0]["outcome"] in ("accepted", "redirected")


def test_decide_cli_accept_and_redirect(monkeypatch):
    from retnovation.orchestration import decide_cli
    from retnovation.types import (
        NextExperienceSpec, Outcome, Proposal, Regime, SelectionReceipt,
    )

    now = _now()

    def cand(ref, eid):
        spec = NextExperienceSpec(target_frames=["f"], ledger_ref=ref,
                                  regime=Regime.open_ended, experience_id=eid)
        rc = SelectionReceipt(frame="f", problem=ref, experience_id=eid, drive="diagnose",
                              scores={"V": 0.5}, runner_up_drive=None, margin=0.0,
                              content_gaps=[], created_at=now)
        return (spec, rc)

    prop = Proposal(candidates=[cand("veldra:p1", "e1"), cand("veldra:p2", "e2")])

    monkeypatch.setattr("builtins.input", lambda *_: "")  # accept
    sel = decide_cli(prop)
    assert sel.outcome is Outcome.accepted and sel.chosen_spec.experience_id == "e1"

    monkeypatch.setattr("builtins.input", lambda *_: "2")  # redirect to problem 2
    sel2 = decide_cli(prop)
    assert sel2.outcome is Outcome.redirected and sel2.chosen_spec.ledger_ref == "veldra:p2"
```

**`tests/test_dry_run.py`** — remove the `queue_push` seed block (and the `NextExperienceSpec`/`Regime` imports), inject the steering fixture, and delete the now-dead queue assertion + helper. Replace the body of `test_dry_run_closes_the_loop` and delete `reloaded_next`:

```python
def _to_license(proposal):
    from retnovation.types import Outcome, Selection

    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.problem_menu():
        if spec.ledger_ref == "veldra:license_fork_risk":
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(proposed_receipt=top_receipt, chosen_spec=spec,
                             chosen_receipt=receipt, outcome=outcome)
    raise AssertionError("license_fork_risk not in the proposal")


def test_dry_run_closes_the_loop(tmp_path):
    store = Store(tmp_path / "dryrun.db")
    store.add_ledger_entry(LedgerEntry(
        id="veldra:license_fork_risk",
        owned_problem="A licensing-continuity decision under a same-day deadline."))
    for ref in ("veldra:license_fork_risk", "veldra:concentrated_market_pricing_power",
                "veldra:first_customer_proof_loop"):
        store.upsert_corpus(CorpusEntry(ledger_ref=ref, domain="founder_ceo", why_owned="real stakes",
                                        unlabeled="genuinely unlabeled", provenance="synthetic-test",
                                        corpus_pointers=[]))
    core = derive_core(aim())
    student_replies = iter([
        "I refuse to weaken the core promise; here is the mechanism...",
        "and I hold the core lane by...",
    ])

    def fixture(exp):
        return Work(opening="my opening reasoning",
                    respond=lambda push: next(student_replies, "..."))  # noqa: E731

    state, assessment = run_session(store, core, _cooperative_model(), _now(),
                                    present=fixture, decide=_to_license, decide_core=lambda c: [])
    assert assessment.trajectory
    assert assessment.stop_reason is StopReason.converged
    assert all(d.code in {"lead_with_what_you_refuse_to_do", "protect_the_core_lane",
                          "commit_under_the_deadline"} for d in assessment.frame_deltas)
    reloaded = Store(tmp_path / "dryrun.db").load_state(_now())
    assert reloaded.frames
    assert any(fs.strength != Strength.weak for fs in reloaded.frames.values())
```

Drop `NextExperienceSpec` and `Regime` from `test_dry_run.py`'s imports (now unused), and delete the `reloaded_next` helper.

**`tests/test_cs_dry_run.py`** — pass the explicit regime; keep the `queue_push` of the cs spec:
`run_session(store, core, _model_unused(), _now(), present=fixture, regime=Regime.cs_technical)`.

**`tests/test_cli.py`** — the seed is gone, so:

```python
def test_build_store_seeds_ledger_but_not_queue(tmp_path):
    store = build_store(tmp_path / "cli.db")
    assert any(e.id == "veldra:license_fork_risk" for e in store.load_ledger())
    assert store.queue_len() == 0  # open_ended proposes from live state; no queue seed


def test_build_store_produces_a_runnable_gated_db(tmp_path):
    """Fresh DB must seed every authored ref so select_experience gates clean (no GateError)."""
    from retnovation.aim import aim, derive_core
    from retnovation.experience import select_experience

    store = build_store(tmp_path / "fresh.db")
    exp = select_experience(
        derive_core(aim()), store.load_state(_NOW), store.load_ledger(), store.load_corpus())
    assert exp.experience_id  # gated selection succeeds on a fresh DB with no queued spec
```

**`tests/test_persistence.py`** — delete `test_log_selection_round_trips` (it calls the now-removed `Store.log_selection`; its coverage is superseded by Task 3's `test_selection_log_decision_columns_fresh_and_old_db`). Drop the `SelectionReceipt` import if it becomes unused.

**`tests/test_scheduler.py`** — remove the four `schedule_next`-based tests (`test_open_ended_uses_the_value_function_over_real_content`, `test_cs_technical_targets_due_concepts_first`, `test_cs_technical_with_nothing_due_targets_soonest`, `test_cs_technical_due_ties_break_by_concept_code`) and the `from retnovation.scheduler import schedule_next` import — coverage now lives in Task 7's `test_propose_open_ended_returns_ranked_proposal`/`test_schedule_cs_targets_due_concepts_first` plus these soonest/tie cases against `schedule_cs`:

```python
def test_schedule_cs_with_nothing_due_targets_soonest():
    from datetime import timedelta
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state({"soon": (now + timedelta(days=1), 1), "later": (now + timedelta(days=9), 8)})
    assert schedule_cs(st, [], now).target_frames == ["soon"]


def test_schedule_cs_due_ties_break_by_concept_code():
    from retnovation.scheduler import schedule_cs

    now = _now()
    st = _cs_state({"zebra": (now, 1), "alpha": (now, 1)})
    assert schedule_cs(st, [], now).target_frames == ["alpha", "zebra"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_orchestration.py tests/test_dry_run.py tests/test_cs_dry_run.py tests/test_cli.py tests/test_scheduler.py -q`
Expected: FAIL (`run_session` has no `decide` param; `schedule_next` import removed but still defined elsewhere, etc.).

- [ ] **Step 3: Rewrite `run_session` + add the CLI decide callbacks**

Rewrite `src/retnovation/orchestration.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .assessment import get_assessor
from .content_loader import load_library, load_progression
from .crystallization import crystallization_candidates
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import propose_open_ended, schedule_cs
from .state import STATE_UPDATERS
from .surface import format_problem_menu
from .types import (
    Assessment, CheckableAssessment, Core, CoreCandidate, CoreVerdict, Experience,
    LearnerState, Outcome, Proposal, Regime, Selection, Work,
)


def present_and_collect(exp: Experience) -> Work:
    def respond(push: str) -> str:
        print(push)
        return input("> ")

    if exp.regime is Regime.cs_technical:
        return Work(opening="", respond=respond)
    print(exp.prompt)
    opening = input("> ")
    return Work(opening=opening, respond=respond)


def decide_cli(proposal: Proposal) -> Selection:
    menu = proposal.problem_menu()
    print(format_problem_menu(proposal))
    while True:
        raw = input("> ").strip()
        if raw == "" or raw == "1":
            spec, receipt = proposal.top
            return Selection(proposed_receipt=proposal.top[1], chosen_spec=spec,
                             chosen_receipt=receipt, outcome=Outcome.accepted)
        if raw.isdigit() and 1 <= int(raw) <= len(menu):
            spec, receipt = menu[int(raw) - 1]
            return Selection(proposed_receipt=proposal.top[1], chosen_spec=spec,
                             chosen_receipt=receipt, outcome=Outcome.redirected)
        print(f"Enter 1-{len(menu)} or just Enter.")


def decide_core_cli(candidates: list[CoreCandidate]) -> list[CoreVerdict]:
    verdicts: list[CoreVerdict] = []
    for c in candidates:
        print(f"[{c.kind.value}] {c.target}: {c.rationale}")
        ans = input("accept? [y/N] > ").strip().lower()
        verdicts.append(CoreVerdict(candidate=c, outcome="accepted" if ans == "y" else "rejected"))
    return verdicts


def run_session(
    store: Store,
    core: Core,
    model: Model,
    now: datetime,
    *,
    regime: Regime = Regime.open_ended,
    present: Callable[[Experience], Work] = present_and_collect,
    decide: Callable[[Proposal], Selection] = decide_cli,
    decide_core: Callable[[list[CoreCandidate]], list[CoreVerdict]] = decide_core_cli,
) -> tuple[LearnerState, Assessment | CheckableAssessment]:
    state = store.load_state(now)
    ledger = store.load_ledger()
    corpus = store.load_corpus()

    if regime is Regime.cs_technical:
        spec = store.queue_pop()
        if spec is None:  # guard the latent open_ended crossover on an empty cs queue
            raise ValueError("cs_technical run requires a queued spec")
        exp = select_experience(core, state, ledger, corpus, spec)
        work = present(exp)
        assessment = get_assessor(exp.regime)(exp, work, model)
        state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id, exp.ledger_ref)
        store.save_state(state)
        store.queue_push(schedule_cs(state, ledger, now))  # cs stays queue-driven (byte-stable)
        return state, assessment

    # open_ended: propose from LIVE state, ignore the queue (§17.2)
    experiences = [e for e in load_library() if e.regime is Regime.open_ended]
    proposal = propose_open_ended(state, experiences, load_progression(), now)
    selection = decide(proposal)
    exp = select_experience(core, state, ledger, corpus, selection.chosen_spec)
    work = present(exp)
    assessment = get_assessor(exp.regime)(exp, work, model)
    state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id, exp.ledger_ref)
    store.save_state(state)
    store.log_decision(selection)

    candidates = crystallization_candidates(state, core, ledger, experiences, now, load_progression())
    if candidates:
        for verdict in decide_core(candidates):
            store.log_core_decision(verdict, now)
    return state, assessment
```

`format_receipt` (Task 5) is the author/log-facing decomposition; it is **not** called by `run_session` in
P3 (the frame-level data reaches the author via `log_decision` → `selection_log`). It stays a tested
library function for the async log / future UI, so `orchestration.py` does **not** import it (no ruff F401).

- [ ] **Step 4: Remove the dead seams (deterministic import edits — every commit passes `ruff check`)**

**`src/retnovation/scheduler.py`:** delete the `schedule_next` function. After it, `schedule_cs`/`propose_open_ended` no longer load content (they take `experiences`/`config` as args), so remove `from .content_loader import load_library, load_progression` entirely, and drop `SelectionReceipt` from the types import. Final imports: `from .policy import select_next` and `from .types import Experience, LearnerState, LedgerEntry, NextExperienceSpec, Proposal, Regime`.

**`src/retnovation/persistence.py`:** delete the old `log_selection(self, receipt)` method (superseded by `log_decision`), then drop `SelectionReceipt` from the `from .types import (...)` block (it is now unused; `Selection`/`CoreVerdict` from Task 3 stay).

**`src/retnovation/cli.py`:** in `build_store`, delete the seed block:

```python
    if store.queue_len() == 0:
        store.queue_push(
            NextExperienceSpec(
                target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
                ledger_ref=_SEED_REF,
                regime=Regime.open_ended,
            )
        )
```

Then delete the now-unused `NextExperienceSpec` import and the `_SEED_REF = "veldra:license_fork_risk"` line. **Keep `Regime`** — it is still used at `build_store`'s `if exp.regime is not Regime.open_ended` guard (removing it is a `NameError`, not an F401). In `main`, pass the regime explicitly (spec §17.2):

```python
        state, assessment = run_session(
            store, core, model, datetime.now(timezone.utc), regime=Regime.open_ended
        )
```

- [ ] **Step 5: Run the full suite + ruff**

Run: `.venv/bin/ruff check .` then `PYTHONPATH=src .venv/bin/pytest -q`
Expected: ruff clean; **all tests pass** (count ≈ 150 baseline − 4 removed `schedule_next` tests + the new P3 tests across tasks 1–8). Confirm 0 failures, 3 skips.

- [ ] **Step 6: Commit (the atomic seam swap)**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/orchestration.py src/retnovation/scheduler.py src/retnovation/persistence.py src/retnovation/cli.py tests/test_orchestration.py tests/test_dry_run.py tests/test_cs_dry_run.py tests/test_cli.py tests/test_scheduler.py tests/test_persistence.py
git commit -m "feat(orchestration): propose-from-live open_ended surface; explicit regime; advisory promote/demote

run_session takes an explicit regime (open_ended default); the open_ended path proposes
from live state, surfaces a problem-level menu (no frame leak), logs the decision, and
runs the advisory crystallization pass. cs stays queue-driven and byte-stable. Removes
schedule_next and the old log_selection; build_store no longer seeds the open_ended queue."
```

---

## Self-Review

**1. Spec coverage (§17.1–§17.6):**
- §17.1 audience split → Task 5 (`format_problem_menu` no-frame guard) + Task 8 (`decide_cli` problem-level, `log_decision` frame-level to log). ✓
- §17.2 explicit regime, no `queue_peek`, cs byte-stable, L-10 four-site rewrite → Task 8. ✓
- §17.3 `select_next` ranked, cross-drive runner-up, margin≈0, `decide` seam → Tasks 4, 5, 8. ✓
- §17.4 promote/demote via `ledger_ref` (not `links_to_experiences`/`breadth`), `experiences` in sig, decayed=`retention_due>0`, advisory+logged, no mutation → Task 6. ✓
- §17.5 `selection_log` columns + `log_decision`, `core_decision_log`, types, fresh+old DB → Tasks 1, 3. ✓ (selection_log is open_ended-only: cs path in Task 8 never calls `log_decision`.) ✓
- §17.6 `theta_ledger_refs` only new config; `_INTERVAL_DAYS` debt NOT folded in (decayed reuses built clock); no-`frame_code` regression guard → Tasks 2, 4, 5. ✓

**2. Placeholder scan:** every step has concrete test + impl code and exact commands. The one optional line (`format_receipt` post-assessment print) is explicitly marked optional with the ruff-import consequence stated — not a placeholder. ✓

**3. Type consistency:** `select_next -> list[tuple[NextExperienceSpec, SelectionReceipt]]` (Task 4) consumed by `propose_open_ended` (Task 7) → `Proposal.candidates` (Task 1) → `problem_menu()`/`top` (Task 1) → `decide_cli`/`format_problem_menu` (Tasks 5, 8). `Selection(proposed_receipt, chosen_spec, chosen_receipt, outcome)` (Task 1) consumed by `log_decision` (Task 3) and produced by `decide_cli` (Task 8) — fields match. `crystallization_candidates(state, core, ledger, experiences, now, config)` (Task 6, state-first per spec §17.4 + `config` appended for `theta_ledger_refs`) — the Task 8 caller passes positionally in that order; the Task 6 tests pass all args by keyword. ✓ `retention_due` public (Task 4) imported by Task 6. ✓ `CoreVerdict(candidate, outcome)` (Task 1) → `log_core_decision` (Task 3) → `decide_core_cli` (Task 8). ✓

**Green-at-every-commit:** Tasks 1–7 are additive (new symbols/columns/files + their tests; existing callers untouched, except Task 4's one-line `schedule_next` `[0]` adaptation keeps its tuple contract). Task 8 is the single atomic swap; its blast radius (verified by adversarial review against the merged source) is **six** test/seed files. Two review-caught blockers are resolved in this revision: (a) the rewritten `open_ended` tests **steer to `license_continuity`** via a redirect fixture rather than relying on cold-start landing on a scripted experience (the real cold-start winner is `decision_under_stakes`, unscripted in the `FakeModel`s); (b) `tests/test_persistence.py` is in Task 8's edit/stage set so the deleted `log_selection` leaves no dangling caller. ✓
