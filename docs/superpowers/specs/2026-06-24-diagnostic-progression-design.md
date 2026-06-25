# Diagnostic Progression — Locating the Learner, Not Ramping Difficulty

Date: 2026-06-24
Status: design — rev. 2 (post external review, round 2); awaiting user approval before plans
Origin: the second open thread from the commitment-frame work (memory `retnovation-commitment-frame-gap`)
and the "escrow scene is a max-difficulty cold-start capstone" note. The user's reframe: progression
must **serve a purpose so the system actually understands where the learner is** — a diagnostic
instrument, not an easy→hard ramp. This is a from-scratch architecture for the selection/progression
layer. Post-MVP; the MVP harness and the commitment-frame feature are complete.

> **Rev. 1** folded in an external design review (see §13): strength is now a pure *derived* function
> of persistent evidence (no stored bucket, no decay mutation, `decay_frame` deleted); the cold-start
> gate is per-experience *max* constituent uncertainty (not a mean × frame-load); and the content-thinness
> reality, the authoring-order dependency, the endogenous-demand gap, and a richer receipt are stated
> honestly.
> **Rev. 2** (see §14) pinned the one call that sets inside Project 1: the staleness clock (the `due`
> interval, the displayed-bucket decay, and the uncertainty staleness-term) keys to the persistent
> **storage tier** (`evidence_count`+`breadth`), never the displayed bucket — acyclic and §5-faithful.
> Plus: incoherent states are unreachable via the *served* paths (not "impossible" — direct construction
> stays open), and the sole-content-frame case surfaces as a content gap, not a scorer special-case.

## 1. Goal

