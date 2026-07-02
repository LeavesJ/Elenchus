# Retnovation — Lessons Learned

Read this checklist before every code change. Update it after every correction or build/test failure.

## Pre-Commit Checklist (every commit)
1. `ruff format .`
2. `ruff check .`
3. `pytest`
4. Update `docs/DEVLOG.md` with what changed and why.
5. No secrets/`.env` staged (`git diff --cached`).
6. No confidential docs tracked:
   `git ls-files | grep -iE 'berkeley|guidebook|blueprint|brief|founderceo|judgmentloop|lifttest|mvp_scope|\.pdf'`
   must be empty.
   Also `git ls-files | grep -E 'content/lift/scenarios\.yaml$|content/lift/candidates\.yaml$'` must be empty
   (the real lift banks are gitignored; only the *.example.yaml stubs are tracked).
7. Inversion check: `git status --short | grep -v '^??'` empty, or every Modified file
   has a written hold reason in DEVLOG.
8. Stage explicit paths only (no `git add -A`).

## Before Declaring a Change Complete
1. Pre-commit checklist passes.
2. The relevant test actually runs and passes — observe the output (evidence before assertion).
3. DEVLOG updated.
4. No confidential docs tracked (`git ls-files` check).
5. For core-path changes (`orchestration`, `judgment_loop`, `persistence`, `types`):
   an adversarial review pass was run and its findings addressed.

## Seeded principles
- **L-1 Doctrine is data.** Maps + curator rubrics live in `content/`, versioned, never
  hardcoded in `src/`. The model rents capability; the gates hold doctrine.
- **L-2 Confidential docs never tracked.** The Berkeley Guidebook is a personal life +
  financial plan; the design docs are internal. Gitignore + `git ls-files` verify, every
  time. (Mirrors the Veldra TP-3 near-miss where a private doc was nearly pushed.)
- **L-3 Reversible decay, never deletion.** State demotes/reschedules; rows are not deleted
  (Guidebook §5: forgetting is retrieval failure, not erasure).
- **L-4 Open-ended state moves on rigor/trajectory, never correctness.** The conclusion is
  never graded.
- **L-5 Judgment-loop disband rules.** It never hands the answer, names the frame, agrees to
  soften, removes effort, or grades the conclusion. The friction is the product.
- **L-6 The unlabeled problem is the moat.** If recognizing the type + running a procedure
  solves it, it is homework in a costume and does not ship.
- **L-7 Never force-add gitignored scratch.** The SDD workspace `.superpowers/sdd/` (task
  briefs, implementer reports, review packages) and tool dirs (`.claude-flow/`) are gitignored
  scratch and must never be committed. A fix subagent used `git add -f` to commit its report;
  it was reverted. Subagent dispatches must say: write reports under `.superpowers/sdd/` and
  stage ONLY source/test/docs paths — never `git add -A`, never `-f` on an ignored file.
- **L-8 A green suite can hide a broken bootstrap.** When a runtime gate fails loud over the
  *whole* content library (e.g. `load_gated_library` raises on any rubric lacking a corpus
  anchor), every state-builder entry point (`cli.build_store`) must seed the WHOLE library, not
  one hardcoded item. In Step 3 the e2e tests seeded all three refs explicitly AND the local
  `data/retnovation.db` was already fully seeded — both masked a fresh-DB `GateError`; only the
  final adversarial review, with a fresh-tempdir repro, caught it. Prevention: for any entry
  point that seeds state, add a fresh-DB end-to-end regression test that exercises the real gated
  path (build state → select → assert no raise), so fixtures and a pre-seeded local DB cannot hide
  a broken shipped seed.
