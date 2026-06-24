# Harden the Judgment Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the open_ended judgment loop fire its `regression` and (distinct-target) `plateau` stops, and add an independent blind grader that gates "sharper" credit by a 2-vote — Build Brief #5.

**Architecture:** Extend the open_ended assessor only; cs_technical (checkable) and `run_session` are untouched. The instructor loop (`judgment_loop.assess`) gains a regression branch and rotates targets so plateau means "two distinct angles failed". After the loop, a separate `assessment/sharper_grader.py::audit_sharper` re-judges each closed frame via a blind, skeptical `Model.grade_sharper`; a disputed call is dropped from `frames_closed_under_pressure` and its `FrameDelta` reverted, so `update_state` scores it weak. Spec: `docs/superpowers/specs/2026-06-23-harden-judgment-loop-design.md`.

**Tech Stack:** Python ≥3.12, pydantic ≥2, anthropic SDK (lazy, grader live path only), pytest, ruff. Run via the project venv: `source .venv/bin/activate`.

## Global Constraints

- **Venv:** all `python`/`pytest`/`ruff` after `source .venv/bin/activate`.
- **ruff:** `line-length = 100`; every commit runs `ruff format .` then `ruff check .`, both clean.
- **TDD:** failing test first, watch it fail, minimal implementation, watch it pass, commit.
- **Commits:** NEVER add a `Co-Authored-By` trailer. Stage explicit paths only — never `git add -A`/`.`/`-f`.
- **DEVLOG:** every task appends a `docs/DEVLOG.md` entry in the same commit.
- **Confidentiality (L-2):** `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` must stay empty; `data/` untracked.
- **SDD scratch (L-7):** reports go under `.superpowers/sdd/` (gitignored); never commit them.
- **Doctrine:** sharper = a gap closed with a *supplied mechanism* (assent ≠ sharper, length ≠ sharper); presence is conclusion-agnostic (the grader must not dispute a call for reaching a different conclusion); the grader is **blind** (it never sees the instructor's outcome); a disputed sharper is dropped + its delta reverted (never scored strong); the bounded_error hard-wrong flag stays the only verdict and still pre-empts.
- **Never-collapse:** this is open_ended only; cs_technical, `STATE_UPDATERS`, `run_session` unchanged.
- Branch: `step5-harden-judgment-loop` (created off `main`).
- Baseline before Task 1: `pytest -q` = 87 passed, 2 skipped.

---

## File Structure

- `src/retnovation/types.py` — modify: `Push.response`; `SharperVerdict`, `SharperAuditItem`; `Assessment.sharper_audit`.
- `content/prompts/grade_sharper.md` — create: the blind skeptical grader doctrine prompt.
- `src/retnovation/model.py` — modify: `Model.grade_sharper`; `FakeModel.grade_sharper`; `AnthropicModel.grade_sharper`.
- `src/retnovation/assessment/sharper_grader.py` — create: `audit_sharper`.
- `src/retnovation/assessment/judgment_loop.py` — modify: regression branch, target rotation + distinct-target plateau, populate `Push.response`, call `audit_sharper`.
- Tests: extend `test_types.py`, `test_model.py`, `test_anthropic_model.py`, `test_live_model.py`, `test_judgment_loop.py`; create `test_sharper_grader.py`.

---

### Task 1: Types — `Push.response`, sharper-audit types, `Assessment.sharper_audit`

**Files:**
- Modify: `src/retnovation/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces:
  - `Push.response: str = ""` (raw student reply to this push).
  - `SharperVerdict(BaseModel)`: `sharper: bool`, `reason: str`.
  - `SharperAuditItem(BaseModel)`: `code: str`, `kind: str`, `instructor_sharper: bool`, `grader_sharper: bool`, `confirmed: bool`, `grader_reason: str`.
  - `Assessment.sharper_audit: list[SharperAuditItem]` (default empty).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_types.py`:

```python
def test_push_carries_raw_response_with_empty_default():
    from retnovation.types import Push

    p = Push(target_code="f", kind="frame", text="push", response_classification="closed")
    assert p.response == ""
    p2 = Push(target_code="f", kind="frame", text="push",
              response_classification="closed", response="my reply")
    assert p2.response == "my reply"


def test_sharper_audit_types_and_assessment_field():
    from retnovation.types import (
        Assessment,
        SharperAuditItem,
        SharperVerdict,
        StopReason,
    )

    assert SharperVerdict(sharper=False, reason="bare assent").sharper is False
    item = SharperAuditItem(code="protect_the_core_lane", kind="frame", instructor_sharper=True,
                            grader_sharper=False, confirmed=False, grader_reason="no mechanism")
    assert item.confirmed is False
    a = Assessment(trajectory=[], frame_deltas=[], frames_closed_under_pressure=[],
                   hard_wrong_flags=[], stop_reason=StopReason.converged)
    assert a.sharper_audit == []  # default empty
    a2 = Assessment(trajectory=[], frame_deltas=[], frames_closed_under_pressure=[],
                    hard_wrong_flags=[], stop_reason=StopReason.converged, sharper_audit=[item])
    assert a2.sharper_audit[0].code == "protect_the_core_lane"
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q`
Expected: FAIL (ImportError on `SharperVerdict` / `Push` has no `response`).

- [ ] **Step 3: Implement in `src/retnovation/types.py`.**

Add `response: str = ""` to the `Push` model (after `response_classification`):

```python
class Push(BaseModel):
    target_code: str
    kind: str
    text: str
    response_classification: str
    response: str = ""
```

Add the two new models (place near `Assessment`):

```python
class SharperVerdict(BaseModel):
    sharper: bool
    reason: str


class SharperAuditItem(BaseModel):
    code: str
    kind: str
    instructor_sharper: bool
    grader_sharper: bool
    confirmed: bool
    grader_reason: str
```

Add `sharper_audit` to `Assessment`:

```python
class Assessment(BaseModel):
    trajectory: list[Push]
    frame_deltas: list[FrameDelta]
    frames_closed_under_pressure: list[str]
    hard_wrong_flags: list[str]
    stop_reason: StopReason
    sharper_audit: list[SharperAuditItem] = Field(default_factory=list)
```

(`Field` is already imported in `types.py`.)

- [ ] **Step 4: Run to verify pass + full suite (no regression)**

Run: `source .venv/bin/activate && pytest tests/test_types.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite still 87 passed + new tests, 2 skipped (`Push.response` default + `sharper_audit` default keep all existing constructions valid); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): Push.response + sharper-audit types + Assessment.sharper_audit"
```
(DEVLOG line: Task 1 — added `Push.response` (default ""), `SharperVerdict`, `SharperAuditItem`, `Assessment.sharper_audit`.)

---

### Task 2: Model grader — `grade_sharper` + the blind doctrine prompt

**Files:**
- Create: `content/prompts/grade_sharper.md`
- Modify: `src/retnovation/model.py`
- Test: `tests/test_model.py`, `tests/test_anthropic_model.py`, `tests/test_live_model.py`

**Interfaces:**
- Consumes: `SharperVerdict` (Task 1); existing `_target_detail`, `_require`, `_PARAMS`, `load_prompt`.
- Produces:
  - `Model.grade_sharper(self, exp, kind, code, push, response) -> SharperVerdict` (Protocol).
  - `FakeModel(intake, responses, grades=None, sharper_verdicts=None)`; `grade_sharper` pops a scripted verdict for `code` if present, else returns `SharperVerdict(sharper=True, reason="(default agree)")`.
  - `AnthropicModel.grade_sharper` — `messages.parse`, `output_format=SharperVerdict`, blind.

- [ ] **Step 1: Author the grader prompt** — create `content/prompts/grade_sharper.md`:

```markdown
You are a blind second grader auditing whether ONE reasoning gap was genuinely made sharper.

You are given only the target angle, the instructor's push, and the student's reply. You do NOT
know whether the instructor credited it. Decide independently.

Sharper means: the student supplied a mechanism or reason that actually engages and closes the
angle. It is NOT sharper when the reply is bare assent ("you're right, I'll fix it"), a restatement
of the push, or simply more words with no new reason. Length is never sharper.

Conclusion-agnostic: a student who engages the angle with a real mechanism is sharper even if they
reach a different conclusion than you would. Never dispute a call merely because the student
disagreed — disagreeing well still counts.

Default to sharper=false when no mechanism is clearly cited. Output {sharper, reason} with a short
reason citing the student's own words (or their absence).
```

- [ ] **Step 2: Write the failing tests.**

Append to `tests/test_model.py`:

```python
def test_fake_model_grade_sharper_scripted_then_default_agree():
    from retnovation.model import FakeModel, IntakeClassification
    from retnovation.types import SharperVerdict

    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={},
                  sharper_verdicts={"f": [SharperVerdict(sharper=False, reason="assent only")]})
    assert m.grade_sharper(None, "frame", "f", "push", "yeah you're right").sharper is False
    # an unscripted code -> the test double's grader agrees by default
    assert m.grade_sharper(None, "frame", "other", "push", "because mechanism X").sharper is True
```

Append to `tests/test_anthropic_model.py`:

```python
def test_grade_sharper_is_blind_and_parses_verdict():
    from retnovation.types import SharperVerdict

    client = _Client(parse_result=_Resp(parsed_output=SharperVerdict(
        sharper=True, reason="cited a mechanism")))
    out = AnthropicModel(client=client).grade_sharper(
        _exp(), "frame", "protect_the_core_lane",
        "What do you give up by holding that line?",
        "I hold it because unverified work destroys revenue exactly when outages cluster.")
    assert out.sharper is True
    call = client.messages.parse_calls[0]
    # the target angle detail reaches the grader's system prompt
    assert "Keep the promise the core product makes" in _system_text(call)
    # the raw student reply reaches the grader's user turn
    assert "unverified work destroys revenue" in _user_text(call)
    # blindness is structural: grade_sharper's signature has no instructor-outcome parameter


def test_grade_sharper_refusal_raises():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).grade_sharper(
            _exp(), "frame", "protect_the_core_lane", "push", "reply")
```

Append to `tests/test_live_model.py` (gate it the SAME way the existing `live` test in this file does — reuse its `_HAS_KEY`/skip mechanism for consistency; if it uses a module-level `@pytest.mark.skipif(not _HAS_KEY, ...)`, mirror that exactly):

```python
@pytest.mark.live
def test_live_grade_sharper_smoke():
    from retnovation.model import AnthropicModel
    from retnovation.types import (
        CheckableSet,
        Experience,
        Frame,
        Mode,
        Regime,
        Rubric,
        Trap,
    )

    exp = Experience(
        experience_id="live", prompt="p", ledger_ref="veldra:x", regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code="protect_the_core_lane",
                          frame_detail="Keep the promise the core product makes to everyone.",
                          paired_trap="t")],
            traps=[Trap(trap_code="t", trap_detail="d")], mode=Mode.genuinely_open))
    v = AnthropicModel().grade_sharper(
        exp, "frame", "protect_the_core_lane",
        "What do you give up by holding that line?", "you're right")
    assert isinstance(v.sharper, bool)
```

(Remove the unused `CheckableSet` import if your final version doesn't reference it; keep ruff clean.)

- [ ] **Step 3: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_model.py tests/test_anthropic_model.py -q`
Expected: FAIL (`FakeModel`/`AnthropicModel` have no `grade_sharper`).

- [ ] **Step 4: Implement in `src/retnovation/model.py`.**

Add `SharperVerdict` to the types import:

```python
from .types import (
    CheckableGrade,
    CheckableQuestion,
    Experience,
    FrameState,
    SharperVerdict,
    TrapState,
)
```

Add to the `Model` Protocol:

```python
    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict: ...
```

Update `FakeModel.__init__` and add the method:

```python
    def __init__(
        self,
        intake: IntakeClassification,
        responses: dict[str, list[ResponseClassification]],
        grades: dict[str, list[CheckableGrade]] | None = None,
        sharper_verdicts: dict[str, list[SharperVerdict]] | None = None,
    ):
        self._intake = intake
        self._responses = responses
        self._grades = grades or {}
        self._sharper_verdicts = sharper_verdicts or {}

    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict:
        scripted = self._sharper_verdicts.get(code)
        if scripted:
            return scripted.pop(0)
        return SharperVerdict(sharper=True, reason="(default agree)")
```

Add `AnthropicModel.grade_sharper` (mirrors `classify_response`; blind — no outcome in the prompt):

```python
    def grade_sharper(
        self, exp: Experience, kind: str, code: str, push: str, response: str
    ) -> SharperVerdict:
        detail = _target_detail(exp.rubric, kind, code)
        system = load_prompt("grade_sharper") + f"\n\nTarget angle: {detail}"
        user = f"Push:\n{push}\n\nStudent reply:\n{response}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=SharperVerdict,
            **_PARAMS,
        )
        return _require(resp)
```

- [ ] **Step 5: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_model.py tests/test_anthropic_model.py tests/test_live_model.py -q && ruff format . && ruff check .`
Expected: PASS (live smoke skipped without a key); ruff clean.

- [ ] **Step 6: Commit**

```bash
git add content/prompts/grade_sharper.md src/retnovation/model.py tests/test_model.py tests/test_anthropic_model.py tests/test_live_model.py docs/DEVLOG.md
git commit -m "feat(model): blind grade_sharper grader + skeptical doctrine prompt"
```

---

### Task 3: Independent grader pass — `audit_sharper`

**Files:**
- Create: `src/retnovation/assessment/sharper_grader.py`
- Test: `tests/test_sharper_grader.py`

**Interfaces:**
- Consumes: `Model.grade_sharper` (Task 2); `Assessment`, `SharperAuditItem`, `Push.response` (Task 1).
- Produces: `audit_sharper(exp, assessment, model) -> Assessment` — re-judges each closed frame; a disputed call is removed from `frames_closed_under_pressure` and its `FrameDelta` removed; records `sharper_audit`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_sharper_grader.py`:

```python
from datetime import datetime, timezone

from retnovation.assessment.sharper_grader import audit_sharper
from retnovation.model import FakeModel, IntakeClassification
from retnovation.state import update_state
from retnovation.types import (
    Assessment,
    Experience,
    Frame,
    FrameDelta,
    FrameState,
    LearnerState,
    Mode,
    Push,
    Regime,
    Rubric,
    SharperVerdict,
    StopReason,
    Strength,
    Trap,
)


def _exp():
    return Experience(
        experience_id="x", prompt="p", ledger_ref="r", regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code="protect_the_core_lane", frame_detail="keep core",
                          paired_trap="t")],
            traps=[Trap(trap_code="t", trap_detail="d")], mode=Mode.genuinely_open))


