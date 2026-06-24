# Step 5 — Harden the Judgment Loop

Date: 2026-06-23
Status: design (author-reviewed; proceeding autonomously under the user's standing delegation
"do step 5, automatically move on… I won't be back for a while, but quadruple-check / be mindful")
Build order: #5 — the LAST locked build-order item. After this the MVP harness is feature-complete.

## 1. Goal

Harden the case-instructor judgment loop (`assessment/judgment_loop.py`) against the two stops the
v0.1/v0.2 runs never exercised and add the independent grader the findings demanded — exactly
Build Brief #5: "Exercise the stops that never fired, **regression and plateau**, and add the
**independent grader pass for the sharper calls**."

Three deliverables:

1. **Regression stop** — the loop must detect a student getting worse ("abandoning a good
   position or doubling down", JudgmentLoop §2) and stop, because more pushing harms. Today a
   `"regressed"` response classification is silently treated like `"unchanged"`; `StopReason.regression`
   is in the enum but **never fires**.
2. **Plateau stop, faithful semantics** — fire when **two pushes on *distinct* targets** both move
   nothing (JudgmentLoop §2, §6), demonstrating breadth before giving up. Today the loop
   re-hammers the same highest-priority target, so "plateau" really means "this one angle failed
   twice." The loop must **rotate to a fresh angle** after a non-moving push.
3. **Independent grader pass for sharper calls** — a separate, blind, skeptical grader re-audits
   each "sharper" (closed-with-mechanism) call the instructor made; a sharper call only credits
   learner state when the independent grader **agrees** (2-vote). This guards the anti-gaming rules
   (assent ≠ sharper, length ≠ sharper) the in-line instructor could violate (JudgmentLoop §6:
   "a separate blind grader should audit the sharper calls the way the admission gate got an
   adversarial pass").

Done = all three stops/grader exercised by tests; the cooperative path, the bounded-error flag, the
CS regime, and the dry-run all stay green; an independent adversarial review confirms the loop's
invariants.

## 2. Non-goals (YAGNI / be-mindful)

- **No push-quality grading.** §6 names a second confound — a weak push misread as the student's
  limit (the *under*-credit direction). Auditing the instructor's pushes for quality is deferred;
  this step audits the *over*-credit direction (the sharper calls), which is what #5 specifies.
- **No live adversarial student.** The model over-refuses to role-play a caving/safety-inverting
  student (§5, EXP-002). The resistant paths (regression, plateau, bounded-error) are exercised by
  **authored fixtures**, exactly as v0.1 did for the bounded-error flag. Live validation remains the
  dogfood's job.
- **No trap-repair auditing.** The grader audits frame-closes (the calls that move learner-state
  strength). Trap repairs don't bump frame strength; auditing them is a possible later extension.
- **No new regime / no orchestration rewrite.** The grader lives inside the open_ended assessor;
  cs_technical (checkable) has no "sharper" and is untouched. `run_session` is unchanged.

## 3. Doctrine constraints this must honor

- **Sharper = a gap closed with a *supplied mechanism*. Assent is not sharper; length is not
  sharper.** The grader enforces this skeptically and blind.
- **Presence is conclusion-agnostic** — a frame is sharper when the angle is engaged with a real
  mechanism even at a different conclusion (JudgmentLoop Decisions). The grader must not dispute a
  sharper call merely because the student disagreed with a "right" answer.
- **The instructor renders exactly one verdict — the bounded_error hard-wrong flag.** The grader is
  not a second conclusion-grader; it only audits whether *sharper* was genuine.
- **The trajectory is the appreciating asset** — every push, delta, stop, and now every grader
  verdict traces to an authored code. The audit trail is part of the trace.
- **Reversible / no fabricated credit** — a disputed sharper is *removed* from the credited set
  (and its frame delta reverted) so learner state is not credited; nothing is deleted destructively.
- **L-1 doctrine as data** — the grader's skeptical doctrine lives in `content/prompts/grade_sharper.md`,
  not in `src/`. **L-8** — add regression tests for the new fail-loud/credit-gating paths.

## 4. Design decisions (made autonomously; rationale recorded)

1. **Regression fires on the first genuine `"regressed"` outcome.** Doctrine: "the student is
   getting worse and more pushing harms" → stop promptly, don't keep pushing. On a frame, lower its
   state one level (present_reasoned → present_asserted → absent) and record the backslide delta; on
   a trap, the trap stays tripped. Then stop with `StopReason.regression`. (Alternative — accumulate
   K regressions — rejected: the doctrine says more pushing *harms*, so one genuine backslide is the
   signal to stop.)
2. **Plateau = two consecutive non-moving pushes on distinct targets, achieved via target
   rotation.** After a non-moving push, the target is added to an `exhausted` set and
   `_select_target` skips it, so the next push tries a *fresh* angle. Plateau fires when the last two
   pushes were on distinct codes and neither moved; also fires when no fresh target remains while not
   converged (the instructor is out of distinct angles). This makes plateau mean "globally stuck,"
   not "stuck on one angle," per §2/§6. The cooperative path (every push closes) never rotates and is
   unaffected; `budget` remains the backstop for mixed move/fail oscillation.
3. **The independent grader is a separate, blind, skeptical pass that gates sharper by 2-vote.**
   A new `assessment/sharper_grader.py::audit_sharper(exp, assessment, model) -> Assessment`
   re-judges each frame the instructor closed, via a new `Model.grade_sharper` method with its own
   `content/prompts/grade_sharper.md` (auditor framing: default to *not* sharper unless a mechanism
   is clearly cited; assent/length never count; disagreement-with-our-conclusion never counts as
   not-sharper). It is **blind** — it sees only `(angle detail, push, raw student response)`, never
   the instructor's outcome. A disputed call is removed from `frames_closed_under_pressure` and its
   `FrameDelta` reverted (so `update_state` scores it weak, not strong); the full audit (confirmed +
   disputed, with the grader's reason) is recorded on the Assessment. `judgment_loop.assess` runs the
   instructor loop then calls `audit_sharper`, returning the audited Assessment — so `run_session`,
   `STATE_UPDATERS`, and the cs_technical path are all unchanged.
4. **The trajectory stores the raw student response.** `Push` gains `response: str = ""` so the
   grader can re-judge independently from the raw push+response (and the trace is complete). The
   default keeps existing `Push(...)` constructions valid.

## 5. Component design

### 5.1 Types (`types.py`)

- `Push`: add `response: str = ""` (the raw student reply to this push). Existing fields unchanged.
- `SharperVerdict(BaseModel)`: `sharper: bool`, `reason: str` — the blind grader's verdict + cited
  reason for one closed call.
- `SharperAuditItem(BaseModel)`: `code: str`, `kind: str`, `instructor_sharper: bool` (always True —
  only the instructor's sharper calls are audited), `grader_sharper: bool`, `confirmed: bool`
  (`instructor_sharper and grader_sharper`), `grader_reason: str`.
- `Assessment`: add `sharper_audit: list[SharperAuditItem] = Field(default_factory=list)`.
  `StopReason.regression` already exists; no enum change.

### 5.2 Model (`model.py`)

- `Model` Protocol gains `grade_sharper(self, exp, kind, code, push, response) -> SharperVerdict`.
- `FakeModel`: add optional `sharper_verdicts: dict[str, list[SharperVerdict]] | None = None`
  (keyed by frame code, popped). `grade_sharper` pops a scripted verdict for the code if present,
  else returns `SharperVerdict(sharper=True, reason="(default agree)")` — the test double's grader
  agrees by default, so existing open_ended tests stay green untouched; a dispute test scripts
  `sharper=False`. Existing `FakeModel(intake, responses)` / `(…, grades=…)` callers are unaffected
  (new param is keyword-optional and last).
- `AnthropicModel.grade_sharper`: a `messages.parse` call against `claude-opus-4-8` (shared `_PARAMS`)
  with `output_format=SharperVerdict`; system = `load_prompt("grade_sharper")` + the rubric angle
  detail (via the existing `_target_detail`); user = the push + the raw student response; `_require`
  guards refusal/empty → `ModelError`. The instructor's outcome is **never** in the prompt (blind).

### 5.3 Grader doctrine prompt (`content/prompts/grade_sharper.md`)

Skeptical auditor: you are a blind second grader auditing whether ONE reasoning gap was genuinely
made sharper. Sharper = the student supplied a *mechanism/reason* that closes the angle. NOT sharper:
bare assent ("you're right, I'll fix it"), restating the push, more words without a new reason.
Conclusion-agnostic: a student who engages the angle with a real mechanism is sharper even if they
reach a different conclusion than you would — do not dispute a call for disagreeing well. Default to
`sharper=false` when no mechanism is clearly cited. Output `{sharper, reason}`.

### 5.4 Judgment loop (`assessment/judgment_loop.py`)

- `_select_target(exp, frame_states, trap_states, exhausted)` — gains an `exhausted: set[str]`
  param; skips any code already in `exhausted` (rotation). Same priority order otherwise (tripped
  traps → binding-adjacent → first unmet frame), among non-exhausted codes.
- `_lower(state: FrameState) -> FrameState` — present_reasoned → present_asserted → absent → absent.
- The loop:
  - tracks `exhausted: set[str]` and `recent: list[tuple[str, bool]]` (last pushes' (code, moved)).
  - **plateau check** (before selecting): if the last two `recent` entries are distinct codes and
    neither moved → `plateau`.
  - selects a target; if `None` while not converged → `plateau` (out of distinct angles).
  - on `rc.outcome == "regressed"`: if frame, lower its state and append a backslide `FrameDelta`
    when the level changed; append the `Push` (with `response`); `stop_reason = regression`; break.
  - on `closed + mechanism_supplied`: move (as today); else add the code to `exhausted`.
  - every `Push` now carries `response=response`.
- After the loop, call `audit_sharper(exp, assessment, model)` and return its result.
- `MAX_PUSHES` unchanged (8).

### 5.5 Independent grader (`assessment/sharper_grader.py`, new)

`audit_sharper(exp, assessment, model) -> Assessment`:
- For each `Push p` in the trajectory where `p.kind == "frame"` and `p.target_code` is in
  `frames_closed_under_pressure`: call `model.grade_sharper(exp, p.kind, p.target_code, p.text,
  p.response)`; build a `SharperAuditItem`; if `not verdict.sharper`, mark the code disputed.
- Return `assessment.model_copy(update={...})` with: `frames_closed_under_pressure` filtered to
  non-disputed codes; `frame_deltas` with disputed codes' deltas removed (so the disputed frame is
  not `present_reasoned` → `update_state` scores it weak); `sharper_audit` = the items.
- Pure given the model; no I/O. One responsibility: audit the instructor's sharper calls.

### 5.6 Nothing else changes

`state.update_state` already reads `frames_closed_under_pressure` + `frame_deltas` — it consumes the
audited Assessment unchanged (disputed calls already removed → scored weak). `orchestration.run_session`,
`STATE_UPDATERS`, the cs_technical scorer/selector, and the CS dry-run are untouched.

## 6. Data flow (open_ended session, post-Step-5)

```
intake → instructor loop (push/respond/classify; rotate on non-move; stop on
         converged | bounded_error_violation | regression | plateau | budget)
       → Assessment (trajectory w/ raw responses, deltas, closed, stop)
       → audit_sharper: blind grade_sharper per closed frame; dispute → drop from closed
         + revert delta; record sharper_audit
       → audited Assessment → update_state (disputed = weak) → persist → schedule_next
```

## 7. Error handling

- Grader refusal / empty parsed output → `ModelError` (no silent default; doctrine-critical, same as
  the other model calls).
- A `"regressed"` outcome in a `genuinely_open` rubric is a normal stop (regression); the bounded
  hard-wrong flag remains the only verdict and still pre-empts (checked before the move/regress branch).
- `audit_sharper` on an Assessment with no closed frames is a no-op returning an empty `sharper_audit`.

## 8. Testing strategy (TDD; authored fixtures for the resistant paths)

- `test_types.py`: `Push.response` default; `SharperVerdict`/`SharperAuditItem`; `Assessment.sharper_audit`.
- `test_model.py`: `FakeModel.grade_sharper` scripted + default-agree; back-compat of existing ctor.
- `test_anthropic_model.py`: `grade_sharper` mock — angle detail + push + response reach the model,
  the instructor's outcome does NOT; refusal raises `ModelError`. `test_live_model.py`: gated smoke.
- `test_judgment_loop.py`:
  - cooperative converges **and** `sharper_audit` is populated + all confirmed (strengthened).
  - **regression**: a fixture where a closed frame later regresses → `stop_reason is regression`,
    backslide delta recorded, frame not present_reasoned.
  - **plateau (distinct targets)**: two distinct frames each return unchanged → `stop_reason is
    plateau`, and the two pushed codes are distinct (rotation happened).
  - bounded_error + budget paths still green.
- `test_sharper_grader.py` (new): confirm-keeps-closed; **dispute demotes** — a closed frame the
  grader disputes is removed from `frames_closed_under_pressure` AND its delta reverted, and
  `update_state` then scores it `weak` (full integration assertion, guarding the strong-misclassification
  trap in `update_state`).
- Regression safety: `test_dry_run.py`, `test_orchestration.py`, `test_state.py`,
  `test_cs_dry_run.py` stay green unchanged (default-agree grader preserves cooperative behavior).

## 9. Adversarial review checklist (core-path; independent subagent before merge)

1. Regression fires only on a genuine `"regressed"` (not on `"unchanged"`); it records the backslide
   and the frame ends NOT present_reasoned (→ weak in state).
2. Plateau is genuinely distinct-target: rotation skips exhausted codes; two distinct non-moves stop;
   the cooperative path never rotates; no infinite loop (every iteration either moves, exhausts, or stops).
3. The grader is blind — the instructor's outcome never enters `grade_sharper`'s prompt; it judges
   from angle+push+response only.
4. A disputed sharper is removed from `frames_closed_under_pressure` AND its delta reverted, so
   `update_state` cannot score it `strong` (verify against `update_state`'s present_reasoned branch).
5. Conclusion-agnostic: the grader prompt does not dispute a call for reaching a different conclusion.
6. `grade_sharper` `_require`-guards refusal/empty.
7. Bounded-error hard-wrong flag still pre-empts and is unchanged; it is checked before regress/move.
8. Founder cooperative path + CS regime + dry-run byte-stable (default-agree grader, no regressions).
9. `Push.response` default keeps existing constructions valid; no raw response leaks into a tracked
   confidential surface (the trajectory lives in-memory / synthetic-test only; `data/` untracked).
10. The loop always terminates and every stop traces to an authored `StopReason`.

## 10. Execution plan (subagent-driven development, mirroring Steps 3-4)

- Branch `step5-harden-judgment-loop` (created).
- `writing-plans` decomposes into right-sized TDD tasks (types → grader prompt+model method →
  sharper_grader pass → loop regression → loop plateau/rotation → wire audit into assess + raw
  response → strengthen/extend tests → full regression). Each task: fresh implementer + independent
  task reviewer; reports under `.superpowers/sdd/` (gitignored, L-7); explicit-path staging; ruff +
  pytest green; `DEVLOG.md` updated.
- Final whole-branch adversarial review (opus) against §9 before merge to `main`.
- Because the user is away: at every gate, prefer the conservative/doctrine-faithful reading, leave a
  complete DEVLOG trail, and stop rather than guess if a genuine blocker (not a design preference)
  appears.

## 11. Open items resolved here (so the plan need not reopen them)

- Regression stops on the first genuine backslide (lower frame one level + stop).
- Plateau via an `exhausted` set + distinct-target check; `budget` stays the oscillation backstop.
- Grader is a separate blind pass gating sharper by 2-vote; disputed → drop-from-closed + revert-delta.
- `Push` stores the raw response; `FakeModel` grader agrees by default (disputes are scripted).
- Grader audits frame-closes only (the state-affecting sharper calls); trap-repair audit deferred.
