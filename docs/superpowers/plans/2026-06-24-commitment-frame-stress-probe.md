# Commitment Frame + Stress Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a `genuinely_open` experience that demands a decision stress that decision exactly once before it may converge, so a strong answer gets pushed (and produces a trajectory) instead of silently converging at intake.

**Architecture:** Probe-gated convergence (spec Approach A). A rubric opts in via a declared `decision_frame` (a `frame_code`). The judgment loop blocks convergence and force-selects that frame until it has been pushed once; the push/response model calls become *stress-aware* so an already-reasoned commitment is probed at its sharpest edge (the reversal tripwire) rather than re-elicited. Every rubric without a `decision_frame` hits identical code paths — byte-stable.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, pytest, ruff. Doctrine prompts are markdown in `content/prompts/`. Tests use the in-repo `FakeModel` (no SDK/network) and a duck-typed fake Anthropic client.

**Spec:** `docs/superpowers/specs/2026-06-24-commitment-frame-stress-probe-design.md`

**Branch:** create `commitment-frame-stress-probe` off `main` before Task 1 (the immersive-scenes pattern: feature branch, merge at the end). `main` is ~39 commits ahead of `origin/main`; **do not push** — the user pushes.

## Global Constraints

Every task implicitly includes these (verbatim from the spec / `.claude/CLAUDE.md` / `docs/lessons.md`):

- **Conclusion-agnostic — never grade the conclusion.** The loop outputs a trajectory, not a grade. The stress probe tests the commitment's *reasoning* (its mechanism / reversal tripwire), never whether the commitment is right. "Presence is conclusion-agnostic."
- **Doctrine as data (L-1).** Stress guidance lives in `content/prompts/*.md`, never hardcoded in `src/`. The decision marker is a rubric field, not a code branch keyed on an experience id.
- **Byte-stable fallback.** Every rubric with `decision_frame is None` (the other two founder experiences, all cs_technical) must hit the identical code paths as today. `stress` is always `False` there; both loop guards are no-ops.
- **Fail-loud at load (L-8).** A `decision_frame` that names no existing frame raises at `Rubric` construction.
- **The unlabeled moat holds.** The new `frame_code`/`trap_code` auto-ban their own phrases from the abstract prompt and the seeded scene; neither may appear in either.
- **TDD.** Write the failing test first; run it RED; implement minimally; run GREEN. No production code before a failing test.
- **Per-commit gate** (run before every commit, all must be clean):
  1. `.venv/bin/ruff format .`
  2. `.venv/bin/ruff check .`
  3. `PYTHONPATH=src .venv/bin/pytest -q`
  4. Confidentiality: `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` is **empty**.
  5. `docs/DEVLOG.md` updated in the same commit (a change without a DEVLOG entry did not happen).
  6. Stage **explicit paths only** (never `git add -A` / `-f`). **No `Co-Authored-By` trailer.**
- **Core-path review.** `judgment_loop`, `types`, `model` are core-path: after Task 6, a whole-branch opus adversarial review (Task 7) runs before finishing.
- **Subagent reports** (if using subagent-driven-development) go under `.superpowers/sdd/`; stage only source/test/docs paths (L-7).

Baseline before Task 1: **109 passed, 3 skipped**, ruff clean.

---

### Task 1: `Rubric.decision_frame` field + fail-loud validator

**Files:**
- Modify: `src/retnovation/types.py:74-78` (the `Rubric` model)
- Test: `tests/test_types.py` (create — no test_types.py exists yet)

**Interfaces:**
- Produces: `Rubric(..., decision_frame: str | None = None)`; constructing a `Rubric` whose `decision_frame` is set but is not one of `frames[].frame_code` raises `ValueError`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_types.py`:

```python
import pytest

from retnovation.types import Frame, Mode, Rubric, Trap


def _frame(code="commit_under_the_deadline"):
    return Frame(frame_code=code, frame_detail="commit and name the reversal")


def test_decision_frame_defaults_to_none():
    rub = Rubric(frames=[_frame()], traps=[], mode=Mode.genuinely_open)
    assert rub.decision_frame is None


