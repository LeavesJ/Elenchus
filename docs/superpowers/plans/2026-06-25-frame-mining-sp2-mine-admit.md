# Frame-Mining SP2 (Mine + Admit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit the first new founder-CEO spine frame(s) end-to-end — mine 6 candidates from the Veldra ore, screen each against `marginal_lift` with the SP1 harness, apply the rest of the v0.2 gate by hand, and admit survivors as provisional spine.

**Architecture:** A thin layer over the untouched SP1 harness (Approach C / hybrid). Phase 1 builds offline, fully-tested tooling: a candidate loader, a persisting `screen_candidate` driver, two pure formatters, a structured `AdmissionRecord` whose pydantic validator turns the v0.2 gate into something a commit enforces, and a content-graph integrity check. Phase 2 is a gated, human-in-loop execution runbook: author candidates + blind scenarios, run the @live screen, adjudicate, admit, regress.

**Tech Stack:** Python 3.12, pydantic v2, PyYAML, pytest, ruff. Anthropic SDK (Opus 4.8) only on the @live path.

## Global Constraints

- Tests run with `PYTHONPATH=src .venv/bin/pytest -q`; every commit leaves the suite green.
- `ruff format .` then `ruff check .` before every commit; both clean.
- **No `Co-Authored-By` trailer.** Stage explicit paths only — never `git add -A`, never `-f`.
- Confidentiality gates (lessons Pre-Commit) must stay empty:
  `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'`
  AND `git ls-files | grep -E 'content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$'`.
- The real banks `content/lift/candidates.yaml` + `content/lift/scenarios.yaml` and `data/**` are gitignored; only `*.example.yaml` and `docs/admissions/*.yaml` are committable.
- **Two-axis doctrine (spec §2):** the record carries both screen axes; `marginal_lift` is a *derived view*, never stored truth.
- **L-13:** authored screen scenarios are blind — the move lives only in the `injection`, never in the scenario `prompt`.
- **L-8/L-9:** any signal the engine consumes gets a production-path test on a fresh-tempdir DB, never a synthetic fixture alone.
- Keep files under 500 lines. Update `docs/DEVLOG.md` on every commit.
- Build subagent-driven: fresh implementer + independent reviewer per task; **OPUS reviewers on T1 (validator coherence) and T4 (two-axis packet)**.

---

## File Structure

- `src/retnovation/types.py` (modify) — add `Provenance`, `MinedCandidate`, `ScreenSummary`, `Gates`, `AdmittedAs`, `AdmissionRecord`; add optional `candidate` field to `LiftScenario`.
- `src/retnovation/content_loader.py` (modify) — add `load_lift_candidates`.
- `src/retnovation/admission.py` (create) — `screen_candidate`, `format_adjudication_packet`, `format_admission_record`, `check_content_graph_integrity`.
- `content/lift/candidates.example.yaml` (create) — committable schema stub.
- `content/lift/scenarios.example.yaml` (modify) — show the `candidate:` tag.
- `docs/admissions/_TEMPLATE.example.yaml` (create) — committable record template carrying the abstraction rule inline.
- `.gitignore` (modify) — add `/content/lift/candidates.yaml`.
- `docs/lessons.md` (modify) — extend the Pre-Commit grep to also catch `candidates.yaml`.
- Tests: `tests/test_admission_types.py`, `tests/test_admission.py` (create); `tests/test_content_loader.py` (modify).

---

## Phase 1 — Tooling (offline, subagent-driven TDD)

### Task 1: Admission types + coherence validator

**Files:**
- Modify: `src/retnovation/types.py` (imports line 9; append new types after `LiftResult`, before `CoreCandidate` at line ~397)
- Test: `tests/test_admission_types.py`

**Interfaces:**
- Consumes: existing `CandidateFrame`, `LiftResult` (in `types.py`).
- Produces: `Provenance(source_type, pointer)`; `MinedCandidate(frame_code, frame_detail, injection, posture, hypothesis, nearest_sibling, separating_artifact, provenance)` with `.to_candidate_frame() -> CandidateFrame`; `ScreenSummary(verdict, screen_action, mean_distinguishability, mean_preference, framed_preferred_count, data_ref)` with `.from_result(result, data_ref="")`; `Gates(surface_independence, atomicity, orthogonality, falsifiable_application, trainable_cognition)`; `AdmittedAs(experience_id, ledger_ref)`; `AdmissionRecord(frame_code, posture, provenance, screen, gates, nearest_sibling, separating_artifact, decision, rationale, admitted_as)` with computed `marginal_lift` + coherence `model_validator`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admission_types.py
import pytest
from pydantic import ValidationError

from retnovation.types import (
    AdmissionRecord, AdmittedAs, Gates, MinedCandidate, Provenance, ScreenSummary,
)


def _screen(verdict, action):
    return ScreenSummary(
        verdict=verdict, screen_action=action,
        mean_distinguishability=2.0, mean_preference=1.0, framed_preferred_count=2, data_ref="x",
    )


def _all_pass_gates(orthogonality="pass"):
    return Gates(
        surface_independence="pass", atomicity="pass", orthogonality=orthogonality,
        falsifiable_application="pass", trainable_cognition="pass",
    )


