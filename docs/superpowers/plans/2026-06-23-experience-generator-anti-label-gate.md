# Experience Generator + Anti-Label Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the single fixed experience: make `select_experience` deterministically pick an authored Founder-CEO experience by process-frame coverage, bind it to a real ledger owned-problem, and gate it (anti-label + ≥8-angle depth) before it ships.

**Architecture:** A new `generator.py` owns the open-ended (posture-path) selector + the anti-label gate. `experience.py` becomes a thin `SELECTORS` registry dispatching by `regime` (mirroring `assessment.ASSESSORS`), so the CS domain-path selector is a clean Step-4 seam. The gate verifies anchoring (against the curated `corpus`) + structure deterministically; no model call in generation.

**Tech Stack:** Python ≥3.12, pydantic v2, PyYAML, SQLite (stdlib), pytest, ruff. No network/model in any Step-3 test.

## Global Constraints

- **Doctrine is data (L-1):** denylists + thresholds live in `content/gate/*.yaml`, frames/traps in `content/rubrics/*.yaml`; never hardcode doctrine values in `src/`.
- **Confidentiality (L-2):** tracked rubric YAML carries only the **abstracted** prompt + frame/trap codes + a `ledger_ref` *id*. Confidential corpus text (`why_owned`, `provenance`, raw friction) stays in gitignored `data/`. Run the `git ls-files` confidential check before every commit. Stage explicit paths only — never `git add -A`, never `-f`.
- **Determinism:** generation/selection makes zero model calls. Selection ties break by `experience_id`.
- **Closed gate vocabulary:** `GateCode` is a closed enum (5 hard rejects + 2 quality floors + 1 user-added depth floor). Extend only by a deliberate, tested migration.
- **Pre-commit gate (lessons.md):** `ruff format .` → `ruff check .` → `pytest` (all green) → update `docs/DEVLOG.md` → confidential check → explicit-path stage. No `Co-Authored-By` trailer.
- **Branch:** work on `step3-experience-generator` (already created).
- **Core-path review:** `generator.py`, the `experience.py` rewrite, and the `MAX_PUSHES` change are core path — an independent adversarial review runs before the final merge (see "Execution notes").

---

## File structure

| File | Create/Modify | Responsibility |
|---|---|---|
| `src/retnovation/types.py` | Modify | Add `GateCode`, `GateResult`; add `experience_id` to `Experience`. |
| `src/retnovation/content_loader.py` | Modify | Add `load_min_angle_count`, `load_denylist`, `load_experience`, `load_library`. |
| `src/retnovation/generator.py` | Create | `angle_count`, `GateError`, `anti_label_gate`, `load_gated_library`, `select_open_ended`, `select_cs_technical`. |
| `src/retnovation/experience.py` | Modify (rewrite) | `SELECTORS` registry + `select_experience` dispatch; retire `FIXED_EXPERIENCE`. |
| `src/retnovation/orchestration.py` | Modify | Load corpus, pass it to `select_experience`, use `exp.experience_id`. |
| `src/retnovation/cli.py` | Modify | Seed a real founder ledger + corpus + spec (drop the orphan ref). |
| `src/retnovation/assessment/judgment_loop.py` | Modify | `MAX_PUSHES` 6→8. |
| `content/gate/depth.yaml` | Create | `min_angle_count: 8`. |
| `content/gate/framework_denylist.yaml` | Create | Framework/method names. |
| `content/gate/scaffold_denylist.yaml` | Create | Category-cueing phrases. |
| `content/rubrics/veldra_licensing_continuity.yaml` | Rename → `license_continuity.yaml` | Re-home the orphan onto a real ledger entry (Task 5). |
| `content/rubrics/decision_under_stakes.yaml` | Create | Seed 2 (Bobby-Axe decision-rep). |
| `content/rubrics/proof_before_promise.yaml` | Create | Seed 3 (`bounded_error`). |
| `tests/test_generator.py` | Create | Gate unit tests + selector + acceptance + real-anchor (db-gated). |
| `tests/test_content_loader.py` | Modify | Loader tests for the new functions. |
| `tests/test_experience.py` | Modify (rewrite) | Dispatch + open-ended selection tests. |
| `tests/test_dry_run.py` | Modify | Use the re-homed seed + corpus. |
| `tests/test_orchestration.py` | Modify | Use the re-homed seed + corpus + `experience_id`. |

**Task dependency note:** the flip from the fixed experience to the gated generator (Task 5) is atomic — `experience.py`, the orphan, `orchestration`, `cli`, and the e2e tests must change together to stay green. The orphan is **re-homed (renamed + re-anchored)**, not deleted, which both retires its dangling `ledger_ref` and keeps every intermediate state green. The other two seeds land in Task 6.

---

### Task 1: Gate vocabulary + `experience_id` on Experience

**Files:**
- Modify: `src/retnovation/types.py`
- Modify: `src/retnovation/content_loader.py` (`load_experience_meta` returns `experience_id`)
- Modify: `src/retnovation/experience.py` (populate `experience_id` so the suite stays green)
- Test: `tests/test_types.py`

**Interfaces:**
- Produces: `GateCode` (str Enum: `recoverable_label`, `pre_named_framework`, `type_hint_scaffold`, `softened_ambiguity`, `cosmetic_engagement`, `owned_or_real`, `process_layer_load`, `insufficient_interrogation_depth`); `GateResult(passed: bool, rejects: list[GateCode], downgrades: list[GateCode], angle_count: int)`; `Experience.experience_id: str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_types.py`:
```python
def test_gatecode_and_gateresult_and_experience_id():
    from retnovation.types import GateCode, GateResult, Experience, Rubric, Mode, Regime

    assert GateCode.recoverable_label.value == "recoverable_label"
    assert len(list(GateCode)) == 8

    res = GateResult(passed=False, rejects=[GateCode.recoverable_label], downgrades=[], angle_count=4)
    assert res.passed is False
    assert res.angle_count == 4

    exp = Experience(
        experience_id="x",
        prompt="p",
        rubric=Rubric(frames=[], traps=[], mode=Mode.genuinely_open, binding_constraint=None),
        ledger_ref="veldra:x",
        regime=Regime.open_ended,
    )
    assert exp.experience_id == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_types.py::test_gatecode_and_gateresult_and_experience_id -v`
Expected: FAIL with `ImportError`/`AttributeError` (`GateCode` undefined).

- [ ] **Step 3: Add the types**