def test_decision_frame_accepts_an_existing_frame_code():
    rub = Rubric(
        frames=[_frame()],
        traps=[],
        mode=Mode.genuinely_open,
        decision_frame="commit_under_the_deadline",
    )
    assert rub.decision_frame == "commit_under_the_deadline"


def test_decision_frame_naming_a_missing_frame_raises():
    with pytest.raises(ValueError):
        Rubric(
            frames=[_frame()],
            traps=[],
            mode=Mode.genuinely_open,
            decision_frame="not_a_frame",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q`
Expected: FAIL — `test_decision_frame_naming_a_missing_frame_raises` does not raise (no validator yet), and `decision_frame` is rejected as an unknown field / the accept test errors.

- [ ] **Step 3: Add the field + validator** — in `src/retnovation/types.py`, replace the `Rubric` class (currently lines 74-78):

```python
class Rubric(BaseModel):
    frames: list[Frame]
    traps: list[Trap]
    mode: Mode
    binding_constraint: str | None = None
    decision_frame: str | None = None

    @model_validator(mode="after")
    def _decision_frame_in_frames(self) -> "Rubric":
        if self.decision_frame and self.decision_frame not in {f.frame_code for f in self.frames}:
            raise ValueError(f"decision_frame {self.decision_frame!r} is not a rubric frame")
        return self
```

(`model_validator` is already imported at `types.py:8`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_types.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full suite (regression)**

Run: `PYTHONPATH=src .venv/bin/pytest -q`
Expected: PASS — 112 passed, 3 skipped (109 + 3 new).

- [ ] **Step 6: Gate + commit**

```bash
cd /Users/a14808/Documents/Retnovation
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo CLEAN
# add a DEVLOG entry: "Task 1 — Rubric.decision_frame + fail-loud validator (TDD); 112/3 green."
git add src/retnovation/types.py tests/test_types.py docs/DEVLOG.md
git commit -m "feat(types): Rubric.decision_frame + fail-loud validator"
```

---

### Task 2: `content_loader` threads `decision_frame`

**Files:**
- Modify: `src/retnovation/content_loader.py:30-37` (`load_rubric`) and `:67-81` (`load_experience`)
- Test: `tests/test_content_loader.py` (append)

**Interfaces:**
- Consumes: `Rubric(..., decision_frame=...)` (Task 1).
- Produces: `load_rubric(name, root)` and `load_experience(name, root)` set `rubric.decision_frame` from the YAML key `decision_frame` (absent key → `None`).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_content_loader.py`:

```python
def _write_decision_rubric(tmp_path):
    import textwrap

    rdir = tmp_path / "rubrics"
    rdir.mkdir()
    (rdir / "x.yaml").write_text(
        textwrap.dedent(
            """
            experience_id: x
            ledger_ref: "veldra:x"
            regime: open_ended
            mode: genuinely_open
            binding_constraint: null
            prompt: "A same-day call forces a real trade-off."
            decision_frame: f1
            frames:
              - frame_code: f1
                frame_detail: commit and name the reversal
            traps: []
            """
        )
    )
    return tmp_path


def test_load_rubric_threads_decision_frame(tmp_path):
    root = _write_decision_rubric(tmp_path)
    rub = content_loader.load_rubric("x", root=root)
    assert rub.decision_frame == "f1"


def test_load_experience_threads_decision_frame(tmp_path):
    root = _write_decision_rubric(tmp_path)
    exp = content_loader.load_experience("x", root=root)
    assert exp.rubric.decision_frame == "f1"


def test_load_rubric_without_decision_frame_is_none():
    rub = content_loader.load_rubric("license_continuity")
    assert rub.decision_frame is None  # not yet authored on the real rubric until Task 6
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q -k decision_frame`
Expected: FAIL — `load_rubric`/`load_experience` drop the key, so `decision_frame` is `None` (the two threading tests fail).

- [ ] **Step 3: Thread the field** — in `src/retnovation/content_loader.py`, update `load_rubric` (lines 32-37) to add `decision_frame`:

```python
    return Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=data["mode"],
        binding_constraint=data.get("binding_constraint"),
        decision_frame=data.get("decision_frame"),
    )
```

And in `load_experience` (the inner `Rubric(...)` at lines 69-74):

```python
    rubric = Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=Mode(data["mode"]),
        binding_constraint=data.get("binding_constraint"),
        decision_frame=data.get("decision_frame"),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "Task 2 — content_loader threads decision_frame in load_rubric + load_experience; 115/3 green."
git add src/retnovation/content_loader.py tests/test_content_loader.py docs/DEVLOG.md
git commit -m "feat(content_loader): thread decision_frame through load_rubric and load_experience"
```
Expected suite: 115 passed, 3 skipped.

---

### Task 3: Probe-gated convergence in the judgment loop (+ `stress` kwarg on the model contract)

**Files:**
- Modify: `src/retnovation/assessment/judgment_loop.py` (`_select_target` :30-51, `_converged` :54-59, `assess` :62-99)
- Modify: `src/retnovation/model.py` — add keyword-only `stress: bool = False` to the `Model` protocol (`:36`, `:37-39`), `FakeModel.generate_push` (`:66`) and `FakeModel.classify_response` (`:69-72`), and `AnthropicModel.generate_push` (`:192`) and `AnthropicModel.classify_response` (`:210-212`) signatures (AnthropicModel **ignores** it this task; rendering lands in Tasks 4-5).
- Test: `tests/test_judgment_loop.py` (append)

**Interfaces:**
- Consumes: `Rubric.decision_frame` (Task 1).
- Produces: `assess(exp, work, model)` — when `exp.rubric.decision_frame` is set, that frame is force-selected before any other target and the loop may not converge until it has been pushed once; the loop calls `model.generate_push(exp, kind, code, stress=stress)` and `model.classify_response(exp, kind, code, push, response, stress=stress)` where `stress = kind == "frame" and frame_states.get(code) is FrameState.present_reasoned`. Model contract methods now accept keyword-only `stress: bool = False`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_judgment_loop.py` (add `Trap` is already imported; add a decision-frame experience builder):

```python
def _exp_decision():
    rub = Rubric(
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="boundary first",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="keep core",
                paired_trap="erode_core_for_one_customer",
            ),
            Frame(
                frame_code="commit_under_the_deadline",
                frame_detail="commit, own the trade, name the reversal",
                paired_trap="commit_without_a_tripwire",
            ),
        ],
        traps=[
            Trap(trap_code="scope_creep_to_please", trap_detail="bend to please"),
            Trap(trap_code="erode_core_for_one_customer", trap_detail="special-case"),
            Trap(trap_code="commit_without_a_tripwire", trap_detail="no reversal line"),
        ],
        mode=Mode.genuinely_open,
        binding_constraint=None,
        decision_frame="commit_under_the_deadline",
    )
    return Experience(
        experience_id="veldra:license_continuity",
        prompt="...",
        rubric=rub,
        ledger_ref="veldra:license_continuity",
        regime=Regime.open_ended,
    )


