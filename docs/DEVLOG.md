# Retnovation — DEVLOG

## 2026-06-27 — SP3 live content-elicitation probe — design spec (intake-equivalence proof + folded review)
- `docs/superpowers/specs/2026-06-27-sp3-live-content-elicitation-design.md` — closes SP3's deferred claim:
  does real frame-naive Opus read `embed_credentials_as_a_list` `present_reasoned` at intake on the two
  authored prompts? (The scripted regression *scripts* that read; this measures it.) A **calibration probe** —
  automates the run, leaves the verdict to the human (SP1/L-15).
- **Key finding folded after an incisive review** (does the probe measure the intake-leg or the full
  `reasoned_unprompted` property?): traced the merged code — for a rubric with no `decision_frame` and target
  ≠ `binding_constraint`, target `present_reasoned` at intake ⟺ target ∈ `reasoned_unprompted`
  (`judgment_loop.py:52/129/147/170-176`): a present-at-intake frame is never selected, probed, or lowered.
  Both in-scope rubrics qualify, so the intake-only probe is provably the SP3 property here — a proof, not a
  weaker proxy. The full live `assess()` loop would add only breadth-under-pressure (not the unprompted
  property), so it is omitted by design.
- Design: thin `src/retnovation/elicitation.py` (pure orchestration over the Model protocol),
  `generate_output(prompt, None)` [bare = the SP2 control call] → `classify_intake`; an
  `assert_intake_equivalence` guard refuses rubrics where the equivalence breaks (L-16); a
  `run_elicitation.py` I/O entrypoint; artifact gitignored under `data/elicitation/`. Folded review points:
  trap-pattern foregrounded for hard-vs-borderline, n-resolution honesty boundary (borderline ⇒ rerun, not a
  stable category), asymmetric P1-weighted sampling (P1=8 / P2=5), live L-13 assertion on the real prompt.
  Next: writing-plans.

## 2026-06-27 — SP3 T3: SelectionReceipt.margin labeled cross-drive in format_receipt + types comment (223 passed, 4 skipped)

## 2026-06-27 — SP3 T2: engine-proof regression — embed weak→forming→strong via the real path; ordering pinned; shadow self-resolves (222 passed, 4 skipped)

## 2026-06-27 — SP3 T1: continuity_lock_in isolate added + L-14 cascade tests re-pointed (Arm 1)
- `content/rubrics/continuity_lock_in.yaml`: single-frame isolate on `veldra:license_fork_risk`, frame `embed_credentials_as_a_list` + 3 traps, 8 angles, clears the anti-label gate.
- `tests/test_sp3_progression.py`: gate assertion (load + frame list + angle_count == 8).
- `tests/test_dry_run.py`, `tests/test_orchestration.py`: re-pointed `_to_license` to steer by `experience_id == "license_continuity"` over `proposal.candidates` (L-14 re-steer); 219 passed, 4 skipped.

## 2026-06-26 — Frame-mining SP3 (isolated experiences) spec written + design review folded
- `docs/superpowers/specs/2026-06-26-frame-mining-sp3-isolated-experiences-design.md` — SP3 makes the
  admitted frame `embed_credentials_as_a_list` locatable by the diagnostic-progression engine across ≥2
  owned problems (reach `strong`, fire transfer), proven by a committable **scripted** regression over the
  REAL engine path (no @live spend). Components: one new single-frame isolated experience
  `continuity_lock_in` on the existing `veldra:license_fork_risk` (no seed/ingest/L-8 cascade); reuse
  `irreversible_anchor` for problem 1; the regression. Decisions settled: content + scripted proof;
  license_fork_risk as the 2nd problem; single-frame isolate (1 frame + 3 traps = 8 angles); reuse problem 1.
- **Two design reviews folded (the second was incisive).** Verified the load-bearing code facts before
  incorporating (L-12/L-15): the cold-start penalty counts FRAMES not traps (`policy.py:68-71`) so the
  single-frame isolate wins session-2 transfer cleanly; the learner menu withholds the frame
  (`surface.py:25`); post-`strong` interval = 30d (`state.py:23`); weights wT=1.5/wU=1.0/wL=0.5. Five
  sharpenings: (1) the regression's REAL-vs-FIXTURED boundary stated explicitly (FakeModel supplies only the
  model's judgments; selection/transfer/not-probed/no-frame-receipt/aggregation/strength are real; the test
  asserts the progression as OUTPUTS, never injects it) + the honesty boundary that it proves the path, not
  content-elicitation (the @live test, deferred); (2) the regression PINS the session-2 ordering (top-ranked
  = continuity_lock_in, drive=deploy, runner-up named) so a weight change fails a test; (3) the 3 traps are
  embed's OWN failure modes (scalar-defer / over-build / amendable-belief), not siblings' — orthogonality in
  the trap slot; (4) the isolate is a genuine 2nd context (legal lock-in vs technical), not a restatement;
  (5) assert the post-`strong` due interval is the long one. Also: `decision_frame` omitted from the isolate
  because a stress-probe would mark embed *probed* and disqualify the unprompted read `strong` depends on.
- **Adversarial spec review folded (OPUS, ran the checks) = YES-WITH-FIXES.** It reproduced the central
  claims live (the unprompted proof: trajectory length 0, embed never probed, `reasoned_unprompted=[embed]`;
  the session-2 isolate win; the anti-label gate; strong/interval). Folded: (B1, blocker) authoring
  `continuity_lock_in` on the shared `license_fork_risk` re-steers `problem_menu` (load=1 wins) and breaks
  `test_dry_run` + `test_orchestration`×2 with `KeyError: embed` — the plan must re-point those 3 (L-14
  cascade); (M1) the §6 ordering assertion was wrong — the true rank-2 is a *competing transfer*
  (`choose_the_failure_default`, forming after S1), the isolate wins on V not the load tie-break, and the
  receipt's margin is *cross-drive only* (`policy.py:99`) so it can't see a same-drive transfer overtaking —
  the regression now asserts the direct rank-1-vs-rank-2 V gap; (M2) the gap is thin (~0.08–0.25,
  staleness-dependent) → run session-2 at a fixed `now`; (M3) steer by `experience_id` not ledger_ref.
- **Second user design-review folded (the gate it named, verified by live runs).** (Issue 1, gating) the
  spec asserted session 1's unprompted read without verifying it — VERIFIED by construction:
  `assess(irreversible_anchor, embed=present_reasoned)` → `reasoned_unprompted=[embed]`, embed never probed
  (no decision_frame → no stress-probe); the regression now re-runs this session-1 construction check. (Issue
  2) the §9 cascade only handled the CI arm — VERIFIED the served-experience arm: the isolate shadows
  `license_continuity` on `license_fork_risk` (the only home of `commit_under_the_deadline`), but the shadow
  is temporary + self-resolving (fresh/forming → isolate; embed `strong` → license_continuity/commit
  surfaces); the plan now tests the default-menu-path arc + records the commit-delay (or relocates to a
  no-collision problem). (Issue 3) pin session-2 at the worst-case forming edge (gap ~0.08), record the
  real-use thinness + the cross-drive logged-margin distortion as calibration items; (smaller) no-frame
  surface asserted for BOTH sessions; angle_count floor (8, no headroom) noted.
  Decision locked: keep `license_fork_risk`, accept the commit delay (founder's call).

## 2026-06-26 — Frame-mining SP3 implementation plan written
- `docs/superpowers/plans/2026-06-26-frame-mining-sp3-isolated-experiences.md` — 3 tasks: (T1)
  `continuity_lock_in` rubric + atomic re-point of the 3 L-14-cascade tests (steer by `experience_id` over
  `proposal.candidates`); (T2) the scripted engine-proof regression (`tests/test_sp3_progression.py`) —
  session-1 construction check, two-session weak→forming→strong over the real path, the session-2 ordering
  pinned by the direct rank-1-vs-rank-2 V gap at the worst-case forming edge, the shadow self-resolution on
  the default menu path; (T3) mark the receipt margin cross-drive in the log surface. Plan code transcribes
  the mechanics I verified by live runs.
- **Adversarial plan review folded (OPUS, ran the regression code green end-to-end) = YES-WITH-FIXES.** 3
  MAJORs: (M1) the ordering-pin used a hand-built embed-only state → comfortable gap ~1.4, missing the real
  ~0.08 window (reviewer proved it: with `wL=0` the real state inverts but the helper still passed) — fixed
  by deriving the pin from the REAL post-session-1 `state1` (carries `choose_failure` forming as the
  competing transfer), folded into the two-session test; (M2) appended imports → 14 ruff E402 → commit
  blocked → hoist all imports to the file top; (M3) Task 3 quoted a non-existent `format_receipt` line whose
  literal edit lowercased the runner-up and broke 2 tests → fixed to the real `surface.py:17` preserving
  `_label`/`over`. Plus a MINOR (session-1 surface-withhold assertion added). NEXT: subagent-driven execution.

## 2026-06-26 — SP2 cosmetic cleanup (post-review minors)
- `ScreenSummary` now rounds `mean_distinguishability`/`mean_preference` to 2dp via a `field_validator`
  (clean committable audit records; the raw `LiftResult` under gitignored `data/lift/` keeps full precision).
  Regenerated the 6 `docs/admissions/*.yaml` records (load -> validator rounds -> re-dump; rationales/gates
  untouched; integrity check re-verified). Map comment for the admitted frame now points to its record
  instead of duplicating the screen fact (no drift). Suite 218/4, ruff clean. Closes the two Minor items
  from the Phase-2 whole-branch review.

## 2026-06-26 — Frame-mining SP2 Phase 2 (mine + admit) RUN: first new spine frame admitted
- **`embed_credentials_as_a_list` admitted as a provisional founder-CEO spine frame** — the first frame
  mined + lift-screened + human-adjudicated through the SP2 machinery. On branch
  `frame-mining-sp2-phase2-admit` (off main `7e68c8f`). Suite **217 passed / 4 skipped**, ruff clean, both
  confidentiality gates empty.
- **The mine:** 6 candidates authored into the gitignored `content/lift/{candidates,scenarios}.yaml` (3 blind
  scenarios each), reviewed by an OPUS adversarial pass (3 must-fix de-spotlight edits folded — would have
  manufactured false nulls). **@live screen** (real Opus, ~72 high-effort calls; order alternated AB/BA to
  break rater position bias) → `data/lift/` (gitignored). Result: **embed = LIFT 3/3 +1.0** (the only clean
  lift; 2 genuine substance wins where the control over-built a remote-update channel / accepted a stranding
  scalar — the immutability-after-ship gap); scope_the_fail_closed = mixed +0.33 (borderline);
  build_more / cap_effort / manufacture / withhold = mixed −0.33 (move registers but doesn't net-lift;
  withhold's predicted-null held). Read at the substance level (not just the verdict): several "lift" cells
  won on 180-word discipline, several "negative" cells lost on execution — the harness automates the kill,
  not the verdict.
- **Adjudication (with the user):** marginal_lift [AUTO] + 4 human gates assessed; the swing gate
  `surface_independence` (founder-spine-or-engineering?) was the user's call → **PASS** (transfers to any
  lock-in-now-or-never decision). Admitted: frame added to `content/maps/founder_ceo.yaml`; minimal
  experience `content/rubrics/irreversible_anchor.yaml` (2 frames + 2 traps = 8 angles, clears the
  anti-label gate at the floor); new owned problem `embedded_anchor_lock_in` in the gitignored seed
  (ADR-001/R-149), ingested. 6 committable abstracted `AdmissionRecord`s in `docs/admissions/` (1
  admit_provisional + 5 reject), each carrying both screen axes; admit-time content-graph integrity check
  green.
- **Production-path regression** (`tests/test_admission_regression.py`, L-8/L-9): the admitted frame is
  reachable through the real `build_store → propose → select → assess → persist` path, **steered to the
  experience via a custom `decide`, not `proposal.top`** (L-14). Adding the experience re-fired the L-8
  cascade (4 test failures: the live DB needed the seed ingested; `test_experience.py`'s synthetic-corpus
  list needed the new ref) — caught by the suite, fixed.
- **Tooling refinement (L-16, dogfood finding):** made `AdmissionRecord.gates` optional so a screen-reject
  doesn't force 5 invented human-gate verdicts into a committable audit record (the validator requires gates
  for admit/subframe, allows None for reject). NEXT: OPUS whole-branch review of the Phase-2 branch →
  finishing-a-development-branch. (Then SP3: author isolated + cross-problem experiences for the admitted frame.)

## 2026-06-25 — SP2 post-review hardening: 4 new tests (axis-value pins, 2 integrity edges, screen_candidate order-dict boundary guard); suite 213 passed 4 skipped

## 2026-06-25 — SP2 T5: `check_content_graph_integrity` + `candidates.yaml` confidentiality wiring (`admission.py` + `.gitignore` + `docs/lessons.md` + `docs/admissions/_TEMPLATE.example.yaml`; 5 new integrity-check tests; suite 210 passed 4 skipped)

## 2026-06-25 — SP2 T4: `format_adjudication_packet` + `format_admission_record` (`admission.py`; both axes + verbatim framed/control per scenario; YAML round-trip with `marginal_lift`; 2 new tests; suite 205 passed 4 skipped)

## 2026-06-25 — SP2 T3: `screen_candidate` driver + persistence (`admission.py`; filters by candidate tag, persists `LiftResult` JSON; 1 new test; suite 203 passed 4 skipped)

## 2026-06-25 — SP2 T2: `load_lift_candidates` + `candidate`-tagged scenarios (`LiftScenario.candidate: str | None`; `candidates.example.yaml` stub; 2 new tests; suite 202 passed 4 skipped)

## 2026-06-25 — SP2 T1: admission types landed (`Provenance`, `MinedCandidate`, `ScreenSummary`, `Gates`, `AdmittedAs`, `AdmissionRecord` with `@computed_field marginal_lift` + coherence validator; 6 new tests; suite 200 passed 4 skipped)

## 2026-06-25 — Frame-mining SP2 (mine + admit) plan written
- `docs/superpowers/plans/2026-06-25-frame-mining-sp2-mine-admit.md` — 5 additive Phase-1 TDD tasks
  (admission types + coherence validator; `load_lift_candidates` + candidate-tagged scenarios;
  `screen_candidate` driver + persistence; adjudication-packet + admission-record formatters; content-graph
  integrity check + `candidates.yaml` confidentiality wiring) + a gated, human-in-loop Phase-2 runbook
  (author the real banks → @live screen → triage/adjudicate → admit → integrity check + fresh-DB
  production-path regression → OPUS whole-branch review → finish). Every Phase-1 commit stays green
  (additive; nothing existing depends on the new `admission.py`). `marginal_lift` is a pydantic
  `@computed_field` derived from `screen.verdict` (the record carries both axes — seam 1); the coherence
  validator constrains all three exits. Verified before commit: the `@computed_field` round-trips through
  YAML under `extra="ignore"`, and `pass` serializes unquoted.
- **Adversarial plan review folded (READY-TO-BUILD: YES-WITH-FIXES).** An OPUS reviewer that *ran* the code
  confirmed all of Phase 1 correct (validator branches, `un_randomize` sign, screen-driver round-trip,
  integrity edges, every-commit-green, `build_store` auto-seed). One MAJOR + four MINORs folded: (M1) the
  Step-E production-path regression now steers selection via a custom `decide` over a minimal load=1 rubric
  — the reviewer reproduced the L-14 trap (a multi-frame rubric drops the new frame to rank #5 →
  `KeyError` on unscripted codes); (m1) spec §4 `check_content_graph_integrity` signature synced to the
  4-arg form; (m2) `ScreenSummary.from_result` wired into Step C + tested; (m3) author ≥3 scenarios
  (matching `min_scenarios`) + surface `below_floor` in the packet; (m4) the abstraction rule scoped so the
  citation-key `pointer` may carry a doc locator/date while reasoning-shape fields may not; (n1) `AdmittedAs`
  min_length guard. NEXT: subagent-driven execution (Phase 1) → gated Phase 2.

