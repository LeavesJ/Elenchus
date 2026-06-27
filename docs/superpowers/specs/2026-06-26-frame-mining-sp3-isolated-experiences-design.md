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
- `angle_count = 1 frame + 3 traps + 0 binding + 4 = 8` (clears the floor; `generator.angle_count`).
- A neutral *legal* lock-in prompt that surfaces the irreversibility + the single-term bait without naming
  the move (L-13): a buyer's counsel wants the continuity terms pinned down before signing; whatever you
  write now is what every customer reads into their risk planning and you can't quietly revise once deals
  depend on it; one straightforward promise covers today's ask; decide what you commit to and how it fails
  if the terms ever must change.

**(b) `irreversible_anchor` unchanged** — the embed experience on problem 1.

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
1. After session 1: `embed.strength == forming`, `breadth == {embedded_anchor_lock_in}`,
   `unprompted_breadth == {embedded_anchor_lock_in}` — produced by the real loop, not set.
2. At session-2 selection: the **top-ranked** `(spec, receipt)` is `continuity_lock_in`, `drive == "deploy"`,
   `runner_up_drive` is named, `margin > 0`; AND `format_problem_menu(proposal)` does **not** contain
   `"embed_credentials_as_a_list"`. (Pins the §6/`policy.py:68-71` ordering against weight/penalty drift —
   §below.)
3. After session 2: `embed.strength == strong`, `unprompted_breadth == {embedded_anchor_lock_in,
   license_fork_risk}`.
4. Post-`strong`: `derive_due(...)` for `embed` is `last_seen + 30 days` (the savings effect; so the
   subsequent quiet reads as scheduled-rarely, not dropped).

**Pinned definition (so a future change fails a test, not the dogfood):** a *trap is not a constituent
frame* for the cold-start penalty or `load` (`policy.py:68-71`). The session-2 ordering depends on it:
worked at the real weights, the embed isolate scores `V = wT·1.0 + (wU−wL)·u_embed = 1.5 + 0.5·u_embed` at
`drive=deploy`, beating the best diagnose candidate (`V = wU·1.0 − wL·1.0 = 0.5`) and any competing transfer
(its single-frame penalty is lower, and `load=1` wins the tie-break). Assertion #2 fails if this inverts.

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
  the real `build_store → propose → select → assess → persist` path, steered via a custom `decide`, never
  `proposal.top` — L-14).

## 10. Out of scope / deferred

- The **@live content-elicitation test** — that real Opus reasons `embed` unprompted from the authored
  prompts (the true content test). Gated; spends tokens.
- A **3rd owned problem** (more transfer opportunities / a more robust `strong`).
- Promotion of `embed` to **durable** (a second, *public* case — the owned→public track).
- Rich multi-frame capstone experiences (the integrative counterpart to isolates) — a later content thread.

## 11. Success criteria

- `continuity_lock_in` authored, clears the anti-label gate, and is reachable through the real gated path.
- The scripted regression is green and asserts §6's four claims — the progression is produced by the real
  engine path (not injected), with the no-frame receipt and the post-`strong` interval verified.
- Suite green, ruff clean, confidentiality gates empty, no `Co-Authored-By`.
