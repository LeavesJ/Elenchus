# Frame-Mining SP3 (Isolated Experiences) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the admitted spine frame `embed_credentials_as_a_list` reach `strong` in the diagnostic-progression engine across 2 owned problems (fire transfer), proven by a committable scripted regression over the *real* engine path — no @live spend.

**Architecture:** Author one single-frame isolated experience (`continuity_lock_in`, 1 frame + 3 traps = 8 angles) on the existing `veldra:license_fork_risk`; reuse `irreversible_anchor` for problem 1. A scripted regression drives the real `propose → select → assess → persist` path: session 1 starts `embed` unprompted (verified by construction, not injected), session-2 selection fires transfer (pinned by the direct rank-1-vs-rank-2 `V` gap at the worst-case forming edge), session 2 reaches `strong`. Adding the experience re-steers `problem_menu` (the L-14 cascade) — both arms are handled.

**Tech Stack:** Python 3.12, pydantic v2, PyYAML, pytest, ruff.

## Global Constraints

- Tests: `PYTHONPATH=src .venv/bin/pytest -q`; every commit leaves the suite green.
- `ruff format .` then `ruff check .` clean before every commit.
- **No `Co-Authored-By` trailer.** Stage explicit paths only — never `git add -A`/`-f`.
- Confidentiality gates stay empty:
  `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'`
  and `git ls-files | grep -E 'content/lift/(scenarios|candidates)\.yaml$'`.
- The new rubric is **committable + abstracted** (a neutral legal-lock-in scenario); `license_fork_risk`'s confidential ore stays in the gitignored seed.
- **L-13:** the learner-facing prompt names no frame/trap code or framework word.
- **L-14:** content that changes which experience is served re-steers selection — fix every dependent fixture in the same commit; steer by `experience_id`, never `proposal.top` or ledger_ref.
- Keep files under 500 lines. Update `docs/DEVLOG.md` on every commit. Branch: `frame-mining-sp3-isolated` (already created, off `main` after the SP2 cosmetics; spec commits already on it).
- Build subagent-driven; OPUS reviewer on Task 2 (the engine-proof regression — doctrine-subtle).

---

## File Structure

- `content/rubrics/continuity_lock_in.yaml` (create) — the single-frame isolate on `license_fork_risk`.
- `tests/test_dry_run.py` (modify) — re-point `_to_license` to steer by `experience_id` (cascade Arm 1).
- `tests/test_orchestration.py` (modify) — same re-point.
- `tests/test_sp3_progression.py` (create) — the scripted engine-proof regression (both cascade arms tested).
- `src/retnovation/types.py` + `src/retnovation/surface.py` (modify) — mark the receipt `margin` cross-drive (calibration log surface).
- `docs/DEVLOG.md` (modify) — per-commit notes.

---

### Task 1: Author `continuity_lock_in` + re-point the 3 cascade-broken tests (atomic — green at every commit)

**Files:**
- Create: `content/rubrics/continuity_lock_in.yaml`
- Modify: `tests/test_dry_run.py` (the `_to_license` helper), `tests/test_orchestration.py` (the `_to_license` helper)
- Test: `tests/test_sp3_progression.py` (the gate assertion only, in this task)

**Interfaces:**
- Consumes: `generator.load_gated_library`, `generator.angle_count`, `content_loader.load_rubric`, the existing `veldra:license_fork_risk` corpus entry (gitignored seed, non-empty `unlabeled`/`why_owned`/`provenance`).
- Produces: a new open_ended experience `continuity_lock_in` (1 frame `embed_credentials_as_a_list` + 3 traps); the rubric is loadable + clears the anti-label gate.

- [ ] **Step 1: Create the rubric**

Create `content/rubrics/continuity_lock_in.yaml` verbatim (1 frame + 3 traps = 8 angles; no `decision_frame` — a stress-probe would mark `embed` probed and disqualify the unprompted read):