def _closed_assessment():
    return Assessment(
        trajectory=[Push(target_code="protect_the_core_lane", kind="frame", text="push",
                         response_classification="closed", response="because mechanism X")],
        frame_deltas=[FrameDelta(code="protect_the_core_lane", before=FrameState.absent,
                                 after=FrameState.present_reasoned)],
        frames_closed_under_pressure=["protect_the_core_lane"],
        hard_wrong_flags=[], stop_reason=StopReason.converged)


def _model(verdicts=None):
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={},
                     sharper_verdicts=verdicts)


def test_grader_confirms_keeps_the_closed_call():
    audited = audit_sharper(_exp(), _closed_assessment(), _model())  # default agree
    assert audited.frames_closed_under_pressure == ["protect_the_core_lane"]
    assert len(audited.frame_deltas) == 1
    assert len(audited.sharper_audit) == 1 and audited.sharper_audit[0].confirmed is True


def test_grader_dispute_demotes_reverts_then_state_is_weak():
    disputed = {"protect_the_core_lane": [SharperVerdict(sharper=False, reason="bare assent")]}
    audited = audit_sharper(_exp(), _closed_assessment(), _model(disputed))
    assert audited.frames_closed_under_pressure == []  # demoted out of closed
    assert audited.frame_deltas == []  # delta reverted
    assert audited.sharper_audit[0].confirmed is False
    # and update_state then scores it weak — guards the strong-misclassification trap
    st = update_state(LearnerState(), audited, datetime(2026, 6, 23, tzinfo=timezone.utc), "x")
    assert st.frames["protect_the_core_lane"].strength is Strength.weak
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_sharper_grader.py -q`
Expected: FAIL (no module `sharper_grader`).

- [ ] **Step 3: Implement `src/retnovation/assessment/sharper_grader.py`:**

```python
from __future__ import annotations

