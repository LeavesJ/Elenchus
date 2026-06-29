# SP3 Live Content-Elicitation Probe — Design

Date: 2026-06-27
Status: design (awaiting user review → writing-plans)
Depends on: SP3 (frame-mining isolated experiences, merged `637a954`)

## Boundary this closes

SP3 proved the *engine path*: given a learner who reasons `embed_credentials_as_a_list`
unprompted, the engine drives the frame weak→forming→strong and fires transfer
(`tests/test_sp3_progression.py`). It proved this with a `FakeModel` whose intake
classification *declares* embed `present_reasoned` — so the one thing the scripted regression
**defers** is whether real, frame-naive Opus actually produces that read from the authored
prompts. This project measures exactly that deferred claim, and nothing more.

This is a **calibration probe**, not a pass/fail gate. It automates the *run* and leaves the
*verdict* to the human — the SP1 discipline ("automate the kill, not the verdict"; L-15).

## What is measured (and the proof it is the right thing)

The property SP3 leans on is `embed ∈ reasoned_unprompted`, and `strong` counts only
`unprompted_breadth` ([`state.py:32`](../../../src/retnovation/state.py)).
`reasoned_unprompted` is defined as intake-state **AND** exit-state **AND** not-probed
([`judgment_loop.py:170-176`](../../../src/retnovation/assessment/judgment_loop.py)):

```python
if s0 is present_reasoned                       # (1) intake
and frame_states.get(code) is present_reasoned  # (2) exit
and code not in probed                          # (3) not-probed
```

A naive probe that stops at intake would capture only condition (1) — a real but *weaker*
property than the one SP3 needs. **However, for the two rubrics in scope the three conditions
collapse to (1).**

**Claim.** For a rubric with `decision_frame is None` and where the target frame is not the
`binding_constraint`: the target frame `present_reasoned` at intake ⟺ the target frame ∈
`reasoned_unprompted` after `assess()`.

**Proof** (tracing every mutating branch):

- **(3) holds.** `_select_target` returns a frame only when its state
  `is not present_reasoned` ([`judgment_loop.py:52`](../../../src/retnovation/assessment/judgment_loop.py)).
  The `decision_frame` force-probe ([`:34`](../../../src/retnovation/assessment/judgment_loop.py))
  and the `binding` branch are inert here — **both rubrics have `decision_frame` absent and
  `binding_constraint: null`**. So a present-at-intake target is never selected → never added
  to `probed`.
- **(2) holds.** `frame_states[target]` is mutated only in the regression
  ([`:129`](../../../src/retnovation/assessment/judgment_loop.py)) and closed
  ([`:147`](../../../src/retnovation/assessment/judgment_loop.py)) branches, both keyed to the
  *currently-probed* `code`. The target is never the probed code → its state is invariant →
  still `present_reasoned` at exit.
- **Converse.** Target not present at intake ⟹ (1) fails ⟹ target ∉ `reasoned_unprompted`,
  even if it later closes under pressure (that lands in `frames_closed_under_pressure`/breadth —
  the "closed-under-pressure cannot reach strong" path).

SP3's own regression encodes this: `test_session1_credits_embed_unprompted_through_the_real_loop`
([`tests/test_sp3_progression.py:81`](../../../tests/test_sp3_progression.py)) runs the **full**
`assess()` and scripts only the *intake*; embed lands in `reasoned_unprompted`, never probed.
The loop is a no-op for the target's credit; the intake read is the whole signal.

**Consequence.** The intake-only probe is not "an easier question wearing the hard one's
clothes" — for these rubrics it is provably the same question, established by proof rather than
by sample. Running the full live `assess()` loop would add only *breadth-under-pressure* data
(how often a not-at-intake target closes when probed), which is explicitly **not** the
unprompted property. So the loop is omitted by design, not by economy.

This equivalence is **rubric-specific**. It rests on the two preconditions above, so the probe
**encodes them as a runtime guard** (below): if a future rubric adds a `decision_frame` or makes
the target its `binding_constraint`, the equivalence breaks and the probe must refuse rather
than silently report the weaker property (the L-16 move — encode the precondition the honesty
rests on).

## Durability of the proof — the guard covers only half

The proof has **two** kinds of hypotheses: the *rubric shape* (no `decision_frame`, target ≠
`binding_constraint`) **and** the *judgment loop's behavior* (`_select_target` skips
present-at-intake frames at [`:52`](../../../src/retnovation/assessment/judgment_loop.py); the
force-probe [`:34`](../../../src/retnovation/assessment/judgment_loop.py) and binding branches
are inert; exit mutations are keyed to the probed code at
[`:129`](../../../src/retnovation/assessment/judgment_loop.py)/[`:147`](../../../src/retnovation/assessment/judgment_loop.py)).
`assert_intake_equivalence` enforces only the **rubric half**. The **loop half** is asserted in
prose and protected by nothing — an edit to `judgment_loop.py` that lets a present-at-intake
frame be probed, adds a state-mutating branch not keyed to the probed code, or changes
`_select_target`'s condition would silently break the intake↔`reasoned_unprompted` equivalence
while every rubric precondition still holds, and the probe would resume reporting the weaker
property through the door the guard does not watch.