```yaml
experience_id: continuity_lock_in
ledger_ref: "veldra:license_fork_risk"
regime: open_ended
mode: genuinely_open
binding_constraint: null
prompt: >
  A buyer's counsel wants the continuity terms in your license pinned down before they will sign this
  quarter. Whatever you write into that clause now is what every customer reads into their own risk
  planning — and once deals depend on it, you cannot quietly revise it. One straightforward continuity
  promise covers what this buyer is asking for today. Decide what you commit to in the clause, and account
  for what you are trading and how it fails if those terms ever have to change.
  (No framework is named for you on purpose.)
frames:
  - frame_code: embed_credentials_as_a_list
    frame_detail: When the choice cannot be amended after it ships, provision the cheap optionality now; the option to add it later will not exist.
    paired_trap: shipped_the_one_shot_term
traps:
  - trap_code: shipped_the_one_shot_term
    trap_detail: Committed a single fixed term now and assumed more could be layered in later, when the shipped commitment admits no quiet later change.
  - trap_code: over_built_the_escape_hatch
    trap_detail: Reached for an elaborate revisable or remote mechanism to preserve flexibility, instead of the cheap optionality provisioned from the start.
  - trap_code: treated_the_shipped_choice_as_amendable
    trap_detail: Assumed the commitment could be revised after others depend on it, missing that shipping removes the later option.
```

- [ ] **Step 2: Add the gate assertion (write the test first)**

Create `tests/test_sp3_progression.py` with the gate test:

```python
from datetime import datetime, timezone

from retnovation.content_loader import load_rubric
from retnovation.generator import angle_count


def test_continuity_lock_in_clears_the_gate():
    r = load_rubric("continuity_lock_in")
    assert [f.frame_code for f in r.frames] == ["embed_credentials_as_a_list"]
    assert len(r.traps) == 3
    assert angle_count(r) == 8  # 1 frame + 3 traps + 0 binding + 4 dims = floor
```

- [ ] **Step 3: Run the suite — observe the cascade RED**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: the new gate test PASSES, but **3 existing tests FAIL** with `KeyError: 'embed_credentials_as_a_list'`:
`tests/test_dry_run.py::test_dry_run_closes_the_loop`, `tests/test_orchestration.py::test_run_session_closes_one_cycle`, `tests/test_orchestration.py::test_run_session_logs_selection_receipt` — because `continuity_lock_in` now wins `problem_menu()` for `license_fork_risk` (load 1 < load 3) and those FakeModels don't script `embed`. This is the expected L-14 cascade.

- [ ] **Step 4: Re-point the 3 tests (steer by `experience_id` over the full candidate list)**

In **both** `tests/test_dry_run.py` and `tests/test_orchestration.py`, replace the `_to_license` helper with this version (the only change: iterate `proposal.candidates` and match `experience_id`, since the deduped `problem_menu` now serves the isolate while `license_continuity` remains in the full ranked list):

```python
def _to_license(proposal):
    # Steer to license_continuity specifically. SP3 added continuity_lock_in on the same ledger_ref,
    # so the deduped problem_menu serves the single-frame isolate; license_continuity is still in the
    # full candidate list — steer by experience_id over proposal.candidates (L-14 re-steer).
    from retnovation.types import Outcome, Selection

    top_spec, top_receipt = proposal.top
    for spec, receipt in proposal.candidates:
        if spec.experience_id == "license_continuity":
            outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
            return Selection(
                proposed_receipt=top_receipt,
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=outcome,
            )
    raise AssertionError("license_continuity not in the proposal")
```

- [ ] **Step 5: Run the suite — GREEN**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all pass (the 3 re-pointed tests now steer to `license_continuity`, which the FakeModels script; the gate test passes). `ruff format . && ruff check .` clean.

- [ ] **Step 6: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add content/rubrics/continuity_lock_in.yaml tests/test_dry_run.py tests/test_orchestration.py tests/test_sp3_progression.py docs/DEVLOG.md
git commit -m "feat(sp3): continuity_lock_in isolate + re-point the L-14 cascade tests (Arm 1)"
```

---

### Task 2: The scripted engine-proof regression

**Files:**
- Modify: `tests/test_sp3_progression.py` (append the progression tests)

**Interfaces:**
- Consumes: `cli.build_store`, `aim.aim`/`derive_core`, `orchestration.run_session`, `policy.select_next`, `assessment.judgment_loop.assess`, `content_loader.{load_experience,load_library,load_progression}`, `persistence.Store`, `model.FakeModel`/`IntakeClassification`/`ResponseClassification`, `surface.format_problem_menu`, types `FrameState`/`TrapState`/`Strength`/`Regime`/`Work`/`Outcome`/`Selection`/`Proposal`.
- Produces: the four engine-proof assertions of spec §6 + the §9 Arm-2 shadow-arc assertion.

- [ ] **Step 1: Write the session-1 construction check (the gating proof — Issue 1)**

Append to `tests/test_sp3_progression.py`:

```python
from retnovation.assessment.judgment_loop import assess
from retnovation.content_loader import load_experience
from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import FrameState, TrapState, Work