Replace the placeholder selection policy (`scheduler.schedule_next`'s `weak > forming > strong` sort)
with a **diagnostic progression system**: a richer learner model that represents *where the learner is*,
and a unified value-function policy that each session serves the experience which best **locates,
consolidates, or deploys** a frame — conclusion-agnostic, ledger-anchored, reversible, and auditable.
The cold-start intro-arc emerges from the same policy (it defers integrative experiences until each
constituent frame is located) rather than being a difficulty ramp.

## 2. Non-goals (YAGNI / be-mindful)

- **No easy→hard difficulty ladder.** "Scope" enters only as integration-readiness at cold start (an
  experience is deferred while any of its frames is still unlocated), never a global difficulty ordering.
- **No change to the assessment layer.** The judgment loop (and the just-shipped commitment-frame /
  stress-probe work) is the *evidence source*; it stays byte-stable. This design is about what the
  system does with the evidence and what it serves next.
- **No change to the `cs_technical` regime's scheduling.** It is checkable (correctness-scored); its
  retrieval-strength spaced repetition already answers "where are you." The value function is the
  founder/process (`open_ended`) path only. cs inherits the persisted-state plumbing, nothing more.
- **No redirect-rewrites-the-weights loop.** A redirect is honored and *logged* as evidence; **nothing
  consumes that evidence yet** (§8). Weight tuning from clustered redirects is a later, dogfood-informed
  step.
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
- **Storage vs. retrieval strength (Berkeley §5).** Forgetting is retrieval failure, not erasure.
  Persistent evidence (storage strength) is never deleted; the *derived* strength bucket (retrieval
  strength) falls with staleness and is restored on re-exposure — the savings effect, by construction.
- **Simultaneity + reversible decay.** Heavy reps *while* learning; decay is de-prioritized review,
  never deletion, and reversible (L-3).
- **Auditability over taste.** Every pick shows its work — the score decomposes into a receipt that also
  names the runner-up drive and its margin. Core promote/demote proposes candidates with receipts; the
  user decides ("propose and decide"; Complete Picture §7). No tool "wisdom."
- **Transfer is the signature move.** A `forming` frame aimed at a *different* ledger problem is the
  deploy test; breadth (cross-problem) is first-class.
- **Earned strength.** `strong` requires repeated spaced unprompted success across ≥2 problems
  (Complete Picture §17 — the current single-use heuristic is "too aggressive"), and it must be
  *reachable* (today it is dead code).
- **Doctrine as data (L-1).** Drive weights and thresholds live in `content/cadence/progression.yaml`,
  not hardcoded. Adding capability = content, not engine edits.
- **L-8 fail-loud / fresh-DB.** Every schema change works on a fresh DB and migrates the existing one;
  every state entry point is exercised by a fresh-DB regression test.
- **Core-path review.** `scheduler`, `state`, `types`, `persistence`, `orchestration` are core-path;
  each project gets an independent adversarial review before finishing.

## 4. Confirmed decisions (from brainstorming, as revised in rev. 1)

1. **Learner model = strength × breadth × uncertainty** per frame — but strength/uncertainty are
   *derived* from the persistent evidence (`evidence_count`, `breadth`, `last_seen`), not stored.
2. **Selection = one unified value function** over three named drives (reduce-uncertainty, retention-due,
   transfer-opportunity); the intro-arc emerges; the score decomposes into the audit receipt.
3. **Cold start = integration readiness.** Defer an experience while any of its constituent frames is
   still unlocated, via a **per-experience max-constituent-uncertainty** penalty. (Rev. 1 refinement of
   the brainstormed "isolation by frame-load": same intent — defer the capstone — but a strictly better
   quantity. The judgment loop already classifies per-frame, so high-load reads are attributable; the
   real reason to defer the capstone is integration readiness, not attribution.)
4. **Receipt + redirect** (fullest "propose and decide"): every pick surfaces its receipt (winning drive,
   per-term contributions, **runner-up drive + margin**); the user accepts or redirects; the redirect is
   logged as evidence (unconsumed for now); core promote/demote uses receipts + user decision.
5. **Candidate space = `(frame × ledger-problem)`** drawn from the content graph (Approach A), not
   whole-experience scoring — preserves per-frame attribution and makes transfer literal.

## 5. Architecture: the seam, the module map, the data flow

The policy seam stays `scheduler.schedule_next`, rewritten from a sort into a diagnostic value function.
Its signature grows to read the **content graph** (the gated library — each experience's frames, its
ledger problem) so it can score real `(frame, problem)` candidates. Today it hardcodes
`ledger_ref = ledger[0].id` (it never actually chooses a problem); the new policy chooses meaningfully.

| Module | Change | Why |
|---|---|---|
| `types.py` | Extend `FrameStrength` storage (+ `evidence_count: int`, `breadth: set[str]`); `strength`/`due` become *derived* values populated on read, not persisted; add `Selection`/`Receipt`; `NextExperienceSpec` carries the chosen problem + drive + receipt | the rich model + the audit surface |
| `persistence.py` | `frames` gains `evidence_count`, `breadth_json` (guarded migration, the `scene_json` pattern); the `strength`/`due` columns go vestigial (computed on load); persist `trap_gallery`; add `selection_log` | storage strength survives; retrieval strength is recomputed |
| `state.py` | Estimator updates `evidence_count`/`breadth`/`last_seen` from the assessment, anchored to the problem; `derive_strength(...)` + `frame_uncertainty(...)` compute the buckets from storage + `now`. **No decay mutation** — decay is automatic as `now` advances | fixes §17; makes `strong` reachable; savings effect free |
| `scheduler.py` | The value function: 3 drives + the per-experience max-constituent-uncertainty cold-start penalty, reading the content graph | the diagnostic policy |
| `experience.py` / `generator.py` | Selector honors the `(frame, chosen-problem)` pairing | transfer needs the right problem |
| `orchestration.py` | Thread `now` into `load_state` (read parameter, not a mutation); split propose from run: propose → receipt → accept/redirect; redirect logged | derivation needs `now`; "propose and decide" |
| `content/cadence/progression.yaml` | Drive weights + uncertainty/staleness thresholds | doctrine as data, tunable |

**Data flow, one session:**
```
load state (derive strength/uncertainty from storage + now) ─▶ policy proposes (frame, problem, drive, receipt)
                     │
   user accepts ◀────┤ user redirects ─▶ log redirect to selection_log, serve the chosen target
        │
   select experience for (frame, problem) ─▶ present ─▶ assess (judgment loop, UNCHANGED)
        │
   update storage (evidence_count, breadth, last_seen, traps) ─▶ persist ─▶ propose next
```

## 6. The learner model (`state` / `types` / `persistence`)

**Persistent storage (storage strength — never deleted):** per frame, `evidence_count: int`,
`breadth: set[str]` (the ledger problems the frame has held `present_reasoned` against), `last_seen`,
`last_evidence`. That's it. `strength` and `due` are **not stored**.

**Derived on read (retrieval strength — falls with staleness), recomputed from storage + `now`:**
- **strength** = `derive_strength(evidence_count, breadth, last_seen, now)`:
  - `strong` = ≥2 unprompted `present_reasoned` observations across ≥2 distinct problems **and** not stale
    (repeated AND cross-context — the §17 bar; reachable, unlike today).
  - `forming` = engaged with a real mechanism (≥1 evidence) but single-context / single-observation /
    only-closed-under-pressure — **or** a higher bucket that has gone stale one step.
  - `weak` = no evidence, or a frame decayed past the forming threshold.
  **Decay is the staleness term, on a storage-keyed clock.** The interval before the displayed bucket
  steps down (and before `retention_due` fires) is a function of the persistent storage tier
  (`evidence_count` + `breadth`) — **never of the displayed/decayed bucket.** This is the one wiring that
  is both *acyclic* (the bucket can't be defined by comparing staleness against a `due` that is itself
  defined from the bucket) and §5-faithful: a frame earned to `strong` keeps its *long* interval even
  after its displayed bucket falls, so it resurfaces *rarely* and springs back on one correct re-exposure
  (`last_seen = now` → staleness 0, `evidence_count`/`breadth` unchanged). Keying the interval to the
  decayed bucket would do the opposite — a stale `strong`→`forming` frame would inherit `forming`'s
  *shorter* interval and get reviewed *more* as it decays, which is the continuous review §5 says loses to
  relearning. The **uncertainty staleness-term rides the same storage-keyed clock**, so a well-earned
  frame's uncertainty also rises slowly (one spaced re-check, not a fast diagnose-driven resurfacing that
  would re-introduce the pathology through the back door). No mutation, no `decay_frame` (deleted), no
  sweep.