from ..model import Model
from ..types import Assessment, Experience, SharperAuditItem


def audit_sharper(exp: Experience, assessment: Assessment, model: Model) -> Assessment:
    """Blind 2-vote audit of the instructor's sharper calls: re-grade each closed frame; a
    disputed call is dropped from frames_closed_under_pressure and its delta reverted, so
    update_state cannot credit it. Records the full audit trail on sharper_audit."""
    closed = set(assessment.frames_closed_under_pressure)
    audit: list[SharperAuditItem] = []
    disputed: set[str] = set()
    seen: set[str] = set()
    for p in assessment.trajectory:
        if (
            p.kind != "frame"
            or p.target_code not in closed
            or p.response_classification != "closed"
            or p.target_code in seen
        ):
            continue
        seen.add(p.target_code)
        verdict = model.grade_sharper(exp, p.kind, p.target_code, p.text, p.response)
        audit.append(
            SharperAuditItem(
                code=p.target_code,
                kind=p.kind,
                instructor_sharper=True,
                grader_sharper=verdict.sharper,
                confirmed=verdict.sharper,
                grader_reason=verdict.reason,
            )
        )
        if not verdict.sharper:
            disputed.add(p.target_code)
    new_closed = [c for c in assessment.frames_closed_under_pressure if c not in disputed]
    new_deltas = [d for d in assessment.frame_deltas if d.code not in disputed]
    return assessment.model_copy(
        update={
            "frames_closed_under_pressure": new_closed,
            "frame_deltas": new_deltas,
            "sharper_audit": audit,
        }
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_sharper_grader.py -q && ruff format . && ruff check .`
Expected: PASS; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/assessment/sharper_grader.py tests/test_sharper_grader.py docs/DEVLOG.md
git commit -m "feat(assessment): independent blind sharper grader (2-vote, demote+revert on dispute)"
```

---

### Task 4: Regression stop + populate `Push.response` in the loop

**Files:**
- Modify: `src/retnovation/assessment/judgment_loop.py`
- Test: `tests/test_judgment_loop.py`

**Interfaces:**
- Consumes: `Push.response` (Task 1); existing `StopReason.regression`, `FrameState`, `FrameDelta`.
- Produces: the loop stops with `StopReason.regression` on a `"regressed"` outcome (lowering the frame one level + recording the backslide delta) and every `Push` carries `response=response`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_judgment_loop.py`:

```python
def test_regression_stops_when_student_backslides():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_asserted,  # unmet; will be targeted
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    m = FakeModel(
        intake,
        {"protect_the_core_lane": [
            ResponseClassification(outcome="regressed", mechanism_supplied=False, hard_wrong=False)]},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.regression
    # backslide recorded: present_asserted -> absent, and not credited as closed
    assert any(d.code == "protect_the_core_lane" and d.after is FrameState.absent
               for d in a.frame_deltas)
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    # the raw student response is captured on the push
    assert a.trajectory[-1].response == "reply"
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py::test_regression_stops_when_student_backslides -q`
Expected: FAIL (no regression branch — the loop treats `"regressed"` as unchanged; `stop_reason` is `plateau`/`budget`, no delta, `push.response` is "").

- [ ] **Step 3: Implement in `src/retnovation/assessment/judgment_loop.py`.**

Add a frame-state lowering helper near the top (after the imports / `MAX_PUSHES`):

```python
_LOWER = {
    FrameState.present_reasoned: FrameState.present_asserted,
    FrameState.present_asserted: FrameState.absent,
    FrameState.absent: FrameState.absent,
}


def _lower(state: FrameState) -> FrameState:
    return _LOWER[state]
```

In the loop body, insert the regression branch immediately AFTER the bounded-error `hard_wrong` block and BEFORE the `if rc.outcome == "closed"` block:

```python
        if rc.outcome == "regressed":
            if kind == "frame":
                before = frame_states.get(code, FrameState.absent)
                after = _lower(before)
                frame_states[code] = after
                if after is not before:
                    deltas.append(FrameDelta(code=code, before=before, after=after))
            trajectory.append(
                Push(
                    target_code=code, kind=kind, text=push_text,
                    response_classification=rc.outcome, response=response,
                )
            )
            stop_reason = StopReason.regression
            break
```

Add `response=response` to the existing bounded-error `hard_wrong` `Push(...)` and the normal end-of-loop `Push(...)` so every push carries the raw response. The normal append becomes:

```python
        trajectory.append(
            Push(
                target_code=code, kind=kind, text=push_text,
                response_classification=rc.outcome, response=response,
            )
        )
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS; full suite green (cooperative/bounded/budget unaffected); ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/assessment/judgment_loop.py tests/test_judgment_loop.py docs/DEVLOG.md
git commit -m "feat(judgment): regression stop on a genuine backslide + capture raw responses"
```

---

### Task 5: Distinct-target plateau via target rotation

**Files:**
- Modify: `src/retnovation/assessment/judgment_loop.py`
- Test: `tests/test_judgment_loop.py`

**Interfaces:**
- Consumes: the loop from Task 4.
- Produces: `_select_target(exp, frame_states, trap_states, exhausted)` skips exhausted codes (rotation); the loop fires `StopReason.plateau` when the last two pushes were on distinct codes and neither moved (or when no fresh target remains while not converged).

- [ ] **Step 1: Write the failing test** — append to `tests/test_judgment_loop.py`:

```python
def test_plateau_stops_on_two_distinct_unmoved_targets():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def unchanged():
        return [ResponseClassification(outcome="unchanged", mechanism_supplied=False,
                                       hard_wrong=False)]

    m = FakeModel(intake, {"lead_with_what_you_refuse_to_do": unchanged(),
                           "protect_the_core_lane": unchanged()})
    a = judgment_loop.assess(_exp(), _work(), m)
    assert a.stop_reason is StopReason.plateau
    # rotation happened: the two pushes were on DISTINCT targets
    pushed = [p.target_code for p in a.trajectory]
    assert len(pushed) == 2 and pushed[0] != pushed[1]
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py::test_plateau_stops_on_two_distinct_unmoved_targets -q`
Expected: FAIL — without rotation the loop re-hammers `lead_with_what_you_refuse_to_do` (the FakeModel script for it is exhausted on the 2nd pop → IndexError, or `pushed` are not distinct).

- [ ] **Step 3: Implement in `src/retnovation/assessment/judgment_loop.py`.**

Replace `_select_target` with the rotation-aware version (add the `exhausted` parameter; skip exhausted codes):

```python
def _select_target(exp: Experience, frame_states, trap_states, exhausted):
    """Tripped traps first, then binding-adjacent absent frames, then remaining absent frames.
    Skips codes already exhausted (a non-moving push) so the loop rotates to a fresh angle."""
    for t in exp.rubric.traps:
        if t.trap_code in exhausted:
            continue
        if trap_states.get(t.trap_code) is TrapState.tripped:
            return ("trap", t.trap_code)
    binding = exp.rubric.binding_constraint
    if (
        binding
        and binding not in exhausted
        and frame_states.get(binding) is not None
        and frame_states[binding] is not FrameState.present_reasoned
    ):
        return ("frame", binding)
    for f in exp.rubric.frames:
        if f.frame_code in exhausted:
            continue
        if frame_states.get(f.frame_code) is not FrameState.present_reasoned:
            return ("frame", f.frame_code)
    return None
```

In `assess`, replace the `recent_moved: list[bool] = []` declaration with rotation state:

```python
    exhausted: set[str] = set()
    recent: list[tuple[str, bool]] = []  # (code, moved) for the last pushes
```

Replace the old plateau check block

```python
        if len(recent_moved) >= 2 and not recent_moved[-1] and not recent_moved[-2]:
            stop_reason = StopReason.plateau
            break
```

with the distinct-target check:

```python
        if (
            len(recent) >= 2
            and recent[-1][0] != recent[-2][0]
            and not recent[-1][1]
            and not recent[-2][1]
        ):
            stop_reason = StopReason.plateau
            break
```

Update the target selection call and the `target is None` branch (None now means "out of distinct angles while not converged" → plateau, not converged):

```python
        target = _select_target(exp, frame_states, trap_states, exhausted)
        if target is None:
            stop_reason = StopReason.plateau
            break
        kind, code = target
```

In the move/no-move handling, add the code to `exhausted` when it does not move, and record `(code, moved)`:

```python
        if rc.outcome == "closed" and rc.mechanism_supplied:
            if kind == "frame":
                before = frame_states.get(code, FrameState.absent)
                frame_states[code] = FrameState.present_reasoned
                if before is not FrameState.present_reasoned:
                    deltas.append(
                        FrameDelta(code=code, before=before, after=FrameState.present_reasoned)
                    )
                closed.append(code)
            else:
                trap_states[code] = TrapState.repaired
            moved = True
        else:
            exhausted.add(code)

        trajectory.append(
            Push(
                target_code=code, kind=kind, text=push_text,
                response_classification=rc.outcome, response=response,
            )
        )
        recent.append((code, moved))
```

(Delete the now-unused old `recent_moved.append(moved)` line.)

- [ ] **Step 4: Run to verify pass + full suite**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS — the new plateau test passes; `test_cooperative_student_converges` (every push closes → no rotation), `test_bounded_error_violation_stops_immediately`, and `test_budget_caps_unproductive_loop` (now stops at `plateau`, still in the asserted `(plateau, budget)` set) all stay green; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/assessment/judgment_loop.py tests/test_judgment_loop.py docs/DEVLOG.md
git commit -m "feat(judgment): distinct-target plateau via angle rotation"
```

---

### Task 6: Wire the audit into `assess` + strengthen/extend the loop tests

**Files:**
- Modify: `src/retnovation/assessment/judgment_loop.py`
- Test: `tests/test_judgment_loop.py`

**Interfaces:**
- Consumes: `audit_sharper` (Task 3); the hardened loop (Tasks 4-5).
- Produces: `judgment_loop.assess` returns the audited Assessment (instructor loop → blind grader audit). The cs_technical path and `run_session` are unchanged.

- [ ] **Step 1: Write the failing/strengthened tests.**

Strengthen `test_cooperative_student_converges` in `tests/test_judgment_loop.py` — add at the end:

```python
    # the independent grader ran and confirmed both sharper calls (default-agree FakeModel)
    assert len(a.sharper_audit) == 2
    assert all(item.confirmed for item in a.sharper_audit)
```

Append the full-loop dispute test:

```python
def test_grader_dispute_demotes_a_sharper_call_in_the_full_loop():
    from retnovation.types import SharperVerdict

    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {"lead_with_what_you_refuse_to_do": closed(), "protect_the_core_lane": closed()},
        sharper_verdicts={"protect_the_core_lane": [
            SharperVerdict(sharper=False, reason="assent only")]},
    )
    a = judgment_loop.assess(_exp(), _work(), m)
    # instructor closed both; the blind grader disputes protect_the_core_lane -> demoted
    assert "lead_with_what_you_refuse_to_do" in a.frames_closed_under_pressure
    assert "protect_the_core_lane" not in a.frames_closed_under_pressure
    assert any(i.code == "protect_the_core_lane" and not i.confirmed for i in a.sharper_audit)
```

- [ ] **Step 2: Run to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py -q`
Expected: FAIL — `a.sharper_audit` is empty (the audit is not wired into `assess` yet), so both new assertions fail.

- [ ] **Step 3: Implement in `src/retnovation/assessment/judgment_loop.py`.**

Add the import at the top:

```python
from .sharper_grader import audit_sharper
```

Replace the final `return Assessment(...)` with: build the instructor assessment, then return its blind audit:

```python
    assessment = Assessment(
        trajectory=trajectory,
        frame_deltas=deltas,
        frames_closed_under_pressure=closed,
        hard_wrong_flags=hard_wrong,
        stop_reason=stop_reason or StopReason.budget,
    )
    return audit_sharper(exp, assessment, model)
```

- [ ] **Step 4: Run to verify pass + full suite (founder + CS regression)**

Run: `source .venv/bin/activate && pytest tests/test_judgment_loop.py tests/test_dry_run.py tests/test_orchestration.py tests/test_state.py tests/test_cs_dry_run.py -q && pytest -q && ruff format . && ruff check .`
Expected: PASS — cooperative now asserts 2 confirmed audits; dispute test demotes; `test_dry_run`/`test_orchestration` (cooperative FakeModel default-agrees → behavior preserved) and the CS dry-run stay green; full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/retnovation/assessment/judgment_loop.py tests/test_judgment_loop.py docs/DEVLOG.md
git commit -m "feat(judgment): run the independent grader audit after the instructor loop"
```

---

## Final: adversarial review + completion

After Task 6:

- [ ] **Adversarial core-path review.** Dispatch an independent reviewer subagent (opus) over the whole branch diff against the spec's §9 checklist (regression fires only on a genuine backslide and ends not-present_reasoned; plateau is genuinely distinct-target and the loop always terminates; the grader is blind; a disputed sharper is dropped + delta reverted so `update_state` can't score it strong; conclusion-agnostic prompt; `_require` guard; the bounded hard-wrong flag still pre-empts; founder cooperative + CS + dry-run byte-stable; `Push.response` default safe; every stop traces to an authored `StopReason`). Address every Critical/Important finding; re-run `pytest -q` + `ruff`. Add a DEVLOG entry recording the review and fixes.
- [ ] **Completion.** Use superpowers:finishing-a-development-branch. Add a "Step 5 COMPLETE — build order finished" DEVLOG entry noting the MVP harness is now feature-complete (all 5 locked build-order steps done), and that post-MVP scope (dogfood wiring, deferred items — blend, crystallization mirror, business-exec expansion) is NOT in the locked build order and needs the user's direction.

## Self-Review (author check, completed)

- **Spec coverage:** regression stop (T4) ✓; distinct-target plateau via rotation (T5) ✓; independent blind grader + 2-vote demote/revert (T2/T3/T6) ✓; `Push.response` + audit types (T1) ✓; grader doctrine prompt as data (T2) ✓; cooperative/CS/dry-run regression-safety (T4/T5/T6 verify steps) ✓; adversarial review (Final) ✓.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; every command has expected output.
- **Type consistency:** `grade_sharper(exp, kind, code, push, response) -> SharperVerdict` identical across Protocol/Fake/Anthropic/`audit_sharper`/the loop; `SharperAuditItem` fields match T1↔T3; `Push.response` added T1, populated T4/T5, consumed T3; `audit_sharper(exp, assessment, model) -> Assessment` matches the call in T6; `_select_target(..., exhausted)` new signature matches its T5 call site.