- **L-9 A green test over a SYNTHETIC fixture can hide a dead production path.** In Project 1 the
  estimator's `strong` path read `unprompted_breadth`, populated only when a frame is reasoned
  *unprompted*. The test hand-built an `Assessment` with that shape and passed — but the judgment loop
  *never emits* it (it co-populates the `present_reasoned` delta with `frames_closed_under_pressure`, and
  intake-reasoned frames make no delta), so `strong` was unreachable in production. The pre-existing code
  even documented the unreachability and the test still "passed." Prevention: for any signal the engine
  *consumes*, add a test that a real PRODUCTION path *produces* it (e.g. run `assess()` and assert the
  field is populated), not only a hand-built fixture. Extends L-8: a fixture that can't occur is a worse
  lie than a pre-seeded DB. The whole-branch review then caught a second-order bug (the
  `reasoned_unprompted` signal over-credited stress-probed decision frames and bypassed the sharper
  veto) → fixed with `code not in probed`.
- **L-10 A return-type change updates every caller in the SAME commit.** When `schedule_next` went from
  returning a spec to `(spec, receipt)`, splitting "change the function" and "fix the callers" into two
  tasks would leave a red suite between them, which breaks the SDD per-task green gate and poisons the
  next task's baseline. Order the plan so the signature swap is one atomic task after the additive pieces
  land; every commit leaves `pytest` green. (Caught in plan self-review, not execution.)
- **L-11 Background processes don't survive agent turn boundaries — use a checkpointed stepper for
  interactive dogfooding.** A long-running `run_session` driver that blocked on file-IPC for the human's
  reply was reaped at the turn boundary (twice). For a multi-turn, human-in-the-loop live dogfood, drive
  the loop as discrete synchronous steps that each run to completion within one turn and persist loop
  state to a checkpoint file (`/tmp/dogfood/step.py`: `opening` → classify_intake + first push;
  `reply` → classify_response + continue), faithfully porting `assess()`'s control flow (the real
  `_select_target`/`_converged`/stress logic, `update_state`, `audit_sharper`) rather than reimplementing
  it loosely.
- **L-12 A spec section inherits stale claims from earlier sections — verify against the MERGED CODE, not
  the prior prose.** §17 (Project 3) leaned on §16's claim that `_INTERVAL_DAYS` "moves to
  `content/cadence/progression.yaml`, loaded via `load_progression()`." Against the merged P2 code that was
  false — P2 deliberately kept the constant in `state.py` (a DEVLOG-recorded refinement) and
  `load_progression` loads no staleness keys, so a P3 promote-threshold plan built on it would have rested
  on an unfinished L-1 migration. A 5-lens adversarial review caught it before writing-plans. Prevention:
  when a new spec section depends on a factual claim an earlier section makes about already-built code,
  re-verify that claim against the code/tests before building on it — prior spec text drifts from what was
  actually shipped (the spec-level cousin of L-9).
- **L-13 Conclusion-agnostic is not leak-proof — a surface that names the FRAME (not the conclusion) still
  contaminates the unprompted signal.** The first P3 receipt draft showed the learner the target frame
  ("serving `lead_with_what_you_refuse_to_do` … aims it at licensing") *before* the experience. Naming a
  frame is not naming a conclusion, so the conclusion-agnostic invariant passed it — yet it re-attaches the
  label `content/prompts/push.md` exists to strip and turns an unprompted deployment into a prompted one,
  corrupting `reasoned_unprompted`/`evidence_count` (the hard-won P1 rev.3 signal). Prevention: any
  learner-facing surface, in any medium, must withhold the move — surface the problem/scenario/trajectory,
  never the frame or drive; guard it with an explicit "no `frame_code` in the learner-facing string"
  assertion, and keep frame-level decomposition to the async author log. Medium-independent — carries to the
  future UI.
- **L-14 Moving selection from queue-time to live-propose changes WHICH item is served — re-verify every
  test fixture that implicitly depended on the old selection.** The P3 plan removed the `build_store` queue
  seed that had steered selection to `license_continuity`; under cold-start propose-from-live the value
  function instead ranks `decision_under_stakes` (frame `choose_the_failure_default_deliberately`) first,
  whose frames the test `FakeModel`s don't script → `KeyError` at the single atomic L-10 commit. The plan's
  own self-review missed it; an adversarial review that *actually ran* `select_next` over the real library
  reproduced it. Prevention: when a change alters a selection policy, enumerate the tests whose model/data
  fixtures assume a specific selected item and re-steer them (e.g. via the redirect seam) or broaden the
  fixture — and don't claim "green at every commit" for the seam-swap commit without running the rewritten
  suite against real content. (Corollary: an adversarial reviewer that runs code beats one that only reads
  it — for selection/ranking claims, have the review execute the function.)
