# Commitment Frame + Stress Probe — Pushing the Decision a Strong Answer Converges On

Date: 2026-06-24
Status: design (awaiting user review before plan)
Origin: surfaced by the live founder dogfood on the `license_continuity` escrow scene. The user
committed to a sharp answer ("Proposal 1": narrow internal-use escrow, hard no-compete line,
objective release triggers). `classify_intake` judged **both** rubric frames `present_reasoned`, so
the loop converged **at intake with zero pushes** (`stop_reason=converged`, `trajectory=[]`,
`sharper_audit=[]`). Two defects: (a) the rubric scores *engaging the angles* but has **no frame for
the decision the prompt demands** ("Decide what you do… they want an answer today"); (b) a
converged-at-intake answer produces **no push and no appreciating-asset trace — the instructor goes
silent exactly when the student is strongest.** This is a post-MVP doctrine/quality feature, not a
locked build-order step.

## 1. Goal

Make a `genuinely_open` experience that demands a decision **stress the decision once** before it may
converge, so a strong answer gets *pushed* (and produces a trajectory) instead of silently
converging. Deliver it as a **general, opt-in convention** keyed on rubric data — not a one-off patch
to `license_continuity` — and author the first instance (the `commit_under_the_deadline` frame on
`license_continuity`). The stress probe stays strictly **conclusion-agnostic**: it tests the
*reasoning* of the commitment (its mechanism, its reversal tripwire), never which commitment is right.

## 2. Non-goals (YAGNI / be-mindful)

- **No new `stop_reason`.** The trajectory is now non-empty when a converged answer was stressed, so
  it already encodes "converged only after the probe." No `converged_after_stress` enum.
- **No auto-stress for every `genuinely_open` rubric.** The convention is opt-in via a declared
  `decision_frame`; an open experience that does not demand a commitment is unaffected (avoids the
  eagerness / push-quality confound, JudgmentLoop v0.1 §6).
- **No progression / intro-arc redesign.** The escrow scene being a max-difficulty capstone wrong for
  a cold start is a *separate* queued thread (see memory `retnovation-commitment-frame-gap`). This
  spec is the rubric-depth + stress-probe mechanism only.
- **No re-authoring of the other founder rubrics.** Only `license_continuity` gets the new frame; the
  other experiences declare no `decision_frame` and behave exactly as today.
- **No restoring `choose_the_failure_default_deliberately`.** It is ReserveGrid/verifier-specific and
  does not fit the escrow scene; out of scope (considered and rejected in brainstorming).

## 3. Doctrine constraints this must honor

- **Conclusion-agnostic, never grade the conclusion** (stressed twice by the user). The loop outputs a
  *trajectory*, not a grade (`response.md`, `intake.md`). The stress push and its classification
  test whether the student *reasoned* the commitment (named the tripwire / the cost of what they will
  not commit to / the failure they accept), never whether the commitment is the one we would pick.
  "Presence is conclusion-agnostic." `sharper` stays = a gap closed with a *student-supplied mechanism*.
- **The disband rules hold for the stress push.** Never name the frame, never hand the answer, never
  validate/soften. The friction is the product (`push.md`).
- **The unlabeled moat still holds.** A new `frame_code` / `trap_code` auto-bans its own phrase
  (snake + spaced) from the abstract prompt *and* the seeded scene
  (`generator._frame_trap_phrases` → `anti_label_gate` / `validate_scene`). The new codes must not
  appear in the abstract prompt or the authored scene.
- **Byte-stable fallback.** Every rubric with `decision_frame is None` (the other two founder
  experiences, all cs_technical) hits the identical code paths as today. No behavior change, no diff
  in their trajectories.
- **L-1 doctrine as data.** The stress-mode guidance lives in `content/prompts/*.md`, not hardcoded
  in `src/`. The decision marker is a rubric field, not a code branch keyed on an experience id.
- **L-8 fail-loud at load.** A `decision_frame` that names no existing frame raises at rubric parse.
- **Core-path review.** `judgment_loop`, `types`, and `model` are core-path; a whole-branch
  adversarial review runs before finishing.

## 4. Confirmed decisions (from brainstorming)

1. **Scope = general stress-mode convention** (not content-only, not a single-rubric patch). The user
   accepted §13's necessity caveat (generalizing from one escrow datapoint) and chose the convention.
2. **Opt-in via a declared `decision_frame`** on the rubric (doctrine-as-data). The named frame is
   exempt from intake-convergence and always gets exactly one stress probe.
3. **Decision bar = commit + own the trade + name the reversal tripwire.** Paired trap
   `commit_without_a_tripwire`. The tripwire (the falsifier) is the supplied mechanism the stress
   probe elicits — conclusion-agnostic by construction.