In `src/retnovation/types.py`, after the `StopReason` enum (around line 44), add:
```python
class GateCode(str, Enum):
    recoverable_label = "recoverable_label"
    pre_named_framework = "pre_named_framework"
    type_hint_scaffold = "type_hint_scaffold"
    softened_ambiguity = "softened_ambiguity"
    cosmetic_engagement = "cosmetic_engagement"
    owned_or_real = "owned_or_real"
    process_layer_load = "process_layer_load"
    insufficient_interrogation_depth = "insufficient_interrogation_depth"
```
Add `experience_id: str` as the first field of `Experience`:
```python
class Experience(BaseModel):
    experience_id: str
    prompt: str
    rubric: Rubric
    ledger_ref: str
    regime: Regime
```
Add the result model after `Experience`:
```python
class GateResult(BaseModel):
    passed: bool
    rejects: list[GateCode]
    downgrades: list[GateCode]
    angle_count: int
```

- [ ] **Step 4: Keep existing Experience construction green**

In `src/retnovation/content_loader.py`, change `load_experience_meta` to also return the id:
```python
def load_experience_meta(name: str, root: Path | None = None) -> dict:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    return {
        "experience_id": data["experience_id"],
        "prompt": data["prompt"],
        "ledger_ref": data["ledger_ref"],
        "regime": data["regime"],
    }
```
In `src/retnovation/experience.py`, pass `experience_id` in the existing `Experience(...)` construction:
```python
    return Experience(
        experience_id=meta["experience_id"],
        prompt=meta["prompt"],
        rubric=rubric,
        ledger_ref=ledger_ref,
        regime=Regime(meta["regime"]),
    )
```

- [ ] **Step 5: Run the full suite to verify green**

Run: `.venv/bin/pytest -q`
Expected: PASS (41 passed, 1 skipped — one new test added).

- [ ] **Step 6: Commit**

```bash
ruff format . && ruff check .
git add src/retnovation/types.py src/retnovation/content_loader.py src/retnovation/experience.py tests/test_types.py
git commit -m "feat: add GateCode/GateResult types + experience_id on Experience"
```

---

### Task 2: Content loaders for gate config, denylists, and the experience library

**Files:**
- Modify: `src/retnovation/content_loader.py`
- Create: `content/gate/depth.yaml`, `content/gate/framework_denylist.yaml`, `content/gate/scaffold_denylist.yaml`
- Test: `tests/test_content_loader.py`

**Interfaces:**
- Consumes: `Experience`, `Rubric`, `Frame`, `Trap`, `Regime`, `Mode` (types.py).
- Produces:
  - `load_min_angle_count(root: Path | None = None) -> int`
  - `load_denylist(name: str, root: Path | None = None) -> list[str]`
  - `load_experience(name: str, root: Path | None = None) -> Experience`
  - `load_library(root: Path | None = None) -> list[Experience]`

- [ ] **Step 1: Create the gate content files**

`content/gate/depth.yaml`:
```yaml
# Minimum distinct interrogation angles an experience must afford.
# angle_count = frames + traps + (1 if binding_constraint) + 4 universal artifact dimensions.
# User-set floor (no corpus basis); doctrine-compatible. Configurable; calibrate from angle_count data.
min_angle_count: 8
```
`content/gate/framework_denylist.yaml`:
```yaml
# Named methods/frameworks. If the prompt names one, it pre-labels the problem (pre_named_framework).
# Method names ONLY — never domain vocabulary (a roleplay may say "leverage" or "hostile takeover").
- swot
- first principles
- five forces
- porter's five forces
- ooda loop
- 5 whys
- five whys
- cost-benefit analysis
- decision matrix
- second-order thinking
- expected value calculation
- bcg matrix
- eisenhower matrix
```
`content/gate/scaffold_denylist.yaml`:
```yaml
# Category-cueing scaffolds. If the prompt cues the problem TYPE, it scaffolds the answer (type_hint_scaffold).
- this is a
- classic case of
- apply the
- use the framework
- the right framework
- which framework
- this is an example of
- think of this as a
- treat this as a
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_content_loader.py`:
```python
def test_load_min_angle_count_and_denylists():
    from retnovation.content_loader import load_min_angle_count, load_denylist

    assert load_min_angle_count() == 8
    fw = load_denylist("framework_denylist")
    assert "swot" in fw and all(isinstance(t, str) for t in fw)
    sc = load_denylist("scaffold_denylist")
    assert "this is a" in sc


def test_load_experience_and_library_build_full_experiences():
    from retnovation.content_loader import load_experience, load_library
    from retnovation.types import Experience, Regime

    lib = load_library()
    assert lib, "content/rubrics should hold at least one experience"
    assert all(isinstance(e, Experience) for e in lib)
    one = lib[0]
    again = load_experience(one.experience_id)
    assert again.experience_id == one.experience_id
    assert again.regime in (Regime.open_ended, Regime.cs_technical)
    assert again.rubric.frames or again.rubric.traps
```
> Note: at this point `load_experience(one.experience_id)` works only because the single existing rubric's filename stem (`veldra_licensing_continuity`) equals its `experience_id`. Task 5 preserves that filename==id invariant for every seed.

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_content_loader.py::test_load_min_angle_count_and_denylists -v`
Expected: FAIL with `ImportError` (`load_min_angle_count` undefined).

- [ ] **Step 4: Implement the loaders**

In `src/retnovation/content_loader.py`, update the type import line to:
```python
from .types import Experience, Frame, Mode, Regime, Rubric, Trap
```
and append:
```python
def load_min_angle_count(root: Path | None = None) -> int:
    data = yaml.safe_load((_root(root) / "gate" / "depth.yaml").read_text())
    return int(data["min_angle_count"])


def load_denylist(name: str, root: Path | None = None) -> list[str]:
    data = yaml.safe_load((_root(root) / "gate" / f"{name}.yaml").read_text())
    if not isinstance(data, list):
        raise ValueError(f"denylist {name} must be a YAML list")
    return [str(x).lower() for x in data]


def load_experience(name: str, root: Path | None = None) -> Experience:
    data = yaml.safe_load((_root(root) / "rubrics" / f"{name}.yaml").read_text())
    rubric = Rubric(
        frames=[Frame(**f) for f in data["frames"]],
        traps=[Trap(**t) for t in data["traps"]],
        mode=Mode(data["mode"]),
        binding_constraint=data.get("binding_constraint"),
    )
    return Experience(
        experience_id=data["experience_id"],
        prompt=data["prompt"],
        rubric=rubric,
        ledger_ref=data["ledger_ref"],
        regime=Regime(data["regime"]),
    )