So the loop half is pinned by a **fixtured regression (no live spend)**: run the real `assess()`
on a crafted intake-present target under each in-scope rubric shape and assert the target lands
in `reasoned_unprompted` and never in `probed`. P1 (`irreversible_anchor`) is already guarded by
[`test_session1_credits_embed_unprompted_through_the_real_loop`](../../../tests/test_sp3_progression.py)
(intake-present embed, `choose_failure` absent+probed → embed unprompted, never probed). The
build adds the **P2 analogue** for `continuity_lock_in`, co-located alongside it in
`tests/test_sp3_progression.py` (intake-present embed, one trap tripped so the loop *actually runs
a probe* on another target, embed still unprompted + unprobed at exit). **The probe's intake-only
validity is declared to depend on these two tests staying green** — a loop edit that breaks the
equivalence turns them red, which is the enforcement the rubric-shaped guard structurally cannot
provide.

## Non-goals

- Re-proving the engine path (selection, ordering, accumulation to `strong`) — done in
  `test_sp3_progression.py`.
- Exercising the live judgment loop end-to-end (live `respond`, live pushes). A separate concern.
- A CI pass/fail on "embed reasoned." The substantive verdict is the human's.

## Architecture

A thin module, **pure orchestration over the `Model` protocol — no doctrine, no I/O**
(rent-capability / gate-doctrine line):

- `src/retnovation/elicitation.py`
  - `assert_intake_equivalence(rubric, target_frame_code)` — raises if
    `rubric.decision_frame is not None` or `rubric.binding_constraint == target_frame_code`.
    The encoded precondition guard.
  - `run_elicitation_probe(experiences, model, *, runs_by_id, target_frame_code="embed_credentials_as_a_list") -> ProbeResult`
    — for each experience, asserts equivalence once, then per run:
    `opening = model.generate_output(exp.prompt, None)` →
    `intake = model.classify_intake(exp, opening.text)` →
    append a `ProbeRun`. Pure; deterministic given the model. A **refused** opening is recorded
    (`refused=True`) and `classify_intake` is skipped (no text to read; states default `absent`/
    `not_tripped`); refused runs are counted separately and excluded from the present-reasoned
    rate denominator — mirroring the lift harness's treatment of inconclusive scenarios.
- Result types in `src/retnovation/types.py` (consistent with `LiftResult` et al. living there):
  - `ProbeRun`: `experience_id`, `run_index`, `opening` (verbatim), `refused`,
    `frame_states: dict[str, FrameState]`, `trap_states: dict[str, TrapState]`.
    Target state is `frame_states[target_frame_code]` — no redundant field.
  - `ProbeResult`: `runs: list[ProbeRun]`, `target_frame_code`, plus derived summary views
    (computed, not stored): per-experience distribution of the target's intake state across
    runs, and the per-run **trap-trip pattern** (which paired trap, how often).
- A thin I/O entrypoint `src/retnovation/run_elicitation.py` (separate module so `elicitation.py`
  stays pure; matches the `veldra_ingest.py` pattern), invoked `python -m retnovation.run_elicitation`:
  builds `AnthropicModel()`, loads the two experiences, runs the probe, writes the artifact, prints
  the abstracted summary. **Run by the human**, gated. No `pyproject` console-script entry needed.

The "learner" is **bare**: `generate_output(prompt, None)` sends the prompt as a bare user
message with no system prompt — frame-naive by construction, the same `injection=None` call shape
SP2 used for the frame-naive control, making the probe directly interpretable against the lift
screen. It differs from the lift control in one budget detail: a larger `max_tokens`
(`LEARNER_MAX_TOKENS`) than the lift default, because the decision-prompt openings run far longer
than the lift scenarios' short outputs and the 1024 default truncates them (or, when adaptive
thinking fires, starves the text block entirely — surfaced on the first @live run). `max_tokens`
is a budget, not a primer, so frame-naiveness is unchanged.

## Scope & sampling

- **Both problems**, because SP3's value is embed *transferring* across both:
  - P1 `irreversible_anchor` (`veldra:embedded_anchor_lock_in`) — the **session-1 read SP3
    asserted rather than verified** (the higher-value half).
  - P2 `continuity_lock_in` (`veldra:license_fork_risk`) — the transfer/session-2 problem.
- **Asymmetric, P1-weighted** default: `runs_by_id = {irreversible_anchor: 8, continuity_lock_in: 5}`
  → 13 runs × 2 calls = **26 Opus calls** at `effort=high`. Per-problem and adjustable.