def test_mined_candidate_to_candidate_frame():
    mc = MinedCandidate(
        frame_code="build_more_to_own_less", frame_detail="d", injection="INJ",
        posture="founder_ceo", hypothesis="model minimizes scope",
        nearest_sibling="protect_the_core_lane", separating_artifact="net-component ledger",
        provenance=Provenance(source_type="owned", pointer="EXECLOG EX-028"),
    )
    cf = mc.to_candidate_frame()
    assert (cf.frame_code, cf.frame_detail, cf.injection) == ("build_more_to_own_less", "d", "INJ")


def test_screen_summary_from_result_and_marginal_lift_is_derived():
    from retnovation.types import LiftResult, ScenarioVerdict
    lr = LiftResult(
        frame_code="f",
        scenarios=[
            ScenarioVerdict(scenario_id="s1", injection_expressed=True, distinguishability=2, preference=1),
            ScenarioVerdict(scenario_id="s2", injection_expressed=True, distinguishability=2, preference=1),
        ],
        theta_dist=1, min_scenarios=2,
    )
    summary = ScreenSummary.from_result(lr, data_ref="data/lift/screen_f.json")
    assert summary.verdict == lr.verdict == "lift"
    assert summary.mean_preference == lr.mean_preference
    assert summary.framed_preferred_count == lr.framed_preferred_count == 2
    assert summary.data_ref == "data/lift/screen_f.json"

    rec = AdmissionRecord(
        frame_code="f", posture="founder_ceo",
        provenance=Provenance(source_type="owned", pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"), gates=_all_pass_gates(),
        nearest_sibling="protect_the_core_lane", separating_artifact="artifact",
        decision="admit_provisional", rationale="lifts on both",
        admitted_as=AdmittedAs(experience_id="exp", ledger_ref="veldra:slug"),
    )
    assert rec.marginal_lift == "pass"  # derived from screen.verdict, not stored


def test_auto_kill_screen_forces_reject():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f", posture="founder_ceo",
            provenance=Provenance(pointer="EXECLOG EX-028"),
            screen=_screen("negative_lift", "auto_kill"), gates=_all_pass_gates(),
            decision="admit_provisional", rationale="x",
            admitted_as=AdmittedAs(experience_id="exp", ledger_ref="veldra:slug"),
            nearest_sibling="s", separating_artifact="a",
        )


def test_reject_requires_rationale():
    with pytest.raises(ValidationError):
        AdmissionRecord(
            frame_code="f", posture="founder_ceo",
            provenance=Provenance(pointer="BIZLOG 2026-04-16"),
            screen=_screen("null", "auto_kill"), gates=_all_pass_gates(),
            decision="reject", rationale="",
        )


def test_admit_requires_separating_artifact_and_admitted_as():
    base = dict(
        frame_code="f", posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"), gates=_all_pass_gates(),
        decision="admit_provisional", rationale="lifts", nearest_sibling="s",
    )
    with pytest.raises(ValidationError):  # missing separating_artifact + admitted_as
        AdmissionRecord(**base, separating_artifact="", admitted_as=None)


def test_subframe_requires_subframe_orthogonality_and_sibling():
    with pytest.raises(ValidationError):  # orthogonality not "subframe"
        AdmissionRecord(
            frame_code="f", posture="founder_ceo",
            provenance=Provenance(pointer="EXECLOG EX-028"),
            screen=_screen("lift", "surface"), gates=_all_pass_gates(orthogonality="pass"),
            decision="file_as_subframe", rationale="merge", nearest_sibling="s",
            separating_artifact="a",
        )
    ok = AdmissionRecord(
        frame_code="f", posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=_screen("lift", "surface"), gates=_all_pass_gates(orthogonality="subframe"),
        decision="file_as_subframe", rationale="merge under sibling",
        nearest_sibling="lead_with_what_you_refuse_to_do", separating_artifact="none found",
    )
    assert ok.gates.orthogonality == "subframe"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission_types.py -q`
Expected: FAIL with `ImportError` (the new types do not exist yet).

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/types.py`, change the pydantic import line (line 9) to:

```python
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
```

Then append after the `LiftResult` class (before `class CoreCandidate`):