def _closed(n=4):
    return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False) for _ in range(n)]


def test_session1_credits_embed_unprompted_through_the_real_loop():
    # embed present_reasoned at intake; choose_failure absent (so the loop WILL probe it). If embed were
    # ever probed, it would not be in reasoned_unprompted. This proves the unprompted credit is earned by
    # the real not-probed path, not injected (irreversible_anchor has no decision_frame -> no stress-probe).
    exp = load_experience("irreversible_anchor")
    intake = IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={"deferred_the_one_time_choice": TrapState.not_tripped,
                     "assumed_the_happy_path": TrapState.not_tripped},
    )
    model = FakeModel(intake, {"choose_the_failure_default_deliberately": _closed()})
    work = Work(opening="reasoning that already holds the anchor move", respond=lambda push: "mechanism")
    a = assess(exp, work, model)
    probed = {p.target_code for p in a.trajectory}
    assert "embed_credentials_as_a_list" in a.reasoned_unprompted
    assert "embed_credentials_as_a_list" not in probed  # never probed -> the read is genuinely unprompted
```

- [ ] **Step 2: Run it — PASS**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_sp3_progression.py::test_session1_credits_embed_unprompted_through_the_real_loop -v`
Expected: PASS (`reasoned_unprompted` contains `embed`; trajectory targets only `choose_…`).

- [ ] **Step 3: Write the two-session progression test (weak → forming → strong, real path)**

Append:

```python
from datetime import timedelta

from retnovation.aim import aim, derive_core
from retnovation.cli import build_store
from retnovation.orchestration import run_session
from retnovation.persistence import Store
from retnovation.surface import format_problem_menu
from retnovation.types import Outcome, Regime, Selection, Strength

EMBED = "embed_credentials_as_a_list"
P1 = "veldra:embedded_anchor_lock_in"
P2 = "veldra:license_fork_risk"


def _S1():  # session 1: irreversible_anchor — embed unprompted, choose_failure closed-under-pressure
    return datetime(2026, 6, 26, tzinfo=timezone.utc)


def _steer(experience_id):
    def decide(proposal):
        top_spec, top_receipt = proposal.top
        for spec, receipt in proposal.candidates:
            if spec.experience_id == experience_id:
                outcome = Outcome.accepted if spec is top_spec else Outcome.redirected
                return Selection(proposed_receipt=top_receipt, chosen_spec=spec,
                                 chosen_receipt=receipt, outcome=outcome)
        raise AssertionError(f"{experience_id} not in proposal")
    return decide


def _model_for(frames_present, traps, probed_responses):
    intake = IntakeClassification(
        frame_states={f: (FrameState.present_reasoned if f in frames_present else FrameState.absent)
                      for f in (set(frames_present) | set(probed_responses))},
        trap_states={t: TrapState.not_tripped for t in traps},
    )
    return FakeModel(intake, {code: _closed() for code in probed_responses})


def _present(exp):
    return Work(opening="reasoning that already holds the move unprompted", respond=lambda push: "mechanism")


def test_two_session_run_reaches_strong_through_the_real_path():
    store = build_store(tmp_path_global := __import__("tempfile").mkdtemp() + "/sp3.db")
    core = derive_core(aim())
    now1 = _S1()

    # --- session 1: irreversible_anchor. embed present_reasoned (unprompted); choose_failure absent (probed, closed).
    s1_model = _model_for(
        frames_present=[EMBED],
        traps=["deferred_the_one_time_choice", "assumed_the_happy_path"],
        probed_responses={"choose_the_failure_default_deliberately"},
    )
    # session-1 surface withholds the frame (both sessions credit an unprompted read)
    captured = {}
    def present_s1(exp):
        return _present(exp)
    state1, _ = run_session(store, core, s1_model, now1, regime=Regime.open_ended,
                            present=present_s1, decide=_steer("irreversible_anchor"), decide_core=lambda c: [])
    assert state1.frames[EMBED].strength is Strength.forming
    assert state1.frames[EMBED].breadth == {P1}
    assert state1.frames[EMBED].unprompted_breadth == {P1}

    # --- session 2 at the worst-case forming edge (7 days later); embed present_reasoned (unprompted).
    now2 = now1 + timedelta(days=7)
    s2_model = _model_for(frames_present=[EMBED],
                          traps=["shipped_the_one_shot_term", "over_built_the_escape_hatch",
                                 "treated_the_shipped_choice_as_amendable"],
                          probed_responses={})
    state2, _ = run_session(store, core, s2_model, now2, regime=Regime.open_ended,
                            present=_present, decide=_steer("continuity_lock_in"), decide_core=lambda c: [])
    assert state2.frames[EMBED].strength is Strength.strong
    assert state2.frames[EMBED].unprompted_breadth == {P1, P2}

    # post-strong savings effect: due interval jumps to 30 days
    from retnovation.state import derive_due
    fs = Store(tmp_path_global).load_state(now2).frames[EMBED]
    assert derive_due(fs.evidence_count, fs.unprompted_breadth, fs.last_seen) == fs.last_seen + timedelta(days=30)
```