def _all_reasoned_intake():
    return IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
            "commit_under_the_deadline": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )


def test_decision_frame_forces_one_stress_probe_before_converging():
    # The dogfood repro: a strong answer rated all-present_reasoned at intake must NOT converge
    # silently — the decision frame is stressed exactly once, then the loop converges.
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(outcome="unchanged", mechanism_supplied=False, hard_wrong=False)
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert len(a.trajectory) == 1
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_decision_frame_stress_probe_can_be_credited_sharper():
    m = FakeModel(
        _all_reasoned_intake(),
        {
            "commit_under_the_deadline": [
                ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
            ]
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    assert a.stop_reason is StopReason.converged
    assert "commit_under_the_deadline" in a.frames_closed_under_pressure
    assert len(a.trajectory) == 1


def test_decision_frame_absent_is_targeted_first():
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.absent,
            "protect_the_core_lane": FrameState.absent,
            "commit_under_the_deadline": FrameState.absent,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
            "commit_without_a_tripwire": TrapState.not_tripped,
        },
    )

    def closed():
        return [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]

    m = FakeModel(
        intake,
        {
            "commit_under_the_deadline": closed(),
            "lead_with_what_you_refuse_to_do": closed(),
            "protect_the_core_lane": closed(),
        },
    )
    a = judgment_loop.assess(_exp_decision(), _work(), m)
    # without the force, rubric order would target lead_with_what_you_refuse_to_do first
    assert a.trajectory[0].target_code == "commit_under_the_deadline"