def load_library(root: Path | None = None) -> list[Experience]:
    rubrics = sorted((_root(root) / "rubrics").glob("*.yaml"))
    return [load_experience(p.stem, root=root) for p in rubrics]
```

- [ ] **Step 5: Run loader tests to verify they pass**

Run: `.venv/bin/pytest tests/test_content_loader.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
ruff format . && ruff check .
git add src/retnovation/content_loader.py content/gate/depth.yaml content/gate/framework_denylist.yaml content/gate/scaffold_denylist.yaml tests/test_content_loader.py
git commit -m "feat: content loaders for gate config, denylists, and the experience library"
```

---

### Task 3: The anti-label gate

**Files:**
- Create: `src/retnovation/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: `Experience`, `Rubric`, `CorpusEntry`, `GateCode`, `GateResult`, `Mode` (types.py).
- Produces:
  - `class GateError(RuntimeError)`
  - `angle_count(rubric: Rubric) -> int`
  - `anti_label_gate(exp: Experience, corpus_entry: CorpusEntry | None, *, min_angle_count: int, framework_denylist: list[str], scaffold_denylist: list[str]) -> GateResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generator.py`:
```python
import pytest

from retnovation.types import (
    CorpusEntry, Experience, Frame, Trap, Rubric, Mode, Regime, GateCode,
)


def _corpus(ref="veldra:x", unlabeled="x is unlabeled", why="real stakes", prov="docs/X"):
    return CorpusEntry(
        ledger_ref=ref, domain="founder_ceo", why_owned=why,
        unlabeled=unlabeled, provenance=prov, corpus_pointers=[],
    )


def _exp(prompt="Decide what you do and account for what you are trading.",
         frames=None, traps=None, mode=Mode.genuinely_open, binding=None, ref="veldra:x"):
    frames = frames if frames is not None else [
        Frame(frame_code="lead_with_what_you_refuse_to_do", frame_detail="State the boundary first.",
              paired_trap="scope_creep_to_please"),
        Frame(frame_code="protect_the_core_lane", frame_detail="Keep the core promise intact.",
              paired_trap="erode_core_for_one_customer"),
    ]
    traps = traps if traps is not None else [
        Trap(trap_code="scope_creep_to_please", trap_detail="Bending to avoid saying no."),
        Trap(trap_code="erode_core_for_one_customer", trap_detail="Weakening the core for one account."),
    ]
    return Experience(
        experience_id="t", prompt=prompt,
        rubric=Rubric(frames=frames, traps=traps, mode=mode, binding_constraint=binding),
        ledger_ref=ref, regime=Regime.open_ended,
    )


GATE_KW = dict(min_angle_count=8, framework_denylist=["swot", "five forces"],
               scaffold_denylist=["this is a", "apply the"])


def test_angle_count_counts_frames_traps_binding_and_four_dims():
    from retnovation.generator import angle_count
    assert angle_count(_exp().rubric) == 2 + 2 + 0 + 4  # 8
    assert angle_count(_exp(mode=Mode.bounded_error, binding="hard line").rubric) == 9


def test_good_experience_passes():
    from retnovation.generator import anti_label_gate
    res = anti_label_gate(_exp(), _corpus(), **GATE_KW)
    assert res.passed and res.rejects == [] and res.angle_count == 8


def test_recoverable_label_trips_when_corpus_missing_or_unlabeled_empty():
    from retnovation.generator import anti_label_gate
    assert GateCode.recoverable_label in anti_label_gate(_exp(), None, **GATE_KW).rejects
    assert GateCode.recoverable_label in anti_label_gate(
        _exp(), _corpus(unlabeled="   "), **GATE_KW).rejects


def test_pre_named_framework_trips_on_method_name_and_frame_leak():
    from retnovation.generator import anti_label_gate
    assert GateCode.pre_named_framework in anti_label_gate(
        _exp(prompt="Run a SWOT and decide."), _corpus(), **GATE_KW).rejects
    assert GateCode.pre_named_framework in anti_label_gate(
        _exp(prompt="Lead with what you refuse to do, then decide."), _corpus(), **GATE_KW).rejects


def test_type_hint_scaffold_trips_on_category_cue():
    from retnovation.generator import anti_label_gate
    assert GateCode.type_hint_scaffold in anti_label_gate(
        _exp(prompt="This is a tradeoff problem; decide."), _corpus(), **GATE_KW).rejects


def test_softened_ambiguity_trips_on_mode_dishonesty():
    from retnovation.generator import anti_label_gate
    assert GateCode.softened_ambiguity in anti_label_gate(
        _exp(mode=Mode.genuinely_open, binding="a hard line"), _corpus(), **GATE_KW).rejects
    assert GateCode.softened_ambiguity in anti_label_gate(
        _exp(mode=Mode.bounded_error, binding=None), _corpus(), **GATE_KW).rejects


def test_cosmetic_engagement_trips_on_wrapper_or_missing_stakes():
    from retnovation.generator import anti_label_gate
    assert GateCode.cosmetic_engagement in anti_label_gate(
        _exp(prompt="Keep your streak alive and decide."), _corpus(), **GATE_KW).rejects
    assert GateCode.cosmetic_engagement in anti_label_gate(
        _exp(), _corpus(why="   "), **GATE_KW).rejects


def test_depth_floor_trips_below_min_angle_count():
    from retnovation.generator import anti_label_gate
    thin = _exp(frames=[Frame(frame_code="protect_the_core_lane", frame_detail="d", paired_trap=None)],
                traps=[])
    res = anti_label_gate(thin, _corpus(), **GATE_KW)  # 1 + 0 + 0 + 4 = 5 < 8
    assert GateCode.insufficient_interrogation_depth in res.rejects
    assert res.passed is False


def test_quality_floors_downgrade_not_reject():
    from retnovation.generator import anti_label_gate
    res = anti_label_gate(_exp(), _corpus(prov="   "), **GATE_KW)  # empty provenance
    assert GateCode.owned_or_real in res.downgrades
    assert res.passed is True  # floors downgrade, never reject
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'retnovation.generator'`.

- [ ] **Step 3: Implement the gate**