4. **Integration = probe-gated convergence (Approach A).** One unified loop path; `generate_push` /
   `classify_response` become stress-aware; reuse the existing push → response → sharper → audit
   machinery. (Approach B, a bolted-on post-converge pass, rejected for permanent dual-path complexity.)

## 5. Component design

### 5.1 Data model — `src/retnovation/types.py`

Add one optional field + a validator to `Rubric`:

```python
class Rubric(BaseModel):
    frames: list[Frame]
    traps: list[Trap]
    mode: Mode
    binding_constraint: str | None = None
    decision_frame: str | None = None        # NEW: frame_code that must be stressed once before converge

    @model_validator(mode="after")
    def _decision_frame_in_frames(self) -> "Rubric":
        if self.decision_frame and self.decision_frame not in {f.frame_code for f in self.frames}:
            raise ValueError(f"decision_frame {self.decision_frame!r} is not a rubric frame")
        return self
```

`content_loader.load_rubric` threads it through: `decision_frame=data.get("decision_frame")`. Rubrics
with no `decision_frame:` key parse identically (default `None`).

### 5.2 The loop — `src/retnovation/assessment/judgment_loop.py`

A new `probed: set[str]` records every code pushed at least once (distinct from `exhausted`, which only
holds non-moving pushes). Two guards consult it:

```python
def _converged(frame_states, trap_states, exp, probed) -> bool:
    df = exp.rubric.decision_frame
    if df is not None and df not in probed:
        return False                          # may not converge until the decision is stressed once
    frames_ok = all(s is FrameState.present_reasoned for s in frame_states.values())
    traps_ok  = all(s is not TrapState.tripped for s in trap_states.values())
    return frames_ok and traps_ok

def _select_target(exp, frame_states, trap_states, exhausted, probed):
    df = exp.rubric.decision_frame
    if df is not None and df not in probed and df not in exhausted:
        return ("frame", df)                  # forced first, even if intake rated it present_reasoned
    # ... existing trap → binding → absent-frame logic unchanged ...
```

In `assess()`:
- initialise `probed: set[str] = set()`;
- after each push, `probed.add(code)`;
- derive the stress flag and pass it to both model calls:
  ```python
  stress = kind == "frame" and frame_states.get(code) is FrameState.present_reasoned
  push_text = model.generate_push(exp, kind, code, stress=stress)
  rc = model.classify_response(exp, kind, code, push_text, response, stress=stress)
  ```

Because normal `_select_target` never returns a `present_reasoned` frame, `stress=True` ⟺ "the forced
`decision_frame` that intake already rated reasoned." A *weak* commitment (`absent` /
`present_asserted`) is still forced first, but with `stress=False` → a normal elicit push.

**`stop_reason` is unchanged (`converged`).** The state machine at
`judgment_loop.py` lines 116–148 is unchanged: a stress `closed` on an already-reasoned frame appends
it to `frames_closed_under_pressure` (no `FrameDelta`, since `before == present_reasoned`) and
`audit_sharper` re-grades it blind — the deepened commitment becomes a real, audited trace.

### 5.3 Stress-aware push + response — `src/retnovation/model.py` + prompts

Add a keyword-only `stress: bool = False` to `generate_push` and `classify_response` on the `Model`
protocol, `FakeModel` (ignores it — scripted), and `AnthropicModel`. Doctrine stays in content:

- **`content/prompts/push.md`** gains a **Stress mode** block: *the angle is already reasoned — do not
  ask the student to re-engage it. Probe the sharpest edge: the single event that would force a
  reversal (the tripwire), what they are choosing NOT to commit to and its cost, or the failure they
  accept. Never name the frame, never hand the answer, never grade the conclusion.* `AnthropicModel`
  appends a one-line activation to the push user message when `stress=True`; the doctrine text lives
  in the prompt.
- **`content/prompts/response.md`** gains a **Stress mode** clause: *under stress, `closed` = the
  student supplied a NEW deepening mechanism (named the tripwire / the cost of the non-commitment /
  the accepted failure); `unchanged` = restated the commitment with no new mechanism. Still
  conclusion-agnostic; never grade the conclusion.* `AnthropicModel` adds the stress line to the
  `classify_response` system prompt when `stress=True`.

### 5.4 Content — `content/rubrics/license_continuity.yaml`

Add one frame, one paired trap, and the `decision_frame` pointer. `mode` stays `genuinely_open`,
`binding_constraint` stays `null`:

```yaml
frames:
  # lead_with_what_you_refuse_to_do — unchanged
  # protect_the_core_lane — unchanged
  - frame_code: commit_under_the_deadline                # NEW
    frame_detail: Commit to a decision today, account for what you trade for it, and name what would force you to reverse.
    paired_trap: commit_without_a_tripwire
traps:
  # scope_creep_to_please — unchanged
  # erode_core_for_one_customer — unchanged
  - trap_code: commit_without_a_tripwire                 # NEW
    trap_detail: Committing to a course without naming what would make you reverse it.
decision_frame: commit_under_the_deadline                # NEW
```

