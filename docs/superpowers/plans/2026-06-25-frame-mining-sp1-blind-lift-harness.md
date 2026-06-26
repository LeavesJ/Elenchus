# Frame Mining — Sub-project 1 (Blind-Lift Harness) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the automated `marginal_lift` blind-lift screen — given a candidate frame, generate framed-vs-control outputs on unlabeled scenarios via Opus, blind-rate them, and return a two-axis `LiftResult` that automates the unambiguous kill and surfaces everything else for human adjudication.

**Architecture:** A new pure-orchestration module (`lift_test.py`) over three additive `Model` methods (`generate_output`, `rate_preference`, `check_injection_expressed`). All result types carry both raw axes (distinguishability + signed preference) and derive `status`/`verdict`/`screen_action` as computed views (never stored bools). The whole sub-project is additive — nothing existing depends on it, so every commit is green.

**Tech Stack:** Python 3, pydantic v2, Anthropic SDK (Opus 4.8, lazy/mocked), pytest, ruff, PyYAML.

**Spec:** `docs/superpowers/specs/2026-06-25-frame-mining-spine-expansion-design.md` §4 (read §4.1–§4.7 before starting; §2 for the doctrine).

## Global Constraints

- Tests run with `PYTHONPATH=src .venv/bin/pytest -q`. Baseline **168 passed / 3 skipped** (the 3 are `@pytest.mark.live`). **Every commit must leave the suite green** (all tasks are additive).
- Before every commit: `.venv/bin/ruff format .` then `.venv/bin/ruff check .` (both clean).
- Stage **explicit paths only** — never `git add -A`, never `-f` (L-7). **No `Co-Authored-By` trailer.**
- **DEVLOG:** implementers do **not** update `docs/DEVLOG.md` per task (it would be noise); the controller adds **one consolidated entry at sub-project completion** (the P1/P2/P3 convention). So the per-task pre-commit DEVLOG gate is satisfied at the sub-project level, not per commit.
- **Confidentiality (L-2, the spec's headline fix):** the real scenario bank `content/lift/scenarios.yaml` is **gitignored**; only `content/lift/scenarios.example.yaml` is committed. Result logs live under `data/lift/` (already gitignored via `/data/`). The confidential gate `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'` stays empty, **and** `git ls-files | grep -E 'content/lift/scenarios\.yaml$'` must be empty.
- **Doctrine-as-data (L-1):** thresholds (`theta_dist`, `min_scenarios`) live in `content/lift/lift.yaml`, not in `src/`.
- **Structured-output discipline:** model calls that parse output use `messages.parse(..., output_format=<pydantic>)` guarded by `_require` (never silently default); `generate_output` uses `messages.create` and **captures a refusal as text (does NOT raise)** — a deliberate divergence from `generate_push` (model.py:222), because a control refusal is lift signal (EXP-002 B2).
- **Doctrine invariants:** both axes raw, `status`/`verdict`/`screen_action` derived (no stored `lift` bool); the manipulation check is a **separate primed** call that **gates** the scenario (un-expressed → inconclusive, excluded from aggregation); same-model rater; unprimed preference rater.

## File Structure

- `src/retnovation/types.py` — **modify**: add `CandidateFrame`, `LiftScenario`, `GeneratedOutput`, `PreferenceRating`, `InjectionExpressed`, `ScenarioVerdict` (+ `status()` method), `LiftResult` (+ derived `verdict`/`screen_action`/aggregate properties).
- `src/retnovation/content_loader.py` — **modify**: `load_lift_config`, `load_lift_scenarios`.
- `src/retnovation/model.py` — **modify**: 3 additive `Model` Protocol methods + `AnthropicModel` impls + a new `FakeLiftModel`.
- `src/retnovation/lift_test.py` — **create**: `randomize`, `un_randomize`, `run_lift_test`.
- `content/lift/lift.yaml` — **create**: config (committable).
- `content/lift/scenarios.example.yaml` — **create**: committable structural stub.
- `content/prompts/lift_rate.md`, `content/prompts/lift_manipulation.md` — **create**: the two prompts.
- `.gitignore` — **modify**: ignore the real scenario bank.
- `docs/lessons.md` — **modify**: extend the confidential-docs gate.
- Tests: `tests/test_lift_types.py`, `tests/test_content_loader.py` (extend), `tests/test_lift_model.py`, `tests/test_lift_test.py`, `tests/test_lift_acceptance.py`.

---

### Task 1: Result types + derived logic (the two-axis truth table)

**Files:**
- Modify: `src/retnovation/types.py`
- Test: `tests/test_lift_types.py`

**Interfaces:**
- Consumes: pydantic `BaseModel`, `Literal` (add `from typing import Literal` if not present — it is already imported in model.py but check types.py).
- Produces:
  - `CandidateFrame(frame_code: str, frame_detail: str, injection: str)`
  - `LiftScenario(scenario_id: str, prompt: str, posture: str)`
  - `GeneratedOutput(text: str, refused: bool = False)`
  - `PreferenceRating(distinguishability: int, preferred: Literal["A","B","tie"], magnitude: int, key_difference: str)`
  - `InjectionExpressed(expressed: bool, evidence: str)`
  - `ScenarioVerdict(scenario_id, injection_expressed, distinguishability=0, preference=0, key_difference="", framed_output="", control_output="", framed_refused=False, control_refused=False)` with `status(theta_dist: int) -> str` ∈ {inconclusive, null, lift, neutral, negative}.
  - `LiftResult(frame_code, scenarios: list[ScenarioVerdict], theta_dist=1, min_scenarios=3)` with properties `inconclusive_count`, `framed_preferred_count`, `mean_preference`, `mean_distinguishability`, `verdict`, `screen_action`, `below_floor`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lift_types.py`:

```python
from retnovation.types import LiftResult, ScenarioVerdict


def _sv(sid, expressed=True, dist=2, pref=1):
    return ScenarioVerdict(
        scenario_id=sid, injection_expressed=expressed, distinguishability=dist, preference=pref
    )


def test_scenario_status_cells():
    assert _sv("s", expressed=False).status(1) == "inconclusive"
    assert _sv("s", dist=0, pref=-1).status(1) == "null"        # below tie-band floor
    assert _sv("s", dist=1, pref=0).status(1) == "neutral"      # tie
    assert _sv("s", dist=2, pref=1).status(1) == "lift"
    assert _sv("s", dist=1, pref=-1).status(1) == "negative"
    assert _sv("s", dist=1, pref=1).status(2) == "null"         # theta_dist=2 -> dist 1 is a wash


def _result(*svs):
    return LiftResult(frame_code="f", scenarios=list(svs), theta_dist=1, min_scenarios=3)


def test_verdict_precedence_is_total():
    assert _result().verdict == "inconclusive"
    assert _result(_sv("a", expressed=False)).verdict == "inconclusive"  # no valid
    assert _result(_sv("a", pref=1), _sv("b", pref=2)).verdict == "lift"  # all lift
    assert _result(_sv("a", pref=1), _sv("b", pref=0)).verdict == "mixed"  # lift + neutral
    assert _result(_sv("a", pref=1), _sv("b", pref=-1)).verdict == "mixed"  # lift + negative
    assert _result(_sv("a", pref=1), _sv("b", dist=0)).verdict == "mixed"  # lift + null
    assert _result(_sv("a", pref=-1), _sv("b", pref=0)).verdict == "negative_lift"  # neg + neutral
    assert _result(_sv("a", pref=-1), _sv("b", dist=0)).verdict == "negative_lift"  # neg + null
    assert _result(_sv("a", pref=0), _sv("b", dist=0)).verdict == "neutral"  # neutral + null
    assert _result(_sv("a", dist=0), _sv("b", dist=0)).verdict == "null"  # all null


def test_screen_action_and_aggregates():
    # auto_kill ONLY on null / negative_lift
    assert _result(_sv("a", dist=0)).screen_action == "auto_kill"        # null
    assert _result(_sv("a", pref=-1)).screen_action == "auto_kill"       # negative_lift
    assert _result(_sv("a", pref=1)).screen_action == "surface"          # lift
    assert _result(_sv("a", pref=1), _sv("b", pref=-1)).screen_action == "surface"  # mixed
    assert _result(_sv("a", pref=0)).screen_action == "surface"          # neutral surfaces
    assert _result(_sv("a", expressed=False)).screen_action == "surface"  # all-inconclusive never kills
    # framed_preferred_count EXCLUDES ties; inconclusive excluded from valid aggregates
    r = _result(_sv("a", pref=2), _sv("b", pref=0), _sv("c", expressed=False))
    assert r.framed_preferred_count == 1  # the tie (b) and inconclusive (c) don't count
    assert r.inconclusive_count == 1
    assert r.mean_preference == 1.0  # (2 + 0) / 2 valid
    assert r.below_floor is True  # 2 valid < min_scenarios 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_types.py -q`
Expected: FAIL with `ImportError` (`LiftResult`/`ScenarioVerdict` not defined).

- [ ] **Step 3: Write the implementation**

In `src/retnovation/types.py`: ensure `from typing import Literal` is imported (add it to the existing `from __future__`-adjacent imports if missing — model.py already uses `Literal`, types.py may not). Add near the other `BaseModel` types (after `SelectionReceipt`):

```python
class CandidateFrame(BaseModel):
    frame_code: str
    frame_detail: str  # carried for SP2/3; the screen never reads it
    injection: str


class LiftScenario(BaseModel):
    scenario_id: str
    prompt: str
    posture: str  # carried for SP2; not read by the screen


class GeneratedOutput(BaseModel):
    text: str
    refused: bool = False


class PreferenceRating(BaseModel):
    distinguishability: int  # 0..3
    preferred: Literal["A", "B", "tie"]
    magnitude: int  # 0..2; 0 iff tie
    key_difference: str


class InjectionExpressed(BaseModel):
    expressed: bool
    evidence: str


class ScenarioVerdict(BaseModel):
    scenario_id: str
    injection_expressed: bool  # the ONLY stored bool that gates aggregation
    distinguishability: int = 0
    preference: int = 0  # signed toward FRAMED after un-randomization; 0 = tie
    key_difference: str = ""
    framed_output: str = ""
    control_output: str = ""
    framed_refused: bool = False
    control_refused: bool = False

    def status(self, theta_dist: int) -> str:
        if not self.injection_expressed:
            return "inconclusive"
        if self.distinguishability < theta_dist:
            return "null"  # not distinguishable (incl. dist 0) — a wash / the model can't see it
        if self.preference > 0:
            return "lift"
        if self.preference < 0:
            return "negative"
        return "neutral"  # distinguishable but a tie


class LiftResult(BaseModel):
    frame_code: str
    scenarios: list[ScenarioVerdict]
    theta_dist: int = 1
    min_scenarios: int = 3

    def _valid(self) -> list[ScenarioVerdict]:
        return [s for s in self.scenarios if s.injection_expressed]

    def _statuses(self) -> list[str]:
        return [s.status(self.theta_dist) for s in self._valid()]

    @property
    def inconclusive_count(self) -> int:
        return sum(1 for s in self.scenarios if not s.injection_expressed)

    @property
    def framed_preferred_count(self) -> int:
        return sum(1 for s in self._valid() if s.preference > 0)  # excludes ties

    @property
    def mean_preference(self) -> float:
        v = self._valid()
        return sum(s.preference for s in v) / len(v) if v else 0.0

    @property
    def mean_distinguishability(self) -> float:
        v = self._valid()
        return sum(s.distinguishability for s in v) / len(v) if v else 0.0

    @property
    def verdict(self) -> str:
        st = self._statuses()
        if not st:
            return "inconclusive"
        if all(s == "lift" for s in st):
            return "lift"
        if any(s == "lift" for s in st):
            return "mixed"
        if any(s == "negative" for s in st):
            return "negative_lift"
        if any(s == "neutral" for s in st):
            return "neutral"
        return "null"

    @property
    def screen_action(self) -> str:
        if self._valid() and self.verdict in ("null", "negative_lift"):
            return "auto_kill"
        return "surface"

    @property
    def below_floor(self) -> bool:
        return len(self._valid()) < self.min_scenarios
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_types.py -q` → PASS. Then full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/types.py tests/test_lift_types.py
git commit -m "feat(lift): two-axis result types + derived verdict/screen_action truth table"
```

---

### Task 2: Confidentiality + config + scenario scaffolding

**Files:**
- Modify: `.gitignore`
- Modify: `docs/lessons.md` (the Pre-Commit confidential gate)
- Create: `content/lift/lift.yaml`, `content/lift/scenarios.example.yaml`
- Modify: `src/retnovation/content_loader.py`
- Test: `tests/test_content_loader.py` (extend)

**Interfaces:**
- Consumes: `LiftScenario` (Task 1), the `_root`/`yaml.safe_load` pattern in content_loader.py.
- Produces: `load_lift_config(root=None) -> dict` (`{"theta_dist": int, "min_scenarios": int}`); `load_lift_scenarios(name="scenarios", root=None) -> list[LiftScenario]`.

- [ ] **Step 1: Add the confidentiality protections first**

Append to `.gitignore` (under the runtime-state section):

```
# === Lift-test scenario bank (Veldra-derived generations stay local) ===
/content/lift/scenarios.yaml
```

In `docs/lessons.md`, extend Pre-Commit Checklist item 6 — after the existing `git ls-files | grep -iE ...` line, add:

```
   Also `git ls-files | grep -E 'content/lift/scenarios\.yaml$'` must be empty
   (the real lift bank is gitignored; only scenarios.example.yaml is tracked).
```

Verify: `git check-ignore content/lift/scenarios.yaml` prints the path (ignored); `git check-ignore content/lift/scenarios.example.yaml` prints nothing (rc=1, committable).

- [ ] **Step 2: Write the failing test**

Add to `tests/test_content_loader.py`:

```python
def test_load_lift_config_and_scenarios():
    from retnovation.content_loader import load_lift_config, load_lift_scenarios
    from retnovation.types import LiftScenario

    cfg = load_lift_config()
    assert cfg["theta_dist"] == 1 and cfg["min_scenarios"] == 3
    assert isinstance(cfg["theta_dist"], int) and isinstance(cfg["min_scenarios"], int)

    scenarios = load_lift_scenarios("scenarios.example")
    assert scenarios and all(isinstance(s, LiftScenario) for s in scenarios)
    assert all(s.scenario_id and s.prompt and s.posture for s in scenarios)
```

- [ ] **Step 3: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py::test_load_lift_config_and_scenarios -q`
Expected: FAIL (`load_lift_config` not defined / file missing).

- [ ] **Step 4: Write the content + loaders**

Create `content/lift/lift.yaml`:

```yaml
# Blind-lift screen config (doctrine-as-data, L-1). Dogfood-tunable.
theta_dist: 1        # distinguishability floor: dist < this => "null" (a wash / can't see it)
min_scenarios: 3     # advisory floor recorded on LiftResult.below_floor (not a hard reject)
```

Create `content/lift/scenarios.example.yaml`:

```yaml
# Example lift-test scenario bank — COMMITTABLE structural stub.
# The REAL bank (content/lift/scenarios.yaml, Veldra-derived) is gitignored.
# Scenarios are UNLABELED generation tasks (a pitch, an announcement, an advisory).
scenarios:
  - scenario_id: example_pitch
    posture: founder_ceo
    prompt: >
      Write a 180-word opening to a skeptical enterprise security buyer for a
      financial-infrastructure product.
  - scenario_id: example_announcement
    posture: founder_ceo
    prompt: >
      Write a 180-word public announcement of a feature that uses customers'
      sensitive data to automate a workflow.
```

In `src/retnovation/content_loader.py`, add (import `LiftScenario` in the existing `from .types import (...)` block):

```python
def load_lift_config(root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "lift" / "lift.yaml").read_text())
    return {
        "theta_dist": int(data["theta_dist"]),
        "min_scenarios": int(data["min_scenarios"]),
    }


def load_lift_scenarios(name: str = "scenarios", root: Path | None = None) -> list[LiftScenario]:
    data = yaml.safe_load((_root(root) / "lift" / f"{name}.yaml").read_text())
    return [LiftScenario(**s) for s in data["scenarios"]]
```

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q` → PASS. Full suite green.

- [ ] **Step 6: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add .gitignore docs/lessons.md content/lift/lift.yaml content/lift/scenarios.example.yaml src/retnovation/content_loader.py tests/test_content_loader.py
git commit -m "feat(lift): config + example scenario bank; gitignore the real bank + extend the confidential gate"
```

---

### Task 3: Model methods + prompts (generate / rate / check)

**Files:**
- Modify: `src/retnovation/model.py` (Protocol + `AnthropicModel` + new `FakeLiftModel`)
- Create: `content/prompts/lift_rate.md`, `content/prompts/lift_manipulation.md`
- Test: `tests/test_lift_model.py`

**Interfaces:**
- Consumes: `GeneratedOutput`, `PreferenceRating`, `InjectionExpressed` (Task 1); `_PARAMS`, `_require`, `load_prompt`, `ModelError` (model.py).
- Produces (added to the `Model` Protocol, `AnthropicModel`, and a new `FakeLiftModel`):
  - `generate_output(scenario_prompt: str, injection: str | None) -> GeneratedOutput` — `create`; framed iff injection given; **captures refusal as text, does NOT raise**.
  - `rate_preference(scenario_prompt: str, output_a: str, output_b: str) -> PreferenceRating` — `parse`, unprimed.
  - `check_injection_expressed(injection: str, framed_output: str) -> InjectionExpressed` — `parse`, primed.
  - `FakeLiftModel(outputs, ratings, expressed)` — `outputs: dict[(prompt, is_framed: bool)] -> GeneratedOutput`; `ratings: dict[prompt] -> PreferenceRating`; `expressed: dict[framed_text] -> InjectionExpressed`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lift_model.py`:

```python
import pytest

from retnovation.model import AnthropicModel, ModelError
from retnovation.types import GeneratedOutput, InjectionExpressed, PreferenceRating


class _Resp:
    def __init__(self, parsed_output=None, content=None, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.content = content or []
        self.stop_reason = stop_reason


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Messages:
    def __init__(self, parse_result=None, create_result=None):
        self._parse_result = parse_result
        self._create_result = create_result
        self.parse_calls = []
        self.create_calls = []

    def parse(self, **kw):
        self.parse_calls.append(kw)
        return self._parse_result

    def create(self, **kw):
        self.create_calls.append(kw)
        return self._create_result


class _Client:
    def __init__(self, parse_result=None, create_result=None):
        self.messages = _Messages(parse_result, create_result)


def _sys(call):
    s = call["system"]
    return s if isinstance(s, str) else " ".join(b["text"] for b in s)


def test_generate_output_control_has_no_system_frame():
    client = _Client(create_result=_Resp(content=[_TextBlock("control text")]))
    out = AnthropicModel(client=client).generate_output("Write a pitch.", None)
    assert isinstance(out, GeneratedOutput) and out.text == "control text" and out.refused is False
    assert "system" not in client.messages.create_calls[0]  # control is frame-naive


def test_generate_output_framed_injects_the_frame_as_system():
    client = _Client(create_result=_Resp(content=[_TextBlock("framed text")]))
    AnthropicModel(client=client).generate_output("Write a pitch.", "lead with what you refuse to do")
    assert "lead with what you refuse to do" in _sys(client.messages.create_calls[0])


def test_generate_output_captures_refusal_instead_of_raising():
    # EXP-002 B2: a control refusal is SIGNAL — must be captured, not raised (unlike generate_push).
    client = _Client(create_result=_Resp(content=[_TextBlock("I can't help with that.")],
                                          stop_reason="refusal"))
    out = AnthropicModel(client=client).generate_output("Announce a data feature.", None)
    assert out.refused is True and out.text == "I can't help with that."


def test_rate_preference_is_unprimed_and_parses():
    pr = PreferenceRating(distinguishability=2, preferred="A", magnitude=1, key_difference="A is concrete")
    client = _Client(parse_result=_Resp(parsed_output=pr))
    out = AnthropicModel(client=client).rate_preference("task", "out A", "out B")
    assert out.preferred == "A" and out.magnitude == 1
    blob = _sys(client.messages.parse_calls[0]) + " " + client.messages.parse_calls[0]["messages"][-1]["content"]
    assert "out A" in blob and "out B" in blob
    assert "refuse" not in blob.lower()  # unprimed: no frame text leaks to the rater


def test_check_injection_expressed_is_primed_and_parses():
    ie = InjectionExpressed(expressed=True, evidence="'we never take custody'")
    client = _Client(parse_result=_Resp(parsed_output=ie))
    out = AnthropicModel(client=client).check_injection_expressed(
        "lead with what you refuse to do", "We never take custody of your funds."
    )
    assert out.expressed is True and out.evidence
    # primed: the injection (the move to check for) reaches the checker
    assert "lead with what you refuse to do" in _sys(client.messages.parse_calls[0])


def test_rate_preference_refusal_raises():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).rate_preference("t", "a", "b")


def test_fake_lift_model_scripts_the_three_methods():
    from retnovation.model import FakeLiftModel

    fake = FakeLiftModel(
        outputs={("p", False): GeneratedOutput(text="C"), ("p", True): GeneratedOutput(text="F")},
        ratings={"p": PreferenceRating(distinguishability=2, preferred="B", magnitude=2, key_difference="k")},
        expressed={"F": InjectionExpressed(expressed=True, evidence="e")},
    )
    assert fake.generate_output("p", None).text == "C"
    assert fake.generate_output("p", "inj").text == "F"
    assert fake.rate_preference("p", "x", "y").preferred == "B"
    assert fake.check_injection_expressed("inj", "F").expressed is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_model.py -q`
Expected: FAIL (`generate_output`/`FakeLiftModel` not defined).

- [ ] **Step 3: Write the prompts**

Create `content/prompts/lift_rate.md`:

```
You are a blind evaluator. You are shown a task and two candidate outputs, A and B.
Judge ONLY which output better serves the task. You are not told how either was produced.

Return:
- distinguishability: 0–3, how tellably different the two outputs are (0 = indistinguishable).
- preferred: "A", "B", or "tie" — which better serves the task; "tie" if neither is better.
- magnitude: 0–2, the strength of that preference (0 if and only if preferred is "tie").
- key_difference: one sentence naming the concrete difference that drove your call.

Do not speculate about how the outputs were generated. Judge the text in front of you.
```

Create `content/prompts/lift_manipulation.md`:

```
You are checking whether a specific reasoning MOVE is expressed in an output.
The move to check for follows this instruction. You are NOT judging quality — only presence.

Return:
- expressed: true only if the output actually performs the move (not merely the topic).
- evidence: a short quoted span (or named location) in the output where the move appears;
  if expressed is false, briefly say what is missing. A bare "yes" is not acceptable —
  the evidence must point at the specific text.
```

- [ ] **Step 4: Write the model implementation**

In `src/retnovation/model.py`: import the new types (`GeneratedOutput, InjectionExpressed, PreferenceRating`) in the `from .types import (...)` block. Add the three methods to the `Model` Protocol:

```python
    def generate_output(self, scenario_prompt: str, injection: str | None) -> GeneratedOutput: ...
    def rate_preference(
        self, scenario_prompt: str, output_a: str, output_b: str
    ) -> PreferenceRating: ...
    def check_injection_expressed(
        self, injection: str, framed_output: str
    ) -> InjectionExpressed: ...
```

Add the impls to `AnthropicModel`:

```python
    def generate_output(self, scenario_prompt: str, injection: str | None) -> GeneratedOutput:
        kwargs = dict(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": scenario_prompt}],
            **_PARAMS,
        )
        if injection is not None:  # framed: the frame is the system guidance; control is frame-naive
            kwargs["system"] = injection
        resp = self._get_client().messages.create(**kwargs)
        refused = getattr(resp, "stop_reason", None) == "refusal"
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        if not text and not refused:  # a truly empty non-refusal is an error; a refusal is signal
            raise ModelError("no text in generate_output response")
        return GeneratedOutput(text=text, refused=refused)

    def rate_preference(
        self, scenario_prompt: str, output_a: str, output_b: str
    ) -> PreferenceRating:
        system = load_prompt("lift_rate")
        user = f"Task:\n{scenario_prompt}\n\nOutput A:\n{output_a}\n\nOutput B:\n{output_b}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=PreferenceRating,
            **_PARAMS,
        )
        return _require(resp)

    def check_injection_expressed(
        self, injection: str, framed_output: str
    ) -> InjectionExpressed:
        system = load_prompt("lift_manipulation") + f"\n\nThe move to check for:\n{injection}"
        resp = self._get_client().messages.parse(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": f"Output:\n{framed_output}"}],
            output_format=InjectionExpressed,
            **_PARAMS,
        )
        return _require(resp)