> Note for the implementer: use a pytest `tmp_path` fixture instead of the `mkdtemp` shim above — pass `tmp_path` into the test and use `build_store(tmp_path / "sp3.db")` / `Store(tmp_path / "sp3.db")`. The shim is only to keep this snippet self-contained; the real test signature is `def test_two_session_run_reaches_strong_through_the_real_path(tmp_path):`.

- [ ] **Step 4: Run it — PASS**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_sp3_progression.py -k reaches_strong -v`
Expected: PASS — `forming` after S1, `strong` after S2, `unprompted_breadth == {P1, P2}`, post-strong due `= last_seen + 30d`. (If `KeyError` on a frame code, the loop probed a frame the model didn't script — adjust `frames_present`/`probed_responses`, do not weaken the assertion.)

- [ ] **Step 5: Write the session-2 ordering pin (direct V gap, forming edge) + the shadow-arc**

Append:

```python
from retnovation.content_loader import load_library, load_progression
from retnovation.policy import select_next
from retnovation.types import Proposal


def _post_s1_state(now):
    # the exact state session 1 leaves: embed forming, unprompted on P1 only.
    from retnovation.types import FrameStrength
    return __import__("retnovation.types", fromlist=["LearnerState"]).LearnerState(
        frames={EMBED: FrameStrength(strength=Strength.forming, last_seen=now, due=now,
                                     last_evidence="irreversible_anchor", evidence_count=1,
                                     breadth={P1}, unprompted_breadth={P1})})


def test_session2_selection_pins_the_isolate_at_the_forming_edge():
    lib = load_library()
    cfg = load_progression()
    now1 = _S1()
    now2 = now1 + timedelta(days=7)  # worst-case forming edge (gap ~0.08)
    ranked = select_next(_post_s1_state(now1), lib, cfg, now2)
    top_spec, top_rcpt = ranked[0]
    assert top_spec.experience_id == "continuity_lock_in"   # resolve by experience_id, not ledger_ref
    assert top_rcpt.frame == EMBED and top_rcpt.drive == "deploy"
    # the REAL ordering risk is a same-drive competing transfer; assert the direct rank gap, not the
    # receipt margin (which is cross-drive only — policy.py:99).
    assert ranked[0][1].scores["V"] - ranked[1][1].scores["V"] > 0
    # the learner-facing menu withholds the frame
    assert EMBED not in format_problem_menu(Proposal(candidates=ranked))


def test_shadow_on_license_continuity_self_resolves(tmp_path):
    # Arm 2 of the cascade, on the DEFAULT menu path (the path real use takes): the isolate shadows
    # license_continuity while embed is unlocated, and license_continuity (commit_under_the_deadline's
    # only home) surfaces once embed is strong. Tested, not routed around.
    from retnovation.types import FrameStrength, LearnerState
    lib = load_library()
    cfg = load_progression()
    now = _S1()

    def served(state):
        menu = Proposal(candidates=select_next(state, lib, cfg, now)).problem_menu()
        return next(s.experience_id for s, _ in menu if s.ledger_ref == P2)

    assert served(LearnerState()) == "continuity_lock_in"  # fresh learner: isolate shadows
    forming = LearnerState(frames={EMBED: FrameStrength(strength=Strength.forming, last_seen=now, due=now,
        last_evidence="x", evidence_count=1, breadth={P1}, unprompted_breadth={P1})})
    assert served(forming) == "continuity_lock_in"  # still the isolate (transfer)
    strong = LearnerState(frames={EMBED: FrameStrength(strength=Strength.strong, last_seen=now, due=now,
        last_evidence="x", evidence_count=2, breadth={P1, P2}, unprompted_breadth={P1, P2})})
    assert served(strong) == "license_continuity"  # self-resolves: commit reachable again
```

- [ ] **Step 6: Run the full file + suite**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_sp3_progression.py -v` then `PYTHONPATH=src .venv/bin/pytest -q`
Expected: all PASS. `ruff format . && ruff check .` clean.