def test_no_decision_frame_all_reasoned_still_converges_at_intake():
    # Byte-stability lock: a rubric with no decision_frame keeps today's behavior —
    # an all-present_reasoned opening converges immediately with an empty trajectory.
    intake = IntakeClassification(
        frame_states={
            "lead_with_what_you_refuse_to_do": FrameState.present_reasoned,
            "protect_the_core_lane": FrameState.present_reasoned,
        },
        trap_states={
            "scope_creep_to_please": TrapState.not_tripped,
            "erode_core_for_one_customer": TrapState.not_tripped,
        },
    )
    a = judgment_loop.assess(_exp(), _work(), FakeModel(intake, {}))
    assert a.stop_reason is StopReason.converged
    assert a.trajectory == []
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_judgment_loop.py -q -k "decision_frame"`
Expected: FAIL — `test_decision_frame_forces_one_stress_probe_before_converging` gets `len(a.trajectory) == 0` (today's loop converges at intake), and `test_decision_frame_absent_is_targeted_first` gets `lead_with_what_you_refuse_to_do` first. (`test_no_decision_frame_all_reasoned_still_converges_at_intake` already passes — it is the regression lock.)

- [ ] **Step 3: Add the `stress` kwarg to the model contract** — in `src/retnovation/model.py`:

`Model` protocol (lines 36-39):
```python
    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str: ...
    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str, *, stress: bool = False
    ) -> ResponseClassification: ...
```

`FakeModel.generate_push` (line 66) and `FakeModel.classify_response` (lines 69-72) — accept and ignore:
```python
    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str:
        return f"[push:{kind}]"

    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str, *, stress: bool = False
    ) -> ResponseClassification:
        return self._responses[code].pop(0)
```

`AnthropicModel.generate_push` (line 192) and `AnthropicModel.classify_response` (lines 210-212) — add the kwarg to the signature only (rendering in Tasks 4-5):
```python
    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str:
```
```python
    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str, *, stress: bool = False
    ) -> ResponseClassification:
```

- [ ] **Step 4: Implement the loop guards** — in `src/retnovation/assessment/judgment_loop.py`:

Replace `_select_target` (lines 30-51) signature + add the force branch at the top:
```python
def _select_target(exp: Experience, frame_states, trap_states, exhausted, probed):
    """Forced decision frame first (once), then tripped traps, binding-adjacent absent frames,
    then remaining absent frames. Skips codes already exhausted (a non-moving push)."""
    df = exp.rubric.decision_frame
    if df is not None and df not in probed and df not in exhausted:
        return ("frame", df)
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

Replace `_converged` (lines 54-59):
```python
def _converged(frame_states, trap_states, exp, probed) -> bool:
    # A rubric that declares a decision_frame may not converge until that frame has been
    # stressed once — even if intake rated it present_reasoned (the silence-when-strong fix).
    df = exp.rubric.decision_frame
    if df is not None and df not in probed:
        return False
    frames_ok = all(s is FrameState.present_reasoned for s in frame_states.values())
    traps_ok = all(s is not TrapState.tripped for s in trap_states.values())
    return frames_ok and traps_ok
```

In `assess` — add a `probed` set next to `exhausted` (line 71):
```python
    exhausted: set[str] = set()
    probed: set[str] = set()
```

Update the convergence check (line 76) and target selection (line 91), and derive + pass `stress` (lines 95-99). The relevant block becomes:
```python
    while True:
        if _converged(frame_states, trap_states, exp, probed):
            stop_reason = StopReason.converged
            break
        if len(trajectory) >= MAX_PUSHES:
            stop_reason = StopReason.budget
            break
        if (
            len(recent) >= 2
            and recent[-1][0] != recent[-2][0]
            and not recent[-1][1]
            and not recent[-2][1]
        ):
            stop_reason = StopReason.plateau
            break

        target = _select_target(exp, frame_states, trap_states, exhausted, probed)
        if target is None:
            stop_reason = StopReason.plateau
            break
        kind, code = target

        stress = kind == "frame" and frame_states.get(code) is FrameState.present_reasoned
        probed.add(code)
        push_text = model.generate_push(exp, kind, code, stress=stress)
        response = work.respond(push_text)
        rc = model.classify_response(exp, kind, code, push_text, response, stress=stress)
```