Create `src/retnovation/generator.py`:
```python
from __future__ import annotations

import re

from .types import CorpusEntry, Experience, GateCode, GateResult, Mode, Rubric

ARTIFACT_DIMENSIONS = 4  # rigor, completeness, internal consistency, defensible assumptions (FounderCEO §2)
WRAPPER_WORDS = ("streak", "points", "badge", "leaderboard", "timer", "reward", "level up")

HARD_REJECTS = frozenset({
    GateCode.recoverable_label,
    GateCode.pre_named_framework,
    GateCode.type_hint_scaffold,
    GateCode.softened_ambiguity,
    GateCode.cosmetic_engagement,
    GateCode.insufficient_interrogation_depth,
})
QUALITY_FLOORS = frozenset({GateCode.owned_or_real, GateCode.process_layer_load})


class GateError(RuntimeError):
    """Raised when no shippable experience exists, or a rubric fails the gate at load."""


def angle_count(rubric: Rubric) -> int:
    binding = 1 if rubric.binding_constraint else 0
    return len(rubric.frames) + len(rubric.traps) + binding + ARTIFACT_DIMENSIONS


def _contains_phrase(text_lc: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text_lc) is not None


def _frame_trap_phrases(rubric: Rubric) -> list[str]:
    phrases: list[str] = []
    for code in [f.frame_code for f in rubric.frames] + [t.trap_code for t in rubric.traps]:
        phrases.append(code.lower())
        phrases.append(code.replace("_", " ").lower())
    return phrases


def anti_label_gate(
    exp: Experience,
    corpus_entry: CorpusEntry | None,
    *,
    min_angle_count: int,
    framework_denylist: list[str],
    scaffold_denylist: list[str],
) -> GateResult:
    rejects: list[GateCode] = []
    downgrades: list[GateCode] = []
    prompt_lc = exp.prompt.lower()
    rubric = exp.rubric

    # recoverable_label: anchored to a curated owned-problem with a non-empty unlabeled rationale.
    if corpus_entry is None or not corpus_entry.unlabeled.strip():
        rejects.append(GateCode.recoverable_label)

    # pre_named_framework: no named method, and no leaked frame/trap code (snake or spaced).
    banned = [t.lower() for t in framework_denylist] + _frame_trap_phrases(rubric)
    if any(_contains_phrase(prompt_lc, p) for p in banned):
        rejects.append(GateCode.pre_named_framework)

    # type_hint_scaffold: no category-cueing scaffold phrase.
    if any(_contains_phrase(prompt_lc, p) for p in scaffold_denylist):
        rejects.append(GateCode.type_hint_scaffold)

    # softened_ambiguity: mode honesty — genuinely_open ⇒ no binding; bounded_error ⇒ a binding.
    has_binding = rubric.binding_constraint is not None
    if (rubric.mode is Mode.genuinely_open and has_binding) or (
        rubric.mode is Mode.bounded_error and not has_binding
    ):
        rejects.append(GateCode.softened_ambiguity)

    # cosmetic_engagement: real stakes present (corpus.why_owned) and no wrapper/gamification words.
    no_stakes = corpus_entry is None or not corpus_entry.why_owned.strip()
    if no_stakes or any(w in prompt_lc for w in WRAPPER_WORDS):
        rejects.append(GateCode.cosmetic_engagement)

    # insufficient_interrogation_depth (hard, user floor)
    ac = angle_count(rubric)
    if ac < min_angle_count:
        rejects.append(GateCode.insufficient_interrogation_depth)

    # quality floors (downgrade, never reject)
    if corpus_entry is None or not corpus_entry.provenance.strip():
        downgrades.append(GateCode.owned_or_real)
    if len(rubric.frames) < 1:
        downgrades.append(GateCode.process_layer_load)

    return GateResult(passed=len(rejects) == 0, rejects=rejects, downgrades=downgrades, angle_count=ac)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: PASS (all gate tests green).

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
git add src/retnovation/generator.py tests/test_generator.py
git commit -m "feat: deterministic anti-label gate (5 rejects, 2 floors, depth floor)"
```

---

### Task 4: Gated library load + the open-ended selector + CS stub

**Files:**
- Modify: `src/retnovation/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: `load_library`, `load_min_angle_count`, `load_denylist` (content_loader); `anti_label_gate`, `GateError` (Task 3).
- Produces:
  - `load_gated_library(corpus: list[CorpusEntry], root=None) -> list[tuple[Experience, GateResult]]` (raises `GateError` on any hard-reject rubric)
  - `select_open_ended(core, state, ledger, corpus, spec, root=None) -> Experience`
  - `select_cs_technical(core, state, ledger, corpus, spec, root=None) -> Experience` (raises `NotImplementedError`)

All tests use a **temp content root**, so they are hermetic and independent of the real `content/`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generator.py`:
```python
def _write_gate_files(root):
    (root / "gate").mkdir()
    (root / "gate" / "depth.yaml").write_text("min_angle_count: 8\n")
    (root / "gate" / "framework_denylist.yaml").write_text("- swot\n")
    (root / "gate" / "scaffold_denylist.yaml").write_text("- this is a\n")
    (root / "rubrics").mkdir()


def _write_seed(root, eid, ref, frames):
    lines = [f"experience_id: {eid}", f'ledger_ref: "{ref}"', "regime: open_ended",
             "mode: genuinely_open", "binding_constraint: null",
             "prompt: Decide and account for the trade today.", "frames:"]
    traps = []
    for code, trap in frames:
        lines.append(f"  - {{frame_code: {code}, frame_detail: angle, paired_trap: {trap}}}")
        traps.append(trap)
    lines.append("traps:")
    for trap in traps:
        lines.append(f"  - {{trap_code: {trap}, trap_detail: shortcut}}")
    (root / "rubrics" / f"{eid}.yaml").write_text("\n".join(lines) + "\n")


def test_load_gated_library_raises_on_a_bad_rubric(tmp_path):
    from retnovation.generator import load_gated_library, GateError
    _write_gate_files(tmp_path)
    # one thin (sub-8-angle) rubric: 1 frame + 1 trap + 4 = 6 < 8
    _write_seed(tmp_path, "thin", "veldra:x", [("protect_the_core_lane", "erode_core_for_one_customer")])
    with pytest.raises(GateError):
        load_gated_library([_corpus(ref="veldra:x")], root=tmp_path)


def test_select_open_ended_ranks_by_frame_coverage(tmp_path):
    from retnovation.generator import select_open_ended
    from retnovation.types import LearnerState, NextExperienceSpec
    _write_gate_files(tmp_path)
    _write_seed(tmp_path, "seed_a", "veldra:a", [
        ("lead_with_what_you_refuse_to_do", "scope_creep_to_please"),
        ("protect_the_core_lane", "erode_core_for_one_customer")])
    _write_seed(tmp_path, "seed_b", "veldra:b", [
        ("choose_the_failure_default_deliberately", "assumed_the_happy_path"),
        ("lead_with_what_you_refuse_to_do", "scope_creep_to_please")])
    corpus = [_corpus(ref="veldra:a"), _corpus(ref="veldra:b")]
    spec = NextExperienceSpec(target_frames=["protect_the_core_lane"], ledger_ref="",
                              regime=Regime.open_ended)
    exp = select_open_ended(core=None, state=LearnerState(), ledger=[], corpus=corpus,
                            spec=spec, root=tmp_path)
    assert exp.experience_id == "seed_a"  # only A carries protect_the_core_lane


def test_select_cs_technical_is_a_step4_stub():
    from retnovation.generator import select_cs_technical
    with pytest.raises(NotImplementedError):
        select_cs_technical(core=None, state=None, ledger=[], corpus=[], spec=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_generator.py::test_select_open_ended_ranks_by_frame_coverage -v`