- **Angle count:** 3 frames + 3 traps + 0 binding + 4 dims = **10** (≥ 8 floor). ✓
- **Moat:** new codes ban `"commit under the deadline"` / `"commit without a tripwire"` (+ underscore
  forms) from the abstract prompt and the seeded scene. The abstract prompt contains neither. The
  gitignored escrow scene is re-checked against the new codes on re-ingest; if it contains a banned
  phrase, reword the **scene** (content), never weaken the gate. The gated moat test is the safety net.

## 6. Edge cases (decided)

- **Weak commitment** (`absent` / `present_asserted` at intake) → forced first, but a normal *elicit*
  push (`stress=False`). A commitment that will not improve plateaus normally — correct.
- **Stress push `unchanged`** → `decision_frame` enters `exhausted` + `probed`; the convergence guard
  passes; the trajectory holds the one probe (silence cured even when nothing deepens).
- **Stress push `regressed`** → frame lowers via `_lower`, loop stops `regression` — a real
  "backslid under stress" trace.
- **Stress push `closed`** → recorded in `frames_closed_under_pressure`, re-graded by `audit_sharper`;
  no `FrameDelta` (state was already `present_reasoned`).
- **No `decision_frame`** (other founder rubrics, all cs_technical) → identical to today.

## 7. Testing (TDD — RED before GREEN, each task)

- **Loop** (`tests/test_judgment_loop.py`): (a) the exact dogfood repro — `decision_frame`
  `present_reasoned` at intake → exactly one forced stress probe, `trajectory` non-empty, then
  `converged`; (b) `decision_frame` `absent` → targeted first as an elicit push; (c) **no
  `decision_frame` → byte-identical to current behavior** (regression lock on the cooperative path);
  (d) stress `unchanged` still converges with the probe recorded; (e) stress `regressed` stops
  `regression`.
- **Types / loader** (`tests/test_types.py`, `tests/test_content_loader.py`): `decision_frame` naming
  a non-frame raises at parse; real `license_continuity` loads with
  `decision_frame == "commit_under_the_deadline"`.
- **Moat** (`tests/test_generator.py`): the new rubric clears `anti_label_gate`, `angle_count == 10`;
  the seeded scene still clears `validate_scene` (re-ingested DB).
- **Model** (`tests/test_anthropic_model.py`): `generate_push(stress=True)` includes the stress
  activation and `classify_response(stress=True)` carries the stress clause; **`stress=False` is
  byte-stable** versus today (no `Stress mode` text in the rendered prompts).
- **Regression**: `tests/test_dry_run.py` / `tests/test_orchestration.py` unchanged (no
  `decision_frame`).

## 8. Build order (subagent-driven, fresh implementer + independent reviewer per task)

1. `types.py` — `Rubric.decision_frame` + validator (+ tests).
2. `content_loader.load_rubric` — thread `decision_frame` (+ tests).
3. `judgment_loop.py` — `probed` set, `_converged` guard, `_select_target` force, `stress` derivation
   (+ loop tests a–e). **Core-path.**
4. `model.py` + `push.md` — stress-aware `generate_push` (+ tests, byte-stability). **Core-path.**
5. `model.py` + `response.md` — stress-aware `classify_response` (+ tests, byte-stability). **Core-path.**
6. Content: `license_continuity.yaml` frame/trap + `decision_frame`; re-ingest the gitignored scene and
   confirm it still clears the moat (+ gate test).
7. Whole-branch opus adversarial review against §3 doctrine + §6 edge cases; address findings; finish.

Unpushed stays unpushed unless the user asks (`main` is ~39 commits ahead of `origin/main`).

## 9. Risks / open items

- **Stress-aware `classify_response` is the doctrine-delicate change.** The "closed = new deepening
  mechanism" bar must not become "graded the conclusion." Mitigation: the prompt clause is explicit and
  conclusion-agnostic; `audit_sharper`'s blind second grader (already conclusion-agnostic per
  `grade_sharper.md`) catches over-credit.
- **Generalizing from one datapoint** (§13 necessity caveat). Accepted by the user. Mitigation: the
  convention is opt-in (`decision_frame`), so it only fires where a curator declares a decision; the
  escrow instance is the validation case for the next dogfood.
- **Scene phrase clash with the new codes.** Low likelihood; caught by the gated moat test; resolved by
  rewording the scene, never the gate.
- **Forced-probe push quality** (JudgmentLoop §6 confound): a weak stress push could misread as the
  student's limit. Mitigation: the stress prompt is specific (tripwire / non-commitment cost / accepted
  failure), and the probe is exactly one — bounded.