```

Add `FakeLiftModel` after `FakeModel`:

```python
class FakeLiftModel:
    """Scripted model for blind-lift-harness tests. Outputs keyed by (prompt, is_framed);
    ratings by prompt; expression-checks by the framed output text."""

    def __init__(self, outputs, ratings, expressed):
        self._outputs = outputs
        self._ratings = ratings
        self._expressed = expressed

    def generate_output(self, scenario_prompt, injection):
        return self._outputs[(scenario_prompt, injection is not None)]

    def rate_preference(self, scenario_prompt, output_a, output_b):
        return self._ratings[scenario_prompt]

    def check_injection_expressed(self, injection, framed_output):
        return self._expressed[framed_output]
```

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_model.py -q` → PASS. Full suite green.

- [ ] **Step 6: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/model.py content/prompts/lift_rate.md content/prompts/lift_manipulation.md tests/test_lift_model.py
git commit -m "feat(lift): generate/rate/check model methods (refusal-captured) + lift prompts + FakeLiftModel"
```

---

### Task 4: The harness — randomize/un-randomize + run_lift_test

**Files:**
- Create: `src/retnovation/lift_test.py`
- Test: `tests/test_lift_test.py`

**Interfaces:**
- Consumes: `CandidateFrame`, `LiftScenario`, `ScenarioVerdict`, `LiftResult` (Task 1); a model with the three Task-3 methods.
- Produces:
  - `randomize(framed: str, control: str, order: Literal["AB","BA"]) -> tuple[str, str]`.
  - `un_randomize(preferred: Literal["A","B","tie"], magnitude: int, order: Literal["AB","BA"]) -> int` (signed toward framed; tie → 0).
  - `run_lift_test(candidate, scenarios, model, order: dict[str, str], config: dict) -> LiftResult`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lift_test.py`:

```python
from retnovation.lift_test import run_lift_test, un_randomize
from retnovation.model import FakeLiftModel
from retnovation.types import (
    CandidateFrame,
    GeneratedOutput,
    InjectionExpressed,
    LiftScenario,
    PreferenceRating,
)

CFG = {"theta_dist": 1, "min_scenarios": 3}


def test_un_randomize_round_trip_catches_sign_flip():
    # framed is clearly stronger and was placed as B (order "BA"); rater prefers B with magnitude 2.
    # un_randomize must attribute that to FRAMED (positive), not control.
    assert un_randomize("B", 2, "BA") == 2     # framed (B under BA) preferred -> +2
    assert un_randomize("A", 2, "BA") == -2    # control (A under BA) preferred -> -2
    assert un_randomize("A", 1, "AB") == 1     # framed (A under AB) preferred -> +1
    assert un_randomize("tie", 0, "AB") == 0   # tie -> 0, order-independent


def _cand():
    return CandidateFrame(frame_code="f", frame_detail="d", injection="INJ")


def test_run_lift_test_builds_verdict_per_scenario():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo")
    fake = FakeLiftModel(
        outputs={("p1", False): GeneratedOutput(text="C1"), ("p1", True): GeneratedOutput(text="F1")},
        ratings={"p1": PreferenceRating(distinguishability=2, preferred="A", magnitude=2, key_difference="k")},
        expressed={"F1": InjectionExpressed(expressed=True, evidence="e")},
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    sv = res.scenarios[0]
    assert sv.injection_expressed is True and sv.preference == 2  # A=framed under AB, mag 2
    assert sv.framed_output == "F1" and sv.control_output == "C1"
    assert res.verdict == "lift"


def test_manipulation_gate_makes_scenario_inconclusive_not_no_lift():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="x")
    fake = FakeLiftModel(
        outputs={("p1", False): GeneratedOutput(text="C1"), ("p1", True): GeneratedOutput(text="F1")},
        ratings={"p1": PreferenceRating(distinguishability=3, preferred="A", magnitude=2, key_difference="k")},
        expressed={"F1": InjectionExpressed(expressed=False, evidence="frame not present")},
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    assert res.scenarios[0].injection_expressed is False
    assert res.verdict == "inconclusive"  # not null / negative_lift
    assert res.screen_action == "surface"  # all-inconclusive never auto-kills


def test_control_refusal_is_captured_on_the_verdict():
    sc = LiftScenario(scenario_id="s1", prompt="p1", posture="x")
    fake = FakeLiftModel(
        outputs={
            ("p1", False): GeneratedOutput(text="I can't.", refused=True),
            ("p1", True): GeneratedOutput(text="A privacy-first announcement."),
        },
        ratings={"p1": PreferenceRating(distinguishability=3, preferred="B", magnitude=2, key_difference="k")},
        expressed={"A privacy-first announcement.": InjectionExpressed(expressed=True, evidence="e")},
    )
    res = run_lift_test(_cand(), [sc], fake, order={"s1": "AB"}, config=CFG)
    sv = res.scenarios[0]
    assert sv.control_refused is True and sv.framed_refused is False
    assert sv.preference == -2  # order "AB": framed=A, control=B; rater preferred B (control) -> -2
```