- **uncertainty(now)** ∈ [0,1] — monotone-high when `evidence_count` is low, `breadth < 2`, or the frame
  is stale. The diagnostic signal.

**Estimator** (`update_state`), anchored to the experience's ledger problem `p`: unprompted
`present_reasoned` → `evidence_count += 1`, `breadth ∪= {p}`, `last_seen = now`; closed-under-pressure →
`breadth ∪= {p}` at forming-grade, `last_seen = now`; failure/unmoved → neither, `last_seen = now`. The
estimator only ever *writes storage*; strength and uncertainty are computed, never written.

This is the Berkeley §5 mapping made structural: storage strength persists and is never lost; retrieval
strength is the derived bucket that falls with disuse and returns on re-exposure.

## 7. The value function (`scheduler`, `open_ended` path)

Candidates: `(frame f, problem p)` pairings with backing content. Score each:

```
V(f,p) =  wU · uncertainty(f)                         # DIAGNOSE  — dominant at cold start
        + wR · retention_due(f)                       # CONSOLIDATE — forming/strong and going stale (just-in-time before decay)
        + wT · transfer_opportunity(f,p)              # DEPLOY    — f forming AND p ∉ breadth(f) AND content pairs (f,p)
        − wL · max( uncertainty(g) for g in frames(e(f,p)) )   # INTEGRATION READINESS — defer e while any constituent is unlocated
```

- **`transfer_opportunity`** is zero unless `f` is forming and `p ∉ breadth(f)` and an authored
  experience pairs them. Where no second-problem experience exists, it can't fire and the receipt records
  "transfer blocked: content gap."
- **The cold-start penalty** is the **max uncertainty across the chosen experience's constituent
  frames** — `e` is deferred while *any* of its frames is unlocated and becomes eligible the moment its
  weakest part is located (the integration test, literal). This single quantity subsumes the old global
  mean scalar and the `frame_load` term; both are dropped.