```python
class Provenance(BaseModel):
    source_type: Literal["owned", "public"] = "owned"  # public = forward-room, untested this arc
    pointer: str


class MinedCandidate(BaseModel):
    frame_code: str
    frame_detail: str
    injection: str
    posture: str
    hypothesis: str  # why base Opus is wrong by default
    nearest_sibling: str | None = None
    separating_artifact: str = ""
    provenance: Provenance

    def to_candidate_frame(self) -> "CandidateFrame":
        return CandidateFrame(
            frame_code=self.frame_code, frame_detail=self.frame_detail, injection=self.injection
        )


class ScreenSummary(BaseModel):
    verdict: str
    screen_action: str
    mean_distinguishability: float
    mean_preference: float
    framed_preferred_count: int
    data_ref: str = ""

    @classmethod
    def from_result(cls, result: "LiftResult", data_ref: str = "") -> "ScreenSummary":
        return cls(
            verdict=result.verdict,
            screen_action=result.screen_action,
            mean_distinguishability=result.mean_distinguishability,
            mean_preference=result.mean_preference,
            framed_preferred_count=result.framed_preferred_count,
            data_ref=data_ref,
        )


class Gates(BaseModel):
    surface_independence: Literal["pass", "fail"]
    atomicity: Literal["pass", "fail"]
    orthogonality: Literal["pass", "fail", "subframe"]
    falsifiable_application: Literal["pass", "fail"]
    trainable_cognition: Literal["pass", "fail"]


class AdmittedAs(BaseModel):
    experience_id: str = Field(min_length=1)
    ledger_ref: str = Field(min_length=1)


class AdmissionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")  # drop the derived marginal_lift on reload

    frame_code: str
    posture: str
    provenance: Provenance
    screen: ScreenSummary
    gates: Gates
    nearest_sibling: str | None = None
    separating_artifact: str = ""
    decision: Literal["admit_provisional", "reject", "file_as_subframe"]
    rationale: str = ""
    admitted_as: AdmittedAs | None = None

    @computed_field  # DERIVED VIEW (spec §2, seam 1): not stored truth
    @property
    def marginal_lift(self) -> str:
        return "pass" if self.screen.verdict in ("lift", "mixed") else "fail"

    @model_validator(mode="after")
    def _coherence(self) -> "AdmissionRecord":
        if self.screen.screen_action == "auto_kill" and self.decision != "reject":
            raise ValueError("auto_kill screen requires decision == reject")
        if self.decision == "reject":
            if not self.screen.verdict or not self.rationale:
                raise ValueError("reject requires a screen verdict and a rationale")
        elif self.decision == "admit_provisional":
            if self.marginal_lift != "pass":
                raise ValueError("admit_provisional requires marginal_lift pass (verdict lift|mixed)")
            human = (
                self.gates.surface_independence,
                self.gates.atomicity,
                self.gates.orthogonality,
                self.gates.falsifiable_application,
                self.gates.trainable_cognition,
            )
            if any(g != "pass" for g in human):
                raise ValueError("admit_provisional requires all human gates pass")
            if self.admitted_as is None:
                raise ValueError("admit_provisional requires admitted_as")
            if not self.separating_artifact:
                raise ValueError("admit_provisional requires a separating_artifact")
            if self.nearest_sibling is None:
                raise ValueError("admit_provisional requires nearest_sibling")
        elif self.decision == "file_as_subframe":
            if self.gates.orthogonality != "subframe":
                raise ValueError("file_as_subframe requires orthogonality == subframe")
            if self.nearest_sibling is None:
                raise ValueError("file_as_subframe requires nearest_sibling")
            if not self.separating_artifact:
                raise ValueError("file_as_subframe requires a separating_artifact")
        return self
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission_types.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/types.py tests/test_admission_types.py docs/DEVLOG.md
git commit -m "feat(admission): MinedCandidate + AdmissionRecord types with coherence validator"
```

---

### Task 2: Candidate loader + scenario `candidate` tag + example files

**Files:**
- Modify: `src/retnovation/types.py:287-290` (`LiftScenario`)
- Modify: `src/retnovation/content_loader.py` (imports line 7-17; append `load_lift_candidates`)
- Create: `content/lift/candidates.example.yaml`
- Modify: `content/lift/scenarios.example.yaml`
- Test: `tests/test_content_loader.py` (append)

**Interfaces:**
- Consumes: `MinedCandidate`, `Provenance` (Task 1); existing `load_lift_scenarios` pattern.
- Produces: `LiftScenario.candidate: str | None`; `load_lift_candidates(name="candidates", root=None) -> list[MinedCandidate]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_content_loader.py
def test_lift_scenario_accepts_optional_candidate():
    from retnovation.types import LiftScenario
    s = LiftScenario(scenario_id="s1", prompt="p", posture="founder_ceo", candidate="frame_x")
    assert s.candidate == "frame_x"
    s2 = LiftScenario(scenario_id="s2", prompt="p", posture="founder_ceo")  # back-compat
    assert s2.candidate is None


def test_load_lift_candidates_parses_example(tmp_path):
    import textwrap
    from retnovation.content_loader import load_lift_candidates
    root = tmp_path / "content"
    (root / "lift").mkdir(parents=True)
    (root / "lift" / "candidates.yaml").write_text(textwrap.dedent("""
        candidates:
          - frame_code: build_more_to_own_less
            frame_detail: A larger build can be the net-simpler system.
            injection: Account for net component count, not effort.
            posture: founder_ceo
            hypothesis: the model conflates more-build with more-complexity
            nearest_sibling: protect_the_core_lane
            separating_artifact: a net-component-count ledger
            provenance:
              source_type: owned
              pointer: EXECLOG EX-028
    """))
    cands = load_lift_candidates(root=root)
    assert len(cands) == 1
    assert cands[0].frame_code == "build_more_to_own_less"
    assert cands[0].provenance.pointer == "EXECLOG EX-028"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -k 'candidate' -q`
Expected: FAIL (`LiftScenario` has no `candidate`; `load_lift_candidates` undefined).

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/types.py`, update `LiftScenario`:

```python
class LiftScenario(BaseModel):
    scenario_id: str
    prompt: str
    posture: str  # carried for SP2; not read by the screen
    candidate: str | None = None  # SP2: groups a scenario under a MinedCandidate.frame_code