- **n-resolution honesty boundary.** Sampling cleanly separates all-vs-none but not the middle;
  a split result (e.g. 5/8) is **"rerun with more samples,"** never recorded as a stable third
  category. The cheapness of intake-only (2 calls/run) is why the default n is raised above 3.

## Recording & adjudication

- Raw verbatim openings + full verdicts → gitignored `data/elicitation/<utc-stamp>.json`
  (`/data/` is already gitignored; verbatim openings are Veldra-ore-derived and never committed —
  mirrors `data/lift/`).
- Committable trace: a **DEVLOG entry** with the *abstracted* summary only — per problem, the
  target-state distribution and trap-trip counts, by code, **no verbatim**. (Frame/trap codes and
  experience_ids are already in committed `content/`, so the abstracted summary reveals nothing
  new.) No new tracked artifact file.
- **Adjudication surface** (presented to the human, per problem):
  1. the per-run **trap-trip pattern — first-class**, because hard-vs-borderline turns on *how*
     embed failed: the same paired trap on every miss = the prompt steering into the trap
     (content-fixable) vs. simply not surfacing (genuinely hard);
  2. each verbatim opening + the target's intake state;
  3. the other frame's state (P1 only — `choose_the_failure_default_deliberately`);
  4. the **refusal rate — first-class**, not merely a denominator adjustment: a heavy-refusal run
     reads as "the prompt is mis-set" (a distinct content finding from "engages without surfacing
     embed"), and at P2's n=5 a couple of refusals shrink the *usable* denominator below the
     already-thin resolution → such a run is flagged, never silently averaged.
  The human renders the three-way calibration read: **reachable** (then check the verbatim that
  the scaffold did not leak it, L-6), **genuinely-hard** (trap tripped — frame counter-intuitive,
  prompt does not leak), or **borderline** (→ rerun, per the n-resolution note). A
  "genuinely-hard" verdict means **hard *at intake***, not hard everywhere: the intake-only probe
  is blind by design to the hard-at-intake-but-recoverable-under-pressure case (the converse — it
  lands in breadth, not `reasoned_unprompted`), which would matter to a content fix and is a
  separate measurement.

## Testing

- `tests/test_elicitation.py` — deterministic, over a fake model (mirrors `test_lift_test.py`):
  - aggregation: verbatim captured; all frame/trap states recorded for every run; the target key
    always present across N runs.
  - `assert_intake_equivalence` **refuses** a rubric with a `decision_frame`, and refuses one
    where the target is the `binding_constraint`; **passes** the two real rubrics.
- **Loop-side equivalence guardian** (`tests/test_sp3_progression.py`, fixtured, no live) — pins
  the *loop half* of the proof: the real `assess()` on an intake-present target lands it in
  `reasoned_unprompted` and never in `probed`, for **each** in-scope rubric shape. P1 exists
  (`test_session1_credits_embed_unprompted_through_the_real_loop`); the build adds the P2 analogue
  for `continuity_lock_in` (one trap tripped so the loop runs a probe, embed untouched). These are
  named the guardians of the equivalence; the probe's intake-only validity depends on them staying
  green.
- `tests/test_elicitation_acceptance.py` — `@pytest.mark.live` + `skipif(no key)` smoke
  (mirrors `test_lift_acceptance.py::test_live_lift_smoke`):
  - the real pipeline returns a valid `ProbeResult`; the target key is in `frame_states`.
  - **the L-13 guard held on the real sent prompt** — the actual string sent to `generate_output`
    (i.e. each real `rubric.prompt`) contains no `frame_code` substring. This invariant must hold
    on the real string, not only the fake.
  - **No** assertion on the substantive verdict.

## Doctrine guards

- **L-13** (no-leak): the only learner-facing string is `rubric.prompt`, which already withholds
  the frame ("No framework is named for you on purpose"); `injection=None` ⇒ no system ⇒
  frame-naive by construction. The live `frame_code`-substring assertion is the **automated
  floor** — it catches the literal code leaking, not a plain-words paraphrase. The **real no-leak
  adjudication is the human verbatim check**: on a *reachable* read, the human reads the opening to
  confirm the scaffold did not hand the move over in different words (L-6). The green substring
  test is the floor, not the whole guarantee.
- **L-16 / equivalence precondition**: `assert_intake_equivalence` refuses where the intake↔
  `reasoned_unprompted` equivalence would not hold, so the tool fails loud instead of reporting
  the weaker property.
- **Confidentiality**: artifact under gitignored `data/`; pre-commit `git ls-files` gate as always.

## Cost

~26 Opus calls (`effort=high`) for the default run; spends the user's tokens. **Gated** — the
live run is confirmed with the user before firing. Re-runs (for a borderline result) are the
same cost.

## Build process

Standard repo arc: this spec → `writing-plans` → subagent-driven build (fresh implementer +
independent reviewer per task; OPUS reviewer on the probe aggregation, the equivalence guard, and
the doctrine assertions; OPUS whole-branch adversarial review before merge) → the gated live run
with the user → DEVLOG + handoff + memory update.