(Everything below line 99 — the hard_wrong / regressed / closed handling, the `Push` append, `recent.append` — is unchanged.)

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_judgment_loop.py -q`
Expected: PASS — the 6 existing loop tests + 4 new (3 feature + 1 regression lock).

- [ ] **Step 6: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "Task 3 — probe-gated convergence (decision_frame force + probed set + stress flag);
#          model contract gains keyword-only stress (AnthropicModel ignores until T4-5); 119/3 green."
git add src/retnovation/assessment/judgment_loop.py src/retnovation/model.py tests/test_judgment_loop.py docs/DEVLOG.md
git commit -m "feat(judgment): probe-gated convergence so a declared decision_frame is stressed once"
```
Expected suite: 119 passed, 3 skipped.

---

### Task 4: Stress-aware `generate_push` (+ `push_stress.md`)

**Files:**
- Create: `content/prompts/push_stress.md`
- Modify: `src/retnovation/model.py:192-208` (`AnthropicModel.generate_push` body)
- Test: `tests/test_anthropic_model.py` (append)

**Interfaces:**
- Consumes: `generate_push(..., *, stress: bool = False)` signature (Task 3).
- Produces: when `stress=True`, the push system prompt = `load_prompt("push") + "\n\n" + load_prompt("push_stress")`; when `stress=False`, it is byte-identical to today (`load_prompt("push")` only).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_anthropic_model.py`:

```python
def test_generate_push_stress_mode_adds_the_stress_doctrine():
    client = _Client(create_result=_Resp(content=[_TextBlock("What would reverse this?")]))
    AnthropicModel(client=client).generate_push(
        _exp(), "frame", "protect_the_core_lane", stress=True
    )
    blob = _system_text(client.messages.create_calls[0])
    assert "already engaged this angle" in blob  # marker from push_stress.md


def test_generate_push_without_stress_is_byte_stable():
    client = _Client(create_result=_Resp(content=[_TextBlock("push")]))
    AnthropicModel(client=client).generate_push(_exp(), "frame", "protect_the_core_lane")
    blob = _system_text(client.messages.create_calls[0])
    assert "already engaged this angle" not in blob  # no stress doctrine when stress=False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_anthropic_model.py -q -k stress`
Expected: FAIL — `push_stress.md` does not exist / is not loaded, so the marker is absent when `stress=True`.

- [ ] **Step 3: Create `content/prompts/push_stress.md`**:

```markdown
## Stress mode (the angle is already reasoned)

The student has already engaged this angle with a reasoned mechanism. Do not ask them to
re-engage it or restate what they already argued — that would be a weak, redundant push.
Probe the sharpest edge instead:

- The single event that would force them to reverse this commitment (the tripwire). If they
  cannot name one, press on what that absence implies.
- What they are choosing NOT to commit to, and the cost they accept by leaving it out.
- The failure mode they are walking into with eyes open.

Still one push, still phrased from the angle, never named. Never hand the answer. Never grade
the conclusion — a different conclusion reasoned under stress still counts.
```

- [ ] **Step 4: Implement the stress branch** — in `src/retnovation/model.py`, update `generate_push` (lines 192-202) so the system prompt appends the stress doctrine when `stress=True`:

```python
    def generate_push(self, exp: Experience, kind: str, code: str, *, stress: bool = False) -> str:
        detail = _target_detail(exp.rubric, kind, code)
        prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""
        user = f"{prefix}Experience:\n{exp.prompt}\n\nAngle to push on:\n{detail}"
        system = load_prompt("push")
        if stress:
            system += "\n\n" + load_prompt("push_stress")
        resp = self._get_client().messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            **_PARAMS,
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise ModelError("push generation refused")
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ModelError("no text block in push response")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_anthropic_model.py -q`
Expected: PASS (existing model tests + 2 new).