- [ ] **Step 7: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add tests/test_sp3_progression.py docs/DEVLOG.md
git commit -m "test(sp3): engine-proof regression — embed weak->forming->strong via the real path; ordering pinned; shadow self-resolves"
```

---

### Task 3: Mark the logged receipt margin as cross-drive (calibration log surface)

**Files:**
- Modify: `src/retnovation/types.py` (the `SelectionReceipt.margin` field comment), `src/retnovation/surface.py` (`format_receipt`)
- Test: `tests/test_surface.py` (append one assertion)

**Interfaces:**
- Consumes: existing `SelectionReceipt`, `surface.format_receipt`.
- Produces: the author/log-facing receipt labels its `margin` as cross-drive, so the dogfood calibration log is not misread when the real contest is same-drive.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_surface.py`:

```python
def test_format_receipt_labels_margin_cross_drive():
    from datetime import datetime, timezone
    from retnovation.surface import format_receipt
    from retnovation.types import SelectionReceipt
    r = SelectionReceipt(frame="f", problem="veldra:p", experience_id="e", drive="deploy",
                         scores={"V": 1.5}, runner_up_drive="diagnose", margin=1.2,
                         content_gaps=[], created_at=datetime(2026, 6, 26, tzinfo=timezone.utc))
    out = format_receipt(r)
    assert "cross-drive" in out  # margin is cross-drive only; not the rank-1-vs-rank-2 gap
```

- [ ] **Step 2: Run it — FAIL**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_surface.py::test_format_receipt_labels_margin_cross_drive -v`
Expected: FAIL (no "cross-drive" in the current output).

- [ ] **Step 3: Implement**

In `src/retnovation/surface.py`, find the line in `format_receipt` that renders the margin/runner-up and add the `cross-drive` qualifier. The existing line renders something like `f"runner-up {receipt.runner_up_drive} (margin {receipt.margin:.2f})"`; change it to:

```python
        f"runner-up {receipt.runner_up_drive} (cross-drive margin {receipt.margin:.2f})"
```

(Read the exact current line first; preserve its surrounding format. If the margin is rendered on its own line, append `" (cross-drive)"` there instead.)

In `src/retnovation/types.py`, on `SelectionReceipt.margin`, add the clarifying comment:

```python
    margin: float  # cross-drive only (vs the best OTHER-drive candidate); NOT the rank-1-vs-rank-2 gap
```

- [ ] **Step 4: Run it — PASS + suite**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_surface.py -v` then `PYTHONPATH=src .venv/bin/pytest -q`
Expected: PASS; full suite green.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/surface.py src/retnovation/types.py tests/test_surface.py docs/DEVLOG.md
git commit -m "chore(sp3): mark SelectionReceipt.margin as cross-drive in the log surface (calibration)"
```

---

## After all tasks

- OPUS whole-branch review (focus: Task 2's regression genuinely exercises the REAL path — does it inject any state? does the session-2 ordering assertion use the direct V gap, not the receipt margin? is the shadow-arc tested on the default menu path? — plus the cascade re-point correctness and confidentiality).
- `superpowers:finishing-a-development-branch` — ff-merge `frame-mining-sp3-isolated` to main; push is the user's call.

## Self-Review (completed during planning)

- **Spec coverage:** §4 isolate → Task 1; §6 four assertions (session-1 construction + forming; session-2 ordering via direct V gap at forming edge + no-frame both sessions; session-2 strong; post-strong interval) → Task 2 Steps 1/3/5; §7 traps → Task 1 rubric; §8 confidentiality → Task 1 (abstracted prompt, ore gitignored); §9 cascade Arm 1 (re-point 3 tests) → Task 1, Arm 2 (shadow self-resolution on the default menu path) → Task 2 Step 5; §6 logged-margin calibration → Task 3. No gaps.
- **Placeholder scan:** none; the one `mkdtemp` shim in Task 2 Step 3 is explicitly flagged with the real `tmp_path` signature to use.
- **Type consistency:** `_to_license`/`_steer` resolve by `experience_id` over `proposal.candidates` everywhere; `select_next` returns `list[(NextExperienceSpec, SelectionReceipt)]` and the V gap reads `scores["V"]` (matches `policy.py:118-124`); `FrameStrength`/`LearnerState`/`derive_due` signatures match `state.py`/`types.py`; `assess(exp, work, model)` and `run_session(store, core, model, now, regime=, present=, decide=, decide_core=)` match the merged code.
