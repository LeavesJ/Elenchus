# Frame Mining — Sub-project 3: Isolated Experiences (light the engine for the admitted frame)

Date: 2026-06-26
Status: design — plan-ready after user review
Origin: SP2 admitted the first new spine frame `embed_credentials_as_a_list` (provisional, on one owned
problem). SP3 is the third of the three frame-mining sub-projects from the umbrella design
(`docs/superpowers/specs/2026-06-25-frame-mining-spine-expansion-design.md` §3). Twice design-reviewed
(the two flagged decisions affirmed; five sharpenings folded in — §6–§8 below).

## 1. Goal

Make `embed_credentials_as_a_list` **locatable by the diagnostic-progression engine across ≥2 owned
problems**, so it can reach `strong` and fire **transfer** — proven by a committable **scripted regression**
that drives the *real* engine path (no @live spend). The engine-lighting payoff: the value function locates
the frame, transfer fires, the frame reaches `strong`, and a series-dogfood becomes possible.

## 2. The engine mechanics this must satisfy (verified against the code)

- **`strong` = `len(unprompted_breadth) ≥ 2`** — the frame held `present_reasoned` **unprompted** (reasoned
  at intake AND exit AND **never probed**) across ≥2 distinct `ledger_ref`s (`state.py:32`; `judgment_loop`
  derives `reasoned_unprompted` from intake-state ∧ exit-state ∧ not-probed). `forming` = `evidence_count ≥
  1` (`state.py:34`). Closed-under-pressure credits `breadth` but **not** `unprompted_breadth` — pressure
  alone cannot reach `strong`.
- **Transfer (`wT`) fires iff** the frame is `forming` AND the experience's `ledger_ref` ∉ `breadth`
  (`policy.py:27-31`). It proposes a new-problem experience for the frame (`drive="deploy"`).
- **The cold-start integration penalty counts FRAMES ONLY, not traps** — `penalty = max(uncertainty(g) for
  g in e.rubric.frames)` and `load = len(e.rubric.frames)` (`policy.py:68-71`). A single-frame isolate's
  penalty is therefore `uncertainty(embed)` alone (low once `forming`). **This is load-bearing** (§6).
- **The learner-facing surface withholds the frame** — `surface.format_problem_menu` renders `ledger_ref`s
  only, never a frame or drive (`surface.py:25-31`, §17.1); `format_receipt` (which names the frame) is
  author/log-only. So an unprompted read stays uncontaminated (L-13).
- **Storage-keyed interval**: `{weak:1, forming:7, strong:30}` days (`state.py:23`); `derive_due` =
  `last_seen + interval[storage_tier]`. Reaching `strong` lengthens the review interval to 30 days (§8).
- **Weights** (`content/cadence/progression.yaml`): `wU=1.0, wR=1.0, wT=1.5, wL=0.5, theta_located=0.5`.

## 3. Scope — decisions settled

- **Content + scripted engine proof.** Author the isolated experience(s) + a committable scripted regression
  that drives the engine `weak → forming → strong` and confirms transfer fires. The @live "does the content
  *elicit* unprompted reasoning" test is **deferred** (gated; §6 honesty boundary).
- **2 owned problems**, reusing the existing `veldra:license_fork_risk` (the escrow/continuity legal lock-in)
  as the 2nd — no new seed entry, no ingest, no L-8 cascade.
- **Single-frame isolate shape** (1 frame + ~3 traps = 8 angles) — the structural inverse of a capstone
  (many frames on one problem, gated until its constituents are located); the isolate is one frame across a
  second problem and is *what does the locating*.
- **Reuse `irreversible_anchor` for problem 1** — authoring a 2nd embed experience on
  `embedded_anchor_lock_in` would give the engine two backing experiences for the same `(frame, problem)`
  pair, reintroducing the §16 candidate-type ambiguity that decision was rewritten to avoid. Lean *and*
  correct.

## 4. Architecture & components

**(a) One new single-frame isolated experience** — `content/rubrics/continuity_lock_in.yaml`:
- `ledger_ref: "veldra:license_fork_risk"`; `regime: open_ended`; `mode: genuinely_open`;
  `binding_constraint: null`; **`decision_frame` omitted** (§7 — a stress-probe on a decision_frame would
  mark `embed` *probed* and disqualify the unprompted read that `strong` depends on).
- **1 frame**: `embed_credentials_as_a_list` (frame_detail: the provision-optionality move) +
  `paired_trap: shipped_the_one_shot_term`.
- **3 traps** = embed's own three failure modes (§7).
- `angle_count = 1 frame + 3 traps + 0 binding + 4 = 8` (clears the floor; `generator.angle_count`) —
  **at the floor, no headroom: this is the deliberate minimal-isolate shape, but any future cut to a trap
  drops it below the gate, so an angle change must re-check `load_gated_library` (a 4th embed-failure trap is
  the margin option if ever needed).**