- [ ] **Step 6: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "Task 4 — stress-aware generate_push: push_stress.md appended only when stress=True;
#          byte-stable otherwise; 121/3 green."
git add content/prompts/push_stress.md src/retnovation/model.py tests/test_anthropic_model.py docs/DEVLOG.md
git commit -m "feat(model): stress-aware generate_push via conditional push_stress doctrine"
```
Expected suite: 121 passed, 3 skipped.

---

### Task 5: Stress-aware `classify_response` (+ `response_stress.md`)

**Files:**
- Create: `content/prompts/response_stress.md`
- Modify: `src/retnovation/model.py:210-230` (`AnthropicModel.classify_response` body)
- Test: `tests/test_anthropic_model.py` (append)

**Interfaces:**
- Consumes: `classify_response(..., *, stress: bool = False)` signature (Task 3).
- Produces: when `stress=True`, the response system prompt inserts `load_prompt("response_stress")` between `load_prompt("response")` and the situation/mode/target lines; when `stress=False`, byte-identical to today.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_anthropic_model.py`:

```python
def test_classify_response_stress_mode_adds_the_stress_doctrine():
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    client = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=client).classify_response(
        _exp(), "frame", "protect_the_core_lane", "push", "reply", stress=True
    )
    sys = _system_text(client.messages.parse_calls[0])
    assert "deepening mechanism" in sys  # marker from response_stress.md


def test_classify_response_without_stress_is_byte_stable():
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    client = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=client).classify_response(
        _exp(), "frame", "protect_the_core_lane", "push", "reply"
    )
    sys = _system_text(client.messages.parse_calls[0])
    assert "deepening mechanism" not in sys  # no stress doctrine when stress=False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_anthropic_model.py -q -k "stress and response"`
Expected: FAIL — `response_stress.md` not loaded; marker absent when `stress=True`.

- [ ] **Step 3: Create `content/prompts/response_stress.md`**:

```markdown
## Stress mode

This reply answers a stress push on an angle the student already reasoned. Under stress:

- `closed` — the student supplied a NEW deepening mechanism: named the reversal tripwire, the
  cost of what they are not committing to, or the failure they accept. The angle got sharper.
- `unchanged` — they restated the commitment with no new mechanism. Nothing deepened.
- `regressed` — they abandoned the committed position or weakened it.

Still conclusion-agnostic. Never grade the conclusion — a well-reasoned different choice still
closes the gap when a new mechanism is supplied.
```

- [ ] **Step 4: Implement the stress branch** — in `src/retnovation/model.py`, update `classify_response` (lines 210-220) to insert the stress doctrine after the base prompt:

```python
    def classify_response(
        self, exp: Experience, kind: str, code: str, push: str, response: str, *, stress: bool = False
    ) -> ResponseClassification:
        detail = _target_detail(exp.rubric, kind, code)
        system = (
            load_prompt("response")
            + (("\n\n" + load_prompt("response_stress")) if stress else "")
            + _situation_block(exp)
            + f"\n\nMode: {exp.rubric.mode.value}"
            + f"\nBinding constraint: {exp.rubric.binding_constraint}"
            + f"\nTarget angle: {detail}"
        )
        user = f"Push:\n{push}\n\nStudent reply:\n{response}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=ResponseClassification,
            **_PARAMS,
        )
        return _require(resp)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_anthropic_model.py -q`
Expected: PASS.

- [ ] **Step 6: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
# DEVLOG: "Task 5 — stress-aware classify_response: response_stress.md inserted only when stress=True;
#          byte-stable otherwise; 123/3 green."
git add content/prompts/response_stress.md src/retnovation/model.py tests/test_anthropic_model.py docs/DEVLOG.md
git commit -m "feat(model): stress-aware classify_response via conditional response_stress doctrine"
```
Expected suite: 123 passed, 3 skipped.

---

### Task 6: Author the `commit_under_the_deadline` frame on `license_continuity`

**Files:**
- Modify: `content/rubrics/license_continuity.yaml`
- Test: `tests/test_content_loader.py` (append) and re-run `tests/test_generator.py` (moat/gate — no new test needed there; `test_every_authored_rubric_passes_the_gate_and_clears_eight_angles` and `test_seeded_license_scene_clears_the_moat` cover it)

**Interfaces:**
- Consumes: the loader threading (Task 2) and the loop force (Task 3).
- Produces: the real `license_continuity` rubric carries `decision_frame: commit_under_the_deadline`, 3 frames / 3 traps (angle_count 10), and still clears the anti-label gate and the seeded-scene moat.

- [ ] **Step 1: Write the failing test** — append to `tests/test_content_loader.py`:

```python
def test_license_continuity_declares_the_commitment_decision_frame():
    rub = content_loader.load_rubric("license_continuity")
    assert rub.decision_frame == "commit_under_the_deadline"
    assert any(f.frame_code == "commit_under_the_deadline" for f in rub.frames)
    assert any(t.trap_code == "commit_without_a_tripwire" for t in rub.traps)