- **L-15 An adversarial review's *synthesis* can be confidently wrong — trust the per-finding VERIFY stage,
  and check terminology against the source before acting.** The lift-harness spec review's headline
  ("dominant, load-bearing defect: EXP-001 mislabeled as `negative_lift`, it's a NULL") was **refuted on
  verification**: the doctrine's phrase "true null *of value*" means null-of-*preference* (the frame landed
  but didn't win), NOT the spec's two-axis dist-0 `null` cell ("the model can't see it") — EXP-001 was
  distinguishable (dist 1) + dispreferred = `negative`, exactly as written. Acting on the synthesis would
  have injected a doctrine error (scripting EXP-001 as indistinguishable, contradicting its documented
  dist=1). Prevention: when a review flags a "dominant defect," read the cited source span yourself before
  changing anything; a confident synthesis built on a terminology conflation is more dangerous than no
  review. (This is why the review harness keeps a separate verify stage — and why a near-tie of opposite
  conclusions gets escalated to the human, not silently resolved.)
- **L-16 An audit/decision record must not force a verdict its author never made.** SP2's `AdmissionRecord`
  required `gates: Gates` (5 non-optional human-gate verdicts), but a *screen-reject* (a candidate killed on
  the marginal_lift necessity result) never reaches the human gate-walk — so writing its record forced 5
  invented `pass`/`fail` verdicts into a committable provenance artifact whose entire purpose is honest
  audit. Surfaced only by **dogfooding the tool for real** (writing the 5 reject records during the Phase-2
  mine), not by any test. Fix: made `gates` optional (`Gates | None`), with the coherence validator
  requiring it for `admit_provisional`/`file_as_subframe` and allowing `None` for `reject`. Prevention: when
  a record models a multi-stage decision, make the later-stage fields optional for the exits that short-circuit
  before those stages — a required field that some valid path can't honestly fill is a latent lie in the
  record. (The spec's own §6 said "human gates left unevaluated" for rejects; the implemented type didn't
  encode it — a spec/impl drift the test suite couldn't catch because no test constructed a reject without
  gates.)
- **L-17 A shared helper's hardcoded resource budget, tuned for its original caller, silently breaks a new
  caller with different output characteristics — and the break may surface only in the live path.**
  `AnthropicModel.generate_output` hardcoded `max_tokens=1024`, correct for SP1's short lift outputs ("write a
  120-word pitch"). Reused by the SP3 elicitation probe on long reasoned-decision prompts, 1024 truncated the
  opening (`stop_reason=max_tokens` with a partial answer) or — when adaptive thinking fired — consumed the whole
  budget and left NO text block, raising `ModelError("no text...")`. Non-deterministic between the two faces.
  EVERY offline fake test passed (fakes return canned text, never hit the cap); it surfaced ONLY on the first
  @live run. Truncation was also a measurement risk: an opening cut off before the embed insight reads as absent
  for a non-genuine reason. Fix: make the budget a keyword param (`max_tokens: int = 1024`) defaulting to the old
  value (lift byte-identical), with the new caller passing a larger `LEARNER_MAX_TOKENS`. Prevention: when reusing
  a shared helper for a caller whose output size/shape differs materially, check its hardcoded budgets/limits
  against the new need and parameterize them (default preserving existing callers) rather than assuming the
  original constant fits; and for live-only behavior, run a cheap single-call sanity BEFORE a full multi-call
  batch — it catches the break without burning the whole run (and the tokens).