- A neutral *legal* lock-in prompt that surfaces the irreversibility + the single-term bait without naming
  the move (L-13): a buyer's counsel wants the continuity terms pinned down before signing; whatever you
  write now is what every customer reads into their risk planning and you can't quietly revise once deals
  depend on it; one straightforward promise covers today's ask; decide what you commit to and how it fails
  if the terms ever must change.

**(b) `irreversible_anchor` unchanged** — the embed experience on problem 1. It has **no `decision_frame`
and `binding_constraint: null`**, so no stress-probe can mark `embed` probed. **Verified by construction**
(the same check the isolate got): `assess(irreversible_anchor, ...)` with `embed = present_reasoned` at
intake (and `choose_the_failure_default_deliberately = absent`, scripted) yields `reasoned_unprompted =
['embed_credentials_as_a_list']` with `embed` **never in the trajectory** (only `choose_…` is probed). So
session 1 starts `embed` at `unprompted_breadth = 1` *through the real not-probed path* — §6 assertion #1 is
verified, not assumed. The regression re-runs this construction check (§6).

**(c) A committable scripted regression** — `tests/test_sp3_progression.py` (§6): drives the real engine
across two sessions and asserts the `weak → forming → strong` progression, the session-2 transfer ordering,
the no-frame receipt, and the post-`strong` interval.

## 5. The progression (data flow the regression proves)

`weak`
→ **session 1** (`irreversible_anchor` on `embedded_anchor_lock_in`; embed reasoned *unprompted*)
→ `forming`, `breadth = {embedded_anchor_lock_in}`, `unprompted_breadth = {embedded_anchor_lock_in}`
→ **session-2 selection**: the value function fires **transfer** on `continuity_lock_in` (embed `forming` +
  `license_fork_risk` ∉ breadth → `drive="deploy"`), beating diagnose-on-unseen-frames
→ **session 2** (`continuity_lock_in` on `license_fork_risk`; embed *unprompted*)
→ `unprompted_breadth = {embedded_anchor_lock_in, license_fork_risk}` → **`strong`**; due interval → 30 days.

## 6. The regression: what is REAL vs FIXTURED (the claim that makes it a proof)

A scripted regression with no @live spend must supply the model's *judgments* through a `FakeModel`. The
proof is only meaningful if the **unprompted property is established by the real gated path, not assumed by
the fake**. Therefore:

- **FIXTURED — the FakeModel supplies ONLY the model's judgments of the learner:** `classify_intake`
  (scripts `embed = present_reasoned` for the unprompted read; other frames as needed), `classify_response`
  (for any probes the loop issues), `grade_sharper`, `generate_push`.
- **REAL — everything that *makes a read count*:** `propose_open_ended`/`select_next` (the value function +
  transfer scoring), the learner-facing menu (`format_problem_menu`, frame withheld), the judgment loop's
  not-probed logic (a frame `present_reasoned` at intake is not targeted → stays unprobed), the
  `reasoned_unprompted` derivation, `update_state` (breadth/unprompted_breadth aggregation),
  `derive_strength`/`derive_due`, persistence + reload.
- **The test NEVER injects `unprompted_breadth`, `strength`, or the strength transition** — it asserts them
  as *outputs* of the real path, and asserts the session-2 learner surface withholds the frame (so the
  credited read is legitimately unprompted).
