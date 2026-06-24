# Diagnostic Progression — Locating the Learner, Not Ramping Difficulty

Date: 2026-06-24
Status: design (awaiting user review before plans)
Origin: the second open thread from the commitment-frame work (memory `retnovation-commitment-frame-gap`)
and the "escrow scene is a max-difficulty cold-start capstone" note. The user's reframe: progression
must **serve a purpose so the system actually understands where the learner is** — a diagnostic
instrument, not an easy→hard ramp. This is a from-scratch architecture for the selection/progression
layer. Post-MVP; the MVP harness and the commitment-frame feature are complete.

## 1. Goal

Replace the placeholder selection policy (`scheduler.schedule_next`'s `weak > forming > strong` sort)
with a **diagnostic progression system**: a richer learner model that represents *where the learner is*,
and a unified value-function policy that each session serves the experience which best **locates,
consolidates, or deploys** a frame — conclusion-agnostic, ledger-anchored, reversible, and auditable.
The cold-start intro-arc emerges from the same policy (it reads frames cleanly while uncertainty is high)
rather than being a difficulty ramp.

## 2. Non-goals (YAGNI / be-mindful)

- **No easy→hard difficulty ladder.** "Scope" enters only as a cold-start frame-load prior, never a
  global difficulty ordering.
- **No change to the assessment layer.** The judgment loop (and the just-shipped commitment-frame /
  stress-probe work) is the *evidence source*; it stays byte-stable. This design is about what the
  system does with the evidence and what it serves next.
- **No change to the `cs_technical` regime's scheduling.** It is checkable (correctness-scored); its
  retrieval-strength spaced repetition already answers "where are you." The value function is the
  founder/process (`open_ended`) path only. cs inherits the persisted-state plumbing, nothing more.
- **No redirect-rewrites-the-weights loop.** A redirect is honored and logged as evidence; weight
  tuning from clustered redirects is a later, dogfood-informed step.
- **No rich crystallization mirror.** Core promote/demote gets a thin candidate-surfacing cut; the
  longitudinal crystallization mirror stays deferred (MVP_Scope §5 — needs an accreted ledger).
- **No experience *synthesis*.** The policy scores over the authored/gated content graph; where content
  can't supply a `(frame, problem)` pairing, the policy surfaces the gap honestly rather than generating.
- **No multi-domain / Blend.** Single founder project, as today.

## 3. Doctrine constraints this must honor

- **Diagnostic + demand-revealed, never difficulty.** Sequence on frame strength + the ledger (owned
  problems are the spine). "Progression is not easy→hard" (Loop v0.1; Complete Picture §11).
- **Conclusion-agnostic.** Locate the learner via rigor / frame-coverage / trap-avoidance /
  sharper-under-pressure / trajectory — **never** the conclusion. No drive may read a conclusion.
- **Simultaneity + reversible decay.** Heavy reps *while* learning; forget-then-relearn beats continuous
  review; decay is de-prioritized review, never deletion, and is reversible (the savings effect; L-3;
  Berkeley §5).
- **Auditability over taste.** Every pick shows its work — the score decomposes into a receipt. Core
  promote/demote proposes candidates with receipts; the user decides ("propose and decide";
  Complete Picture §7). No tool "wisdom."
- **Transfer is the signature move.** A `forming` frame aimed at a *different* ledger problem is the
  deploy test; breadth (cross-problem) is first-class.
- **Earned strength.** `strong` requires repeated spaced unprompted success (Complete Picture §17 — the
  current single-use heuristic is "too aggressive"), and it must be *reachable* (today it is dead code).
- **Doctrine as data (L-1).** Drive weights and thresholds live in `content/cadence/progression.yaml`,
  not hardcoded. Adding capability = content, not engine edits.
- **L-8 fail-loud / fresh-DB.** Every schema change works on a fresh DB and migrates the existing one;
  every state entry point is exercised by a fresh-DB regression test.
- **Core-path review.** `scheduler`, `state`, `types`, `persistence`, `orchestration` are core-path;
  each project gets an independent adversarial review before finishing.

## 4. Confirmed decisions (from brainstorming)

1. **Learner model = strength × breadth × uncertainty** per frame (the richest option). To be located,
   the learner must be represented richly: earned strength, transfer breadth, and the system's own
   uncertainty.
2. **Selection = one unified value function** over three named drives (reduce-uncertainty, retention-due,
   transfer-opportunity); the intro-arc emerges as the high-uncertainty regime; the score decomposes
   into the audit receipt.
3. **Cold start = isolation by frame-load.** While uncertainty is high, penalize high-frame-load
   experiences so reads are attributable; the integrative capstone becomes the integration test once the
   parts are located. Not a difficulty ramp.
4. **Receipt + redirect** (fullest "propose and decide"): every pick surfaces its receipt; the user
   accepts or redirects; the redirect is evidence; core promote/demote uses receipts + user decision.
5. **Candidate space = `(frame × ledger-problem)`** drawn from the content graph (Approach A), not
   whole-experience scoring — preserves per-frame attribution and makes transfer literal.

## 5. Architecture: the seam, the module map, the data flow

The policy seam stays `scheduler.schedule_next`, rewritten from a sort into a diagnostic value function.
Its signature grows to read the **content graph** (the gated library — each experience's frames, its
ledger problem, its frame-load) so it can score real `(frame, problem)` candidates. Today it hardcodes
`ledger_ref = ledger[0].id` (it never actually chooses a problem); the new policy chooses meaningfully.

| Module | Change | Why |
|---|---|---|
| `types.py` | Extend `FrameStrength` (+ `evidence_count: int`, `breadth: set[str]`); add `Selection`/`Receipt`; `NextExperienceSpec` carries the chosen problem + drive + receipt | the rich model + the audit surface |
| `persistence.py` | `frames` columns + guarded migration (the `scene_json` pattern); persist `trap_gallery`; add `selection_log` | the model must survive sessions; the trap lens is evidence |
| `state.py` | Estimator redesign: evidence-accumulated strength, earned/reachable `strong`, breadth from the anchored problem; `frame_uncertainty(fs, now)` + staleness helpers; decay wired | fixes §17; makes `strong` reachable |
| `scheduler.py` | The value function: 3 drives + cold-start frame-load penalty, reading the content graph | the diagnostic policy |
| `experience.py` / `generator.py` | Selector honors the `(frame, chosen-problem)` pairing | transfer needs the right problem |
| `orchestration.py` | Split propose from run: propose → receipt → accept/redirect; redirect logged as evidence | "propose and decide" |
| `content/cadence/progression.yaml` | Drive weights + uncertainty/staleness thresholds | doctrine as data, tunable |

**Data flow, one session:**
```
load rich state ─▶ policy proposes (frame, problem, drive, receipt) over the content graph
                     │
   user accepts ◀────┤ user redirects ─▶ log redirect as evidence, serve the chosen target
        │
   select experience for (frame, problem) ─▶ present ─▶ assess (judgment loop, UNCHANGED)
        │
   update rich state (evidence_count, breadth, strength, staleness, traps) ─▶ persist ─▶ propose next
```

## 6. The learner model (`state` / `types` / `persistence`)

`FrameStrength` grows from `{strength, last_seen, due, last_evidence}` to also carry **`evidence_count`**
and **`breadth`** (the set of ledger problems the frame has held `present_reasoned` against). Three lenses
are *derived* from these + `last_seen`:

- **strength** (the headline bucket, now earned):
  - `strong` = ≥2 unprompted `present_reasoned` observations across ≥2 distinct problems (repeated AND
    cross-context — the §17 bar; reachable, unlike today).
  - `forming` = engaged with a real mechanism but single-context, single-observation, or only
    closed-under-pressure.
  - `weak` = failed to close / unmoved.
- **staleness** = `now − last_seen`, with the "due" interval set longer for stronger frames.
- **uncertainty(fs, now)** ∈ [0,1] — monotone-high when evidence is thin, breadth is narrow (`<2`), or
  the frame is stale. This is the diagnostic signal.

**Estimator redesign** (`update_state`), anchored to the experience's ledger problem `p`:
- unprompted `present_reasoned` → `evidence_count += 1`, `breadth ∪= {p}`.
- closed-under-pressure → `breadth ∪= {p}` at forming-grade (engaged, not yet sharp).
- failure / unmoved → neither; weak evidence recorded.
- **Decay sweep** (session start): a frame whose `due` has passed is demoted one bucket while keeping
  `evidence_count` and `breadth` (reversible; savings effect; L-3). This gives the dormant `decay_frame`
  its caller and makes `due` meaningful (today it is reset to `now` every session).

## 7. The value function (`scheduler`, `open_ended` path)

Candidates: `(frame f, problem p)` pairings with backing content. Score each:

```
V(f,p) =  wU · uncertainty(f)                     # DIAGNOSE  — dominant at cold start
        + wR · retention_due(f)                   # CONSOLIDATE — forming/strong and going stale (just-in-time before decay)
        + wT · transfer_opportunity(f,p)          # DEPLOY    — f forming AND p ∉ breadth(f) AND content pairs (f,p)
        − wL · cold_start(state) · frame_load(e)  # the intro-arc penalty
```

- **`transfer_opportunity`** is zero unless `f` is forming and `p ∉ breadth(f)` and an authored
  experience pairs them. Where no second-problem experience exists, it can't fire and the receipt records
  "transfer blocked: content gap."
- **`cold_start(state)`** = mean core uncertainty. Near 1 while the learner is unknown → the frame-load
  penalty bites → low-load, attributable experiences win (the emergent intro-arc). As the model fills in,
  it → 0 and integrative experiences (the escrow capstone) become eligible as the integration test.
- **argmax** with a deterministic tie-break (frame id) — no randomness; reproducible tests.
- The winning term names the **drive**; the full decomposition becomes the **receipt**.

Weights `wU/wR/wT/wL` and the uncertainty/staleness thresholds live in `content/cadence/progression.yaml`.

## 8. Receipt + redirect + core promote/demote (`orchestration`)

`run_session` splits "propose" from "run":
1. Session start: the policy proposes `(frame, problem, drive, receipt)` from **live** state (fresh beats
   the end-of-session queued spec, which can go stale; the 1-element `queue` stops being the authority).
2. The receipt is surfaced as a plain-language decomposition ("serving TRANSFER: `lead_with_what_you_
   refuse_to_do` is forming, held only on the pricing problem; this aims it at licensing. Retention: not
   due. Uncertainty: moderate.").
3. The user **accepts** (run) or **redirects** (choose another frame/problem). A redirect is **honored
   and logged** to `selection_log` (evidence: what the user thinks they need).

**Core promote/demote (thin cut):** surface a demote candidate (a core frame untouched and unreferenced
by the ledger) or a promote candidate (a decayed concept that keeps surfacing in active problems) as a
receipt for the user to decide. Rich crystallization deferred.

## 9. Persistence / schema / types

- `frames`: `+ evidence_count INTEGER`, `+ breadth_json TEXT`. PRAGMA-guarded `ADD COLUMN`; old rows →
  `evidence_count=0, breadth=[]`. Fresh-DB + old-DB regression (L-8).
- New `trap_gallery` table (frame/trap code, experience_id, occurred_at, detail) — persist what's
  currently computed then dropped.
- New `selection_log` table (timestamp, proposed frame/problem/drive, receipt_json, accepted|redirected,
  chosen frame/problem) — the audit trail.
- `types.py`: `FrameStrength` extension; a structured `Selection` (frame, problem, drive, receipt) and
  `Receipt` (per-term contributions); `NextExperienceSpec` uses `ledger_ref` meaningfully and carries the
  drive/receipt (or a parallel `Selection` is threaded — decided in the Project 2 plan).

## 10. Decomposition — three implementation projects (build #1 first)

1. **Learner-model substrate.** `FrameStrength` extension; estimator redesign (evidence/breadth/earned
   strength); `frame_uncertainty` + staleness helpers; decay wired; schema + migration; persisted
   `trap_gallery`. **No selection-behavior change yet** — a shim derives the legacy `weak>forming>strong`
   from the richer model so the existing scheduler keeps running unchanged. The only orchestration touch
   is a one-line `decay_due_frames(state, now)` call at `run_session` start; it fires **only on elapsed
   staleness** (`due < now`), so the existing same-session tests — which set `due=now`, no elapsed time —
   stay green, and decay gets its own dedicated tests. Fully testable state-in/state-out. This is the
   foundation and the first writing-plans target.
2. **Value-function policy.** `scheduler` rewrite (3 drives + cold-start load penalty, reads the content
   graph); selector honors `(frame, problem)`; `progression.yaml`. Swaps the placeholder sort.
3. **Receipt + redirect surface.** `orchestration` propose→accept/redirect; redirect logging; core
   promote/demote candidates.

This spec captures the whole architecture; **writing-plans produces the Project 1 plan only.** Projects
2–3 get their own plan cycles (re-entering brainstorming if their details need refining).

## 11. Testing (TDD throughout, each project)

- **Substrate:** evidence accumulates; `strong` needs 2 unprompted × 2 problems (and is reachable);
  decay demotes one bucket *keeping* evidence/breadth (reversible); `frame_uncertainty` monotone in
  evidence/breadth/staleness; migration on fresh AND old DB; trap_gallery round-trips; the legacy-shim
  keeps the current scheduler/orchestration tests green.
- **Policy:** each drive in isolation; cold-start penalty dominates at high uncertainty then relaxes;
  transfer fires only on forming + new-problem + content-exists; content-gap surfaces; deterministic
  tie-break; the policy picks the expected `(frame, problem)` on crafted states.
- **Surface:** propose→accept→run; redirect honored + logged; receipt decomposition correct;
  promote/demote candidate surfaced on crafted evidence.
- **Invariants throughout:** conclusion-agnostic (no drive reads a conclusion); the judgment loop and
  the cs path stay byte-stable; confidentiality (`data/` untracked); no `Co-Authored-By`.

## 12. Risks / open items

- **Weight tuning is empirical.** The value-function weights/thresholds are first guesses; the dogfood
  (user-zero over a semester) is how they get calibrated. `progression.yaml` makes this a content edit.
  Logged redirects are the calibration signal.
- **Content thinness bounds transfer.** With only a few authored experiences, transfer fires rarely; the
  policy must surface that gap rather than degrade silently. Real breadth needs more authored content
  (a separate content effort, related to the mined-case-library idea).
- **Uncertainty is a heuristic, not a posterior.** We approximate "what the system doesn't know" with a
  monotone blend, not a calibrated probability. Sufficient to drive selection; not a claim of calibration.
- **The legacy shim (Project 1) must be genuinely behavior-preserving** — the existing scheduler reads
  the derived `strength`, so deriving the same buckets from the richer model is the compatibility
  contract, verified by keeping every current scheduler/orchestration test green.
- **`strong` becoming reachable changes state trajectories** — frames can now reach `strong`, which the
  current scheduler routes to the decay branch. Project 1's shim must preserve today's observable
  behavior; the new routing is Project 2's concern.