## 2026-06-25 — Frame-mining SP2 (mine + admit) spec written + adversarial review folded
- `docs/superpowers/specs/2026-06-25-frame-mining-sp2-mine-admit-design.md` — SP2 admits the first new
  spine frame(s) end-to-end: mine the Veldra ore (6 candidates surfaced via parallel recon), screen each
  with the SP1 harness as the auto-screen, apply the rest of the v0.2 gate by hand, admit survivors as
  provisional. **Architecture C (hybrid):** a thin layer over the untouched harness — `screen_candidate`
  (persists each @live `LiftResult`), a pure adjudication-packet formatter (both axes + framed/control
  outputs), and a structured committable **`AdmissionRecord`** that turns the v0.2 gate into a
  coherence-validated artifact a commit can enforce. Decisions settled in brainstorming: end-to-end, all 6
  candidates, hybrid.
- **One external adversarial design review folded in (4 seams):** (1) **schema-gating** — the record now
  carries **both** screen axes (`mean_distinguishability` + `mean_preference`) with `marginal_lift` a
  *derived view*, honoring the umbrella spec's "the verdict must carry both axes; lift is a derived view" so
  the `surface_independence` gate one line down reads distinguishable-but-dispreferred (native cognition /
  style-not-substance) directly instead of blind; (2) the **coherence validator** now constrains all three
  exits (reject needs a screen verdict + rationale; admit needs `separating_artifact`; subframe needs a
  named sibling; `auto_kill ⇒ reject`); (3) a **content-graph integrity check** at admit
  (`ledger_ref`/`experience_id` referential cross-check) distinct from the e2e regression; (4) per-gate
  **referent** annotation, `public` provenance marked untested-this-arc, a concrete **abstraction rule** for
  committable records, and the arc's success criterion = **completes on whatever survives** (~1–2; a high
  kill rate is the screen working). Verified the review's §-citation (depreciation is §4 + §11–§12, not §12)
  and the `LiftResult` axis field names before folding (L-12/L-15). NEXT: user reviews spec → writing-plans.

## 2026-06-25 — Frame-mining SP1 (blind-lift harness) BUILT — subagent-driven, 5 tasks + final review
- **Sub-project 1 of the frame-mining architecture complete** on branch `frame-mining-lift-harness`
  (7457eae..bfa6a0c, 6 commits). Suite **194 passed / 4 skipped** (the 4th skip = the new `@live` lift
  smoke), ruff clean, both confidential gates empty, no Co-Authored-By. Executed subagent-driven (fresh
  implementer + independent reviewer per task; OPUS reviewers on T1 truth-table / T3 refusal-divergence /
  T4 un_randomize-sign + the final whole-branch review).
- What shipped: `src/retnovation/lift_test.py` (`run_lift_test` + pure `randomize`/`un_randomize`) over three
  additive `Model` methods — `generate_output` (**captures a refusal as signal, doesn't raise** — divergence
  from `generate_push`), `rate_preference` (**unprimed** blind rater), `check_injection_expressed`
  (**primed** gate). Two-axis result types (`ScenarioVerdict`/`LiftResult`) with `status`/`verdict`/
  `screen_action` **derived, no stored `lift` bool**; a **total** verdict precedence; `auto_kill` only on
  {null, negative_lift}. Prompts `lift_rate.md`/`lift_manipulation.md`; config `content/lift/lift.yaml`;
  the **confidentiality fix** (`/content/lift/scenarios.yaml` gitignored, `scenarios.example.yaml`
  committable, lessons gate extended). The acceptance suite reproduces the documented EXP verdicts
  (EXP-001→`negative_lift` at dist=1 — the L-15 `negative` cell, not dist-0 `null`; EXP-002→`lift` incl. a
  captured control refusal; EXP-003→`mixed`). The harness **automates the kill, not the verdict** — it
  surfaces verbatim outputs + the rater's key-difference for human adjudication, with the same-model bias
  named directional (false-positive-leaning) so the human adjudicates preference on survivors.
- Process: brainstorm → spec (5-lens adversarial review; its "EXP-001 is null" headline refuted on verify →
  L-15) → plan (4-lens review, hand-traced the truth-table + un_randomize signs + EXP verdicts, clean) →
  subagent-driven build (per-task reviews caught nothing C/I) → final OPUS review **READY TO MERGE: YES**,
  one fast-follow fix landed (bfa6a0c): `PreferenceRating` Field bounds + `magnitude==0 iff tie` validator —
  hardening the rented-Opus boundary ("validate input at system boundaries") before SP2 consumes it. NEXT:
  Sub-project 2 (mine + admit the first spine frame[s] from the Veldra ore, using this harness as the
  auto-screen) — its own brainstorm/spec/plan cycle.

## 2026-06-25 — Frame-mining SP1 (blind-lift harness) plan written + reviewed
- `docs/superpowers/plans/2026-06-25-frame-mining-sp1-blind-lift-harness.md` — 5 **additive** TDD tasks
  (two-axis result types + the derived verdict truth-table; confidentiality + config + scenario scaffolding;
  the 3 model methods + prompts + FakeLiftModel; the `run_lift_test` harness + pure randomize/un_randomize;
  the EXP-reproduction acceptance suite). Every commit green (new module; nothing existing depends on it).
- Self-review caught + fixed an **A/B↔framed `un_randomize` inversion** in two acceptance scripts (EXP-002
  needed `preferred="A"`, EXP-001 `preferred="B"` under `order="AB"`). A 4-lens adversarial plan review
  **hand-traced** the truth-table totality, every un_randomize sign, the three EXP reproductions (EXP-001→
  negative_lift NOT null, EXP-002→lift incl. control-refusal capture, EXP-003→mixed), and the
  confidentiality fix (verified `content/lift/scenarios.yaml` is currently un-ignored; the plan closes it) —
  returned **CLEAN, no blockers/majors**. Folded 3 nits (live-skip `ANTHROPIC_AUTH_TOKEN` guard, a
  consolidated-DEVLOG note, a comment cleanup). NEXT: subagent-driven execution of SP1.

## 2026-06-25 — Frame-mining (spine expansion) design + Sub-project 1 (blind-lift harness) spec
- New thread after P3: expand the founder spine by **mining new counter-intuitive frames** (where the base
  Opus is wrong by default) and validating each against `marginal_lift` via an automated **blind-lift
  screen** + human adjudication, then authoring isolated experiences (the engine-lighting payoff). Mine is
  **source-agnostic** — Veldra's owned record now, public cases (books/blogs/speeches/biographies) later;
  provenance source-typed. Decomposed (one design, 3 sub-projects): (1) the harness; (2) mine+admit; (3)
  author experiences. Spec: `docs/superpowers/specs/2026-06-25-frame-mining-spine-expansion-design.md`,
  §4 pins Sub-project 1 plan-ready.
- Brainstormed the harness + 2 reviews. Forks decided: mine new spine frames (vs subframes/assessment-only);
  hybrid lift test (auto screen + human final call); same-model rater. The harness **automates the kill,
  not the verdict** — `LiftResult` carries verbatim framed/control outputs + the rater's key-difference for
  the human. Two-axis result (distinguishability + signed preference), `lift`/`verdict`/`status` **derived**
  not stored; manipulation check is a **gating precondition** via a separate **primed** checker; refusals
  are **captured as signal** (EXP-002 B2's control refusal IS the lift), not raised.
- A five-lens adversarial review found real fixes (folded in): pydantic wire models (no bare tuple/bool);
  the `{A,B,tie}` cell; a **total** verdict precedence (all-lift→lift, some-lift→mixed, neg→negative_lift,
  neutral, null) + screen `auto_kill` only on {null,negative_lift}; checker false-pass bias named; n=2
  validation vs the min-3 advisory floor; and a **confidentiality blocker** — `content/lift/scenarios.yaml`
  is NOT gitignored and the lessons grep omits it (the SP1 plan must add the scoped ignore + the
  `scenarios.example.yaml` split + extend the grep). The review's headline ("EXP-001 is a null mislabeled
  as negative") was **refuted on verification** (EXP-001 is `negative` — distinguishable + dispreferred);
  lesson **L-15** added. NEXT: user reviews the spec → writing-plans for SP1.

## 2026-06-25 — Project 3 (interactive surface) BUILT — subagent-driven, 8 tasks + final review
- Diagnostic-progression **Project 3 complete** on branch `diagnostic-progression-surface`
  (b45b44d..0c26f32, 9 commits). Suite **168 passed / 3 skipped**, ruff clean, confidential gate empty,
  no Co-Authored-By. Executed subagent-driven (fresh implementer + independent reviewer per task; OPUS
  reviewers on T4/T6/T8 + final; haiku implementers on the transcription tasks T1/T2/T5).
- What shipped: P3 makes the engine interactive. `run_session` now takes an explicit `regime` and, on the
  open_ended path, **proposes from live state at session start** (the queue stops being the authority),
  surfaces a **problem-level** decide menu (the §17.1 gating fix — the learner never sees a frame/drive, so
  the unprompted signal stays uncontaminated; the no-frame guarantee is *structural* — only `ledger_ref` is
  rendered), logs the decision to `selection_log` (now with proposed-vs-chosen columns; open_ended-only —
  cs never logs), and runs an **advisory promote/demote** pass (`crystallization.py`) keyed to the
  exogenous `Experience.ledger_ref ∩ active-ledger` signal (NOT the dead `links_to_experiences`, NOT
  endogenous `breadth`), mutating nothing. `select_next` returns the full ranking with a cross-drive
  runner-up receipt; pure `surface.py` formatters; `propose_open_ended`/`schedule_cs` replace
  `schedule_next`; cs stays queue-driven + byte-stable. Guarded migrations (L-8). The atomic L-10 seam swap
  (T8) landed green in one commit.
- Process: per-task adversarial reviews caught nothing Critical/Important across the build. The final
  whole-branch OPUS review (verified each commit independently green via detached worktrees) returned
  **READY TO MERGE: YES** with one worthwhile minor — a latent KeyError in the promote rationale reachable
  only if `theta_ledger_refs` were tuned to 0 — fixed in 0c26f32 (TDD: RED KeyError → GREEN). The two prior
  adversarial reviews (spec §17, then the plan) had already caught the real design/plan bugs before code
  (the frame-naming leak; the cold-start-picks-decision_under_stakes test-fixture trap; the dead
  `links_to_experiences` predicate). The diagnostic-progression engine is now real through all three
  projects. NEXT: merge to main (user's call on push); the real unlock remains authored content (isolated
  diagnostic experiences + the case library); UI/UX is its own future thread.

## 2026-06-25 — Project 3 implementation plan written (8 TDD tasks) + adversarial review
- `docs/superpowers/plans/2026-06-25-diagnostic-progression-p3-interactive-surface.md` — 8 tasks ordered so
  Tasks 1–7 are additive (suite green at each commit) and Task 8 is the single atomic L-10 seam swap
  (run_session restructure + schedule_next/log_selection removal + six test/seed-site rewrites in one
  commit). Inline self-review passed (spec §17.1–§17.6 coverage, no placeholders, type-thread consistency).
- A 5-lens adversarial review ran against the merged source and **empirically reproduced two blockers**
  (it actually ran `select_next` over the real library):
  - **F1 (blocker):** removing the queue seed means open_ended proposes from cold-start live state, whose
    deterministic winner is `decision_under_stakes`/`choose_the_failure_default_deliberately` — unscripted
    in the test `FakeModel`s → `KeyError`. Fix: every rewritten open_ended test **steers to
    `license_continuity`** via a redirect `decide` fixture (doubles as the redirect-path test).
  - **F2 (blocker):** Task 8 deleted `Store.log_selection` but omitted `tests/test_persistence.py`
    (`test_log_selection_round_trips` calls it) → red commit. Fix: added it to Task 8's edit/stage set.
  - Refinements folded in: F4 crystallization signature aligned to spec order `(state, core, …)` + `config`;
    F5 deterministic per-file import cleanup (notably KEEP `Regime` in cli.py — removing it is a NameError,
    not F401); F6 dry_run dead-helper/assertion removal made explicit; F7 `cli.main` passes
    `regime=open_ended` explicitly; F8 guard the cs empty-queue → open_ended crossover. F3 was downgraded to
    a nit by verification (the test stays green) but tidied anyway.
- New lesson **L-14** (a selection-policy change alters WHICH item is served → re-steer dependent test
  fixtures; an adversarial reviewer that runs code beats one that only reads it). NEXT: choose execution
  mode (subagent-driven vs inline) and implement.

## 2026-06-25 — Project 3 scope pinned (§17) — the interactive surface
- Brainstormed P3 (spec §8/§10.3) to plan-ready and appended **§17** to the diagnostic-progression spec.
  Two user forks: redirect = ranked menu; core promote/demote = advisory + logged, in P3. Then two
  adversarial reviews (an external design review + a 5-lens internal review against the merged code)
  reshaped the draft:
  - **Gating fix (§17.1):** the receipt must NOT name the frame to the learner pre-experience — it
    re-attaches the label and contaminates `reasoned_unprompted`/`evidence_count` (the P1 rev.3 signal).
    Split audiences: learner sees the problem/scenario level only; full frame-level decomposition →
    `selection_log` + post-assessment. (`push.md` already forbids naming the frame at the model layer.)
  - **Explicit `regime` param (§17.2):** removes the need for a nonexistent `queue_peek` AND the cs
    one-way-door lock; open_ended ignores the queue, cs stays queue-driven (behavior byte-stable).
  - **Promote/demote re-keyed (§17.4)** to the experience library's `ledger_ref` back-pointer (exogenous,
    symmetric, populated) — NOT the dead `links_to_experiences` field (vacuous, L-9) nor endogenous
    `breadth`. Signature gains `experiences`. "Decayed" = `retention_due>0` on the built clock (no new
    staleness config); only `theta_ledger_refs` is new.
  - **§16 correction (§17.6):** §16's claim that `_INTERVAL_DAYS` moved to progression.yaml is false vs
    merged code (it stays in `state.py` per the P2 refinement); the hardcoded-interval L-1 debt is named,
    not folded into P3.
  - L-10 atomic task expanded to `test_dry_run.py` + `test_cli.py` + `cli.build_store`/`main` +
    `log_selection` signature. Push-back kept: cs never writes `selection_log` (`receipt=None`), so the §16
    read-caveat lift is total.
- New lessons **L-12** (spec sections inherit stale claims — verify vs merged code) and **L-13**
  (conclusion-agnostic ≠ leak-proof — a frame-naming surface contaminates the unprompted signal; guard with
  a no-`frame_code` check; medium-independent → carries to the future UI).
- Captured the **UI/UX-as-selling-surface** directive as a first-class future thread (own brainstorm +
  market research): the invisible engine must be made FELT; not a chatbox; P3's injectable seams +
  structured types mean a rich UI plugs in later with no backend rework. (Memory: `retnovation-ui-ux-vision`.)
- Spec written; suite still 150/3 (docs-only). NEXT: writing-plans for the P3 implementation plan.

## 2026-06-24 — SESSION CLOSE + HANDOFF
- Three features shipped + merged to main (unpushed, 70 ahead, HEAD c8bb565, 150/3, clean): commitment-frame
  stress probe; diagnostic-progression **Project 1** (learner-model substrate); **Project 2**
  (value-function policy). Live re-dogfood of the escrow scene confirmed the stress probe fires once (not
  silence) end-to-end. **Project 3** (interactive propose/accept/redirect surface + core promote/demote;
  orchestration → propose-from-live-state) is the only remaining piece — no spec yet, start with
  brainstorming. The real unlock is authored content (isolated diagnostic experiences — the content-gap
  predicate flags none exist; + the mined case library).
- Handoff written to `docs/SESSION_HANDOFF.md` (gitignored, local-only — read it first next session, after
  `docs/lessons.md`). lessons.md gained L-9 (synthetic test hid a dead production path), L-10 (return-type
  change → atomic caller update, every commit green), L-11 (checkpointed stepper for interactive
  dogfooding). Memory `retnovation-commitment-frame-gap` updated through P2.