- **argmax** with a deterministic tie-break (frame id) — no randomness; reproducible tests.
- The winning term names the **drive**; the full decomposition **plus the runner-up drive and its
  margin** becomes the **receipt**.
- **`retention_due(f)`** fires off the **storage-keyed clock** (§6): a frame is due when its staleness
  reaches the interval its storage tier earns — well-earned frames come due rarely, never more often as
  they decay.

**Sole-content-frame → a content gap, not a policy special-case.** A frame whose *only* home is a
high-load (gated capstone) experience can't be cleanly located while that experience's other constituents
are still unlocated (the max-uncertainty penalty defers it, and serving it would yield an uninterpretable
read anyway). Rather than an escape hatch in the scorer, this **surfaces as a content gap** — "this frame
has no isolated experience to locate it" — exactly like transfer-blocked-content-gap. It routes the fix
to authored content (the same effort that unblocks `strong` and transfer) and keeps the policy
principled. Once the capstone's other frames *are* located, the penalty releases and it serves the frame
as the integration test, with no special case.

Weights `wU/wR/wT/wL` and the uncertainty/staleness thresholds live in `content/cadence/progression.yaml`.

## 8. Receipt + redirect + core promote/demote (`orchestration`)

`run_session` splits "propose" from "run":
1. Session start: the policy proposes `(frame, problem, drive, receipt)` from **live** state (fresh beats
   the end-of-session queued spec, which can go stale; the 1-element `queue` stops being the authority).