Expected: FAIL with `ImportError` (`select_open_ended` undefined).

- [ ] **Step 3: Implement the gated library + selectors**

Append to `src/retnovation/generator.py` and add the imports at the top of the file:
```python
from .content_loader import load_denylist, load_library, load_min_angle_count
```
```python
def load_gated_library(corpus, root=None):
    """Load every authored experience and gate it. Raise on any hard reject (fail loud at load)."""
    min_angle = load_min_angle_count(root)
    fw = load_denylist("framework_denylist", root)
    sc = load_denylist("scaffold_denylist", root)
    by_ref = {c.ledger_ref: c for c in corpus}
    out: list[tuple[Experience, GateResult]] = []
    for exp in load_library(root):
        res = anti_label_gate(
            exp, by_ref.get(exp.ledger_ref),
            min_angle_count=min_angle, framework_denylist=fw, scaffold_denylist=sc,
        )
        if not res.passed:
            raise GateError(f"{exp.experience_id} failed the gate: {[c.value for c in res.rejects]}")
        out.append((exp, res))
    return out


def _coverage(exp: Experience, target_frames: list[str]) -> int:
    codes = {f.frame_code for f in exp.rubric.frames}
    return sum(1 for tf in target_frames if tf in codes)


def select_open_ended(core, state, ledger, corpus, spec, root=None) -> Experience:
    gated = [(e, r) for (e, r) in load_gated_library(corpus, root) if e.regime is Regime.open_ended]
    if not gated:
        raise GateError("no shippable open_ended experience in the library")
    target = spec.target_frames if spec is not None else []
    # Rank: most target-frame coverage first; clean experiences before downgraded; then id.
    ranked = sorted(
        gated,
        key=lambda er: (-_coverage(er[0], target), len(er[1].downgrades), er[0].experience_id),
    )
    return ranked[0][0]


def select_cs_technical(core, state, ledger, corpus, spec, root=None) -> Experience:
    raise NotImplementedError("cs_technical domain-path selector is built in step 4")
```
Also add `Regime` to the `from .types import (...)` line at the top of `generator.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: PASS (gate + library + selector + stub tests green). Full suite still green (`.venv/bin/pytest -q`) — the real `experience.py`/orchestration are untouched.

- [ ] **Step 5: Commit**

```bash
ruff format . && ruff check .
git add src/retnovation/generator.py tests/test_generator.py
git commit -m "feat: gated library load + open_ended selector + cs_technical Step-4 stub"
```

---

### Task 5: Flip to the gated generator (re-home the orphan as the single seed)

This is the atomic cut from the fixed experience to the gated generator. The orphan is **re-homed** (renamed + re-anchored to a real ledger entry), `experience.py` becomes the `SELECTORS` dispatcher, and `orchestration`/`cli`/e2e tests move onto the gated path. The suite is green at the end.

**Files:**
- Rename + edit: `content/rubrics/veldra_licensing_continuity.yaml` → `content/rubrics/license_continuity.yaml`
- Modify (rewrite): `src/retnovation/experience.py`
- Modify: `src/retnovation/orchestration.py`, `src/retnovation/cli.py`
- Modify (rewrite): `tests/test_experience.py`; Modify: `tests/test_dry_run.py`, `tests/test_orchestration.py`

**Interfaces:**
- Produces: `SELECTORS: dict[Regime, Callable]`; `select_experience(core, state, ledger, corpus, spec=None, root=None) -> Experience`; **removes** `FIXED_EXPERIENCE`. `run_session` records `exp.experience_id`.

- [ ] **Step 1: Re-home the orphan**

```bash
git mv content/rubrics/veldra_licensing_continuity.yaml content/rubrics/license_continuity.yaml
```
Then edit `content/rubrics/license_continuity.yaml` — change only the first two lines:
```yaml
experience_id: license_continuity
ledger_ref: "veldra:license_fork_risk"
```
(Leave `regime`, `mode`, `binding_constraint`, `prompt`, the 2 frames, and the 2 traps unchanged — 2+2+4 = 8 angles.)

- [ ] **Step 2: Rewrite `experience.py`**

Replace the entire contents of `src/retnovation/experience.py`:
```python
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import generator
from .types import Core, CorpusEntry, Experience, LearnerState, LedgerEntry, NextExperienceSpec, Regime

# Experience selection is pluggable by regime, mirroring assessment.ASSESSORS, so the CS
# domain-path selector (content-concept coverage) is a clean Step-4 seam and is never
# collapsed into the founder posture-path's process-frame coverage (Complete Picture §10).
SELECTORS: dict[Regime, Callable] = {
    Regime.open_ended: generator.select_open_ended,
    Regime.cs_technical: generator.select_cs_technical,
}


def select_experience(
    core: Core,
    state: LearnerState,
    ledger: list[LedgerEntry],
    corpus: list[CorpusEntry],
    spec: NextExperienceSpec | None = None,
    root: Path | None = None,
) -> Experience:
    regime = spec.regime if spec is not None else Regime.open_ended
    return SELECTORS[regime](core, state, ledger, corpus, spec, root)