```

In `src/retnovation/content_loader.py`, add `MinedCandidate` to the `.types` import block, then append:

```python
def load_lift_candidates(name: str = "candidates", root: Path | None = None) -> list[MinedCandidate]:
    data = yaml.safe_load((_root(root) / "lift" / f"{name}.yaml").read_text())
    return [MinedCandidate(**c) for c in data["candidates"]]
```

Create `content/lift/candidates.example.yaml`:

```yaml
# Example mined-candidate bank — COMMITTABLE structural stub.
# The REAL bank (content/lift/candidates.yaml, Veldra-derived) is gitignored.
# Each candidate is an abstracted reasoning move; provenance is a POINTER, never quoted ore.
candidates:
  - frame_code: example_build_more_to_own_less
    frame_detail: A larger-looking build can be the net-simpler system when it deletes a subsystem.
    injection: Account for net component count, not effort, before choosing scope.
    posture: founder_ceo
    hypothesis: the base model conflates "build more" with "more complexity".
    nearest_sibling: protect_the_core_lane
    separating_artifact: a net-component-count ledger (+1 client, -2 services).
    provenance:
      source_type: owned
      pointer: "EXECLOG EX-028 (abstracted)"
```

In `content/lift/scenarios.example.yaml`, add a `candidate:` line to the first example to show the tag:

```yaml
  - scenario_id: example_pitch
    posture: founder_ceo
    candidate: example_build_more_to_own_less
    prompt: >
      Write a 180-word opening to a skeptical enterprise security buyer for a
      financial-infrastructure product.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_content_loader.py -q`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/types.py src/retnovation/content_loader.py content/lift/candidates.example.yaml content/lift/scenarios.example.yaml tests/test_content_loader.py docs/DEVLOG.md
git commit -m "feat(admission): load_lift_candidates + candidate-tagged scenarios"
```

---

### Task 3: `screen_candidate` driver with persistence

**Files:**
- Create: `src/retnovation/admission.py`
- Test: `tests/test_admission.py`

**Interfaces:**
- Consumes: `run_lift_test` (`lift_test.py`); `MinedCandidate.to_candidate_frame()` (Task 1); `FakeLiftModel` (`model.py`).
- Produces: `screen_candidate(candidate, scenarios, model, order, config, *, out_dir) -> LiftResult` that writes `out_dir/screen_{frame_code}.json`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admission.py
import json

from retnovation.admission import screen_candidate
from retnovation.model import FakeLiftModel
from retnovation.types import (
    GeneratedOutput, InjectionExpressed, LiftResult, LiftScenario, MinedCandidate,
    PreferenceRating, Provenance,
)

CFG = {"theta_dist": 1, "min_scenarios": 2}


def _candidate():
    return MinedCandidate(
        frame_code="cap_effort", frame_detail="d", injection="INJ", posture="founder_ceo",
        hypothesis="model over-persists", nearest_sibling=None, separating_artifact="stop rule",
        provenance=Provenance(pointer="BIZLOG 2026-05-28"),
    )


def _fake():
    outputs = {
        ("p1", False): GeneratedOutput(text="control1"),
        ("p1", True): GeneratedOutput(text="framed1"),
        ("p2", False): GeneratedOutput(text="control2"),
        ("p2", True): GeneratedOutput(text="framed2"),
    }
    ratings = {
        "p1": PreferenceRating(distinguishability=2, preferred="A", magnitude=1, key_difference="kd1"),
        "p2": PreferenceRating(distinguishability=2, preferred="A", magnitude=1, key_difference="kd2"),
    }
    expressed = {
        "framed1": InjectionExpressed(expressed=True, evidence="e"),
        "framed2": InjectionExpressed(expressed=True, evidence="e"),
    }
    return FakeLiftModel(outputs=outputs, ratings=ratings, expressed=expressed)


def test_screen_candidate_filters_persists_and_returns(tmp_path):
    scenarios = [
        LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo", candidate="cap_effort"),
        LiftScenario(scenario_id="s2", prompt="p2", posture="founder_ceo", candidate="cap_effort"),
        LiftScenario(scenario_id="s3", prompt="other", posture="founder_ceo", candidate="someone_else"),
    ]
    result = screen_candidate(
        _candidate(), scenarios, _fake(),
        order={"s1": "AB", "s2": "AB"}, config=CFG, out_dir=tmp_path,
    )
    assert result.verdict == "lift" and len(result.scenarios) == 2  # s3 filtered out
    path = tmp_path / "screen_cap_effort.json"
    assert path.exists()
    reloaded = LiftResult(**json.loads(path.read_text()))
    assert reloaded.verdict == "lift"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -q`
Expected: FAIL (`No module named 'retnovation.admission'`).

- [ ] **Step 3: Write minimal implementation**

Create `src/retnovation/admission.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .lift_test import run_lift_test
from .types import LiftResult, MinedCandidate