2. The receipt is surfaced as a plain-language decomposition that also **names the runner-up drive and
   its margin** ("serving TRANSFER (margin 0.12 over CONSOLIDATE): `lead_with_what_you_refuse_to_do` is
   forming, held only on the pricing problem; this aims it at licensing."). A redirect against a near-tie
   is then a sharper calibration signal than one against a runaway.
3. The user **accepts** (run) or **redirects** (choose another frame/problem). A redirect is **honored
   and logged** to `selection_log`. **Nothing consumes that evidence yet** — the redirect-informs-weights
   loop is explicitly out of scope (§2); the log is for later, dogfood-informed tuning.

**Core promote/demote (thin cut):** surface a demote candidate (a core frame untouched and unreferenced
by the ledger) or a promote candidate (a decayed concept that keeps surfacing in active problems) as a
receipt for the user to decide. Rich crystallization deferred.

## 9. Persistence / schema / types

- `frames`: `+ evidence_count INTEGER`, `+ breadth_json TEXT` (PRAGMA-guarded `ADD COLUMN`; old rows →
  `evidence_count=0, breadth=[]`). The existing `strength`/`due` columns are **retained but vestigial**
  (computed on load, no longer authoritative — a clean `DROP COLUMN` needs SQLite 3.35+/table rebuild and
  isn't worth it). Fresh-DB + old-DB regression (L-8).
- New `trap_gallery` table (frame/trap code, experience_id, occurred_at, detail) — persist what's
  currently computed then dropped.
- New `selection_log` table (timestamp, proposed frame/problem/drive, runner-up + margin, receipt_json,
  accepted|redirected, chosen frame/problem) — the audit trail.
- `types.py`: `FrameStrength` carries the storage fields + the derived `strength`/`due` (populated on
  read); a structured `Selection` (frame, problem, drive, receipt) and `Receipt` (per-term contributions,
  runner-up, margin); `NextExperienceSpec` uses `ledger_ref` meaningfully and carries the drive/receipt.

## 10. Decomposition — three implementation projects (build #1 first)

1. **Learner-model substrate.** `FrameStrength` storage extension; estimator writes
   evidence/breadth/last_seen; `derive_strength` + `frame_uncertainty` compute the buckets from storage +
   `now`; schema migration (add `evidence_count`, `breadth_json`); persisted `trap_gallery`. **No
   selection-behavior change and no state mutation for decay** — decay is automatic in the derivation. The
   only orchestration touch is threading `now` into `load_state` (a read parameter). The legacy shim is
   automatic: the scheduler still reads `fs.strength`, and at same-session staleness 0 the derived buckets
   reproduce the old reachable cases, so `test_state.py` stays green; `test_scheduler.py`'s direct
   `FrameStrength(strength=…)` construction still works (the field is retained, just not persisted). This
   is the foundation and the first writing-plans target.
2. **Value-function policy.** `scheduler` rewrite (3 drives + the max-constituent-uncertainty cold-start
   penalty, reads the content graph; resolve the cold-start edge from §7); selector honors
   `(frame, problem)`; `progression.yaml`. Swaps the placeholder sort.
3. **Receipt + redirect surface.** `orchestration` propose→accept/redirect; receipt with runner-up +
   margin; redirect logging; core promote/demote candidates.

This spec captures the whole architecture; **writing-plans produces the Project 1 plan only.** Projects
2–3 get their own plan cycles (re-entering brainstorming if their details need refining).

## 11. Testing (TDD throughout, each project)

- **Substrate:** evidence accumulates; `strong` needs 2 unprompted × 2 problems (and is reachable);
  `derive_strength` steps the bucket down as staleness crosses thresholds and **restores it on
  re-exposure** (the savings effect — same evidence, `last_seen=now` → bucket back) *without* changing
  `evidence_count`/`breadth`; **the staleness clock keys to the storage tier** — a well-earned frame that
  has decayed keeps its long interval and comes due *no sooner* than (in fact later than) a thin frame at
  the same staleness, i.e. it is reviewed *less* as it decays, not more (the explicit anti-continuous-
  review test); `frame_uncertainty` monotone in evidence/breadth/staleness and its staleness-rise is
  slower for higher storage tiers; migration on fresh AND old DB; `trap_gallery` round-trips; the legacy
  shim keeps the current state/scheduler/orchestration tests green at staleness 0.
- **Policy:** each drive in isolation; the max-constituent-uncertainty penalty defers an experience while
  any constituent is unlocated and releases it once all are located; a frame whose only home is a
  multi-frame experience with other unlocated constituents surfaces as a **content gap** (not forced into
  service, not silently deadlocked); transfer fires only on forming + new-problem + content-exists;
  transfer-content-gap surfaces; deterministic tie-break; the policy picks the expected `(frame, problem)`
  on crafted states.
- **Surface:** propose→accept→run; redirect honored + logged (and nothing consumes it); receipt
  decomposition + runner-up/margin correct; promote/demote candidate surfaced on crafted evidence.
- **Invariants throughout:** conclusion-agnostic (no drive reads a conclusion); the judgment loop and the
  cs path stay byte-stable; confidentiality (`data/` untracked); no `Co-Authored-By`.

## 12. Risks / open items

- **Content thinness gates the headline behavior, not just transfer.** `strong` needs two problems and
  transfer needs a new problem, and the authored content barely supplies second problems (§12-era note).
  On today's content, almost no frame reaches `strong`, transfer rarely fires, and the system's
  *observable* behavior collapses toward "reduce uncertainty on single-problem frames, then keep them from
  decaying" — close to the placeholder it replaces. **This is expected and not a reason to hold the
  build** (build the engine right before the content exists). The honest framing: Projects 2–3 on today's
  content deliver the *plumbing* (rich state, receipts, the seam), not visibly smarter sequencing; the
  actual unlock is the authored-content effort (the mined case library). State this so Project 2 isn't
  read as underdelivery.
- **Cold-start order is the authoring order.** At cold start every uncertainty ≈ 1, so the diagnose drive
  barely ranks and the deterministic tie-break decides — i.e. authored content order *is* the cold-start
  curriculum. Fine if authoring order is deliberate, but it is a **dependency on authoring**, not the
  value function doing the work; name it, and order the authored set intentionally.
- **Revealed demand is endogenous.** `last_seen` updates only from experiences the tool *served*, so
  "live work reveals what stays warm" is not wired — what is warm is what the tool last scheduled. For a
  single-user founder whose real founding happens outside the tool, that is a genuine doctrine↔
  implementation gap. **Latent mitigation:** the Veldra *ledger* is the external-demand signal already
  flowing in (owned problems from real work); a future version could gate warmth/retention on
  ledger-referenced activity rather than tool-scheduling. Named, not closed now.
- **Weights are unaudited taste.** The receipt exposes the arithmetic but the weights in
  `progression.yaml` are judgment one level below "show your work." The runner-up-and-margin in the
  receipt (§8) is the cheap partial fix; full calibration comes from the logged redirects over the
  dogfood.
- **Uncertainty is a heuristic, not a posterior.** A monotone blend, not a calibrated probability.
  Sufficient to drive selection; not a calibration claim.

## 13. Revision 1 — what the external design review changed

1. **Strength: stored → derived.** §6/§9 originally treated `strength` as both a persisted field and a
   derived value, with decay mutating the stored bucket — a contradiction. Now strength (and `due`) are
   pure functions of persistent `{evidence_count, breadth, last_seen}` + `now`, computed on read. This
   deletes `decay_frame`, removes the planned decay-sweep mutation, makes incoherent states unreachable
   **through the served paths** (`load_state` derives, `update_state` writes only storage) — direct
   `FrameStrength(strength=…)` construction stays open for tests, the seam the shim leans on, so the
   served path must never set strength directly — and gives the Berkeley §5 savings effect for free.
   Project 1 shrinks.
2. **Cold start: mean × frame-load → per-experience max constituent uncertainty.** A mean conflated
   "uniformly half-known" with "half located, half blank"; the integration test needs *its own* frames
   located. Max-constituent-uncertainty states that directly and subsumes the global scalar and the
   `frame_load` proxy. The §4.3 rationale was corrected from "attribution" (the loop already classifies
   per-frame) to "integration readiness." Added the sole-content-frame edge for the Project 2 plan.
3. **Content honesty.** Connected `strong`-starvation to the same content thinness as transfer; stated
   that Projects 2–3 on current content deliver plumbing, with the authored-content effort as the unlock.
4. **Smaller seams.** Named the cold-start-order = authoring-order dependency; named the endogenous-
   revealed-demand gap (with the ledger as the latent external signal); enriched the receipt with the
   runner-up drive + margin; stated plainly that redirect evidence is logged but unconsumed.

## 14. Revision 2 — the Project-1 pin and two tightenings

1. **The staleness clock keys to the persistent storage tier, never the displayed bucket** (§6, §7). Rev. 1
   left "derived from `{evidence_count, breadth, last_seen}`" true under two wirings. Keying the `due`
   interval / decay thresholds to the *displayed* (decayed) bucket is circular (bucket ← staleness-vs-`due`
   ← bucket) and produces continuous review (a stale `strong`→`forming` frame inherits the shorter
   interval and is reviewed *more* as it decays — exactly what §5 says loses to relearning). Keying them to
   the **storage tier** (`evidence_count`+`breadth`) is acyclic and is the savings effect: a well-earned
   frame keeps its long interval as its display falls, resurfaces rarely, springs back on one re-exposure.
   The **uncertainty staleness-term rides the same storage-keyed clock** (else the diagnose drive would
   resurface well-earned stale frames on a fast clock and re-introduce the pathology). This is the one open
   call that sets inside Project 1; it is now pinned.
2. **"Incoherent state impossible" → "unreachable via the served paths."** Accurate boundary: `load_state`
   derives and `update_state` writes only storage, so the served path can't produce an incoherent
   `FrameStrength`; but `test_scheduler` constructs `FrameStrength(strength=…)` directly on purpose (the
   shim seam), so the field stays settable. The Project 1 plan states this boundary and the rule: the
   served path never sets strength directly.
3. **Sole-content-frame → a content gap, not a scorer special-case** (§7). A frame whose only home is a
   gated capstone (with other unlocated constituents) surfaces as a content gap — "no isolated experience
   to locate this frame" — the same mechanism as transfer-blocked, routing the fix to authored content,
   instead of an exclude-from-max / floor-`wU` escape hatch in the policy. Once the capstone's other frames
   are located, the penalty releases and it serves the frame as the integration test, no special case.