```

- [ ] **Step 3: Update `orchestration.py`**

Change the import line `from .experience import FIXED_EXPERIENCE, select_experience` to `from .experience import select_experience`, and replace the `run_session` body (lines 33–43) with:
```python
    state = store.load_state()
    ledger = store.load_ledger()
    corpus = store.load_corpus()
    spec = store.queue_pop()
    exp = select_experience(core, state, ledger, corpus, spec)
    work = present(exp)
    assessor = get_assessor(exp.regime)
    assessment = assessor(exp, work, model)
    state = update_state(state, assessment, now, exp.experience_id)
    store.save_state(state)
    store.queue_push(schedule_next(state, ledger, now, exp.regime))
    return state, assessment
```

- [ ] **Step 4: Update `cli.py`**

Replace the `_SEED_PROBLEM` constant and `build_store` in `src/retnovation/cli.py`:
```python
DEFAULT_DB = Path("data/retnovation.db")
_SEED_REF = "veldra:license_fork_risk"
_SEED_PROBLEM = "A licensing-continuity decision under a same-day deadline (abstracted seed)."


def build_store(db_path: str | Path = DEFAULT_DB) -> Store:
    store = Store(db_path)
    if not store.load_ledger():
        store.add_ledger_entry(LedgerEntry(id=_SEED_REF, owned_problem=_SEED_PROBLEM))
    if store.get_corpus(_SEED_REF) is None:
        store.upsert_corpus(CorpusEntry(
            ledger_ref=_SEED_REF, domain="founder_ceo", why_owned="seed stakes (abstracted)",
            unlabeled="genuinely unlabeled (abstracted seed)", provenance="seed", corpus_pointers=[]))
    if store.queue_len() == 0:
        store.queue_push(NextExperienceSpec(
            target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
            ledger_ref=_SEED_REF, regime=Regime.open_ended))
    return store
```
Update the `cli.py` import line to: `from .types import CorpusEntry, LedgerEntry, NextExperienceSpec, Regime`.
> `retnovation-ingest` (Step 2) overwrites this hermetic seed with the real confidential corpus when run; both leave a gate-passing experience selectable.

- [ ] **Step 5: Rewrite `tests/test_experience.py`**

Replace the entire contents:
```python
import pytest

from retnovation.aim import aim, derive_core
from retnovation.experience import SELECTORS, select_experience
from retnovation.persistence import Store
from retnovation.types import CorpusEntry, LearnerState, NextExperienceSpec, Regime

SEED_REFS = ("veldra:license_fork_risk", "veldra:concentrated_market_pricing_power",
             "veldra:first_customer_proof_loop")


def _seed_corpus(store: Store):
    """Synthetic (non-confidential) corpus covering every authored seed's ledger_ref."""
    for ref in SEED_REFS:
        store.upsert_corpus(CorpusEntry(
            ledger_ref=ref, domain="founder_ceo", why_owned="real stakes",
            unlabeled="genuinely unlabeled", provenance="synthetic-test", corpus_pointers=[]))


def test_selectors_registry_routes_by_regime():
    assert Regime.open_ended in SELECTORS and Regime.cs_technical in SELECTORS


def test_select_experience_dispatches_open_ended_and_gates(tmp_path):
    store = Store(tmp_path / "e.db")
    _seed_corpus(store)
    spec = NextExperienceSpec(target_frames=["protect_the_core_lane"], ledger_ref="",
                              regime=Regime.open_ended)
    exp = select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)
    assert exp.regime is Regime.open_ended
    assert exp.experience_id and exp.ledger_ref.startswith("veldra:")
    assert any(f.frame_code == "protect_the_core_lane" for f in exp.rubric.frames)


def test_select_experience_cs_technical_is_stubbed(tmp_path):
    store = Store(tmp_path / "e2.db")
    _seed_corpus(store)
    spec = NextExperienceSpec(target_frames=[], ledger_ref="", regime=Regime.cs_technical)
    with pytest.raises(NotImplementedError):
        select_experience(derive_core(aim()), LearnerState(), [], store.load_corpus(), spec)


def test_fixed_experience_is_retired():
    import retnovation.experience as experience_mod
    assert not hasattr(experience_mod, "FIXED_EXPERIENCE")
```
> `_seed_corpus` already covers all three seed refs, so it keeps working unchanged when Task 6 adds the other two seeds.

- [ ] **Step 6: Update `tests/test_dry_run.py`**

Add `CorpusEntry` to the `from retnovation.types import (...)` block. Replace the arrange block (the `store = Store(...)` through `queue_push(...)`, lines 51–64) with:
```python
    store = Store(tmp_path / "dryrun.db")
    store.add_ledger_entry(LedgerEntry(
        id="veldra:license_fork_risk",
        owned_problem="A licensing-continuity decision under a same-day deadline."))
    store.upsert_corpus(CorpusEntry(
        ledger_ref="veldra:license_fork_risk", domain="founder_ceo", why_owned="real stakes",
        unlabeled="genuinely unlabeled", provenance="synthetic-test", corpus_pointers=[]))
    store.queue_push(NextExperienceSpec(
        target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
        ledger_ref="veldra:license_fork_risk", regime=Regime.open_ended))
```
The cooperative model already classifies `lead_with_what_you_refuse_to_do`/`protect_the_core_lane` + their traps — exactly the `license_continuity` rubric — so the trajectory/frame-delta assertions hold unchanged.

- [ ] **Step 7: Update `tests/test_orchestration.py`**

Remove the line `from retnovation.experience import FIXED_EXPERIENCE`. Add `CorpusEntry` to the `from retnovation.types import (...)` block. Replace the arrange block (lines 44–51) with:
```python
    store.add_ledger_entry(LedgerEntry(id="veldra:license_fork_risk", owned_problem="..."))
    store.upsert_corpus(CorpusEntry(
        ledger_ref="veldra:license_fork_risk", domain="founder_ceo", why_owned="stakes",
        unlabeled="unlabeled", provenance="synthetic-test", corpus_pointers=[]))
    store.queue_push(NextExperienceSpec(
        target_frames=["protect_the_core_lane"],
        ledger_ref="veldra:license_fork_risk", regime=Regime.open_ended))
```
and replace the final assertion (line 61) with:
```python
    assert any("license_continuity" in fs.last_evidence for fs in state.frames.values())