def screen_candidate(
    candidate: MinedCandidate,
    scenarios,
    model,
    order: dict[str, str],
    config: dict,
    *,
    out_dir: str | Path,
) -> LiftResult:
    """Run the blind-lift screen for one candidate and persist the raw result.

    Filters the flat scenario bank to this candidate (by the `candidate` tag), runs the
    SP1 harness, and writes the LiftResult JSON to out_dir/screen_{frame_code}.json so an
    expensive @live run is never lost. Returns the LiftResult.
    """
    cand_scenarios = [s for s in scenarios if s.candidate == candidate.frame_code]
    result = run_lift_test(candidate.to_candidate_frame(), cand_scenarios, model, order, config)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"screen_{candidate.frame_code}.json").write_text(
        json.dumps(result.model_dump(), indent=2)
    )
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/admission.py tests/test_admission.py docs/DEVLOG.md
git commit -m "feat(admission): screen_candidate driver with persisted LiftResult"
```

---

### Task 4: Adjudication-packet + admission-record formatters

**Files:**
- Modify: `src/retnovation/admission.py` (append two functions; add imports)
- Test: `tests/test_admission.py` (append)

**Interfaces:**
- Consumes: `LiftResult`, `ScenarioVerdict.status()`, `MinedCandidate`, `AdmissionRecord`.
- Produces: `format_adjudication_packet(candidate, result) -> str` (markdown, both axes + per-scenario framed/control); `format_admission_record(record) -> str` (YAML, round-trippable).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_admission.py
def test_adjudication_packet_shows_both_axes_and_outputs(tmp_path):
    from retnovation.admission import format_adjudication_packet
    result = screen_candidate(
        _candidate(),
        [
            LiftScenario(scenario_id="s1", prompt="p1", posture="founder_ceo", candidate="cap_effort"),
            LiftScenario(scenario_id="s2", prompt="p2", posture="founder_ceo", candidate="cap_effort"),
        ],
        _fake(), order={"s1": "AB", "s2": "AB"}, config=CFG, out_dir=tmp_path,
    )
    packet = format_adjudication_packet(_candidate(), result)
    assert "mean_distinguishability" in packet and "mean_preference" in packet
    assert "below_floor" in packet  # advisory floor surfaced for the human (m3)
    assert "framed1" in packet and "control1" in packet  # verbatim outputs for the human
    assert "kd1" in packet  # rater's key_difference


def test_admission_record_yaml_round_trips():
    from retnovation.admission import format_admission_record
    from retnovation.types import AdmissionRecord, AdmittedAs, Gates, Provenance, ScreenSummary
    rec = AdmissionRecord(
        frame_code="cap_effort", posture="founder_ceo",
        provenance=Provenance(source_type="owned", pointer="BIZLOG 2026-05-28"),
        screen=ScreenSummary(verdict="lift", screen_action="surface",
                             mean_distinguishability=2.0, mean_preference=1.0,
                             framed_preferred_count=2, data_ref="data/lift/screen_cap_effort.json"),
        gates=Gates(surface_independence="pass", atomicity="pass", orthogonality="pass",
                   falsifiable_application="pass", trainable_cognition="pass"),
        nearest_sibling="protect_the_core_lane", separating_artifact="a pre-committed stop rule",
        decision="admit_provisional", rationale="lifts on both; sales-persistence reflex inverted",
        admitted_as=AdmittedAs(experience_id="prospect_focus", ledger_ref="veldra:first_customer_proof_loop"),
    )
    text = format_admission_record(rec)
    import yaml
    reloaded = AdmissionRecord(**yaml.safe_load(text))
    assert reloaded.model_dump() == rec.model_dump()
    assert "marginal_lift: pass" in text  # derived view rendered for humans
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -k 'packet or round_trips' -q`
Expected: FAIL (formatters undefined).

- [ ] **Step 3: Write minimal implementation**

In `src/retnovation/admission.py`, add `import yaml` near the top imports and append:

```python
def format_adjudication_packet(candidate: "MinedCandidate", result: LiftResult) -> str:
    """Human-readable markdown for adjudicating one screened candidate.

    Surfaces BOTH screen axes plus, per scenario, the verbatim framed/control outputs and the
    rater's key-difference — so the surface_independence call is made with the evidence, not blind.
    """
    lines = [
        f"# Adjudication — {candidate.frame_code}",
        f"hypothesis: {candidate.hypothesis}",
        f"nearest_sibling: {candidate.nearest_sibling}",
        f"separating_artifact: {candidate.separating_artifact}",
        "",
        f"verdict: {result.verdict}    screen_action: {result.screen_action}",
        f"mean_distinguishability: {result.mean_distinguishability:.2f}    "
        f"mean_preference: {result.mean_preference:.2f}    "
        f"framed_preferred_count: {result.framed_preferred_count}    "
        f"below_floor: {result.below_floor}",  # advisory: fewer valid scenarios than min_scenarios
        "",
        "## Per-scenario",
    ]
    for s in result.scenarios:
        lines += [
            f"### {s.scenario_id} — status={s.status(result.theta_dist)} "
            f"dist={s.distinguishability} pref={s.preference}",
            f"key_difference: {s.key_difference}",
            f"framed_refused={s.framed_refused}  control_refused={s.control_refused}",
            "FRAMED:",
            s.framed_output,
            "CONTROL:",
            s.control_output,
            "",
        ]
    return "\n".join(lines)


def format_admission_record(record: "AdmissionRecord") -> str:
    """Serialize an AdmissionRecord to committable YAML (derived marginal_lift included)."""
    return yaml.safe_dump(record.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
```