```

(Note: `test_load_rubric_without_decision_frame_is_none` from Task 2 asserted the OLD state. Update that test in the same step to reflect the new reality — change its body to assert a *different* rubric with no decision_frame, or delete it since Task 6 supersedes it. Replace it with:)

```python
def test_a_rubric_without_a_decision_frame_loads_with_none(tmp_path):
    import textwrap

    rdir = tmp_path / "rubrics"
    rdir.mkdir()
    (rdir / "y.yaml").write_text(
        textwrap.dedent(
            """
            experience_id: y
            ledger_ref: "veldra:y"
            regime: open_ended
            mode: genuinely_open
            binding_constraint: null
            prompt: "p"
            frames:
              - frame_code: f1
                frame_detail: d
            traps: []
            """
        )
    )
    assert content_loader.load_rubric("y", root=tmp_path).decision_frame is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q -k commitment`
Expected: FAIL — the real rubric has no `commit_under_the_deadline` frame yet.

- [ ] **Step 3: Edit `content/rubrics/license_continuity.yaml`** — add the frame, the trap, and the `decision_frame` pointer (keep `mode: open_ended`/`genuinely_open` semantics and the existing two frames/traps; the file's current `experience_id`, `ledger_ref`, `regime`, `prompt` lines are unchanged):

```yaml
frames:
  - frame_code: lead_with_what_you_refuse_to_do
    frame_detail: State the boundary you will not cross before proposing any action.
    paired_trap: scope_creep_to_please
  - frame_code: protect_the_core_lane
    frame_detail: Keep the promise the core product makes to everyone intact under pressure.
    paired_trap: erode_core_for_one_customer
  - frame_code: commit_under_the_deadline
    frame_detail: Commit to a decision today, account for what you trade for it, and name what would force you to reverse.
    paired_trap: commit_without_a_tripwire
traps:
  - trap_code: scope_creep_to_please
    trap_detail: Bending the offer to avoid saying no.
  - trap_code: erode_core_for_one_customer
    trap_detail: Special-casing one account in a way that weakens the core promise.
  - trap_code: commit_without_a_tripwire
    trap_detail: Committing to a course without naming what would make you reverse it.