Note: in the last test, `order="AB"` ⇒ framed is A, control is B; rater preferred "B" (control) ⇒ `un_randomize("B", 2, "AB") == -2` (toward control). That asserts the control-refusal scenario still maps preference correctly even though the framed output should win on a real run — the point here is refusal *capture* + correct sign, not the EXP verdict (that's Task 5, which scripts the framed output winning).

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_test.py -q`
Expected: FAIL (`run_lift_test` not defined).

- [ ] **Step 3: Write the harness**

Create `src/retnovation/lift_test.py`:

```python
from __future__ import annotations

from typing import Literal

from .types import CandidateFrame, LiftResult, LiftScenario, ScenarioVerdict


def randomize(framed: str, control: str, order: Literal["AB", "BA"]) -> tuple[str, str]:
    return (framed, control) if order == "AB" else (control, framed)


def un_randomize(preferred: Literal["A", "B", "tie"], magnitude: int, order: Literal["AB", "BA"]) -> int:
    """Map the rater's preference (toward shown A/B) back to a signed value toward FRAMED."""
    if preferred == "tie":
        return 0
    framed_letter = "A" if order == "AB" else "B"
    return magnitude if preferred == framed_letter else -magnitude


def run_lift_test(
    candidate: CandidateFrame,
    scenarios: list[LiftScenario],
    model,
    order: dict[str, str],
    config: dict,
) -> LiftResult:
    verdicts: list[ScenarioVerdict] = []
    for sc in scenarios:
        control = model.generate_output(sc.prompt, None)
        framed = model.generate_output(sc.prompt, candidate.injection)
        ie = model.check_injection_expressed(candidate.injection, framed.text)
        if not ie.expressed:  # gate: un-expressed -> inconclusive, excluded from aggregation
            verdicts.append(
                ScenarioVerdict(
                    scenario_id=sc.scenario_id,
                    injection_expressed=False,
                    framed_output=framed.text,
                    control_output=control.text,
                    framed_refused=framed.refused,
                    control_refused=control.refused,
                )
            )
            continue
        a, b = randomize(framed.text, control.text, order[sc.scenario_id])
        pr = model.rate_preference(sc.prompt, a, b)
        preference = un_randomize(pr.preferred, pr.magnitude, order[sc.scenario_id])
        verdicts.append(
            ScenarioVerdict(
                scenario_id=sc.scenario_id,
                injection_expressed=True,
                distinguishability=pr.distinguishability,
                preference=preference,
                key_difference=pr.key_difference,
                framed_output=framed.text,
                control_output=control.text,
                framed_refused=framed.refused,
                control_refused=control.refused,
            )
        )
    return LiftResult(
        frame_code=candidate.frame_code,
        scenarios=verdicts,
        theta_dist=config["theta_dist"],
        min_scenarios=config["min_scenarios"],
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_test.py -q` → PASS. Full suite green.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add src/retnovation/lift_test.py tests/test_lift_test.py
git commit -m "feat(lift): run_lift_test harness + pure randomize/un_randomize (round-trip pinned)"
```

---

### Task 5: EXP-reproduction acceptance suite

**Files:**
- Test: `tests/test_lift_acceptance.py`

**Interfaces:**
- Consumes: `run_lift_test` (Task 4), `FakeLiftModel` (Task 3), the types (Task 1), `AnthropicModel` (for the `@live` smoke).
- Produces: the doctrine-fidelity acceptance suite (no new source).

- [ ] **Step 1: Write the acceptance tests**

Create `tests/test_lift_acceptance.py`:

```python
import os

import pytest

from retnovation.lift_test import run_lift_test
from retnovation.model import FakeLiftModel
from retnovation.types import (
    CandidateFrame,
    GeneratedOutput,
    InjectionExpressed,
    LiftScenario,
    PreferenceRating,
)

CFG = {"theta_dist": 1, "min_scenarios": 2}  # EXP ran at n=2; min is advisory, not a reject


def _scn(n):
    return [LiftScenario(scenario_id=f"s{i}", prompt=f"p{i}", posture="founder_ceo") for i in range(1, n + 1)]


def _fake(per_scenario):
    """per_scenario: {prompt: (control_text, framed_text, PreferenceRating, expressed_bool)}"""
    outputs, ratings, expressed = {}, {}, {}
    for prompt, (c, f, pr, exp) in per_scenario.items():
        outputs[(prompt, False)] = GeneratedOutput(text=c, refused=(c == "<refusal>"))
        outputs[(prompt, True)] = GeneratedOutput(text=f, refused=(f == "<refusal>"))
        ratings[prompt] = pr
        expressed[f] = InjectionExpressed(expressed=exp, evidence="e")
    return FakeLiftModel(outputs=outputs, ratings=ratings, expressed=expressed)


def _cand(code):
    return CandidateFrame(frame_code=code, frame_detail="d", injection="INJ")


def test_exp002_lead_reproduces_lift_with_a_control_refusal():
    # A2 pitch: framed wins; B2 announcement: control REFUSES, framed converts -> framed wins.
    fake = _fake({
        "p1": ("control pitch", "framed pitch", PreferenceRating(distinguishability=2, preferred="A", magnitude=1, key_difference="concrete boundary"), True),
        "p2": ("<refusal>", "privacy-first announcement", PreferenceRating(distinguishability=3, preferred="A", magnitude=2, key_difference="control refused"), True),
    })
    res = run_lift_test(_cand("lead_with_what_you_refuse_to_do"), _scn(2), fake,
                        order={"s1": "AB", "s2": "AB"}, config=CFG)
    assert res.verdict == "lift" and res.framed_preferred_count == 2
    assert res.scenarios[1].control_refused is True  # the refusal was captured, not raised


def test_exp001_choose_reproduces_negative_lift_not_null():
    # EXP-001: distinguishable (dist 1) but dispreferred in both -> negative_lift (NOT the dist-0 null cell).
    fake = _fake({
        "p1": ("control", "framed", PreferenceRating(distinguishability=1, preferred="B", magnitude=1, key_difference="control broader"), True),
        "p2": ("control", "framed", PreferenceRating(distinguishability=1, preferred="B", magnitude=1, key_difference="control broader"), True),
    })
    res = run_lift_test(_cand("choose_the_failure_default_deliberately"), _scn(2), fake,
                        order={"s1": "AB", "s2": "AB"}, config=CFG)
    # order "AB" => framed is A; the rater prefers the CONTROL (B) in both -> preference < 0 -> negative.
    assert res.verdict == "negative_lift" and res.screen_action == "auto_kill"


def test_exp003_partial_is_mixed_and_surfaces():
    # 1 lift + 1 tie -> mixed, surfaced (never auto-killed).
    fake = _fake({
        "p1": ("control", "framed", PreferenceRating(distinguishability=2, preferred="A", magnitude=1, key_difference="sharper"), True),
        "p2": ("control", "framed", PreferenceRating(distinguishability=2, preferred="tie", magnitude=0, key_difference="false precision distrusted"), True),
    })
    res = run_lift_test(_cand("ledger_context"), _scn(2), fake,
                        order={"s1": "AB", "s2": "AB"}, config=CFG)
    assert res.verdict == "mixed" and res.screen_action == "surface"


@pytest.mark.live
@pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")),
    reason="no Anthropic credential",
)
def test_live_lift_smoke():
    from retnovation.model import AnthropicModel

    cand = CandidateFrame(
        frame_code="lead_with_what_you_refuse_to_do",
        frame_detail="lead with the boundary you will not cross",
        injection="Lead with the capability you deliberately do not have or the boundary you will not cross.",
    )
    scn = [LiftScenario(scenario_id="s1", prompt="Write a 120-word pitch to a skeptical security buyer.", posture="founder_ceo")]
    res = run_lift_test(cand, scn, AnthropicModel(), order={"s1": "AB"}, config=CFG)
    assert res.verdict in ("lift", "mixed", "neutral", "null", "negative_lift", "inconclusive")
```

**Mapping reminder (already baked into the scripts above):** with `order="AB"` the framed output is shown as **A** and the control as **B**, so `un_randomize(preferred, mag, "AB")` is `+mag` when `preferred=="A"` (framed) and `−mag` when `preferred=="B"` (control). EXP-002 (framed wins) scripts `preferred="A"`; EXP-001 (framed loses) scripts `preferred="B"`; EXP-003 scripts one `"A"` + one `"tie"`.

- [ ] **Step 2: Run to verify**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_lift_acceptance.py -q`
Expected: all non-live tests PASS; the live test self-skips without a key. Full suite green.

- [ ] **Step 3: Commit**

```bash
.venv/bin/ruff format . && .venv/bin/ruff check .
git add tests/test_lift_acceptance.py
git commit -m "test(lift): EXP-reproduction acceptance (lead->lift w/ control-refusal, choose->negative_lift, EXP-003->mixed) + live smoke"
```

---

## Self-Review

**1. Spec coverage (§4.1–§4.7):**
- §4.1 types (both axes raw; status/verdict/screen_action derived; framed_preferred excludes ties; θ_dist floor) → Task 1. ✓
- §4.2 module map (3 model methods, wire models, generate_output refusal-capture, FakeLiftModel, prompts, example bank) → Tasks 2, 3. ✓
- §4.3 data flow (generate → primed gate → randomize → rate → un-randomize → aggregate) → Task 4. ✓
- §4.4 reproducibility/blindness (injected order Literal, pure inverses, round-trip, unprimed rater + separate primed checker) → Tasks 3, 4. ✓
- §4.5 verdict truth table + screen_action + two biases (rater unprimed/human adjudicates; checker cites evidence) → Tasks 1 (logic), 3 (evidence in prompt). ✓
- §4.6 validation (lead→lift w/ refusal-capture, choose→negative_lift, EXP-003→mixed, manipulation gate, null-vs-negative, round-trip) → Tasks 4, 5. ✓
- §4.7 config + confidentiality (gitignore real bank + example split + grep extension; data/lift result logs already ignored) → Task 2. ✓ (Result-log *writer* is not built in SP1 — the harness returns `LiftResult`; persisting it is the caller's/SP2's concern, noted; `data/lift/` is pre-ignored so no leak.)

**2. Placeholder scan:** every step has concrete, correct-as-written test + impl code + exact commands; no TODOs, no fix-before-run dances (the A/B↔framed mapping is baked into the scripts + a reminder note). ✓

**3. Type consistency:** `generate_output -> GeneratedOutput` (Task 1/3) consumed by `run_lift_test` (Task 4) which reads `.text`/`.refused`. `PreferenceRating{distinguishability, preferred, magnitude, key_difference}` (Task 1) produced by `rate_preference` (Task 3), consumed by `un_randomize(preferred, magnitude, order)` (Task 4). `InjectionExpressed{expressed, evidence}` (Task 1) from `check_injection_expressed` (Task 3) gates in Task 4. `LiftResult.verdict`/`screen_action` (Task 1) asserted in Tasks 4, 5. `load_lift_config` keys (`theta_dist`, `min_scenarios`, Task 2) consumed by `run_lift_test`'s `config` (Task 4). ✓

**Green-at-every-commit:** all five tasks are additive (new types, new content, new Protocol methods + new fake, new module, new tests). Nothing existing imports them, so the suite only grows. ✓

**Note for execution (model selection):** T1 (derived truth table — subtle) sonnet impl + **opus** review; T2 haiku; T3 (refusal-capture divergence) sonnet + opus review; T4 (un-randomize sign) sonnet + opus review; T5 sonnet. Final whole-branch opus review. The confidentiality task (T2) and its gitignore assertion are a must-verify in review.