Add `AdmissionRecord` and `MinedCandidate` to the `.types` import in `admission.py` (MinedCandidate is already imported from Task 3; add `AdmissionRecord`).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
git add src/retnovation/admission.py tests/test_admission.py docs/DEVLOG.md
git commit -m "feat(admission): adjudication-packet + admission-record formatters"
```

---

### Task 5: Content-graph integrity check + confidentiality wiring

**Files:**
- Modify: `src/retnovation/admission.py` (append `check_content_graph_integrity`)
- Create: `docs/admissions/_TEMPLATE.example.yaml`
- Modify: `.gitignore`
- Modify: `docs/lessons.md`
- Test: `tests/test_admission.py` (append)

**Interfaces:**
- Consumes: `Experience`, `AdmissionRecord` (Task 1).
- Produces: `check_content_graph_integrity(experiences, process_frames, valid_ledger_refs, records) -> None` (raises `ValueError` on a broken edge).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_admission.py
import pytest

from retnovation.admission import check_content_graph_integrity
from retnovation.types import (
    AdmissionRecord, AdmittedAs, Experience, Frame, Gates, Mode, Provenance, Regime, Rubric,
    ScreenSummary, Trap,
)


def _exp(eid, ledger_ref, frame_code):
    return Experience(
        experience_id=eid, prompt="p", ledger_ref=ledger_ref, regime=Regime.open_ended,
        rubric=Rubric(
            frames=[Frame(frame_code=frame_code, frame_detail="d", paired_trap="t")],
            traps=[Trap(trap_code="t", trap_detail="td")], mode=Mode.genuinely_open,
        ),
    )


def _admit_record(frame_code, eid, ledger_ref):
    return AdmissionRecord(
        frame_code=frame_code, posture="founder_ceo",
        provenance=Provenance(pointer="EXECLOG EX-028"),
        screen=ScreenSummary(verdict="lift", screen_action="surface", mean_distinguishability=2.0,
                             mean_preference=1.0, framed_preferred_count=2, data_ref="x"),
        gates=Gates(surface_independence="pass", atomicity="pass", orthogonality="pass",
                   falsifiable_application="pass", trainable_cognition="pass"),
        nearest_sibling="protect_the_core_lane", separating_artifact="a",
        decision="admit_provisional", rationale="lifts",
        admitted_as=AdmittedAs(experience_id=eid, ledger_ref=ledger_ref),
    )


def test_integrity_passes_on_consistent_graph():
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    check_content_graph_integrity(
        exps, ["frame_x"], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
    )  # no raise


def test_integrity_catches_dangling_ledger_ref():
    exps = [_exp("e1", "veldra:TYPO", "frame_x")]
    with pytest.raises(ValueError, match="does not resolve"):
        check_content_graph_integrity(exps, ["frame_x"], {"veldra:slug_a"}, [])


def test_integrity_catches_duplicate_experience_id():
    exps = [_exp("e1", "veldra:slug_a", "frame_x"), _exp("e1", "veldra:slug_a", "frame_y")]
    with pytest.raises(ValueError, match="duplicate experience_id"):
        check_content_graph_integrity(exps, ["frame_x", "frame_y"], {"veldra:slug_a"}, [])


def test_integrity_catches_frame_not_in_process_frames():
    exps = [_exp("e1", "veldra:slug_a", "frame_x")]
    with pytest.raises(ValueError, match="not in process_frames"):
        check_content_graph_integrity(
            exps, [], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
        )


def test_integrity_catches_frame_not_in_rubric():
    exps = [_exp("e1", "veldra:slug_a", "other_frame")]
    with pytest.raises(ValueError, match="not in rubric"):
        check_content_graph_integrity(
            exps, ["frame_x"], {"veldra:slug_a"}, [_admit_record("frame_x", "e1", "veldra:slug_a")]
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -k 'integrity' -q`
Expected: FAIL (`check_content_graph_integrity` undefined).

- [ ] **Step 3: Write minimal implementation**

Append to `src/retnovation/admission.py` (and add `Experience` to the `.types` import):

```python
def check_content_graph_integrity(
    experiences: list["Experience"],
    process_frames: list[str],
    valid_ledger_refs: set[str],
    records: list["AdmissionRecord"],
) -> None:
    """Assert the three-file admit edit is referentially intact BEFORE the gated path runs.

    A ledger_ref typo or duplicate experience_id surfaces here as a named assertion, not as an
    opaque failure deep in select/assess (spec §8, seam 3).
    """
    ids = [e.experience_id for e in experiences]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate experience_id: {dupes}")
    by_id = {e.experience_id: e for e in experiences}
    for e in experiences:
        if e.ledger_ref not in valid_ledger_refs:
            raise ValueError(
                f"experience {e.experience_id!r} ledger_ref {e.ledger_ref!r} does not resolve"
            )
    pf = set(process_frames)
    for r in records:
        if r.decision != "admit_provisional" or r.admitted_as is None:
            continue
        aa = r.admitted_as
        if aa.experience_id not in by_id:
            raise ValueError(f"admission {r.frame_code!r}: admitted_as.experience_id does not resolve")
        exp = by_id[aa.experience_id]
        if aa.ledger_ref != exp.ledger_ref:
            raise ValueError(f"admission {r.frame_code!r}: admitted_as.ledger_ref mismatch")
        if r.frame_code not in pf:
            raise ValueError(f"admitted frame {r.frame_code!r} not in process_frames")
        rubric_frames = {f.frame_code for f in (exp.rubric.frames if exp.rubric else [])}
        if r.frame_code not in rubric_frames:
            raise ValueError(f"admitted frame {r.frame_code!r} not in rubric of {exp.experience_id!r}")
```