decision_frame: commit_under_the_deadline
```

- [ ] **Step 4: Run the content + moat + gate tests**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py tests/test_generator.py -q`
Expected: PASS. Specifically `test_every_authored_rubric_passes_the_gate_and_clears_eight_angles` confirms the new abstract prompt does not leak `commit under the deadline` / `commit without a tripwire` and `angle_count == 10`. `test_seeded_license_scene_clears_the_moat` runs only if `data/retnovation.db` has the scene (the user's machine); it confirms the gitignored escrow scene still clears the moat against the new codes.

  **If `test_seeded_license_scene_clears_the_moat` FAILS** (the authored scene contains a now-banned phrase): reword the **gitignored scene** in `data/seed/veldra_ledger.yaml` so it no longer contains "commit under the deadline" / "commit without a tripwire" (or underscore forms), then re-ingest with `PYTHONPATH=src .venv/bin/python -m retnovation.veldra_ingest` and re-run. **Never weaken the gate.** The seed/db stay gitignored/untracked.

- [ ] **Step 5: Full suite + gate + commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check . && PYTHONPATH=src .venv/bin/pytest -q
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf' || echo CLEAN
git status --short   # confirm data/ is NOT staged (gitignored)
# DEVLOG: "Task 6 — license_continuity gains commit_under_the_deadline frame + commit_without_a_tripwire
#          trap + decision_frame (10 angles); gate + seeded-scene moat green; 124/3."
git add content/rubrics/license_continuity.yaml tests/test_content_loader.py docs/DEVLOG.md
git commit -m "feat(content): commit_under_the_deadline decision frame on license_continuity"
```
Expected suite: 124 passed, 3 skipped.

---

### Task 7: Whole-branch adversarial review + finish (CONTROLLER — not an implementer subagent)

**Files:** none new — review + (if findings) targeted fixes.

- [ ] **Step 1: Dispatch an independent opus adversarial review** of the whole branch diff (`git diff main...HEAD`) against the spec's §3 doctrine and §6 edge cases. The review checklist:
  - **Conclusion-agnostic:** the stress push (`push_stress.md`) and classification (`response_stress.md`) never grade the conclusion; "closed under stress" credits only a *supplied mechanism*. Verify against `grade_sharper.md` (the blind auditor is already conclusion-agnostic).
  - **Byte-stability:** for any rubric with `decision_frame is None`, `assess` produces an identical trajectory to `main` (the `test_no_decision_frame_all_reasoned_still_converges_at_intake` lock plus a spot diff of `generate_push`/`classify_response` system prompts with `stress=False`).
  - **The force fires exactly once:** `probed` guarantees the decision frame is pushed once; it cannot loop the decision frame forever (after one push it is in `probed`, and `exhausted` if unmoved).
  - **Moat:** the new frame/trap codes do not leak into the abstract prompt or the seeded scene; the gate test passes hermetically (synthetic corpus).
  - **No new `stop_reason`; state machine unchanged below the push call.**
  - **Confidentiality:** `git ls-files` confidential grep empty; `data/` untracked.
- [ ] **Step 2: Address findings** as additive fixes (own commits, same gate). Re-run the full suite.
- [ ] **Step 3: Re-dogfood** (optional, live): present the escrow scene, commit a strong answer, confirm the instructor now issues exactly one stress probe on the commitment (asks for the reversal tripwire) instead of going silent. Capture the trajectory in `docs/DEVLOG.md`.
- [ ] **Step 4: Finish** — invoke `superpowers:finishing-a-development-branch` to merge `commitment-frame-stress-probe` into `main`. **Do not push** unless the user asks. Update memory `retnovation-commitment-frame-gap` to resolved (link the spec/plan), and note the progression/intro-arc thread is still open.

---

## Self-Review

**Spec coverage:**
- §5.1 data model → Task 1. ✓
- §5.2 loop (probed, `_converged`, `_select_target`, stress derivation) → Task 3. ✓
- §5.3 stress-aware push/response → Tasks 4 (push) + 5 (response). **Refinement vs. spec:** the spec described "a Stress mode block in push.md + an activation line"; the plan instead uses **separate `push_stress.md` / `response_stress.md` files loaded only when `stress=True`**. This is a strictly cleaner realization of the same intent and makes the spec's byte-stability guarantee trivially true (the stress doctrine is absent from the prompt unless stressed). Documented here and in the Task 4/5 interfaces.
- §5.4 content → Task 6. ✓
- §6 edge cases → covered by Task 3 tests (forced-probe/unchanged, absent-targeted-first, no-decision-frame lock) + Task 7 review; "closed/credited" → Task 3 `test_decision_frame_stress_probe_can_be_credited_sharper`. ✓
- §7 testing → each task's tests; loader threading via tmp fixtures (Task 2), gate/moat (Task 6). ✓
- §8 build order → Tasks 1-7 in the spec's order (types → loader → loop → push → response → content → review). ✓
- Loader threads BOTH `load_rubric` and `load_experience` (spec §5.1 implied "loader"; the codebase has two constructors) → Task 2 covers both. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; every command shows expected output. ✓

**Type consistency:** `decision_frame: str | None` (Task 1) is read in Task 2 (`data.get("decision_frame")`), Task 3 (`exp.rubric.decision_frame`), Task 6 (YAML). `stress: bool = False` keyword-only is identical across the `Model` protocol, `FakeModel`, and `AnthropicModel` (Tasks 3-5). Markers `"already engaged this angle"` (push_stress) and `"deepening mechanism"` (response_stress) are authored in Tasks 4/5 exactly as the tests assert. `frame_code`/`trap_code` strings (`commit_under_the_deadline`, `commit_without_a_tripwire`) are identical across Tasks 3 (test fixture) and 6 (real content). ✓