## 2026-06-24 — P2 Final-review fixes — empty-candidates guard (ValueError) + receipt margin/runner-up consistency + type annotations on select_next/_content_gaps + log round-trip coverage extended to JSON columns and margin. 150/3.

## 2026-06-24 — P2 Task 6 — schedule_next dispatches open_ended to the value function (returns (spec, receipt)); run_session logs the receipt + queues the spec; cs byte-stable; placeholder removed; suite green. Project 2 policy complete. 149/3.

## 2026-06-24 — P2 Task 5 — selection_log table + log_selection; queue carries experience_id (guarded migration); 149/3.

## 2026-06-24 — P2 Task 4 — select_open_ended runs the exact experience_id (legacy coverage fallback for the seed); 147/3.

## 2026-06-24 — P2 Task 3 — policy.select_next value function (drives, argmax + constituent-count tie-break, content-gap predicate, receipt); 146/3.

## 2026-06-24 — P2 Task 2 — progression.yaml + load_progression + state.frame_interval_days; 141/3.

## 2026-06-24 — P2 Task 1 — NextExperienceSpec.experience_id + SelectionReceipt; 139/3.

## 2026-06-24 — Project 2 plan written (value-function policy)
- `docs/superpowers/plans/2026-06-24-diagnostic-progression-p2-policy.md` — 6 implementer TDD tasks +
  controller review: (1) types (NextExperienceSpec.experience_id + SelectionReceipt); (2) progression.yaml
  + load_progression + state.frame_interval_days (`_INTERVAL_DAYS` stays in state.py — refines §16 to avoid
  churning the P1 derive_* core path); (3) **policy.select_next** — the pure value function (4 drives over
  the built frame_uncertainty, argmax with the (constituent_count asc, frame_id, problem, experience_id)
  tie-break, static content-gap predicate, the receipt); (4) select_open_ended honors experience_id;
  (5) selection_log + queue experience_id (guarded migration); (6) the single ATOMIC integration task
  (schedule_next → policy tuple-return + run_session logs the receipt + all callers updated at once, so no
  commit ever leaves the suite red). Self-review caught + fixed a red-commit ordering bug (reordered so the
  return-type swap is one task after selector+persistence land). Expected suite 137→~151. **Status: plan
  ready; awaiting execution-mode choice.**

## 2026-06-24 — Project 2 scope rev (external review r2): candidate = (frame, experience)
- External review of §16 (analyzed via receiving-code-review, verified vs content). 4 points, all sound,
  applied: (1) **candidate (frame,problem) → (frame, experience)** [gates the plan] — the penalty (max over
  frames(e)) and the served artifact are per-experience, so a (f,p) with 2 homes (capstone / transfer)
  makes the score ambiguous and the selector could run a different e than the penalty scored (attribution
  break); keying to (frame,experience) keeps per-frame attribution, unambiguous penalty, selector =
  lookup; selection_log stores experience_id. (2) **tie-break (constituent_count asc, frame_id, problem,
  experience_id)** — at cold start all V≈0.5 uniform, so the intro-arc + determinism rest on the tie-break;
  count term makes lowest-load-first true at the FIRST pick (capstone last), experience_id totalizes.
  (3) **content-gap as a static predicate** — "no experience containing f has all its OTHER frames located
  (single-frame = trivial home; located = uncertainty ≤ θ_located)" replaces the vague runtime
  "dominated by penalty"; deterministic + testable; current content has no single-frame experiences so
  cold-start flags every frame (accurate: author isolated experiences). (4) notes: wT>wR is a deliberate
  default (transfer preempts consolidate, decisive on thick content); selection_log is queue-time, not
  live (propose-from-live is P3). §16 amended. **Status: P2 scope plan-ready, awaiting user validation.**

## 2026-06-24 — Live re-dogfood (full pipeline) + Project 2 scoping
- **Live re-dogfood** of the escrow license_continuity scene through the real Opus instructor + the full
  new pipeline (resumable checkpointed stepper /tmp/dogfood/step.py, since background processes don't
  survive turn boundaries). Result: all 3 frames present_reasoned at intake → OLD code converges silent
  (0 pushes); NEW code force-stressed commit_under_the_deadline for exactly ONE stress probe (stress-mode
  push probed the reversal tripwire), student closed it, blind sharper-grader confirmed; converged with a
  non-empty trajectory. Substrate recorded: lead/protect forming (reasoned_unprompted, 1 problem),
  commit forming (closed-under-pressure); `reasoned_unprompted=[lead,protect]` EXCLUDES the probed commit
  (the final-review fix, live); none `strong` (single problem); storage-keyed due +7d; trap_gallery empty;
  state persisted (frames 0→3). One cosmetic finding: commit's last_evidence reads "unmoved" (no delta
  because present_reasoned at intake) though it was closed-under-pressure — label-only, strength correct.
- **Project 2 scoped (value-function policy), §16 added to the spec.** Decided (scoping pass): P2 = the
  value function in scheduler (4 drives: uncertainty/retention_due/transfer_opportunity − cold-start
  max-constituent-uncertainty penalty; weights wU/wR/wT/wL in progression.yaml, defaults 1/1/1.5/0.5) +
  selector honoring (frame,problem) + progression.yaml (moves _INTERVAL_DAYS) + a selection_log (decision
  + logged receipt, the validation surface). Orchestration stays queue-based; the interactive
  propose/accept/redirect surface + core promote/demote stay Project 3. Cold-start edge → content gap (no
  scorer escape hatch). **Status: P2 scope pinned (§16), awaiting user validation before the P2 plan.**

## 2026-06-24 — final-review fix: exclude stress-probed frames from reasoned_unprompted (`and code not in probed`); 137/3.

## 2026-06-24 — P1 Task 5 — persist trap_gallery (delete+reinsert, idempotent); 135/3. Project 1 substrate complete.

## 2026-06-24 — P1 Task 4 — persistence: load_state(now) derives, storage columns + guarded migration, decay_frame deleted; 134/3.

## 2026-06-24 — P1 Task 3b: reasoned_unprompted signal from assess(); estimator reads it; strong reachable in production (rev.3)
- P1 Task 3b — reasoned_unprompted signal from assess(); estimator reads it; strong reachable in production (rev.3); 132/3.

## 2026-06-24 — Diagnostic-progression spec rev. 3: the unprompted signal (mid-impl correction)
- PT3 review surfaced (via a fixture-inconsistency thread, traced to root) that `strong` was UNREACHABLE
  in production: the estimator inferred unprompted from "present_reasoned NOT in frames_closed_under_pressure",
  but the judgment loop co-populates those, and intake-reasoned frames produce no delta — so unprompted_breadth
  could only be populated by a synthetic Assessment the loop never emits (the synthetic test hid it). User chose
  option A (doctrine-faithful): add an additive `reasoned_unprompted` list to Assessment, populated by assess()
  (frames present_reasoned at intake that held), estimator reads it. Spec → rev. 3 (§2 boundary amended, §6
  estimator, §15 added); plan gains Task 3b. Assessment-layer change is additive; loop behavior byte-stable.

## 2026-06-24 — P1 Task 3: estimator writes storage anchored to ledger_ref
- P1 Task 3 — estimator writes evidence/breadth anchored to the problem; strong reachable across 2 problems; 131/3.

## 2026-06-24 — P1 Task 2: storage-keyed staleness clock derivation functions
- P1 Task 2 — derive_strength/derive_due/frame_uncertainty on the storage-keyed clock; 129/3.

## 2026-06-24 — P1 Task 1: FrameStrength storage fields
- P1 Task 1 — FrameStrength storage fields (evidence_count, breadth, unprompted_breadth); 125/3.

## 2026-06-22 — Repo init
- Created the **separate** Retnovation git repo at `~/Documents/Retnovation` (Python, src
  layout, branch `main`). The home dir is an inert git repo (0 tracked files, no remote);
  Retnovation is its own nested repo, and the confidential design docs are gitignored and
  untracked anywhere.
- Ported lean session hygiene from Veldra: `.claude/CLAUDE.md` (Felix protocol, module
  boundaries, doctrine-as-data, commit rules), `docs/lessons.md` (checklists + seeded
  principles L-1..L-6), this DEVLOG.
- Approved stack decisions: Python + SQLite (runtime state/ledger/queue); curated maps +
  curator rubrics as versioned YAML in `content/`; lean hygiene.
- Read doctrine source: Berkeley Operating Guidebook §5 (retention: reversible decay, not
  erasure) and §6 (innovation bridge: the ledger of owned, unlabeled problems).
- Committed the approved harness design as a spec (`docs/superpowers/specs/2026-06-22-harness-skeleton-design.md`).
- Produced the Step-1 implementation plan via writing-plans: 13 right-sized TDD tasks
  (`docs/superpowers/plans/2026-06-22-harness-skeleton.md`), self-reviewed for spec
  coverage, placeholders, and type consistency.
- Next: isolate an execution worktree (using-git-worktrees) and execute Step 1 task-by-task
  under TDD; adversarial review on the core path (judgment loop, orchestration) before done.

## 2026-06-22 — Task 1: Types & enums (TDD PASS)
- Wrote the full `src/retnovation/types.py` module: 6 str Enums, 13 BaseModel classes, 1 dataclass; all match the brief specification exactly.

## 2026-06-22 — Task 2: Content loader (TDD PASS)
- Wrote `src/retnovation/content_loader.py` (load_map, load_rubric, load_experience_meta) with YAML maps and rubrics in `content/`. All 3 tests pass; ruff clean.

## 2026-06-22 — Task 3: Persistence (SQLite Store) (TDD PASS)
- Wrote `src/retnovation/persistence.py` (Store class: load_state, save_state, decay_frame, ledger I/O, queue FIFO); decay_frame enforces no-delete invariant (UPDATE only). All 3 tests pass; ruff clean.

## 2026-06-22 — Task 4: Model protocol + FakeModel (TDD PASS)
- Wrote `src/retnovation/model.py`: Model Protocol (classify_intake, generate_push, classify_response); IntakeClassification and ResponseClassification Pydantic models; FakeModel deterministic test double (pops responses); AnthropicModel stub (raises NotImplementedError). Fixed conftest.py to add src to path. All 11 tests pass; ruff clean.

## 2026-06-22 — Fix editable install (controller infra)
- Task 4 switched packaging to explicit `packages=["retnovation"]`, which broke `import retnovation` outside pytest and would have hidden Task 8 subpackages. Reverted to `[tool.setuptools.packages.find] where=["src"]` and reinstalled with `editable_mode=compat` (plain src-on-path .pth): plain import works, new modules/subpackages import without reinstall. Kept tests/conftest.py as a safety net; documented the compat flag in README.

## 2026-06-22 — Task 5: Aim & Core (onboarding) (TDD PASS)
- Wrote `src/retnovation/aim.py`: aim(posture="founder_ceo") → Aim at MAX_PROCESS_DIAL=10; derive_core(a: Aim, root=None) → Core pulling frames and seed from load_map. Both tests pass; ruff clean.

## 2026-06-22 — Task 6: State update + strength estimator (TDD PASS)
- Wrote `src/retnovation/state.py`: update_state(state, assessment, now, experience_id) → LearnerState with rigor/trajectory-only strength heuristic (strong: reasoned without push; forming: closed under pressure; weak: absent/asserted/regressed); trap_gallery records tripped traps (kind=="trap", response != "closed"). All 3 tests pass; ruff clean.

## 2026-06-22 — Task 7: Scheduler (TDD PASS)
- Wrote `src/retnovation/scheduler.py`: schedule_next(state, ledger, now, regime=open_ended) → NextExperienceSpec with ledger_ref=first ledger entry id; targets weakest frames (all weak, else all forming, else soonest-due strong). Both tests pass; ruff clean.

## 2026-06-22 — Task 8: Judgment loop (assessment subpackage) (TDD PASS)
- Created `src/retnovation/assessment/__init__.py` (empty marker) and `src/retnovation/assessment/judgment_loop.py`: assess(exp, work, model) → Assessment; MAX_PUSHES=6; five stops (converged, bounded_error_violation, budget, plateau; regression in enum but not triggered); sharper = closed AND mechanism_supplied; target order = tripped traps / binding-adjacent / remaining absent. Updated FakeModel.generate_push to return `[push:{kind}]` (no frame_code in output) to enforce the disband rule in tests. All 3 tests pass; ruff clean; 21/21 suite green.

## 2026-06-22 — Strengthen judgment-loop disband assertion (verbatim passthrough)
- Added `assert all(p.text == f"[push:{p.kind}]" for p in a.trajectory)` to `test_cooperative_student_converges`; confirms loop relays generate_push output verbatim without frame_code wrapping. 21/21 suite green; ruff clean.

## 2026-06-22 — Task 9: Assessor dispatch + checkable_scorer stub (TDD PASS)
- Created `src/retnovation/assessment/checkable_scorer.py`: assess raises NotImplementedError (built in step 4). Overwrote `__init__.py` with ASSESSORS registry (open_ended → judgment_loop, cs_technical → checkable_scorer) and get_assessor(regime) dispatch. Both tests pass; ruff clean; 23/23 suite green.

## 2026-06-22 — Task 10: Experience selection (TDD PASS)
- Wrote `src/retnovation/experience.py`: FIXED_EXPERIENCE="veldra_licensing_continuity"; select_experience(core, state, ledger, spec, root) loads the fixed experience from content, overriding ledger_ref if spec is given. Test verifies real load of protect_the_core_lane rubric frame and open_ended regime. 24/24 suite green; ruff clean.

## 2026-06-22 — Task 11: Orchestration (run_session) (TDD PASS)
- Wrote `src/retnovation/orchestration.py`: present_and_collect (interactive default) and run_session wiring all six links (persistence, experience, assessment, state, scheduler, model) into one cycle; present is injectable for tests. 25/25 suite green; ruff clean.

## 2026-06-22 — Task 12: Dry-run acceptance test (TDD PASS)
- Wrote `tests/test_dry_run.py`: end-to-end test proving all six links close without manual stitching; real Store, real FakeModel, fixture student; four acceptance assertions (trajectory, converged, frame_deltas trace to rubric codes, persisted frames, fresh NextExperienceSpec queued). 26/26 suite green; ruff clean.

## 2026-06-22 — Strengthen criterion-3 assertion (frame strength movement)
- Test criterion 3 now asserts `assert any(fs.strength != Strength.weak for fs in reloaded.frames.values())` — proves a frame strength actually moved, not just that frames persisted. Criterion 3 still proves persistence via `assert reloaded.frames`. 26/26 suite green; ruff clean.

## 2026-06-22 — Final-review fixes (experience-id provenance, graceful CLI, cleanups)
- Fix 1: orchestration now passes FIXED_EXPERIENCE (not exp.ledger_ref) as experience_id; test_orchestration asserts FIXED_EXPERIENCE appears in last_evidence. Fix 2: main() wraps run_session in NotImplementedError guard, prints frames_total. Fix 3: state.py emits fstate.value not enum repr in last_evidence. Fix 4: clarifying comments on unreachable strong branch and vacuous _converged. 28/28 suite green; ruff clean.

## 2026-06-22 — Task 13: CLI entrypoint + non-consuming queue_len (TDD PASS)
- Added `queue_len() -> int` non-consuming method to Store (Task 3); build_store checks empty state via queue_len (not consuming queue_pop); main wires aim, core, model, run_session. Tests verify seeding and non-consuming invariant. 28/28 suite green; ruff clean.

## 2026-06-22 — Post-review hygiene
- Reverted an erroneous force-add of the gitignored SDD scratch report (commit 670f6b7, removed). Added lesson L-7; gitignored `.superpowers/` and `.claude-flow/` tooling scratch.

## 2026-06-22 — Step two: live Opus 4.8 model adapter (branch live-model)
- Pushed the repo to GitHub: `LeavesJ/Retnovation` (private). Started step two: wire the
  real `AnthropicModel` so the judgment loop runs against `claude-opus-4-8` instead of the
  scripted `FakeModel`.