Create `docs/admissions/_TEMPLATE.example.yaml`:

```yaml
# Admission record TEMPLATE (committable, ABSTRACTED). One file per screened candidate as
# docs/admissions/{frame_code}.yaml. ABSTRACTION RULE (spec §7), enforced by eye on commit:
#   - provenance.pointer is a POINTER only (e.g. "EXECLOG EX-028") — never quoted ore.
#   - frame_code / separating_artifact / rationale describe the REASONING SHAPE only:
#     no customer names, dollar figures, dates, or internal product/service identifiers.
#   - the move must read as a portable founder principle (surface_independence is the test).
frame_code: example_frame
posture: founder_ceo
provenance:
  source_type: owned          # public = forward-room, untested this arc
  pointer: "EXECLOG EX-000 (abstracted)"
screen:
  verdict: lift               # lift|mixed|neutral|null|negative_lift|inconclusive
  screen_action: surface      # surface|auto_kill
  mean_distinguishability: 2.0
  mean_preference: 1.0
  framed_preferred_count: 2
  data_ref: "data/lift/screen_example_frame.json"   # gitignored raw result
marginal_lift: pass           # DERIVED from screen.verdict — not authored
gates:
  surface_independence: pass
  atomicity: pass
  orthogonality: pass         # pass|fail|subframe
  falsifiable_application: pass
  trainable_cognition: pass
nearest_sibling: protect_the_core_lane
separating_artifact: "a concrete artifact distinguishing this from its nearest sibling"
decision: admit_provisional   # admit_provisional|reject|file_as_subframe
rationale: "one line; required on every decision"
admitted_as:
  experience_id: example_experience
  ledger_ref: "veldra:example_slug"
```

In `.gitignore`, under the lift-bank section (after line 25 `/content/lift/scenarios.yaml`), add:

```
/content/lift/candidates.yaml
```

In `docs/lessons.md`, in the Pre-Commit Checklist item 6, extend the lift-bank grep so it reads:

```
   Also `git ls-files | grep -E 'content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$'` must be empty
   (the real lift banks are gitignored; only the *.example.yaml stubs are tracked).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_admission.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
PYTHONPATH=src .venv/bin/pytest -q
# Confirm gates empty:
git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'
git ls-files | grep -E 'content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$'
git add src/retnovation/admission.py tests/test_admission.py docs/admissions/_TEMPLATE.example.yaml .gitignore docs/lessons.md docs/DEVLOG.md
git commit -m "feat(admission): content-graph integrity check + candidates.yaml confidentiality wiring"
```

---

## Phase 2 — Execution (gated, human-in-loop)

> Phase 2 spends real Anthropic tokens and writes committed library content. It runs WITH THE USER PRESENT for adjudication. The only legitimately-deferred values are the empirical screen outcomes (which candidates survive, the admitted `frame_code`/`experience_id`) — they cannot be known before the @live screen. Each step below is concrete; fill the survivor identities from the screen results.

### Step A — Author the real banks (gitignored)

- [ ] Author `content/lift/candidates.yaml` — the 6 `MinedCandidate` definitions (spec §3 table), each abstracted per the §7 rule. Schema = `content/lift/candidates.example.yaml`.
- [ ] Author `content/lift/scenarios.yaml` — **≥3 blind scenarios per candidate** (matching the `min_scenarios: 3` advisory floor in `content/lift/lift.yaml`, so a survivor is not admitted below the floor — m3), each tagged `candidate: <frame_code>`. **L-13: the scenario `prompt` must NOT name the move** — it is a plain generation task (a pitch, an announcement, an advisory); the move lives only in the candidate's `injection`. Fan authoring out per-candidate to parallel subagents; review each for leak + task-only framing.
- [ ] Confirm both files are gitignored: `git status --short content/lift/` shows nothing.

### Step B — Run the @live screen

- [ ] Write a throwaway driver under the gitignored scratch (NOT committed) that, for each candidate, loads the candidate + its scenarios, builds an `order` dict (default all `"AB"`), and calls `screen_candidate(cand, scenarios, AnthropicModel(), order, load_lift_config(), out_dir="data/lift")`. Persisted results land in gitignored `data/lift/screen_{frame_code}.json`.
- [ ] Run it with `ANTHROPIC_API_KEY` set. Expect ~50–60 high-effort Opus calls.
- [ ] For each candidate, render `format_adjudication_packet(cand, result)` to read.

### Step C — Triage + adjudicate (with the user)