- **Honesty boundary (stated so the claim isn't overread):** this regression proves the progression *through
  the real engine path, given a scripted learner*. It is **not** a content-elicitation proof — that real
  Opus, reading `continuity_lock_in`'s prompt, actually reasons `embed` unprompted is the **@live test,
  deferred** (§10). Without this boundary, SP3 would prove the state machine (P1's job), not this content.

**Assertions the regression must make:**
1. **Session 1 starts the frame unprompted *through the real path* (the step the first draft asserted
   without verifying — the gating fix).** Assert `embed ∈ assessment.reasoned_unprompted` AND `embed` is
   **never a trajectory target** in session 1 (it is not probed — verified by construction:
   `irreversible_anchor` has no `decision_frame`, so a frame `present_reasoned` at intake stays unprobed and
   the credit is earned, not an artifact of a stress-probe the FakeModel silently omitted). Then assert
   `embed.strength == forming`, `breadth == {embedded_anchor_lock_in}`, `unprompted_breadth ==
   {embedded_anchor_lock_in}` — produced by the real loop, not set. AND the session-1 **learner surface
   withholds the frame** too (both sessions credit an unprompted read, so both presentations must withhold
   the move, not only session 2's).
2. At session-2 selection: **`ranked[0]` is `continuity_lock_in` resolved by `experience_id`** (NOT by
   ledger_ref — two experiences now share `veldra:license_fork_risk`, §M3 below), with `drive == "deploy"`
   and `frame == "embed_credentials_as_a_list"`; AND the **true rank gap `ranked[0].V − ranked[1].V > 0`
   asserted directly over the scored candidates** — NOT the receipt's `margin`. (The receipt's
   `margin`/`runner_up_drive` are **cross-drive only** — `policy.py:99` filters `others` to a *different*
   drive — so they are blind to a same-drive *competing transfer* overtaking the isolate, which is the real
   failure mode; the receipt margin would pass while the actual ordering inverted.) AND
   `format_problem_menu(proposal)` (a multi-item menu, `license_fork_risk` among the four problems) does
   **not** contain `"embed_credentials_as_a_list"`.
3. After session 2: `embed.strength == strong`, `unprompted_breadth == {embedded_anchor_lock_in,
   license_fork_risk}`.
4. Post-`strong`: `derive_due(...)` for `embed` is `last_seen + 30 days` (the savings effect; so the
   subsequent quiet reads as scheduled-rarely, not dropped).

**Pinned definition (so a future change fails a test, not the dogfood) — corrected against a live
`select_next` run.** A *trap is not a constituent frame* for the cold-start penalty or `load`
(`policy.py:68-71`), so the single-frame isolate has the lowest penalty. The embed isolate wins session-2
**on `V`** (≈1.77), and its true runner-up is a **competing transfer**, not the diagnose floor:
`choose_the_failure_default_deliberately` — the 2nd frame in `irreversible_anchor`, which goes `forming` in
session 1 — fires `deploy` on `decision_under_stakes`/`proof_before_promise` at `V`≈1.55. The isolate wins
because its penalty is `wL·u_embed` (one *seen* frame) vs the competitor's `wL·1.0` (its 2nd frame unseen);
the `load=1` tie-break **never fires** (the `V`s differ). The gap is **real but thin: ~0.25 same-day,
shrinking to ~0.08 at the 7-day `forming` edge** as `retention_due` and uncertainty drift — so the
regression must run session-2 **pinned at the worst case (the 7-day forming edge, gap ~0.08), not a
comfortable midpoint**, so a passing test guards the whole window rather than a wide point inside it, and
assert the direct rank-1-vs-rank-2 `V` gap. A weight change that lets the competing transfer overtake the
isolate then fails the test — which the receipt-margin assertion would have missed.

**Known thinness (calibration territory, not a build blocker — §10).** That ~0.08 forming-edge margin is a
*real-use* fragility, not just a test concern: in the dogfood the learner returns when they return, so if
session 2 lands near the forming edge the transfer win sits on a margin the competing transfer's own
retention drift can invert — making "embed reaches `strong`" timing-dependent. The fixed test offset must
**not** hide this; it is recorded here as a known thinness to tune in `content/cadence/progression.yaml`
(e.g. a larger `wT`), not left implied-robust. Relatedly, the cross-drive receipt `margin` (the dogfood's
calibration *log* surface) **overstates decisiveness whenever the real contest is same-drive** — it would
log a comfortable cross-drive margin while the call was nearly tied. The plan should either log the absolute
rank-1-vs-rank-2 gap alongside it, or mark the logged `margin` as cross-drive-only so it is not misread
during calibration.

## 7. The three traps are embed's OWN failure modes

To keep the isolate genuinely single-frame, every trap must be a way of getting **embed** wrong — not the
failure mode of an adjacent move smuggled in through the trap slot (the SP2 orthogonality discipline applied
to traps). The three map to embed's three-part definition (provision the cheap optionality now for an
immutable-after-ship choice; reject both the naive single value and the elaborate remote fix):

- `shipped_the_one_shot_term` (paired to embed): committed a single fixed term now and assumed more could be
  layered in later, when the shipped commitment admits no quiet later change. *(the scalar-defer failure)*
- `over_built_the_escape_hatch`: reached for an elaborate revisable/remote mechanism to preserve flexibility
  instead of the cheap optionality provisioned from the start. *(the over-engineering failure)*
- `treated_the_shipped_choice_as_amendable`: assumed the commitment could be revised after others depend on
  it, missing that shipping removes the later option. *(the enabling false belief)*

Each `trap_detail` is "the provision-optionality move gone wrong," never an adjacent decision's failure.

## 8. Confidentiality + a genuine second context

- The new rubric is **committable + abstracted**: a neutral legal-lock-in scenario. `license_fork_risk`'s
  confidential ore (the real escrow detail + its authored scene) stays in the **gitignored** seed; the
  abstracted prompt does not reproduce it. No new gitignored entry; the abstraction rule (SP2 §7) applies.
- **It must be a real second deployment context, not a sanitized restatement of problem 1.** The isolate is
  the *legal* lock-in (an escrow/continuity clause shipped to buyers); problem 1 is the *technical*
  embedded-credential lock-in. The breadth it adds is real cross-context transfer — exactly the
  `surface_independence` PASS the founder affirmed (the frame transfers to any lock-in-now-or-never
  decision), not the same problem twice.

## 9. Testing

- The scripted regression (§6) is the engine proof.
- `load_gated_library` must not raise — `continuity_lock_in` clears the anti-label gate (8 angles;
  `genuinely_open` + null binding; prompt leaks no frame/trap code or framework word; corpus entry for
  `license_fork_risk` already has non-empty `unlabeled`/`why_owned`/`provenance`).
- Build features subagent-driven TDD; the regression is the L-8/L-9-class production-path test (it exercises
  the real `build_store → propose → select → assess → persist` path, steered via a custom `decide` resolving
  the experience by **`experience_id`**, never `proposal.top` and never by ledger_ref — L-14).
- **Cascade fix (BLOCKER — the plan MUST cover BOTH arms of the L-14 re-steer, verified by live runs).**
  Authoring `continuity_lock_in` on the *shared* `veldra:license_fork_risk` re-steers
  `Proposal.problem_menu()`: the isolate wins the per-problem dedup over `license_continuity` at `load=1` vs
  `load=3`, **even from empty state** (equal `V`, the `(-V, load, …)` tie-break picks the smaller load). This
  has two arms — the spec must address **both**, not only the first:
  - **Arm 1 — CI breakage.** The served experience for `license_fork_risk` becomes `continuity_lock_in`,
    whose frame `embed` is not scripted by the FakeModels in three existing tests → `KeyError:
    'embed_credentials_as_a_list'` in `tests/test_dry_run.py::test_dry_run_closes_the_loop`,
    `tests/test_orchestration.py::test_run_session_closes_one_cycle`, and `::test_run_session_logs_selection_receipt`.
    The plan re-points those three (steer by `experience_id`, extend their FakeModels to script `embed`, or
    move them to a different ledger_ref) so the suite is green at every commit. *The branch must not land CI-red.*
  - **Arm 2 — the served-experience shadow (the consequence past CI).** `license_continuity` is **production
    content**, and it is the **only home of `commit_under_the_deadline`** (lead/protect have other homes;
    commit does not). While `embed` is unlocated the isolate shadows `license_continuity` on
    `license_fork_risk`, so `commit` has no menu path. **This is NOT the §16 (frame, problem) ambiguity** —
    `continuity_lock_in` carries `embed`, `license_continuity` carries other frames, so the pair (embed,
    license_fork_risk) still has exactly one backing experience; the collision is in the *coarser per-problem
    dedup under the menu*, which darkens the richer experience as a side effect of lighting `embed`.
    **Verified the shadow is temporary + self-resolving** (`select_next` over the real library, three
    states): fresh → `continuity_lock_in` (diagnose); embed `forming` → `continuity_lock_in` (deploy); embed
    **`strong` → `license_continuity` surfaces** (`commit_under_the_deadline`, diagnose). So `commit` is
    *delayed* behind `embed` reaching `strong`, **not lost** — which is consistent with the
    isolate-before-capstone doctrine (diagnose the single-frame isolate before the load-3 mini-capstone). The
    plan must **(i)** add a regression assertion exercising the **default menu path** on `license_fork_risk`
    (fresh + forming → `continuity_lock_in`; embed-`strong` → `license_continuity`/`commit` surfaces), so the
    shadow + self-resolution is *tested*, not routed around by the `experience_id`-steered §6 assertions; and
    **(ii)** record the `commit` delay as an **accepted consequence** — the founder's call (2026-06-26):
    keep `license_fork_risk` (the shadow is temporary, self-resolving, and doctrine-consistent); the
    relocate-to-`cross_pool_data_optics` and menu-fix alternatives were considered and declined.

## 10. Out of scope / deferred

- The **@live content-elicitation test** — that real Opus reasons `embed` unprompted from the authored
  prompts (the true content test). Gated; spends tokens.
- A **3rd owned problem** (more transfer opportunities / a more robust `strong`).
- Promotion of `embed` to **durable** (a second, *public* case — the owned→public track).
- Rich multi-frame capstone experiences (the integrative counterpart to isolates) — a later content thread.

## 11. Success criteria

- `continuity_lock_in` authored, clears the anti-label gate, and is reachable through the real gated path.
- The scripted regression is green and asserts §6's four claims — the progression is produced by the real
  engine path (not injected), the session-2 ordering pinned by the **direct rank-1-vs-rank-2 `V` gap** (not
  the receipt margin), with the no-frame receipt and the post-`strong` interval verified.
- Suite green **including the three re-pointed tests** (§9 cascade fix), ruff clean, confidentiality gates
  empty, no `Co-Authored-By`.