```

- [ ] **Step 8: Run the full suite to verify green**

Run: `ruff format . && ruff check . && .venv/bin/pytest -q`
Expected: PASS (all green; 1 skipped live test). With one rubric (`license_continuity`) in the library and corpus for `veldra:license_fork_risk`, `load_gated_library` gates it and selection returns it.

- [ ] **Step 9: Confirm the orphan ref is gone and no confidential leak**

Run:
```bash
grep -rn "veldra:licensing_continuity" src/ tests/ content/ || echo "(orphan ref gone)"
git ls-files content/rubrics/ ; grep -riE 'why_owned|provenance|PB-|ADR-|TESTLOG' content/rubrics/ || echo "(clean — abstracted prompts only)"
```
Expected: orphan ref gone; rubric grep clean.

- [ ] **Step 10: Commit**

```bash
git add src/retnovation/experience.py src/retnovation/orchestration.py src/retnovation/cli.py \
  content/rubrics/license_continuity.yaml tests/test_experience.py tests/test_dry_run.py tests/test_orchestration.py
git commit -m "feat: flip to the gated generator; re-home the orphan onto a real ledger entry"
```

---

### Task 6: Add the remaining two founder seeds + the acceptance tests

**Files:**
- Create: `content/rubrics/decision_under_stakes.yaml`, `content/rubrics/proof_before_promise.yaml`
- Test: `tests/test_generator.py` (append acceptance + discrimination + real-anchor tests)

**Interfaces:**
- Consumes: `load_library`, `load_min_angle_count`, `load_denylist`, `anti_label_gate`, `angle_count`; `Store.get_corpus`.
- Produces: two more gate-passing `open_ended` founder experiences (one `bounded_error`), with frame subsets distinct from `license_continuity` so the selector discriminates.

- [ ] **Step 1: Author the two seeds**

`content/rubrics/decision_under_stakes.yaml` (Bobby-Axe decision-rep; 2 frames + 2 traps + 4 = 8):
```yaml
experience_id: decision_under_stakes
ledger_ref: "veldra:concentrated_market_pricing_power"
regime: open_ended
mode: genuinely_open
binding_constraint: null
prompt: >
  You hold unusual pricing power in a concentrated market. One move could lock in a year of
  margin or trigger a backlash that invites a competitor in. The number is yours to set, today,
  on incomplete information. Make the call and account for how it fails if you are wrong.
  (No framework is named for you on purpose.)
frames:
  - frame_code: choose_the_failure_default_deliberately
    frame_detail: State which way it fails if you are wrong, and justify defaulting to the reversible direction.
    paired_trap: assumed_the_happy_path
  - frame_code: lead_with_what_you_refuse_to_do
    frame_detail: State the boundary you will not cross before proposing any action.
    paired_trap: scope_creep_to_please
traps:
  - trap_code: assumed_the_happy_path
    trap_detail: Failure direction left unstated, or defaulted to whatever was cheapest.
  - trap_code: scope_creep_to_please
    trap_detail: Bending the offer to avoid saying no.
```
`content/rubrics/proof_before_promise.yaml` (`bounded_error`; 2 frames + 2 traps + 1 binding + 4 = 9):
```yaml
experience_id: proof_before_promise
ledger_ref: "veldra:first_customer_proof_loop"
regime: open_ended
mode: bounded_error
binding_constraint: >
  You may not commit to a capability the system has not actually demonstrated end to end;
  an unproven claim made to win the deal is the hard line you do not cross.
prompt: >
  Your first reference customer will sign if you commit to a capability you have not yet proven
  end to end. Closing them funds the next two quarters; over-committing and missing puts the only
  proof you have at risk. Decide what you commit to and on what evidence. (No framework is named
  for you on purpose.)
frames:
  - frame_code: protect_the_core_lane
    frame_detail: Keep the promise the core product makes to everyone intact under pressure.
    paired_trap: erode_core_for_one_customer
  - frame_code: choose_the_failure_default_deliberately
    frame_detail: State which way it fails if you are wrong, and justify defaulting to the reversible direction.
    paired_trap: assumed_the_happy_path
traps:
  - trap_code: erode_core_for_one_customer
    trap_detail: Special-casing one account in a way that weakens the core promise.
  - trap_code: assumed_the_happy_path
    trap_detail: Failure direction left unstated, or defaulted to whatever was cheapest.
```

- [ ] **Step 2: Write the failing acceptance tests**

Append to `tests/test_generator.py`:
```python
def test_every_authored_rubric_passes_the_gate_and_clears_eight_angles():
    """The moat: the gate holds the unlabeled test over everything the generator produces."""
    from retnovation.content_loader import load_library, load_min_angle_count, load_denylist
    from retnovation.generator import anti_label_gate, angle_count

    min_angle = load_min_angle_count()
    fw, sc = load_denylist("framework_denylist"), load_denylist("scaffold_denylist")
    lib = load_library()
    assert len(lib) >= 3, "the founder thin seed must hold the three authored experiences"
    for exp in lib:
        corpus = _corpus(ref=exp.ledger_ref)  # synthetic, hermetic — no confidential db
        res = anti_label_gate(exp, corpus, min_angle_count=min_angle,
                              framework_denylist=fw, scaffold_denylist=sc)
        assert res.passed, f"{exp.experience_id} tripped {[c.value for c in res.rejects]}"
        assert angle_count(exp.rubric) >= min_angle, exp.experience_id


def test_seed_frame_subsets_differ_so_the_selector_discriminates():
    from retnovation.content_loader import load_library
    subsets = {frozenset(f.frame_code for f in e.rubric.frames) for e in load_library()}
    assert len(subsets) >= 2


@pytest.mark.skipif(
    not __import__("pathlib").Path("data/retnovation.db").exists(),
    reason="real seeded corpus (gitignored data/) not present",
)
def test_seed_ledger_refs_resolve_in_the_real_corpus():
    """Catch the orphan class of bug: every seed must bind to a real seeded founder entry."""
    from retnovation.content_loader import load_library
    from retnovation.persistence import Store

    store = Store("data/retnovation.db")
    try:
        for exp in load_library():
            entry = store.get_corpus(exp.ledger_ref)
            assert entry is not None, f"{exp.experience_id} -> orphan {exp.ledger_ref}"
            assert entry.unlabeled.strip(), f"{exp.ledger_ref} has empty unlabeled rationale"
    finally:
        store.close()