- [ ] Build each record's `screen:` block with `ScreenSummary.from_result(result, data_ref=f"data/lift/screen_{frame_code}.json")` (do not hand-transcribe the axes — derive them from the persisted `LiftResult`).
- [ ] For every candidate whose `screen_action == auto_kill` (null/negative_lift): write `docs/admissions/{frame_code}.yaml` with `decision: reject`, the full `screen:` block (both axes — preserves null vs negative_lift), and a one-line `rationale`. (The validator requires the screen verdict + rationale.)
- [ ] For every `surface` candidate: walk the five human gates with the user using the packet; record verdicts + `separating_artifact` + `nearest_sibling`; set `decision` ∈ {admit_provisional, file_as_subframe, reject}; write `docs/admissions/{frame_code}.yaml`.
- [ ] Each record must construct as a valid `AdmissionRecord` (the validator is the gate). Doctrine: expect ~1–2 admits; a high kill rate is the screen working (spec §11).

### Step D — Admit survivors (hand-authored content)

For each `admit_provisional` survivor:
- [ ] Append its `frame_code` to `process_frames` in `content/maps/founder_ceo.yaml`.
- [ ] Author the minimal experience `content/rubrics/{experience_id}.yaml` carrying the frame: `regime: open_ended`, a `mode`, a `ledger_ref` (reuse an existing owned problem from `data/seed/veldra_ledger.yaml`, or add a new gitignored seed entry + run `retnovation-ingest`), the frame in `frames:` with a `paired_trap`, and the trap in `traps:`. (Schema = `content/rubrics/license_continuity.yaml`.)
- [ ] If a new owned problem was needed, add the gitignored ledger seed entry (slug, domain, owned_problem, why_owned, unlabeled, provenance, corpus_pointers) — provenance is a pointer.
- [ ] Set the record's `admitted_as` to `{experience_id, ledger_ref}` and re-write `docs/admissions/{frame_code}.yaml`.

### Step E — Integrity check + production-path regression

- [ ] Run the integrity check in a scratch script:
  `check_content_graph_integrity(load_library(), load_map("founder_ceo")[0], {ledger_ref(s.slug) for s in load_seed(DEFAULT_SEED)}, [<the admission records>])` — must not raise.
- [ ] Add a fresh-DB regression test `tests/test_admission_regression.py` exercising each admitted frame through the **real gated path** (pattern from `tests/test_dry_run.py`). **Steer the selection explicitly — do NOT accept `proposal.top` (L-14 trap, confirmed in plan review):** the cold-start value function ranks by a `load` tiebreak, so if the new frame lands in a multi-frame rubric it drops in rank and `run_session` will select a *different* experience whose codes the `FakeModel` does not script → `KeyError` in `classify_response` (model.py). Concretely:
  1. **Author the new frame in a minimal load=1 rubric** (one frame, one trap) — Step D's minimal-experience requirement; this also keeps the regression's `FakeModel` small.
  2. `store = build_store(tmp_path / "db")` (auto-seeds the new rubric's `ledger_ref` — the L-8 path), `core = derive_core(aim())`.
  3. Build a `FakeModel` whose `intake` marks the new frame `absent` and whose `responses[frame_code] = [ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)]`.
  4. Call `run_session(store, core, fake, _now(), present=fixture, decide=_to_new_frame, decide_core=lambda c: [])` where `_to_new_frame` selects the new `experience_id` from `proposal.problem_menu()` (copy the `_to_license` pattern at `tests/test_dry_run.py:51-64`, swapping in the new `ledger_ref`), and `fixture` returns a `Work(opening=..., respond=lambda push: ...)`.
  5. Assert the new `frame_code` appears in `assessment.frame_deltas` and the reloaded `Store(...).load_state(_now())` has a non-weak strength for it.
  This proves the frame is reachable in production through the real select→assess→persist path, not just in a synthetic fixture (L-8/L-9), and is steered so a rank change cannot spuriously red the test (L-14).
- [ ] `PYTHONPATH=src .venv/bin/pytest -q` green; `ruff format . && ruff check .` clean.

### Step F — Commit, review, finish

- [ ] Commit the committable admit content + records + regression test explicitly (map, rubrics, `docs/admissions/*.yaml`, the regression test, DEVLOG). Confidentiality gates empty; no `Co-Authored-By`.
- [ ] OPUS whole-branch adversarial review (verify each commit independently green; re-check the two-axis record, the validator exits, the integrity check, no leak in committed records).
- [ ] `superpowers:finishing-a-development-branch` — ff-merge `frame-mining-sp2-mine-admit` to main, delete branch. Push is the user's call.

---

## Self-Review (completed during planning)

- **Spec coverage:** §4 components → T1–T5; §5 pipeline → Phase 2 A–F; §6 record+validator → T1; §7 confidentiality+abstraction rule → T2 (examples) + T5 (.gitignore/lessons/template); §8 admit+integrity+testing → T5 + Phase 2 D/E; §9 sequencing → Phase 1/2 split; §11 success criterion → Phase 2 C note. No gaps.
- **Placeholder scan:** none; the only deferred values are empirical screen outcomes in Phase 2, explicitly flagged.
- **Type consistency:** `MinedCandidate.to_candidate_frame`, `ScreenSummary.from_result`, `Gates` literal members, `AdmissionRecord.marginal_lift` (computed), `screen_candidate(..., *, out_dir)`, `check_content_graph_integrity(experiences, process_frames, valid_ledger_refs, records)` are used identically across tasks and tests. `ledger_ref` format `veldra:{slug}` matches `veldra_ingest.ledger_ref`.