- Consulted the `claude-api` reference: model `claude-opus-4-8`, adaptive thinking +
  `effort="high"`, no sampling params, structured output via `messages.parse`.
- Approved design (inline TDD): doctrine prompts as versioned `content/prompts/`; list-of-pairs
  wire schema for strict structured outputs; mock unit tests + gated live smoke (skips with no
  key — none in env). Spec: `docs/superpowers/specs/2026-06-22-live-model-adapter.md`.
- Authored `content/prompts/{intake,push,response}.md` (disband rules + sharper definition) +
  `content_loader.load_prompt`; tests in `tests/test_prompts.py`.
- Implemented `AnthropicModel.{classify_intake,generate_push,classify_response}` against
  `claude-opus-4-8` (adaptive thinking, `effort=high`, no sampling params). Doctrine loaded
  from `content/prompts/`; rubric rendered by the adapter. Intake uses a list-of-pairs wire
  schema (`_IntakeWire`) for strict structured outputs → `IntakeClassification` with
  `absent`/`not_tripped` defaulting. Refusal/empty raises `ModelError`. Client injectable for
  tests (no SDK/network in unit tests).
- Tests: `tests/test_anthropic_model.py` (4, mock client) + gated `tests/test_live_model.py`
  (`@pytest.mark.live`, skips without a key); registered the `live` marker. 34 passed, 1 skipped;
  ruff clean. Next: adversarial core-path review, then merge to main + push.
- Adversarial review (independent subagent) of the Opus 4.8 SDK path + doctrine. Fixes applied:
  - **Critical:** `classify_intake` now ignores hallucinated codes not in the rubric — an invented
    key would corrupt `judgment_loop._converged`/`_select_target`. Test
    `test_classify_intake_ignores_hallucinated_codes` added.
  - Minor: `_render_rubric` omits `(paired trap: None)`; `response.md` wording matches where the
    angle is actually provided; live smoke asserts value types.
  - Dismissed the reviewer's ValidationError-bubble finding: `messages.parse` sets
    `parsed_output=None` on a schema miss (does not raise), already handled by `_require`.
  - 35 passed, 1 skipped; ruff clean.

## 2026-06-22 — Step 2: Veldra ingestion (branch veldra-ingestion)
- Read-only Workflow sweep of Veldra docs (5 parallel readers over blockers/ADRs/BIZLOG/EXECLOG/
  runbooks/vision) surfaced 30 candidate owned-problems; curated to a balanced 14 (7 founder + 7 CS),
  user-vetted: ingest all 14, storage = gitignored `data/`, corpus = pointers + metadata.
- Spec `docs/superpowers/specs/2026-06-22-veldra-ingestion.md`: seed YAML (gitignored `data/seed/`) +
  `corpus` table + `veldra_ingest` (load_seed, idempotent ingest, `retnovation-ingest` console script);
  generalizes the single fixed experience. Confidential ledger/corpus live only in gitignored `data/`;
  tests use synthetic temp seeds.
- Implemented (TDD): `types.CorpusEntry`; persistence `corpus` table + `upsert_corpus`/`load_corpus`/
  `get_corpus` (idempotent UPSERT); `veldra_ingest` (`SeedEntry`, `load_seed` YAML→model,
  idempotent `ingest` upserting ledger+corpus with `ledger_ref=veldra:<slug>`, `main` +
  `retnovation-ingest` console script). `tests/test_ingestion.py` (corpus CRUD+idempotent, load_seed,
  ingest+idempotent) with hermetic temp seeds. 38 passed, 1 skipped; ruff clean.
- Adversarial review (independent subagent): confidentiality clean (no Critical). Fixes applied:
  - **Important:** ledger UPSERT now preserves `links_json` on conflict — a re-ingest no longer
    clobbers downstream-accumulated experience links (the seed is not their authority).
  - **Important:** `load_seed` rejects a non-list YAML with a clear `ValueError`.
  - Minor: `retnovation-ingest` anchors seed + db paths to repo root (no cwd foot-gun); idempotency
    test now asserts field stability; added link-preservation + non-list-seed tests.
  - 40 passed, 1 skipped; ruff clean.
- Next: merge to main + push, then create the confidential 14-entry seed in main `data/seed/` + run ingestion.

## 2026-06-22 — Step 2 COMPLETE + handoff for Step 3
- Veldra ingestion merged (`8f4c5e0`); the confidential 14-entry ledger + corpus is seeded into
  gitignored `data/` (`data/retnovation.db`: 14 ledger + 14 corpus; 7 founder_ceo + 7 cs_technical).
  Run/refresh anytime with `retnovation-ingest`; git tracks none of the seed/db.
- Live Opus 4.8 is wired and verified (a real classify call + a full live `run_session`); key lives in
  gitignored `.env` — **rotate it** (it was echoed into a session transcript).
- **NEXT SESSION -> Step 3: experience generator + the anti-label gate (the moat).** Read first per the
  session-start protocol: `docs/lessons.md` (esp. L-6, the unlabeled-problem test) and the design docs
  the Build Brief points to — Build Brief build-order #3 + "anti label gate",
  `Retnovation_JudgmentLoop_v0.1.md`, `Retnovation_FounderCEO_Design_v0.1.md`,
  `Berkeley_Operating_Guidebook_v2.1.md` (all **local-only, gitignored** — present on this machine, do
  NOT travel with a clone).
- **Where Step 3 starts:** `src/retnovation/experience.py::select_experience` still returns the single
  fixed experience. The 14-entry ledger is seeded in `data/` but not yet driving selection. Step 3:
  generate experiences against the ledger's `weak`/`forming` frames + an owned problem, and gate each so
  it is genuinely unlabeled (recognize-type-and-run-procedure => rejected). `checkable_scorer`
  (cs_technical) is still a `NotImplementedError` stub (Step 4).

## 2026-06-23 — Task 7: Raise MAX_PUSHES 6→8 (COMPLETE)
- Baseline judgment-loop tests: 3 passed (cooperative paths green).
- Change: `src/retnovation/assessment/judgment_loop.py` line 16, `MAX_PUSHES = 6` → `MAX_PUSHES = 8` with
  comment explaining 8-angle depth floor + budget-only semantics.
- Post-change: judgment-loop tests 3 passed, full suite 61 passed + 1 skipped; no regression.
- Linting: ruff format + check all clean.
- Commit: `1cf6f4b` on `step3-experience-generator` with message "feat: raise MAX_PUSHES 6->8 to fit the 8-angle depth floor (budget-only)".
- Self-review: Loop mechanics untouched; cooperative paths (`converged`, `bounded_error_violation`) remain green; budget-only prep for Step 5 deeper interrogation.

## 2026-06-23 — Step 3 COMPLETE: experience generator + anti-label gate (the moat) + Step 4 handoff
- Built on branch `step3-experience-generator` via subagent-driven development (7 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review). Spec:
  `docs/superpowers/specs/2026-06-23-experience-generator-anti-label-gate.md`; plan:
  `docs/superpowers/plans/2026-06-23-experience-generator-anti-label-gate.md`.
- **What shipped:** `select_experience` retired the single fixed experience. It now dispatches by regime
  through a `SELECTORS` registry (mirroring `assessment.ASSESSORS`): `open_ended` →
  `generator.select_open_ended` (deterministic: ranks the authored library by process-frame coverage of
  the scheduler's `target_frames`, tie-break by `experience_id`, binds the candidate's own
  `ledger_ref`); `cs_technical` → a `NotImplementedError` Step-4 stub.
- **The gate** (`generator.anti_label_gate`, `src/retnovation/generator.py`): deterministic, closed
  `GateCode` enum — 5 hard rejects (`recoverable_label`, `pre_named_framework`, `type_hint_scaffold`,
  `softened_ambiguity`, `cosmetic_engagement`) + 1 user depth floor
  (`insufficient_interrogation_depth`, ≥8 angles = frames+traps+binding+4 artifact dims) + 2 quality
  floors (`owned_or_real`, `process_layer_load`, downgrade-not-reject). It verifies anchoring to the
  curated corpus + structure; the curator's `unlabeled` rationale holds the semantic judgment.
  `load_gated_library` fails loud (raises `GateError`) on any hard-reject rubric. Denylists + the depth
  threshold are versioned content under `content/gate/` (L-1).
- **Content:** founder thin seed = 3 abstracted `open_ended` rubrics bound to real founder ledger refs
  (`license_continuity`→`license_fork_risk`, `decision_under_stakes`→`concentrated_market_pricing_power`,
  `proof_before_promise`→`first_customer_proof_loop`, one `bounded_error`); the orphan
  `veldra_licensing_continuity.yaml` (dangling `ledger_ref`) was re-homed, not deleted. Tracked rubrics
  carry only abstracted prompts + codes + a ref id; the confidential corpus stays in gitignored `data/`.
- **Doctrine correction absorbed mid-build (Complete Picture §10, interest tree):** Founder CEO is a
  *posture path* (process core, ledger-driven, `open_ended`); CS is a *domain path* (content core,
  checkable, `cs_technical`) — different types. Selection is pluggable-by-regime so the two never
  collapse. Bobby-Axe = a founder articulation/decision-rep experience (in scope), not executive.
- **MAX_PUSHES 6→8** (budget-only; the loop still pushes frames/traps — deeper dimension interrogation
  is Step 5).
- **Final adversarial review (opus)** confirmed the core-path invariants (gate soundness/no
  false-negative, selection determinism, confidentiality, fail-loud, orphan retirement, loop closes,
  cooperative path unchanged) and caught one real bug the green suite masked: `cli.build_store` seeded
  only 1 of the 3 required corpus refs, so a *fresh* DB raised an uncaught `GateError`. Fixed
  (`51029e3`): `build_store` now seeds every authored `open_ended` ref + a fresh-DB regression test.
- **Verified:** full suite **62 passed, 1 skipped** (only skip = `@pytest.mark.live`, no key); ruff
  clean; fresh-DB `build_store`→`select_experience` returns `license_continuity` with no error.
- **NEXT SESSION -> Step 4: the CS checkable scorer + the cs_technical domain-path selector.** Two clean
  seams are waiting, both `NotImplementedError`: `src/retnovation/assessment/checkable_scorer.py::assess`
  (the checkable regime — answer keys, retrieval strength read off performance) and
  `src/retnovation/generator.py::select_cs_technical` (the domain-path selector — selects by
  *content-concept* coverage, not process-frame coverage). Adding CS is "content + a map + a registered
  selector + the scorer", not an engine rewrite. Read first per the session-start protocol:
  `docs/lessons.md`, then the local-only gitignored corpus — `Retnovation_Complete_Picture.md` §10–§12,
  MVP Scope §4 (the two regimes), and the Build Brief build-order #4.