```

- [ ] **Step 3: Run to verify the acceptance tests pass**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: PASS (all three seeds pass the gate; ≥2 distinct frame subsets; real-anchor test passes if `data/retnovation.db` has the founder corpus, else self-skips).

- [ ] **Step 4: Run the full suite (3 seeds now in the library)**

Run: `.venv/bin/pytest -q`
Expected: PASS. The e2e tests seed corpus for all three refs (`_seed_corpus` in `test_experience`; `test_dry_run`/`test_orchestration` only touch `license_continuity` but `load_gated_library` now gates all three — confirm those two tests seed corpus for **all three** refs. If they fail with a `recoverable_label` `GateError`, add the two missing `upsert_corpus` rows for `veldra:concentrated_market_pricing_power` and `veldra:first_customer_proof_loop` to each e2e test's arrange block.)

- [ ] **Step 5: Confirm no confidential leak**

Run:
```bash
git ls-files content/rubrics/ ; grep -riE 'why_owned|provenance|PB-|ADR-|TESTLOG|setup b' content/rubrics/ || echo "(clean — abstracted prompts only)"
```
Expected: three rubric files; grep clean.

- [ ] **Step 6: Commit**

```bash
ruff format . && ruff check . && .venv/bin/pytest -q
git add content/rubrics/decision_under_stakes.yaml content/rubrics/proof_before_promise.yaml tests/test_generator.py tests/test_dry_run.py tests/test_orchestration.py
git commit -m "feat: add the Bobby-Axe + bounded_error founder seeds; gate-acceptance tests"
```

---

### Task 7: Raise the judgment-loop push budget to fit 8 angles

**Files:**
- Modify: `src/retnovation/assessment/judgment_loop.py`
- Test: `tests/test_judgment_loop.py` (confirm the cooperative path stays green)

**Interfaces:**
- Produces: `MAX_PUSHES = 8` (budget-only; the loop still pushes frames/traps — deeper dimension interrogation is Step 5).

- [ ] **Step 1: Confirm the current cooperative tests are green (baseline)**

Run: `.venv/bin/pytest tests/test_judgment_loop.py -v`
Expected: PASS (3 passed) — the pre-change baseline.

- [ ] **Step 2: Make the change**

In `src/retnovation/assessment/judgment_loop.py`, change `MAX_PUSHES = 6` to:
```python
MAX_PUSHES = 8  # >= the 8-angle depth floor; budget-only (loop still pushes frames/traps — Step 5 probes dims)
```

- [ ] **Step 3: Run the judgment-loop + full suite to confirm no regression**

Run: `.venv/bin/pytest tests/test_judgment_loop.py -v && .venv/bin/pytest -q`
Expected: PASS (cooperative `converged` + `bounded_error_violation` paths unchanged; full suite green).

- [ ] **Step 4: Commit**

```bash
ruff format . && ruff check .
git add src/retnovation/assessment/judgment_loop.py
git commit -m "feat: raise MAX_PUSHES 6->8 to fit the 8-angle depth floor (budget-only)"
```

---

## Execution notes

- **DEVLOG:** after each task, append a one-line entry to `docs/DEVLOG.md` (what changed + why) per the lessons.md pre-commit checklist; stage it with the task's commit.
- **Adversarial review (required before merge):** `generator.py`, the `experience.py` rewrite, and the `MAX_PUSHES` change are core path. After Task 7, commission an independent adversarial subagent review against this checklist: (1) **confidentiality** — no corpus text in tracked rubrics, `git ls-files` clean; (2) **gate soundness** — every `GateCode` has a check that trips AND passes correctly, no false-negative that would ship a labeled experience; (3) **selection determinism** — total order, ties by id, first-session fallback; (4) **fail-loud** — a bad rubric raises at `load_gated_library`; (5) **orphan retirement** — no dangling `ledger_ref`, the six-link loop still closes; (6) **cooperative path** — `converged`/`bounded_error_violation` unchanged. Address findings, then merge `step3-experience-generator` → `main`.
- **Final gate:** `ruff format . && ruff check . && .venv/bin/pytest` all green; `git ls-files | grep -iE 'guidebook|blueprint|brief|founderceo|judgmentloop|complete_picture|interest_tree|\.pdf|\.svg'` empty.

---

## Self-review

**Spec coverage** (§ refers to spec `2026-06-23-experience-generator-anti-label-gate.md`):
- §2 module shape + `SELECTORS` dispatch → Tasks 4, 5. ✓
- §2 selection/binding rules (frame-coverage, tie-break by id, own `ledger_ref`, first-session fallback) → Task 4 `select_open_ended` + Task 5. ✓
- §3 the 8 `GateCode`s + checks + hard/floor split + `GateResult` → Tasks 1, 3. ✓
- §3 two enforcement points (load fail-loud + selection) → Task 4 `load_gated_library` (raises) feeding `select_open_ended`. ✓
- §3 denylists/threshold as content → Task 2. ✓
- §4 schema + config additions → Tasks 1, 2; roleplay prompt-only (no `persona` field) honored. ✓
- §5 founder thin seed (3 experiences, real anchors, one `bounded_error`, orphan retired via re-home, confidentiality boundary) → Tasks 5, 6. ✓
- §5 loop budget bump → Task 7. ✓
- §6 deterministic tests, acceptance moat test, updated e2e tests, pre-commit gate, adversarial review → Tasks 3–7 + Execution notes. ✓
- §7 D4 (pluggable by regime) → Tasks 4, 5. ✓
- §8 out-of-scope (cs scorer/selector stubs, no model-generation, no persona, function-mapping deferred, deeper loop Step 5) → cs stubs Tasks 4–5; honored. ✓
- §9 acceptance criteria → Task 6 acceptance + real-anchor, Task 5/6 loop-closes tests. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `select_experience(core, state, ledger, corpus, spec, root)` consistent Tasks 5/orchestration; `anti_label_gate(exp, corpus_entry, *, min_angle_count, framework_denylist, scaffold_denylist)` consistent Tasks 3/4/6; `GateResult(passed, rejects, downgrades, angle_count)` consistent Tasks 1/3/4; `load_gated_library(corpus, root) -> list[tuple[Experience, GateResult]]` consumed by `select_open_ended`; `experience_id` added Task 1, consumed Tasks 5/6; filename==`experience_id` invariant holds for all seeds (Tasks 5, 6). ✓

**Ordering check:** every task ends green — the orphan is re-homed (not deleted) so no `FileNotFound`; the gated path goes live with one seed (Task 5) before the other two are added (Task 6); e2e tests seed corpus for every ref the gated library loads. ✓