- **L-18 A runnable entry point that needs an env var must load it — or the documented launch command fails,
  even when a `.env` file is present.** `python -m retnovation.web` started uvicorn WITHOUT loading `.env`, so
  `ANTHROPIC_API_KEY` never reached `os.environ` and the Anthropic SDK raised `TypeError("Could not resolve
  authentication method…")` at the first model call — surfaced only in the founder's BROWSER dogfood, because the
  @live smokes had each done `set -a && . ./.env && set +a` first, so "it works in my smoke" was not "the
  documented command works." A mounted `.env` file ≠ the variable in the process environment. Fix: a best-effort
  `.env` loader in the launch entry (`os.environ.setdefault` per KEY=VALUE line, so a real exported var always
  wins; never log values). Prevention: when an entry point depends on env vars, either load them itself or make
  the documented launch command include the sourcing — and when validating a runnable thing, run it the EXACT way
  the user will (a smoke that pre-sets env the real command doesn't is testing a different command).
- **L-19 The setuptools editable install (`pip install -e .`) is UNRELIABLE on this Python 3.14 venv — launch and
  test with `PYTHONPATH=src`, do NOT depend on `import retnovation` resolving on its own.** Recurring symptom: the
  founder runs the documented `python -m retnovation.web` and gets `ModuleNotFoundError: No module named
  'retnovation'`. Root cause (diagnosed 2026-06-29): the `__editable__.retnovation-0.1.0.pth` is present and
  contains the correct plain path (`…/src`), yet `src` is NOT added to `sys.path` at startup — Python 3.14 +
  setuptools silently drops it. Every editable mode fails the **`-m`/`runpy`** resolution path: lenient (plain
  `.pth`) → `src` never on `sys.path`; strict (`editable_mode=strict`) → a `build/__editable__…` symlink-finder
  makes `import retnovation` work in a `python -c` context but `python -m retnovation.web` STILL raises (runpy
  doesn't consult the editable finder the same way). Prior handoffs "fixed" it with `pip install -e . --no-deps`,
  which works *momentarily in the same shell* then breaks again — a false fix. **The robust, deterministic
  commands (verified via health smoke, `GET /api/health → {"ok":true}`, `GET / → 200`):**
  - Web app: `cd ~/Documents/Retnovation && PYTHONPATH=src .venv/bin/python -m retnovation.web` → http://127.0.0.1:8000
  - Tests: `PYTHONPATH=src .venv/bin/pytest -q` (already the documented form).
  `PYTHONPATH=src` does not depend on the editable install at all, so it cannot recur. Prevention: when a `python
  -m pkg` launch fails with ModuleNotFoundError on a `src/` layout, do NOT reinstall editable and call it fixed —
  validate the EXACT command with a health smoke, and prefer `PYTHONPATH=src` (a thin repo-root launcher script is
  the only way to restore the bare `python -m` form, since a package cannot self-bootstrap its own import for `-m`).
- **L-20 MEASURE per-call latency before tuning `effort` — with adaptive thinking, high effort is NOT slow on easy
  calls, and the real lever is usually call COUNT, not per-call depth.** Diagnosing "the engaged agent is slow," the
  intuitive fix was to drop `output_config.effort` to low/medium on the simple classifier calls. Measured on Opus
  4.8 (2026-06-29): `classify_entry` was 1.3s at HIGH vs 1.8s at low and 6.5s at medium — high is *faster*, because
  adaptive thinking already spends little when the task is easy; lowering effort just changed the thinking regime
  for the worse. `generate_push` (a real judgment call) was 3.3s, not the 20–30s assumed. The actual cost was the
  egress fan-out: the old gate made one `check_injection_expressed` call PER hidden move (4 serial calls ≈ 11.3s),
  fired on every Echo, ~6–8× per session — that is where the minutes went. Fix that moved the needle: BATCH the N
  per-move screens into ONE `screen_moves(moves, text)` call (≈2.5s), reducing call count; the effort-lowering was
  reverted as a wash-or-worse. Prevention: never assume effort↔latency is monotonic on adaptive-thinking models —
  time low/medium/high (n≥3; they're noisy) on the ACTUAL call before changing it, and look first for redundant
  serial round-trips to collapse. A counterfactual timing of the old path (per-move @ high) vs the new (batched) is
  what proved the win — bake that comparison into the change; don't claim a speedup you didn't measure.
- **L-21 A review subagent that runs the suite on the SHARED working tree, dispatched while the controller keeps
  editing, will report false failures from the half-applied tree — isolate the reviewer.** During the engaged-agent
  build (controller-implements + parallel review subagents), the T1 terrain reviewer ran `pytest` on the live tree
  while the controller was mid-T3 editing `session_runner.py`/`voice.py`/`model.py`; it saw "8 failures in
  test_session_runner/test_web_api, one that passes in isolation but fails in the full run" and correctly flagged
  them as likely-unrelated. They were an ARTIFACT: at that instant the tree was inconsistent (a caller referenced
  `voice.opening`/`concierge_open` before the source defined them). Every committed state was green (282→284→288);
  re-running at the clean HEAD confirmed 0 failures and no random-ordering plugin. Prevention: dispatch review
  subagents that run tests with `isolation: "worktree"` (a frozen checkout at the reviewed commit, immune to the
  controller's later edits), OR instruct them to review the COMMIT via `git show <sha>` and run only that commit's
  own tests — never `pytest` the live tree — and to treat any full-suite failure as possibly later in-progress work,
  not the commit under review. "Passes in isolation, fails in the full run" during an active build is the tell.
- **L-22 A key-gated (@live) test rots SILENTLY when a signature changes — it never runs offline, so the drift
  is invisible until the next paid live run.** `test_live_intake_on_fixed_experience` called
  `select_experience(core, state, ledger, spec=None)`; when Step 3/immersive-scenes added the required `corpus`
  param (3915964/6d0f836) every OFFLINE caller was updated (L-10) but this @live test was not — it is
  `skipif(no key)`, so six merged builds and every `pytest -q` stayed green while the test was un-runnable. It
  surfaced a week later as a TypeError in the founder's first full `-m live` run, costing a 5-minute paid run to
  discover a bug that was free to catch. Prevention: (a) L-10's "update every caller in the same commit" includes
  callers the offline suite never EXECUTES — when changing a signature, grep tests/ for the symbol including
  live/skipped files, and treat a hit in an @live file as a real caller; (b) build live-test setups on the
  production path shared with offline-covered helpers (mirror `_first_open_exp`), never on retired shortcuts —
  everything before the model call should be executable offline, so a setup-only repro
  (`python -c` the setup lines) can verify it for free; (c) after fixing a live-only break, verify with a
  single-call live run of just that test (L-17), not the whole batch.
- **L-24 Read the ERROR CLASS of a live failure before debugging anything — `529 Overloaded` is Anthropic-side
  capacity, not the product.** A full `-m live` run died 9/25 with identical `anthropic.OverloadedError: 529`
  during a sustained overload window (the SDK's 2 default retries can't outlast minutes-long windows); the 16
  outside the window passed, including tests that had "failed" suspiciously the run before. Prevention: (a) a
  block of same-class 5xx/529 failures = infrastructure — wait it out, don't touch code; (b) resume with the
  cache instead of re-burning the whole suite: `pytest -m live --lf -q` re-runs exactly the failed subset;
  (c) only an ASSERTION failure (read the printed turn) is product signal on live runs.
- **L-23 A `pytest | tail` pipe MASKS the exit status — an `&&` gate chain built on it will commit a RED
  state.** The woven-stance Minor-hardening commit ran `pytest -q ... | tail -2 && ... && git commit`; pytest
  failed but the chain's status came from `tail` (zsh, no pipefail), so the commit landed red and had to be
  amended after a fix-forward. Prevention: when a pipe feeds the gate, capture the real status — either
  `pytest -q > /tmp/out 2>&1; echo "exit: $?"; tail -1 /tmp/out` and branch on the echoed status, or read the
  tail output and ONLY commit after seeing the literal "N passed" with 0 failed — never let `&&` after a piped
  pytest stand in for "tests passed."