## 2026-06-23 — Step 4 design spec (branch step4-cs-checkable-scorer)
- Read the session-start docs (lessons.md) + the local-only design corpus (Complete Picture §9–§12,
  §15; MVP Scope §4; Build Brief build-order #4) and mapped both Step-4 seams against every engine
  contract before designing.
- Brainstormed the design with the user; two decisions confirmed: (1) **scoring = deterministic by
  default, model-graded optional per question** (each question carries its own `check_type`; the
  live grader path stays gated like the judgment-loop adapter); (2) **CS content = generic,
  tracked in `content/`** (a non-confidential distributed-systems/consensus concept set; questions
  anchor to `cs_technical` ledger refs for provenance but nothing confidential is tracked).
- Chose **Approach 1 — shared types, regime-dispatched behavior** (over parallel CS types, and over
  a regime-agnostic tagged-union core). One `Experience`/one loop, extended not forked; behavior
  dispatches by regime through registries mirroring `ASSESSORS`/`SELECTORS`. CS drives the existing
  unused `declarative_seed`/`SpacedItem` spaced index (new `concepts` persistence table); the two
  paths (founder process-frames vs CS content-concepts) never collapse (Complete Picture §10).
- Recorded that the Step-3 handoff's "content + map + selector + scorer" under-counted: honoring
  "never collapse the two paths" needs a bounded engine change (a parallel concept-based
  state/scheduling path), not a rewrite.
- Spec committed: `docs/superpowers/specs/2026-06-23-cs-checkable-scorer-design.md` (self-reviewed:
  no placeholders, internally consistent, single-plan scope). Baseline green before any code: 62
  passed, 1 skipped; confidential-docs `git ls-files` check clean.
- Next: user review of the spec, then `writing-plans` → subagent-driven TDD → final adversarial
  review (§9 checklist) → merge.

## 2026-06-23 — Step 4 implementation plan (branch step4-cs-checkable-scorer)
- User approved the spec. Authored the TDD implementation plan:
  `docs/superpowers/plans/2026-06-23-cs-checkable-scorer.md` — 11 right-sized tasks
  (types/invariant → CS content + loaders → model grader → checkable scorer → cs selector →
  concept state + `STATE_UPDATERS` → regime-aware scheduler → `concepts` persistence →
  domain-path onboarding → orchestration/CLI dispatch → CS dry-run acceptance), then a final
  adversarial core-path review against spec §9.
- Plan grounded in the real test suite (read all existing tests first) so every step has complete,
  fixture-accurate code and no placeholders; verified against the project's ruff line-length=100
  and the gated `live` marker. Self-review: full spec coverage, no placeholders, type-consistent
  signatures end to end.
- Next: execute via subagent-driven development (fresh implementer + independent reviewer per task).

## 2026-06-23 — Step 4 Task 1: Checkable types + Experience regime/payload invariant (TDD PASS)
Task 1 — checkable types (`CheckType`, `CheckableQuestion/Set`, `ConceptResult`, `CheckableAssessment`, `CheckableGrade`); `Experience.rubric` optional + regime/payload validator; `Aim`/`Core` content_core widened.

## 2026-06-23 — Step 4 Task 2: CS content + content-loader functions (TDD PASS)
- Authored all CS content files: `content/maps/cs_systems.yaml` (domain path, 6 content-core
  concepts), `content/cadence/spacing.yaml` (initial 1d, ease 2.0, min 1d),
  `content/prompts/grade.md` (strict grader doctrine), `content/checkables/consensus_safety_liveness.yaml`
  (3 deterministic questions), `content/checkables/replication_models.yaml` (2 deterministic + 1
  model-graded question).
- Additive edit to `content/maps/founder_ceo.yaml`: prepended `path_type: posture`; existing
  `process_frames` / `declarative_seed` keys unchanged.
- CS content lives in `content/checkables/` (separate from `content/rubrics/`) so
  `load_library` / anti-label gate never pick it up.
- Updated `src/retnovation/content_loader.py`: expanded import to include checkable types
  (`CheckableQuestion`, `CheckableSet`); appended `load_path_type`, `load_content_map`,
  `load_spacing`, `load_checkable_experience`, `load_checkable_library`.
- TDD: wrote 3 failing tests first (RED — ImportError); implemented loaders; all 3 turned GREEN.
- Full suite: 67 passed, 1 skipped; ruff format + check clean; confidentiality gate CLEAN.

## 2026-06-23 — Step 4 Task 4: Checkable scorer (cs_technical regime) (TDD PASS)
- Replaced the `NotImplementedError` stub in `src/retnovation/assessment/checkable_scorer.py`
  with the real scorer: `_normalize` (lowercase, strip, collapse whitespace, strip punctuation),
  `_render` (question prompt + choices if any), `score_question` (deterministic: normalized
  match against `answer_key`, model-free; model_graded: `model.grade_answer(...).correct`),
  `assess` (iterates `exp.checkable.questions`, collects answers via `work.respond`, returns
  `CheckableAssessment`). Empty `answer_key` on deterministic raises `ValueError` (fail loud).
- TDD: wrote `tests/test_checkable_scorer.py` first (4 tests); confirmed RED (all 4 failed
  with `NotImplementedError`); implemented; all 4 GREEN.
- Updated `tests/test_dispatch.py`: replaced the old stub-era `NotImplementedError` expectation
  with a real-registration assertion (`checkable_scorer.assess is get_assessor(Regime.cs_technical)`).
- Full suite: 74 passed, 2 skipped (was 70 + 2 baseline; net +4 scorer tests); ruff clean.

## 2026-06-23 — Step 4 Task 5: CS domain-path selector `select_cs_technical` (TDD PASS)
- Replaced the `NotImplementedError` stub in `src/retnovation/generator.py::select_cs_technical`
  with the real CS selector: `_concept_coverage(exp, targets)` counts how many target codes appear
  in `{q.concept for q in exp.checkable.questions}`; `select_cs_technical` loads the checkable
  library via `load_checkable_library` (NEVER `load_gated_library` / `load_library` — the anti-label
  gate must never touch CS experiences), raises `GateError` if empty, resolves targets from
  `spec.target_frames` → `core.content_core` → `[]` (cold start), ranks by
  `(-coverage, experience_id)`, returns `ranked[0]`.
- Added `load_checkable_library` to the import block in `generator.py`.
- TDD: replaced `test_select_cs_technical_is_a_step4_stub` with two new tests (RED first — both
  failed `NotImplementedError`); replaced `test_select_experience_cs_technical_is_stubbed` in
  `test_experience.py` with `test_select_experience_dispatches_cs_technical`; confirmed RED (3
  failures); implemented; all 3 GREEN.
- Removed now-unused `import pytest` from `tests/test_experience.py` (ruff F401).
- Full suite: 75 passed, 2 skipped (baseline was 74 + 2); ruff format + check clean.

## 2026-06-23 — Step 4 Task 6: Concept state update + `STATE_UPDATERS` registry (TDD PASS)
- Added `update_state_checkable(state, assessment, now, experience_id, spacing=None) -> LearnerState`
  to `src/retnovation/state.py`. Aggregates `CheckableAssessment.results` by concept; recalled iff
  ALL questions correct (strict `all(corrects)`); recall multiplies interval by `ease_factor`
  (floored at `min_interval_days`); miss resets to `min_interval_days` — the `SpacedItem` is
  UPDATED, never deleted (L-3 reversible decay). Writes ONLY to `state.declarative_seed`; never
  touches `state.frames` (NEVER-COLLAPSE invariant, Complete Picture §10).
- Added `STATE_UPDATERS: dict[Regime, Callable]` = `{open_ended: update_state, cs_technical:
  update_state_checkable}`, mirroring `ASSESSORS`/`SELECTORS` registries for orchestration dispatch
  (Task 10).
- Updated imports in `state.py`: `Callable`, `timedelta`, `load_spacing`, `CheckableAssessment`,
  `Regime`, `SpacedItem`.
- TDD: 3 failing tests appended to `tests/test_state.py` first (RED — ImportError on
  `update_state_checkable`/`STATE_UPDATERS`); implemented; all 3 GREEN. Original 3 founder tests
  unaffected.
- Full suite: 78 passed, 2 skipped (was 75+2); ruff format + check clean.

## 2026-06-23 — Step 4 Task 7: Regime-aware scheduler (TDD PASS)
- Made `schedule_next` regime-aware: inserted a `cs_technical` branch before the existing frame
  logic. For `cs_technical`, reads `state.declarative_seed` (`SpacedItem`); returns all
  due concepts (`due <= now`, ordered by `due`) when any exist; otherwise the single
  soonest-due concept; puts codes in `NextExperienceSpec.target_frames` with `regime=cs_technical`.
- `open_ended` branch byte-identical — no logic touched.
- TDD: 2 failing tests appended first (RED — both returned `[]`); implemented cs branch;
  both GREEN. Existing 2 open_ended tests unchanged and still pass.
- ruff: 1 file reformatted (dict-literal style in test); check clean.
- Full suite: 80 passed, 2 skipped (baseline was 78+2; net +2).

## 2026-06-23 — Step 4 Task 3: Model grader (`grade_answer`) (TDD PASS)
- Added `grade_answer(exp, question, answer) -> CheckableGrade` to the `Model` Protocol,
  `FakeModel`, and `AnthropicModel`; updated the types import in `model.py`.
- `FakeModel.__init__` gains an optional `grades: dict[str, list[CheckableGrade]] | None = None`
  third param (pops by `question_id`); existing callers with 2 positional args unchanged.
- `AnthropicModel.grade_answer`: builds system prompt from `load_prompt("grade")` + question
  prompt/answer_key/criteria, sends student answer as user message, parses via `messages.parse`
  with `output_format=CheckableGrade`; refusal/empty raises `ModelError` via `_require` (mirrors
  `classify_response`).
- TDD: 3 failing tests first (RED — unexpected kwarg + AttributeError); implemented; all 3 GREEN.
- Full suite: 70 passed, 2 skipped (added 3 tests; live smoke stays skipped without key); ruff clean.

## 2026-06-23 — Step 4 Task 8: Persistence — `concepts` table + `declarative_seed` I/O (TDD PASS)
- Added `SpacedItem` to the types import in `src/retnovation/persistence.py`.
- Appended `CREATE TABLE IF NOT EXISTS concepts (concept TEXT PRIMARY KEY, due TEXT NOT NULL,
  interval_days INTEGER NOT NULL)` to `_SCHEMA` — fresh DB supports the CS path with no migration
  (L-8: fresh-DB end-to-end; Spec §5.8).
- Extended `load_state`: after the frames loop, reads every `concepts` row and populates
  `st.declarative_seed[concept]` as a `SpacedItem`.
- Extended `save_state`: after the frames loop, UPSERTs every `(concept, si)` in
  `state.declarative_seed` via `INSERT ... ON CONFLICT(concept) DO UPDATE SET ...` — NO DELETE
  (L-3: reversible decay; a demoted concept keeps its row, interval shrinks).
- Frames I/O and all existing tables (frames, ledger, queue, corpus) are unchanged.
- TDD: `test_concepts_roundtrip_and_never_deleted` appended first; ran RED (KeyError —
  `declarative_seed` not persisted); implemented; GREEN in 0.14 s.
- Full suite: 81 passed, 2 skipped (was 80+2; net +1); ruff format + check clean.

## 2026-06-23 — Step 4 Task 10: Orchestration + CLI regime dispatch (COMPLETE)
- Updated `src/retnovation/orchestration.py`: swapped `from .state import update_state` for
  `from .state import STATE_UPDATERS`; added `CheckableAssessment, Regime` to the types import.
  `present_and_collect` is now regime-aware — `cs_technical` skips the opening prompt (returns
  `Work(opening="", respond=respond)`); `open_ended` path byte-identical. `run_session` dispatches
  the state update via `STATE_UPDATERS[exp.regime]`; return type widens to
  `tuple[LearnerState, Assessment | CheckableAssessment]`.
- Updated `src/retnovation/cli.py`: replaced the single `print(f"stop_reason=...")` line with a
  regime-aware `isinstance(assessment, CheckableAssessment)` branch — CS prints
  `concepts_scored=/recalled=`; founder prints `stop_reason=/frames_total=`.
- Verification: no new tests this task; verification gate = founder-regression-stays-green + ruff
  + full suite. Command:
  `pytest tests/test_dispatch.py tests/test_orchestration.py tests/test_cli.py tests/test_dry_run.py -q`
  → 6 passed. `ruff format . && ruff check .` → clean. Full suite `pytest -q` → **83 passed,
  2 skipped** (baseline unchanged).
- Files changed: `src/retnovation/orchestration.py`, `src/retnovation/cli.py`, `docs/DEVLOG.md`.
- `tests/test_dispatch.py` NOT touched (Task 4 already provides the stronger assertion).

## 2026-06-23 — Step 4 Task 11: CS dry-run acceptance test (TDD PASS)
- Created `tests/test_cs_dry_run.py` (verbatim from brief): builds a real `Store`, queues a
  `cs_technical` `NextExperienceSpec` targeting `safety_vs_liveness`, `idempotency_under_retry`,
  `quorum_intersection`; derives a CS `Core` via `aim("cs_systems")`; runs `run_session` with a
  fixture that answers each question correctly via `answer_key[0]` (fully deterministic, model-free).
- Three acceptance assertions: (1) scorer ran every question, all correct; (2) concept spaced-index
  moved + persisted across a `Store` reopen; (3) a fresh `cs_technical` next experience is queued.
- Result: 1 passed in 0.15s. Full suite: **84 passed, 2 skipped** (was 83+2; net +1);
  ruff format + check clean; confidentiality gate CLEAN.
- Files changed: `tests/test_cs_dry_run.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Step 4 Task 9: Domain-path onboarding (`aim` / `derive_core`) (TDD PASS)
- Added `MIN_PROCESS_DIAL = 0` constant to `src/retnovation/aim.py` (CS — content axis maxed,
  process near-empty per Complete Picture §10).
- Made `aim(posture, root=None)` path-type-aware: calls `load_path_type(posture, root=root)`;
  sets `dial = MAX_PROCESS_DIAL` for `path_type == "posture"` (founder), `MIN_PROCESS_DIAL`
  otherwise (domain / CS). Signature now accepts `root` parameter (mirrors `derive_core`).
- Made `derive_core(a, root=None)` branch by path type: for `domain` maps loads
  `load_content_map` → `concepts`; returns `Core(process_frames=[], declarative_seed=concepts,
  content_core=concepts)` — frames empty, seed = content concepts; for `posture` maps the
  original `load_map` path is byte-identical (frames + seed, `content_core=None`).
- Founder posture path (`aim()` / `derive_core(aim())`) fully unchanged — existing two tests
  still pass.
- TDD (RED then GREEN): appended 2 CS domain-path tests to `tests/test_aim.py` first;
  ran RED (`ImportError: cannot import name 'MIN_PROCESS_DIAL'` + `KeyError: 'process_frames'`);
  implemented; all 4 aim tests GREEN.
- Full suite: 83 passed, 2 skipped (was 81+2; net +2 new CS tests); ruff format + check clean.

## 2026-06-23 — Step 4 final-review fixes (MERGE-CLEAN verdict, 3 minor closures)

Whole-branch adversarial review returned MERGE CLEAN with one Minor finding and two
guard-coverage gaps (L-8: cover fail-loud guards). Applied exactly three changes:

1. **Scheduler tie-determinism** (`src/retnovation/scheduler.py`): Added concept-code
   tiebreak to both sort keys in the `cs_technical` branch of `schedule_next`, matching
   the deliberate `sorted()` determinism of the `open_ended` branch. Due-list key:
   `(items[c].due, c)`; soonest-due fallback key: `(kv[1].due, kv[0])`.
   New test: `test_cs_technical_due_ties_break_by_concept_code` asserts
   `["alpha", "zebra"]` when both have identical due timestamps.

2. **Guard regression test — `checkable is None`** (`tests/test_checkable_scorer.py`):
   `test_assess_raises_when_checkable_is_none` uses `Experience.model_construct` to
   bypass the regime validator and constructs a `cs_technical` experience with
   `checkable=None`, then asserts the scorer's defensive `ValueError` guard fires.

3. **Guard regression test — empty checkable library** (`tests/test_generator.py`):
   `test_select_cs_technical_raises_on_empty_library` creates an empty `checkables/`
   directory in a `tmp_path` and asserts `select_cs_technical` raises `GateError`.

Results: 87 passed, 2 skipped (was 84+2; +3 new tests); ruff format + check clean.

## 2026-06-23 — Step 4 COMPLETE: CS checkable scorer + cs_technical regime + Step 5 handoff
- Built on branch `step4-cs-checkable-scorer` via subagent-driven development (11 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review on opus).
  Spec: `docs/superpowers/specs/2026-06-23-cs-checkable-scorer-design.md`; plan:
  `docs/superpowers/plans/2026-06-23-cs-checkable-scorer.md`. Approach 1 (shared types,
  regime-dispatched behavior) — one `Experience`/one loop, extended not forked.
- **What shipped — the second assessment regime runs through the same six-link plumbing:**
  - `assessment/checkable_scorer.py::assess` retired its stub: iterates `exp.checkable.questions`,
    collects each answer over the SAME `Work` channel the judgment loop uses, scores correctness, and
    returns a `CheckableAssessment`. **Deterministic by default** (normalized answer-key match, NO model
    call), **optional `model_graded` per question** (Opus grader via `Model.grade_answer`, `_require`-guarded
    so refusal/empty raises — no silent leniency; gated live smoke).
  - `generator.py::select_cs_technical` — the domain-path selector: ranks the checkable library by
    **content-concept coverage** of the scheduler's target codes (cold-start fallback to `core.content_core`),
    tie-break by `experience_id`. CS is **ungated** (the anti-label gate is the open_ended moat; CS is the
    labeled/checkable contrast) — it loads from `content/checkables/`, which `load_library`/the gate never touch.
  - CS drives the previously-unused `declarative_seed`/`SpacedItem` spaced index via
    `state.update_state_checkable` (recall grows the interval by `ease_factor`, a miss resets to the floor —
    reversible demotion, never deletion, L-3); new `concepts` SQLite table persists it; regime-aware
    `schedule_next` targets due concepts. Dispatch is table-driven (`STATE_UPDATERS` mirroring
    `ASSESSORS`/`SELECTORS`). **The two paths never collapse**: founder process-frames stay in `frames`,
    CS content-concepts stay in `declarative_seed`/`concepts`.
  - Domain-path onboarding: `aim("cs_systems")` → `MIN_PROCESS_DIAL`; `derive_core` loads the CS content
    core (Complete Picture §10 — domain path maxes the content axis). Founder posture path byte-stable.
  - `Experience` gained a regime/payload invariant (open_ended ⇒ rubric; cs_technical ⇒ checkable).
- **Content (generic, non-confidential, tracked):** `content/maps/cs_systems.yaml` (a distributed-systems /
  consensus content core), two `content/checkables/*.yaml` experiences (MCQ + short-answer + one model-graded),
  `content/prompts/grade.md`, `content/cadence/spacing.yaml`. Nothing confidential tracked (`git ls-files` clean).
- **Final adversarial review (opus): MERGE CLEAN** — all ten §9 invariants verified with live repros
  (fresh-DB CS session closes the loop end-to-end; never-collapse holds across a 5-session run; confidentiality
  `git ls-files` empty; founder path byte-stable). One Minor (scheduler tie-order determinism) fixed +
  two fail-loud-guard regression tests added (L-8).
- **Verified:** full suite **87 passed, 2 skipped** (only skips = the two `@pytest.mark.live` smokes, no key);
  ruff format + check clean; confidentiality + `data/`-untracked clean; `test_cs_dry_run.py` closes the six
  links for `cs_technical`.
- **NEXT SESSION -> Step 5 (the last build-order item): harden the judgment loop.** Exercise the stops that
  have never fired — `regression` and `plateau` (only the cooperative `converged`/`bounded_error_violation`
  paths are proven; the model won't play a caving/safety-inverting student, so these need authored fixtures or
  the dogfood) — and add the independent-grader pass for the "sharper" calls. Read first per the session-start
  protocol: `docs/lessons.md`, then the local-only gitignored corpus — `Retnovation_JudgmentLoop_v0.1.md`,
  `Retnovation_Complete_Picture.md` §12 (the judgment loop) + §13 (the empirical spine), and Build Brief
  build-order #5.

## 2026-06-23 — Step 5 design spec (branch step5-harden-judgment-loop)
- Resumed under the user's standing delegation (do Step 5, then continue autonomously, "quadruple-check /
  be mindful", user away). Read the session-start docs + the local-only Step-5 corpus
  (`Retnovation_JudgmentLoop_v0.1.md` §2/§5/§6/Decisions, Build Brief #5) and the current
  `assessment/judgment_loop.py` before designing.
- **Diagnosis:** `regression` is in the `StopReason` enum but the loop has no branch for a `"regressed"`
  outcome (silently treated as `"unchanged"`) → never fires. `plateau` fires on two consecutive non-moves
  but the loop re-hammers one target, so it means "stuck on one angle", not the doctrine's "two *distinct*
  targets moved nothing" (§2/§6). No independent grader exists — the instructor scores sharper in-line,
  the over-credit confound §6 flagged.
- **Design (Approach: extend the open_ended assessor; cs_technical untouched):** (1) regression stops on the
  first genuine backslide (lower the frame one level + record delta); (2) plateau becomes distinct-target via
  an `exhausted` set that rotates `_select_target` to a fresh angle, firing on two distinct consecutive
  non-moves (or no fresh angle left while not converged); (3) a separate **blind skeptical grader**
  (`assessment/sharper_grader.py::audit_sharper` + `Model.grade_sharper` + `content/prompts/grade_sharper.md`)
  re-audits each closed frame and gates sharper by 2-vote — a disputed call is dropped from
  `frames_closed_under_pressure` AND its `FrameDelta` reverted (so `update_state` scores it weak, not strong).
  `Push` gains the raw `response` so the grader re-judges independently; `judgment_loop.assess` runs the loop
  then the audit; `run_session`/`STATE_UPDATERS`/cs_technical all unchanged.
- Resolved all design forks autonomously (recorded in spec §4/§11): regression-on-first-backslide,
  distinct-target plateau via rotation, separate-pass 2-vote grader, `FakeModel` grader agrees-by-default
  (disputes scripted) so existing open_ended tests stay green untouched.
- Spec committed: `docs/superpowers/specs/2026-06-23-harden-judgment-loop-design.md` (self-reviewed: no
  placeholders, internally consistent, single-plan scope). Baseline before any code: 87 passed, 2 skipped;
  confidentiality `git ls-files` clean.
- Next: `writing-plans` → subagent-driven TDD → final adversarial review (§9) → merge.

## 2026-06-23 — Step 5 implementation plan (branch step5-harden-judgment-loop)
- Authored the TDD plan `docs/superpowers/plans/2026-06-23-harden-judgment-loop.md` — 6 right-sized
  tasks then a final opus adversarial review: (1) types (`Push.response`, `SharperVerdict`,
  `SharperAuditItem`, `Assessment.sharper_audit`) → (2) `Model.grade_sharper` + blind skeptical
  `content/prompts/grade_sharper.md` → (3) `assessment/sharper_grader.py::audit_sharper` (2-vote
  demote+revert) → (4) regression stop + capture raw responses → (5) distinct-target plateau via
  angle rotation → (6) wire the audit into `assess` + strengthen/extend the loop tests.
- Plan grounded in the real suite (read judgment_loop + all touched tests first); every step has
  complete, fixture-accurate code; quadruple-checked the cooperative/bounded/budget paths survive
  rotation and the audit-wiring no-ops on no-closed-frame assessments. Self-review: full spec
  coverage, no placeholders, type-consistent signatures end to end.
- Next: execute via subagent-driven development (fresh implementer + independent reviewer per task),
  then the final adversarial review.

## 2026-06-23 — Step 5 Task 1: Types — Push.response + sharper-audit types + Assessment.sharper_audit (TDD PASS)
Task 1 — added `Push.response` (default ""), `SharperVerdict`, `SharperAuditItem`, `Assessment.sharper_audit` (default []); 89 passed, 2 skipped; ruff clean.

## 2026-06-23 — Step 5 Task 2: Model grader — `grade_sharper` + blind doctrine prompt (TDD PASS)
- Created `content/prompts/grade_sharper.md`: skeptical auditor doctrine — assent≠sharper,
  length≠sharper, conclusion-agnostic, default to not-sharper; identifies sharper by mechanism/reason
  cited in the student's own words.
- Added `Model.grade_sharper(self, exp, kind, code, push, response) -> SharperVerdict` to the
  Protocol (blind: no instructor-outcome parameter).
- Extended `FakeModel.__init__` with optional `sharper_verdicts: dict[str, list[SharperVerdict]] | None = None`
  as the last param (existing callers unchanged). `FakeModel.grade_sharper` pops a scripted verdict
  for `code` if present, else returns `SharperVerdict(sharper=True, reason="(default agree)")` so all
  existing open_ended tests stay green without modification.
- Implemented `AnthropicModel.grade_sharper`: `messages.parse` with `output_format=SharperVerdict`,
  system = `load_prompt("grade_sharper")` + target detail via `_target_detail`, user = push + student
  reply; refusal/empty raises `ModelError` via `_require` (mirrors `classify_response`).
- Added `SharperVerdict` to the `model.py` types import.
- TDD evidence: 3 tests RED before implementation (`AttributeError: 'AnthropicModel'/'FakeModel'
  object has no attribute 'grade_sharper'`); GREEN after; live smoke (`test_live_grade_sharper_smoke`)
  gated with `@pytest.mark.skipif(not _HAS_KEY, ...)` — adds 3rd skip.
- Full suite: **92 passed, 3 skipped** (was 89+2; net +3 tests, +1 skip); ruff format + check clean.

## 2026-06-23 — Step 5 Task 4: Regression stop + populate `Push.response` in the loop (TDD PASS)
- Added `_LOWER` dict and `_lower(state) -> FrameState` helper after `MAX_PUSHES` in
  `src/retnovation/assessment/judgment_loop.py`: lowers `present_reasoned → present_asserted →
  absent → absent` (floor clamp).
- Inserted a `rc.outcome == "regressed"` branch immediately AFTER the `bounded_error hard_wrong`
  block and BEFORE the `rc.outcome == "closed"` block (bounded hard-wrong still pre-empts).
  On regression: lowers the frame one level, appends a `FrameDelta` if the level changed,
  appends a `Push(response=response)`, sets `stop_reason = StopReason.regression`, breaks.
  Doctrine: "the student is getting worse and more pushing harms" (§5.4).
- Added `response=response` to the bounded-error `hard_wrong` `Push` and the normal end-of-loop
  `Push` so every push carries the raw student reply (required by the Task 6 independent grader).
- TDD evidence: test `test_regression_stops_when_student_backslides` written first (RED — loop
  treated `"regressed"` as unchanged, re-hammered the target until `IndexError: pop from empty
  list`); implemented; GREEN in 0.13 s.
- Cooperative (`converged`), bounded-error, and budget/plateau paths all still pass (4/4
  judgment_loop tests green).
- Full suite: **95 passed, 3 skipped** (was 94+3; net +1 new test); ruff format + check clean.

## 2026-06-23 — Step 5 Task 5: Distinct-target plateau via angle rotation (TDD PASS)
- Replaced the single-target `recent_moved: list[bool]` plateau with a rotation-aware mechanism.
- `_select_target` gains an `exhausted: set[str]` parameter; skips any code already in `exhausted`
  so the loop rotates to a fresh angle on each non-moving push.
- In `assess`: `recent_moved` replaced by `exhausted: set[str]` + `recent: list[tuple[str, bool]]`
  (code, moved) for the last pushes.
- Plateau check updated: fires when `recent[-1][0] != recent[-2][0]` and both moves are False —
  i.e., two DISTINCT targets both moved nothing, matching JudgmentLoop §2/§6 doctrine.
- `_select_target(...)` call updated to pass `exhausted`; the `target is None` branch now maps to
  `StopReason.plateau` (out of distinct angles while not converged, not converged).
- Move/no-move handling: `else: exhausted.add(code)` added; `recent.append((code, moved))`
  replaces the old `recent_moved.append(moved)`.
- TDD evidence: `test_plateau_stops_on_two_distinct_unmoved_targets` written first (RED —
  `IndexError: pop from empty list` because loop re-hammered the first target); implemented;
  GREEN. All 5 judgment_loop tests pass.
- Regression checks: `test_cooperative_student_converges` (every push closes → moved=True → no
  rotation → still converges), `test_bounded_error_violation_stops_immediately`,
  `test_budget_caps_unproductive_loop` (stops at plateau, still in asserted set),
  `test_regression_stops_when_student_backslides` (Task 4) all GREEN.
- Full suite: **96 passed, 3 skipped** (was 95+3; net +1 new test); ruff format + check clean.

## 2026-06-23 — Step 5 Task 3: Independent blind sharper grader `audit_sharper` (TDD PASS)
- Created `src/retnovation/assessment/sharper_grader.py`: `audit_sharper(exp, assessment, model) ->
  Assessment` — a pure function that re-grades every closing push for frames in
  `frames_closed_under_pressure` (one audit per code, `kind == "frame"`,
  `response_classification == "closed"`) using `model.grade_sharper` (the blind Task-2 grader).
- A DISPUTED verdict (`verdict.sharper is False`) removes the code from
  `frames_closed_under_pressure` AND removes its `FrameDelta` from `frame_deltas`, so a subsequent
  `update_state` scores the frame `Strength.weak`, not strong — the misclassification trap is
  closed. Records the full `SharperAuditItem` trail on `Assessment.sharper_audit`.
- Returns via `assessment.model_copy(update={...})` — input Assessment is never mutated.
- TDD evidence: tests written first (`tests/test_sharper_grader.py`); RED
  (`ModuleNotFoundError: No module named 'retnovation.assessment.sharper_grader'`); implemented;
  both GREEN in 0.10s. The dispute test asserts the end-to-end `update_state` → `Strength.weak`
  chain, guarding the strong-misclassification trap.
- Full suite: **94 passed, 3 skipped** (was 92+3; net +2 new tests); ruff format + check clean.

## 2026-06-23 — Step 5 Task 6: Wire `audit_sharper` into `assess` + strengthen/extend loop tests (TDD PASS)
- Added `from .sharper_grader import audit_sharper` import to
  `src/retnovation/assessment/judgment_loop.py`.
- Replaced the final `return Assessment(...)` with: build the instructor `assessment = Assessment(...)`,
  then `return audit_sharper(exp, assessment, model)` — so every call to `assess` now runs the
  independent blind grader pass before the Assessment reaches `update_state`.
- `run_session`, `STATE_UPDATERS`, the `cs_technical` scorer, and all other modules are unchanged.
  The `FakeModel.grade_sharper` default-agree behaviour preserves all cooperative/dry-run/CS paths.
- **Strengthened** `test_cooperative_student_converges`: added 2 assertions at the end verifying
  that the grader ran and confirmed both sharper calls (`len(a.sharper_audit) == 2`,
  `all(item.confirmed for item in a.sharper_audit)`).
- **Added** `test_grader_dispute_demotes_a_sharper_call_in_the_full_loop`: instructor closes both
  frames; the scripted `FakeModel` disputes `protect_the_core_lane`; asserts demoted frame is absent
  from `frames_closed_under_pressure` and the audit item has `confirmed=False`.
- TDD evidence: tests written first; RED — `assert 0 == 2` (sharper_audit empty, audit not wired)
  and `AssertionError` on dispute demotion. Implemented; GREEN in 0.14 s.
- Regression: `test_dry_run`, `test_orchestration`, `test_state`, `test_cs_dry_run` all pass.
- Full suite: **97 passed, 3 skipped** (was 96+3; net +1 new test, +2 assertions); ruff format + check clean.
- Files changed: `src/retnovation/assessment/judgment_loop.py`, `tests/test_judgment_loop.py`,
  `docs/DEVLOG.md`.

## 2026-06-23 — Step 5 COMPLETE: judgment loop hardened + BUILD ORDER FINISHED
- Built on branch `step5-harden-judgment-loop` via subagent-driven development (6 TDD tasks, fresh
  implementer + independent task reviewer each, then a final whole-branch adversarial review on opus).
  Spec: `docs/superpowers/specs/2026-06-23-harden-judgment-loop-design.md`; plan:
  `docs/superpowers/plans/2026-06-23-harden-judgment-loop.md`. Done autonomously under the user's
  standing delegation (user away; "quadruple-check / be mindful").
- **What shipped (open_ended assessor only; cs_technical + run_session untouched):**
  - **Regression stop** now fires on a genuine `"regressed"` outcome (previously in the enum but
    never triggered): the targeted frame is lowered one level (`_lower`), the backslide delta is
    recorded, and the loop stops — "more pushing harms". It ends NOT present_reasoned → scored weak.
  - **Distinct-target plateau**: `_select_target` gained an `exhausted` set and rotates to a fresh
    angle after a non-moving push; plateau fires on two distinct consecutive non-moves (or when no
    fresh angle remains while not converged), matching JudgmentLoop §2/§6. The loop provably
    terminates (convergence progress / exhausted-set shrinkage / `MAX_PUSHES` backstop). Cooperative
    path never rotates; bounded hard-wrong still pre-empts.
  - **Independent blind grader**: `assessment/sharper_grader.py::audit_sharper` re-judges each closed
    frame via a separate skeptical `Model.grade_sharper` (`content/prompts/grade_sharper.md`;
    blind — no instructor outcome in the prompt; assent/length ≠ sharper; conclusion-agnostic;
    `_require`-guarded). A disputed sharper is dropped from `frames_closed_under_pressure` AND its
    delta reverted, so `update_state` scores it **weak**, not strong (the strong-misclassification
    trap is genuinely closed). `Push` now carries the raw `response`; `assess` runs the loop then the
    audit. The grader gates "sharper" by a 2-vote (instructor + blind grader must agree).
- **Final adversarial review (opus): MERGE CLEAN** — all ten §9 invariants verified with live repros
  (loop termination; plateau + regression repros; disputed-sharper → `update_state` weak end-to-end
  incl. fresh-DB persistence; bounded hard-wrong pre-empts a simultaneous regression; grader blind;
  cooperative/CS/dry-run byte-stable). Two Minors, both DEFER (no live trigger): `audit_sharper`
  requires a "closed" push (unreachable from the loop); a disputed frame persists evidence
  `"unmoved"` (observability nit). Not fixed (mindful: no speculative churn for unreachable paths).
- **Verified:** full suite **97 passed, 3 skipped** (only skips = the three `@pytest.mark.live`
  smokes, no key); ruff format + check clean; confidentiality + `data/`-untracked clean.
- **BUILD ORDER COMPLETE.** All 5 locked build-order steps are done (harness → Veldra ingestion →
  experience generator + anti-label gate → CS checkable scorer → harden the judgment loop). The MVP
  harness is feature-complete.
- **NO "Step 6" in the locked build order.** What remains is post-MVP and needs the user's direction
  (it was not autonomously started, per "be mindful"): (a) **dogfood** — run it as user-zero over a
  semester to exercise the resistant paths live (the model over-refuses to role-play a caving student,
  so regression/plateau/bounded are proven only by authored fixtures; real users are the validation);
  (b) the deferred items, each its own spec → plan → build (MVP Scope §5): **blend** (needs two mature
  stateful projects), the **crystallization mirror** (needs an accreted ledger), richer experience
  types, the **business-executive** domain expansion (first per the locked decision), multi-user infra;
  (c) a **usable surface** for the dogfood (today it is a CLI + `pytest`). See MVP Scope §7 success
  criteria for what the harness now satisfies vs. what only real use can prove.

## 2026-06-23 — First founder dogfood (live Opus 4.8) + immersive-scenes design (branch immersive-scenes)
- Ran the first real user-zero dogfood: a turn-by-turn relay against live Opus 4.8 (a `/tmp` background
  driver doing file-IPC around the unchanged `run_session`; the seeded `data/retnovation.db` selected the
  founder `license_continuity` experience). Smoke-tested the relay plumbing first.
- **Dogfood surfaced friction** (the loop working as intended — use → notice → improve): the abstracted
  `license_continuity` prompt felt flat / not immersive, and selection shows no progression. Three distinct
  threads: (a) immersion/concrete prompts, (b) a progression/curriculum model in selection, (c) the
  intro/onboarding arc. User chose to brainstorm **(a) immersion** first.
- **Root cause:** the immersive flatness is a confidentiality artifact — the tracked rubric prompt is
  abstracted because the concrete Veldra specifics are gitignored; the corpus carries
  `owned_problem`/`why_owned`/`unlabeled` but NO student-facing prompt. The JudgmentLoop ReserveGrid anchor
  (concrete, named, numbered) is the immersion bar.
- **Design (spec `docs/superpowers/specs/2026-06-23-immersive-scenes-design.md`):** add a `Scene` (concrete
  `prompt` + a reusable `situation` block) to the gitignored corpus/seed; `select_experience` overrides the
  displayed prompt + attaches the scene when present (abstract stays the fallback); `AnthropicModel` weaves
  the situation into all three judgment-loop calls so the back-and-forth stays situated; **the moat holds
  over the concrete prompt** via a new `generator.validate_scene` (same anti-label checks on what the student
  actually sees). Corpus gains a nullable `scene_json` column (fresh-DB `_SCHEMA` + guarded `ADD COLUMN`
  migration, L-8). Founder/open_ended only; CS untouched. v1 drafts ONE scene (`license_continuity`) from the
  gitignored material so the next dogfood is immediately immersive; the rest stay abstract.
- Baseline before any code: 97 passed, 3 skipped; confidentiality `git ls-files` clean. Next: user review of
  the spec → `writing-plans` → subagent-driven TDD → final adversarial review (§9) → merge → re-dogfood.
- User approved the spec. Authored the plan `docs/superpowers/plans/2026-06-23-immersive-scenes.md` — 6
  subagent TDD tasks (types → persistence scene_json+migration → ingest threading → validate_scene →
  select_experience attach → model situation-weaving) + a controller-executed Final (author the confidential
  `license_continuity` scene into the gitignored seed, re-ingest, a gated tracked moat test, opus adversarial
  review). Plan self-reviewed: full spec coverage, no placeholders, type-consistent.
- Also captured (user idea, graded high-ROI): a **mined founder/exec case library** as the NEXT project after
  scenes — diversify the posture path beyond Veldra with real cases (Stripe…, later Dimon/Solomon/Lip-Bu Tan).
  Reframe: founder path has two content sources (the learner's owned ledger vs. a curated case library); mined
  cases fill the latter. Memory: `retnovation-case-library-idea`. Sequenced after immersive-scenes ships.

## 2026-06-23 — Immersive-scenes Task 1: Types — `Scene`, `CorpusEntry.scene`, `Experience.scene` (TDD PASS)
Added `Scene(BaseModel)` (`prompt`, `situation`) before `CorpusEntry`; `CorpusEntry.scene: Scene | None = None`; `Experience.scene: Scene | None = None` (runtime-only, after `checkable`). 98 passed, 3 skipped; ruff clean.

## 2026-06-23 — Immersive-scenes Task 2: Persistence — `scene_json` column + guarded migration + round-trip (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/persistence.py`.
- Extended `_SCHEMA` corpus table with `scene_json TEXT` (nullable) — fresh DBs get the column
  automatically (L-8).
- Added a guarded `ALTER TABLE corpus ADD COLUMN scene_json TEXT` migration in `Store.__init__`
  (after `executescript`/`commit`): reads `PRAGMA table_info(corpus)`, adds the column only if
  absent — idempotent; existing `data/retnovation.db` (and any pre-existing corpus table) is
  migrated transparently on first open.
- Updated `upsert_corpus`: inserts/updates `scene_json` via `entry.scene.model_dump_json()` or NULL.
- Updated `_corpus_row`: parses `scene_json` back with `Scene.model_validate_json` when non-NULL;
  returns `scene=None` for NULL rows — round-trip lossless.
- TDD evidence: wrote 2 failing tests first (RED — `AttributeError: 'NoneType' has no attribute
  'prompt'` on both); implemented; GREEN in 0.20 s. Existing 5 persistence tests unaffected.
- Full suite: **100 passed, 3 skipped** (was 98+3; net +2 new tests); ruff format + check clean.

## 2026-06-23 — Immersive-scenes Task 3: Ingest — `SeedEntry.scene` threads into the corpus (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/veldra_ingest.py`
  (`from .types import CorpusEntry, LedgerEntry, Scene`).
- Added `scene: Scene | None = None` field to `SeedEntry` — optional; existing seed YAMLs without
  a `scene:` key parse identically (Pydantic default None); idempotent ingest unchanged.
- Added `scene=s.scene` to the `CorpusEntry(...)` call inside `ingest`'s `upsert_corpus` invocation
  so the scene propagates from seed → corpus row (persisted by Task 2's `scene_json` column).
- TDD evidence: appended `test_seed_scene_threads_into_the_corpus` first; ran RED
  (`AttributeError: 'NoneType' object has no attribute 'prompt'` — `SeedEntry` silently dropped the
  `scene` kwarg before the field existed, so corpus `scene` was always None); implemented; GREEN.
- Full suite: **101 passed, 3 skipped** (was 100+3; net +1 new test); ruff format + check clean.
- Files changed: `src/retnovation/veldra_ingest.py`, `tests/test_ingestion.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 4: `generator.validate_scene` — the moat over the concrete prompt (TDD PASS)
- Added `Scene` to the types import in `src/retnovation/generator.py`.
- Implemented `validate_scene(scene, rubric, *, framework_denylist, scaffold_denylist) -> None`
  immediately before `anti_label_gate`, reusing the existing helpers `_contains_phrase`,
  `_frame_trap_phrases`, `WRAPPER_WORDS`, and `GateError` — no duplicated logic.
- Guard order mirrors `anti_label_gate`: framework+frame/trap codes first, then scaffold denylist,
  then wrapper words; raises `GateError` on the first violation found.
- TDD evidence: appended `test_validate_scene_passes_clean_and_rejects_leaks` to
  `tests/test_generator.py` first; ran RED (`ImportError: cannot import name 'validate_scene'`);
  implemented; GREEN in 0.11 s. All four `GateError` branches exercised (framework, frame-code
  spaced, scaffold, wrapper).
- Full suite: **102 passed, 3 skipped** (was 101+3; net +1 new test); ruff format + check clean.
- Files changed: `src/retnovation/generator.py`, `tests/test_generator.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 5: `select_experience` attaches + moat-validates the corpus scene (TDD PASS)
- Added `_attach_scene(exp, corpus, root) -> Experience` helper to `src/retnovation/experience.py`:
  looks up the corpus entry for `exp.ledger_ref`; if the entry has a `scene` AND `exp.rubric` is
  not None (open_ended), calls `validate_scene` via local imports of `load_denylist`
  (content_loader) and `validate_scene` (generator) — the moat holds over what the student sees;
  then returns `exp.model_copy(update={"prompt": scene.prompt, "scene": scene})`.
  No scene, no corpus entry, or `exp.rubric is None` (cs_technical) → `exp` unchanged.
- Updated `select_experience`: captures the selector result as `exp`, passes it through
  `_attach_scene(exp, corpus, root)`, returns the result. `run_session`, the selectors, and
  all other modules are untouched.
- TDD evidence: appended two failing tests to `tests/test_experience.py` first:
  `test_select_experience_attaches_a_corpus_scene_and_overrides_prompt` (RED —
  `exp2.prompt` still the abstract prompt; `exp2.scene` is None) and
  `test_select_experience_without_a_scene_is_unchanged` (RED — would have passed coincidentally,
  but the first test failure confirms the feature is not yet wired). Implemented; both GREEN.
- Regression: `test_dry_run.py` and `test_orchestration.py` (corpus has no scenes) → experiences
  unchanged; both pass. Full suite: **104 passed, 3 skipped** (was 102+3; net +2 new tests);
  ruff format + check clean.
- Files changed: `src/retnovation/experience.py`, `tests/test_experience.py`, `docs/DEVLOG.md`.

## 2026-06-23 — Immersive-scenes Task 6 review-fix: complete situation-weaving test coverage (additive tests only)
- Extended `test_situation_is_woven_in_when_a_scene_is_present` with a `classify_response` block (asserts `"mid-rollout"` reaches the system text); extended `test_no_scene_calls_omit_the_situation` with `classify_intake` + `classify_response` byte-stability assertions (assert `"Situation:"` absent). No production code changed. 11 model tests pass; ruff clean.

## 2026-06-23 — Immersive-scenes final-review fix: `validate_scene` checks both prompt AND situation (COMPLETE)
- Closed spec §9.6 gap: `validate_scene` now builds `text_lc` from `"{prompt}\n{situation}"` so a leaked frame code or framework name in the situation (woven into instructor pushes the student sees) is caught with the same anti-label bar as the prompt. Added two new cases to `test_validate_scene_passes_clean_and_rejects_leaks`: situation-leaks-frame raises, fully-clean (both prompt and situation) passes. 106 passed, 3 skipped; ruff clean.

## 2026-06-23 — Immersive-scenes Task 6: `AnthropicModel` weaves `situation` into judgment-loop calls (TDD PASS)
- Added module-level helper `_situation_block(exp) -> str` to `src/retnovation/model.py` (near
  `_render_rubric`): guards `getattr(exp, "scene", None)` — returns `"\n\nSituation:\n{situation}"`
  when a scene is present, `""` otherwise. Safe on any experience type.
- Wove `_situation_block(exp)` into all three judgment-loop calls:
  - `classify_intake` system: `load_prompt("intake") + _situation_block(exp) + "\n\n" + _render_rubric(exp.rubric)`
  - `generate_push` user: replaced single `user = ...` line with `prefix`/`user` two-line version —
    `prefix = f"Situation:\n{exp.scene.situation}\n\n" if getattr(exp, "scene", None) else ""`
    then `user = f"{prefix}Experience:\n..."`. No unused local variable (ruff clean).
  - `classify_response` system: inserted `_situation_block(exp)` between `load_prompt("response")`
    and the mode/binding-constraint/target-angle lines.
- Byte-stability: when `exp.scene` is None, all three calls produce NO `Situation:` text —
  identical to pre-Task-6 behaviour. `FakeModel` unchanged (scripted; scenes irrelevant).
- TDD evidence: appended `_exp_with_scene`, `test_situation_is_woven_in_when_a_scene_is_present`,
  `test_no_scene_calls_omit_the_situation` to `tests/test_anthropic_model.py` BEFORE implementing.
  `test_situation_is_woven_in_when_a_scene_is_present` RED (assert "mid-rollout" in call failed —
  situation not yet in call). Implemented; both tests GREEN; all 11 model tests pass.
- Full suite: **106 passed, 3 skipped** (was 104+3; net +2 new tests); ruff format + check clean.
- Files changed: `src/retnovation/model.py`, `tests/test_anthropic_model.py`, `docs/DEVLOG.md`.

## 2026-06-23 — immersive-scenes COMPLETE: concrete corpus-sourced experience prompts
- Built on branch `immersive-scenes` via subagent-driven development (6 TDD mechanism tasks, fresh
  implementer + independent reviewer each, then an opus whole-branch adversarial review). Spec/plan:
  `docs/superpowers/specs|plans/2026-06-23-immersive-scenes(.md|-design.md)`.
- **What shipped:** a founder open-ended experience can present a concrete, situated `Scene`
  (`prompt` + a reusable `situation` block) sourced from the gitignored corpus, while tracked content
  stays abstract. `Scene` on `CorpusEntry`/`SeedEntry`/`Experience` (runtime-only); corpus `scene_json`
  column (fresh-DB `_SCHEMA` + guarded `ADD COLUMN` migration, L-8); `SeedEntry.scene` threads through
  ingest; `select_experience` validates the scene against the moat then overrides the prompt + attaches
  the scene (no scene → unchanged fallback); `AnthropicModel` weaves the `situation` into all three
  judgment-loop calls (intake/push/response); CS untouched, `run_session` unchanged.
- **The moat holds over what the student sees:** `generator.validate_scene` runs the anti-label checks
  (named framework / leaked frame-trap code / type-hint scaffold / cosmetic wrapper) over BOTH the
  concrete `prompt` AND the `situation` (the latter feeds the student-facing push). Final-review fix
  (3a33642) extended the gate from prompt-only to prompt+situation, closing a cross-task gap and making
  spec §9.6 true; controller-repro'd against the real `license_continuity` rubric.
- **Final opus review: MERGE WITH FIXES → resolved.** All 7 §9 invariants verified under live repro
  (confidentiality; production-path moat; byte-stable no-scene fallback; fresh + old-table migration;
  runtime-only scene; 3-call grounding; CS untouched). The one Important finding (situation ungated)
  fixed; all minors DEFER.
- **First authored scene (controller, gitignored):** drafted a concrete `license_continuity` scene
  (the escrow-and-continuity-clause decision: procurement unlock vs. competitive exit-roadmap, BSL
  rejected in a ~dozen-buyer market) into `data/seed/veldra_ledger.yaml`, re-ingested. It clears
  `validate_scene` and drives `select_experience` → the concrete (escrow) prompt with the scene
  attached. The scene is confidential → stays in the gitignored seed/`data/`, NEVER tracked.
- **Gated tracked moat test** (`test_generator.py::test_seeded_license_scene_clears_the_moat`, skipif
  `data/` absent): the authored scene must clear the moat against its real rubric — the spec §8 safety
  net. **Verified:** full suite **107 passed, 3 skipped**; ruff clean; `git ls-files` confidential grep
  empty; seed/db untracked.
- Note: `python -m retnovation.veldra_ingest` is a no-op (no `__main__` guard); re-ingest via the
  `retnovation-ingest` console script or `main()`. (Flagged as a follow-up.)
- Next: merge to `main`; re-run the live dogfood to feel the concrete scene; then the queued
  mined-case-library project (see memory `retnovation-case-library-idea`).

## 2026-06-23 — `veldra_ingest` `__main__` guard: `python -m retnovation.veldra_ingest` now runs `main()`
- Added `if __name__ == "__main__": raise SystemExit(main())` so the module runs via `python -m` instead of silently importing and doing nothing (resolves the follow-up flagged in the immersive-scenes entry). Verified `PYTHONPATH=src python -m retnovation.veldra_ingest` → `ingested 14 ledger entries (...)`, exit 0; ruff format/check clean; pytest 107 passed, 3 skipped.

## 2026-06-24 — Scene legibility refinement (branch scene-legibility)
- Dogfood feedback: make the experience the student reads **legible** (bold key terms, separated
  paragraphs) — bare-minimum MVP; visual representation stays post-MVP. Also noted (deferred to the
  progression thread): the escrow scene is a *max-difficulty capstone*, wrong as a cold-start intro —
  input for the intro-arc / case-library work.
- **Moat hardening (TDD, core-path):** scenes now carry markdown (`**bold**`), so `validate_scene`
  strips emphasis (`*`, `` ` ``) before the anti-label checks — otherwise a frame phrase split by
  bold (`**Lead** with what you refuse to do`) would slip past. `_` is kept (snake_case frame codes).
  New `test_validate_scene_sees_through_markdown_emphasis` (RED→GREEN: bold-split phrase still raises;
  legitimate bold passes). Independent adversarial review on the moat change.
- **Content (gitignored):** re-authored the `license_continuity` scene prompt + situation into legible
  markdown — 4 short paragraphs, key terms bolded, the ask set off — in `data/seed/veldra_ledger.yaml`;
  re-ingested. Loads with real `\n\n` paragraph breaks + bold; still clears the gated moat test against
  its rubric (the gate strips the `**`). Scene stays confidential/untracked.
- **Verified:** full suite **108 passed, 3 skipped**; ruff clean; confidentiality `git ls-files` empty;
  `data/` untracked.
- **Adversarial-review fix (Important):** the review found the strip was applied only in
  `validate_scene`, not in `anti_label_gate` (the abstract-prompt gate) — an asymmetry that would let
  markdown into `Experience.prompt` bypass the moat if abstract prompts also become legible. Extracted a
  shared `generator._strip_emphasis(text)` and applied it in BOTH gates; new
  `test_anti_label_gate_sees_through_markdown_emphasis` (bold-split frame leak in `exp.prompt` now
  rejected). Minor (pathological non-spaced bold `a**b**c`) deferred: the space-replacement alternative
  would reopen a worse single-char hiding hole, so empty-replacement is the right tradeoff for curated
  content. Full suite **109 passed, 3 skipped**; ruff clean.

## 2026-06-24 — SESSION PAUSE + HANDOVER (read this first to resume)

**Exactly where we left off.** A live founder dogfood was run and two product findings were captured;
the user chose to **act on the finding** but **paused before building** and asked for a clean handover.

### Repo state (the literal facts)
- Branch `main`, HEAD **`3344788`**, working tree **clean**. Suite **109 passed, 3 skipped** (the 3
  skips are `@pytest.mark.live`, no key). `ruff format`/`check` clean. Confidentiality `git ls-files`
  grep empty; `data/` untracked.
- `main` is **~38 commits ahead of `origin/main` and has NOT been pushed** (every step this run merged
  locally; the user never asked to push — ask before pushing).
- The gitignored `data/seed/veldra_ledger.yaml` holds the authored, **legibly-formatted** concrete
  `license_continuity` scene (escrow-continuity decision); `data/retnovation.db` is re-ingested with it
  (scene present, 4 paragraphs). These are confidential, gitignored, local-only.
- Throwaway live-dogfood relay: `/tmp/dogfood/driver.py` (file-IPC around `run_session`). `/tmp` is
  ephemeral — recreate if gone; the seed/db are ready.

### What shipped this session (post-MVP; build order was already complete)
1. **`immersive-scenes`** (spec/plan `docs/superpowers/{specs,plans}/2026-06-23-immersive-scenes*`):
   `Scene` (`prompt`+`situation`) on `CorpusEntry`/`SeedEntry`/`Experience` (runtime-only); corpus
   `scene_json` column + guarded migration; `select_experience` moat-validates + attaches a scene and
   overrides the prompt (abstract = fallback); `AnthropicModel` weaves `situation` into all 3
   judgment-loop calls; `generator.validate_scene` (the moat over the concrete prompt + situation);
   one authored scene + a gated moat test. cs_technical untouched. Subagent-driven TDD + opus review.
2. **`scene-legibility`** (this entry's predecessors): scenes are legible markdown; both gates
   (`validate_scene` + `anti_label_gate`) strip emphasis via shared `generator._strip_emphasis` so
   bolding can't split a banned phrase past the moat. Plus the `veldra_ingest` `__main__` guard.

### The dogfood + the findings (the reason for the next task)
- Presented the concrete `license_continuity` escrow scene to the user (founder = user-zero). User
  explored 6 proposals + a bonus, then **committed to "Proposal 1" (narrow internal-use escrow, hard
  no-compete line, objective release triggers)**.
- Fed Proposal 1 to the **live** instructor. Result: `classify_intake` judged **both** rubric frames
  (`lead_with_what_you_refuse_to_do`, `protect_the_core_lane`) `present_reasoned` → the loop
  **converged at intake with ZERO pushes / empty trajectory** (`stop_reason=converged`,
  `trajectory=[]`, `sharper_audit=[]`).
- **Finding (→ memory `retnovation-commitment-frame-gap`):** (a) the `genuinely_open` rubric scores
  *engaging the angles* but has **no frame for the decision the prompt demands** ("Decide what you
  commit to… before they sign this quarter"); (b) a **converged-at-intake answer produces no push and
  no appreciating-asset trace — the case instructor goes silent exactly when the student is strong**.

### NEXT SESSION — START HERE: "act on the finding" (rubric depth)
**Goal:** deepen the `license_continuity` rubric (and the pattern for `genuinely_open` experiences
that demand a decision) so a strong answer gets **pushed** instead of silently converging.
**Candidate moves (decide in brainstorming — these are forks, not a fixed plan):**
- Add a **commitment/decision frame** (e.g. `commit_under_the_deadline`) and/or restore the dropped
  `choose_the_failure_default_deliberately` frame from the JudgmentLoop v0.1 anchor.
- Consider a **"stress even a converged answer" loop mode** so the instructor probes the sharpest edge
  rather than stopping when the thin rubric is already satisfied (relates to JudgmentLoop §6
  push-quality / convergence concerns).
- Decide scope: just `license_continuity`, or a general convention for decision-under-deadline
  experiences (and whether a `binding_constraint` / `bounded_error` fits).
**How to start (the established workflow, do not skip):** Session-start protocol → read
`docs/lessons.md`; then this entry; then the local-only gitignored docs `Retnovation_JudgmentLoop_v0.1.md`
(§2 the loop, §6 findings), `Retnovation_Complete_Picture.md` §12–§13; then the code:
`src/retnovation/assessment/judgment_loop.py`, the `license_continuity` rubric in `content/rubrics/`,
`src/retnovation/generator.py`. Then **brainstorming → writing-plans → subagent-driven-development
(fresh implementer + independent reviewer per task) → final adversarial review → finishing**.
**Hard doctrine the user stressed TWICE:** the loop is **conclusion-agnostic — NEVER score or grade
the conclusion.** It outputs a *trajectory*, not a grade. Keep `sharper = a gap closed with a supplied
mechanism`; presence is conclusion-agnostic; reversible decay (L-3); the unlabeled moat
(`validate_scene`/`anti_label_gate`); confidentiality (Veldra design docs + `data/` are gitignored —
verify `git ls-files` after any content work). Core-path changes get an independent adversarial review.

### Other queued threads (not the immediate next, but live — see memory)
- **Progression / intro-arc:** the escrow scene is a *max-difficulty capstone*, wrong as a cold start —
  pairs with the rubric-depth work (`retnovation-commitment-frame-gap`).
- **Mined founder/exec case library** (`retnovation-case-library-idea`): diversify the posture path
  beyond Veldra (Stripe…, later Dimon/Solomon/Lip-Bu Tan); the two-content-sources reframe + 3 moat
  tensions are captured there. Build *on* the scene mechanism.

## 2026-06-24 — Task 1 — Rubric.decision_frame + fail-loud validator (TDD); 112/3 green.

## 2026-06-24 — Task 2 — content_loader threads decision_frame in load_rubric + load_experience; 115/3 green.

## 2026-06-24 — Commitment frame + stress probe: brainstorm + spec (design, pre-plan)
- Picked up the handover's next task ("act on the commitment-frame finding / rubric depth"). Ran the
  brainstorming skill against the dogfood finding (`retnovation-commitment-frame-gap`): the
  `license_continuity` rubric scores *engaging the angles* but has no frame for the decision the
  prompt demands, and a strong answer converges at intake with zero pushes / empty trajectory — the
  instructor goes silent exactly when the student is strongest.
- **Decisions (brainstorming, 4 forks):** (1) scope = a general opt-in **stress-mode convention**, not
  a one-off patch (user accepted §13's generalize-from-one-datapoint caveat); (2) trigger = a declared
  `decision_frame` rubric field (doctrine-as-data) — the named frame is exempt from intake-convergence
  and always gets exactly one stress probe; (3) decision bar = **commit + own the trade + name the
  reversal tripwire**, paired trap `commit_without_a_tripwire` (the tripwire is the supplied mechanism
  → conclusion-agnostic by construction); (4) integration = **Approach A, probe-gated convergence** —
  one unified loop path (`_converged`/`_select_target` guards on a new `probed` set; `generate_push`/
  `classify_response` become stress-aware), reusing the existing push→response→sharper→audit machinery;
  byte-stable for every rubric with no `decision_frame`. Rejected: content-only (doesn't cure the
  silence), auto-stress-all-genuinely_open (eagerness confound), post-converge bolt-on (dual-path),
  restoring `choose_the_failure_default_deliberately` (ReserveGrid-specific, misfits escrow).
- **Hard doctrine carried through:** never grade the conclusion (the probe tests the commitment's
  *reasoning*, not its rightness); the unlabeled moat auto-bans the new frame/trap phrases from prompt
  + scene; no new `stop_reason` (the non-empty trajectory already encodes "converged after stress");
  core-path (`judgment_loop`/`types`/`model`) gets a whole-branch adversarial review before finishing.
- Spec written + self-reviewed: `docs/superpowers/specs/2026-06-24-commitment-frame-stress-probe-design.md`
  (goal, non-goals, doctrine, 7-task build order, edge cases, TDD plan, risks). User approved.
- Implementation plan written + self-reviewed:
  `docs/superpowers/plans/2026-06-24-commitment-frame-stress-probe.md` — 7 bite-sized TDD tasks
  (types → loader → loop → stress push → stress response → content → adversarial review/finish), full
  code per step, per-commit gate, expected suite counts 112→124. One refinement vs. the spec: stress
  doctrine lives in separate `content/prompts/{push,response}_stress.md` files loaded only when
  `stress=True` (cleaner byte-stability than an inline block). **Status: plan ready; awaiting the
  execution-mode choice (subagent-driven vs inline).** No code changed yet; suite still 109/3. `main`
  remains ~39 commits ahead of origin, unpushed (ask before pushing).

## 2026-06-24 — Task 3: probe-gated convergence
- Task 3 — probe-gated convergence (decision_frame force + probed set + stress flag);
  model contract gains keyword-only stress (AnthropicModel ignores until T4-5); 119/3 green.

## 2026-06-24 — Task 4: stress-aware generate_push via push_stress.md
- Task 4 — stress-aware generate_push: push_stress.md appended only when stress=True;
  byte-stable otherwise; 121/3 green.

## 2026-06-24 — Task 5: stress-aware classify_response via response_stress.md
- Task 5 — stress-aware classify_response: response_stress.md inserted only when stress=True;
  byte-stable otherwise; 123/3 green.

## 2026-06-24 — Task 6: commit_under_the_deadline decision frame on license_continuity
- Task 6 — license_continuity gains commit_under_the_deadline frame + commit_without_a_tripwire
  trap + decision_frame (10 angles); gate + seeded-scene moat green; 124/3.

## 2026-06-24 — commitment-frame + stress-probe: whole-branch review + finish
- Branch `commitment-frame-stress-probe` built via subagent-driven development (6 implementer TDD
  tasks, fresh implementer + independent reviewer each; Task 3 — the core loop — got an opus reviewer).
  All per-task reviews ✅ Approved; the seeded escrow scene cleared the moat against the new codes with
  no rewording; `data/` stayed untracked throughout.
- **Whole-branch opus adversarial review: MERGE — Yes.** Zero Critical, zero Important. Every checklist
  item verified at source: byte-stability provable for non-`decision_frame` rubrics (both loop guards
  no-op; `stress` structurally False; `stress=False` system prompts byte-identical); the forced probe
  fires exactly once and terminates (unconditional `probed.add`, unmoved→`exhausted`+`probed`→converge);
  the stress path stays conclusion-agnostic AND is independently policed by the unchanged blind
  `grade_sharper` (which never sees `stress`); the moat auto-bans the new codes; confidentiality holds.
  The plan's separate-stress-files refinement judged a strict improvement over the spec's inline block.
- **Applied the review's one hardening:** the two `*_byte_stable` model tests asserted the stress
  marker absent but not the base prompt present — a "base prompt dropped" regression could pass them
  (cf. L-8 vacuous-pass lesson). Added `assert "case instructor" in {blob,sys}` to both. Test-only.
- Final: suite 124 passed / 3 skipped (the hardening added assertions to two existing tests, not new
  tests), ruff clean, confidentiality grep empty, `data/` untracked. Feature complete on the branch;
  ready to merge to `main`. Not pushed (ask before pushing).

## 2026-06-24 — Diagnostic-progression architecture: brainstorm + spec (design, pre-plan)
- Picked up the second open thread (progression / intro-arc; memory `retnovation-commitment-frame-gap`).
  User reframe: progression is a DIAGNOSTIC instrument (locate the learner), not an easy→hard ramp. Heavy
  brainstorming, architected from scratch. Deep parallel recon first (code: scheduler/state/persistence/
  orchestration/experience/generator; docs: Complete Picture, Loop, FounderCEO, Berkeley Guidebook,
  Blueprint, MVP Scope, interest tree).
- **Findings that shaped it:** the policy seam is `scheduler.schedule_next` (placeholder `weak>forming>
  strong`, and it hardcodes `ledger_ref=ledger[0].id` — never actually picks a problem). The substrate is
  half-built: estimator "too aggressive" (§17), `strong` is dead code, `decay_frame` never called, `due`
  reset to now (no temporal signal), `trap_gallery` not persisted. So locating a learner needs the model
  rebuilt to BE locatable.
- **Decisions (brainstorming, 5 forks):** (1) learner model = strength × breadth × uncertainty per frame;
  (2) selection = one unified value function over 3 named drives (reduce-uncertainty / retention-due /
  transfer-opportunity), intro-arc emergent; (3) cold start = isolation by frame-load (uncertainty-gated
  penalty, not difficulty); (4) receipt + redirect (fullest propose-and-decide; redirect = evidence);
  (5) candidate space = (frame × ledger-problem) from the content graph (per-frame attribution,
  transfer-native). cs_technical stays on its SM2-lite spacing; the judgment loop is untouched (evidence
  source). Decomposes into 3 implementation projects (substrate → policy → receipt surface); Project 1
  first.
- Spec written + self-reviewed: `docs/superpowers/specs/2026-06-24-diagnostic-progression-design.md`.
- **Rev. 1 (external design review, received-via-receiving-code-review).** Analyzed faithfully (verified
  each claim against the code/tests, not yes-manned). Four seams, all sound — accepted with two additions:
  (1) **strength stored→derived** — the spec had strength as both persisted and derived with decay
  mutating it (a real contradiction I introduced); now strength/due are pure functions of persistent
  `{evidence_count, breadth, last_seen}`+`now`, computed on read → deletes `decay_frame`, removes the
  decay-sweep mutation, kills incoherent-state class, gives the Berkeley §5 savings effect for free,
  shrinks Project 1 (verified test_state forming/weak reproduce at staleness 0; test_scheduler direct
  construction still works). (2) **cold start mean×frame-load → per-experience MAX constituent
  uncertainty** — a mean conflates "half-known" with "half-blank"; max makes "integration test once the
  parts are located" literal and subsumes both proxies; corrected the rationale from attribution (loop
  already classifies per-frame) to integration readiness; added the sole-content-frame edge for Project 2.
  (3) **content honesty** — `strong` is starved by the same thinness as transfer; P2/P3 on current content
  deliver plumbing, the unlock is authored content (mined case library). (4) named the
  authoring-order=cold-start-curriculum dependency, the endogenous-revealed-demand gap (ledger as latent
  external signal), runner-up+margin in the receipt, and that redirect evidence is logged-but-unconsumed.
- **Rev. 2 (external review, round 2).** One substantive pin (sets inside Project 1) + two tightenings,
  all verified and accepted: (1) **the staleness clock keys to the persistent storage tier
  (`evidence_count`+`breadth`), never the displayed bucket** — keying to the decayed bucket is circular and
  causes continuous review (decays→shorter interval→reviewed more); storage-keyed is acyclic + the §5
  savings effect. My extension: the uncertainty staleness-term rides the same clock (else diagnose
  resurfaces well-earned stale frames and re-introduces the pathology). (2) "incoherent state impossible"
  → **unreachable via the served paths** (load_state/update_state); direct `FrameStrength(strength=…)`
  stays open for tests (the shim seam) and the served path must never set strength directly. (3) the
  **sole-content-frame surfaces as a content gap**, not a scorer special-case (drops the exclude-from-max/
  floor-wU escape hatch). Spec → rev. 2 (§14 added). No code changed; 124/3.
- **Project 1 plan written + self-reviewed:**
  `docs/superpowers/plans/2026-06-24-diagnostic-progression-p1-substrate.md` — 5 implementer TDD tasks
  (FrameStrength storage fields → derive_strength/derive_due/frame_uncertainty on the storage-keyed clock
  → estimator writes storage anchored to ledger_ref, strong reachable across 2 problems → persistence
  derives on load + migration + delete decay_frame → persist trap_gallery) + a controller review/finish.
  Full code per step, per-commit gate, expected suite 124→134. Decided in the plan: the strong bar needs
  an `unprompted_breadth` storage field (subset of breadth) to distinguish unprompted from
  closed-under-pressure — a faithful refinement of spec §6's "≥2 unprompted × ≥2 problems." **Status: plan
  ready; awaiting execution-mode choice.** `main` ~48 commits ahead of origin, unpushed.
