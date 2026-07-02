# Chained Sittings — bounded engine sessions inside one continuous thread — Design

Date: 2026-07-01
Status: design (founder-stated vision). 3-lens adversarial review RUN (SOUND-WITH-FIXES) — all 6 must-fixes
FOLDED (MF-1 same-day-grind guard [EMPIRICALLY proven: a 12-segment same-day chain re-serves the identical
problem from segment 9 — within-sitting the clock freezes retention_due≡0/staleness≡0 so rotation dies], MF-2
exception-safe next-top, MF-3 crash-safe honest auto-pick, MF-4 store-leak reap, MF-5 honest mid-segment exit,
MF-6 Continue lifecycle). Awaiting founder review → writing-plans.
Related: user-owned closure (built); Earned Landing (built); the valley-as-homepage vision (future — this is
the near-term bridge); beta feedback "short convergent sessions feel like friction."

## 1. The vision (founder-stated)

The engine's session stays convergence-bounded (one problem, one clean diagnostic, one house). The USER's
experience becomes continuous: after a convergence lands, they can just keep going in the same thread — a new
bounded session starts under the hood, another house is built "unawaringly" — until they choose to end, at
which point the village reveals with however many houses this sitting earned. **"Session" is the engine's
concept; "sitting" is the user's.** End session appears at the FIRST convergence and persists, inert, until
clicked. This resolves the beta tension: flow-lovers get a long sitting of clean segments; beat-lovers stop at
any landing; the ledger gets proper houses either way; the 3-hour-chat amnesia never returns.

## 2. Goal & scope

**In scope:** the in-thread continuation flow (segue + Continue affordance), server-side session chaining
(new engine session per segment, same thread), End-anytime semantics across segments, terrain timing (reveal
only at the true exit), signal-integrity guardrails. Voice/web layer; **engine byte-untouched**.

**Out of scope:** the valley-as-homepage (future); sitting-level close synthesis (the close mirrors the final
segment — residual §6); any cadence-model change; multi-user. **Honesty correction (MF-1): the ENGINE's cadence model is untouched,
but the user-experienced cadence is NOT — within a sitting the clock is effectively frozen (same-day
retention_due≡0, staleness_term≡0), so the policy CANNOT rotate a just-worked item away; an unguarded
one-click chain re-serves the identical problem (proven empirically at segment 9+ of a simulated chain). The
chaining layer therefore carries its own repeat guard (§3b).**

## 3. The design

### 3a. The seam (UI, `index.html`)

On `done` (unchanged: landing bubble renders, End control revealed in the composer and STAYS for the rest of
the sitting):

- A new inline **Continue affordance** renders after the landing: a button
  `Continue → {next_title}` (a clean `display_title`, never a ref) plus a smaller `other doors…` link.
  **MF-6 (lifecycle):** the affordance FOLLOWS the conversation — after each converse reply it re-renders at
  the thread bottom (the prior instance is removed), so it is never stranded in scrollback; on click it
  disables and freezes the composer (mirroring the End guard) until the new opening `say` arrives; a converse
  request in flight completes before a continue is issued. Layer split is DELIBERATE: proceed = a one-tap
  in-thread door; exit = the sticky composer control — the composer row never gains a Continue button
  (served-shell assertion; the row already holds input+Send+End at mobile widths).
- **Typing still = converse** on the just-landed session (unchanged wind-down). The Continue button is the
  explicit "next door" — no ambiguity between reflecting and proceeding.
- Continue → `POST /api/session/{sid}/continue` → the reply is the NEW session's opening `say`; the thread
  just keeps appending; `mode` flips back to `'engine'`. `other doors…` → same endpoint with `{"menu": true}`
  → the menu renders INLINE in the thread (existing `renderMenu`), then the normal choose flow.
- **No terrain between segments** ("unawaringly"): the only inter-segment beat is the landing text + the
  Continue affordance. Two-phase timing per segment is preserved by construction — the next segment's read
  starts clean.
- End click (any time after the first convergence) → `/close` → the close + the FULL village (all houses,
  including this sitting's — terrain projects from persisted state, so accumulation is automatic).

### 3b. Server chaining (`session_runner.py`, `app.py`)

- **`done` payload gains `next_title` (+ server-held ref):** after `run_session` returns, the worker computes
  the next top proposal by running the PURE policy over the RETURNED post-session state (`propose_open_ended(
  state, exps, load_progression(), now).problem_menu()`), stores the ranked refs server-side (the
  `last_menu_refs` discipline — never on the client payload), and puts the top TITLE on the payload. Zero
  model calls; `display_title` is the menu's existing clean surface. **MF-2 (exception-safe, ordered):** this
  block runs INSIDE the worker's `try`, after `run_session`, BEFORE `finally: store.close()` (it needs no
  store), and is wrapped in its own `try/except` — "empty menu" is an EXCEPTION path in this codebase
  (`select_next` raises `ValueError` on no candidates; `Proposal.top` raises `IndexError`) — any failure sets
  `next_title=""`/no refs and the payload stays `kind:"done"` (never `error`). `app._emit`'s `done` branch
  passes `next_title` through explicitly. **MF-1 (the same-day-repeat guard, chaining-layer, engine
  untouched):** the registry keeps the set of refs CONVERGED this sitting; the auto-pick candidate is the
  highest-ranked proposal NOT in that set — if every proposal repeats, `next_title=""` (the user can still
  use `other doors…` or End). Offline test: a real multi-segment same-day chain never auto-picks a repeated
  ref while alternatives remain.
- **`SessionRegistry.continue_session(sid, menu: bool)`:** starts a NEW engine session on the same sid and,
  for the one-click path, internally does `start()` → (menu) → `step(menu_index(offered_ref))` → returns the
  opening `say` (two queue round-trips; `menu=True` stops after the menu for the inline picker). **MF-3
  (crash-safe + honest):** `menu_index` raises `ValueError` when the offered ref is absent from the new
  session's menu (e.g. the `ledger_ref` dedup collapses entries) — on that path the registry does NOT
  silently substitute door 0 (the button's title would lie and `selection_log` would record an accept the
  user never saw): it returns the MENU inline instead. Auto-pick of the ref the button NAMED keeps
  decide/selection_log semantics intact (`Outcome.accepted`, consent via the titled button). **MF-6
  (idempotency):** a per-record `continued` flag makes continue idempotent per segment — a double-click
  cannot spawn two workers/split-brain the sid.
- **End-anytime across segments:** the registry keeps the LAST CONVERGED record at registry level
  (`_last_record[sid]`, updated on every convergence) so `/close` and `/converse` work even mid-segment.
  **MF-5 (honest mid-segment exit):** when the CURRENT channel is non-terminal with `record is None` (an
  in-flight segment exists past the last convergence), `/close` does NOT author the mirrored close (it would
  reflect the PREVIOUS problem while the user's current turns vanish — a felt betrayal): it returns a short
  ENGINE-FREE static sign-off ("You stepped away mid-problem — here's the village you built.") plus the
  terrain from the last converged record. No model call. **MF-4 (reap the abandoned worker):** a mid-segment
  continue/close otherwise leaks an OPEN store connection (the parked worker's `finally` never runs —
  distinct from the post-`done` abandon, whose worker already exited). On replacing/closing over a live
  channel, the registry puts a sentinel poison-pill on the OLD channel's `to_worker`; `present`'s collectors
  and `respond` check for it and raise a private `_Abandoned` exception, which the worker swallows (no error
  emission — the channel is orphaned) so `finally: store.close()` runs and the thread exits.

### 3c. What the engine sees (signal integrity — load-bearing)

- Each chained segment is a **byte-clean engine session**: fresh `run_session`, fresh worker `recent=[]`,
  fresh intake on the user's OWN opening for the new problem. The thread's prior bubbles exist only in the
  browser; they never enter any graded call. The bridge-transparency property is per-segment and unchanged.
- The segue is **not model-authored** (it is UI copy around a `display_title`), so it introduces no egress
  surface and can never name a move for the new problem (L-13 holds trivially).
- The cadence/value-function model still decides what is OFFERED (the proposal). Chaining changes only how
  cheaply the user can accept it — spaced-retention scheduling is untouched.

### 3d. End control semantics (founder-stated)

- End appears at the FIRST convergence of the sitting and **persists inert** across all subsequent segments
  (engine mode included) until clicked. Clicking mid-segment closes from the last converged record (§3b).
- Before the first convergence, End is hidden (nothing to close) — unchanged from today.

## 4. Moat / invariants

- **Engine byte-untouched:** `orchestration.py`, `assessment/`, graded methods — empty diff. The next-top
  proposal reuses the same pure scheduler functions the worker's `decide` path already exercises.
- **L-13:** the Continue affordance carries only `display_title`s (the menu's existing clean surface); refs
  stay server-side (`last_menu_refs` pattern). No new model-authored surface.
- **Two-phase timing:** per segment — no terrain until the sitting's true exit; the landing remains the only
  inter-segment beat.
- **Signal purity:** fresh intake per segment on the user's own opening; no cross-segment dialogue enters
  graded calls; selection_log records every segment's accept/redirect exactly as today.

## 5. Testing

- **Offline (structural):** the `done` payload carries `next_title` (FakeModel flow); `continue_session`
  auto-picks the offered ref (arc restart proven via a `concierge_turn` spy across BOTH segments — the
  counter is not observable on the payload); `continue_session(menu=True)` returns a menu; the absent-ref
  path returns a MENU, never a silent door-0; the double-continue path is idempotent (one worker);
  End-mid-segment returns the STATIC sign-off + last-converged terrain (no mirrored close, no error) and
  the abandoned worker's store is closed (the sentinel reap); a raising/empty proposal yields `done` with
  `next_title=""` (never `error`); the same-day-repeat guard: a real multi-segment chain never auto-picks a
  converged-this-sitting ref while alternatives remain; **a fresh-db two-segment chain ends with terrain
  reflecting BOTH houses (hard behavioral gate)**; L-13: `next_title` has no `veldra:`, ranked refs never
  reach a client payload (parallel to the menu-titles test). Bridge-transparency per segment unchanged.
- **UI (served-shell assertions):** Continue button + `other doors…` render on `done` when `next_title`
  non-empty; omitted when empty; End persists across `mode==='engine'` after first convergence.
- **Health smoke:** documented launch; a chained FakeModel sitting (converge → continue → converge → End)
  through the HTTP API.

## 6. Honest residuals

- **The close mirrors the FINAL converged segment,** not the whole sitting (converse turns on earlier
  segments don't reach it). A sitting-level synthesis is a future increment; the terrain already tells the
  whole sitting's story.
- **An abandoned mid-segment leaves a parked worker thread** (existing abandon behavior, daemon threads; one
  per abandoned segment). Bounded by user behavior; a worker-reaping follow-up belongs to multi-user
  hardening.
- **The auto-picked continuation is always the TOP non-repeated proposal** — a user who always clicks
  Continue never sees other doors unless they use `other doors…`. Deliberate (minimal seam tax).
- **First segment starts from the menu; later segments auto-continue** — a deliberate asymmetry (a chosen
  cold-open vs flow continuation), not an inconsistency.
- **Within-sitting repeat guard is by CONVERGED refs only** — a plateaued/abandoned problem may legitimately
  be re-offered (it was not banked).

## 7. Files touched (voice/web only)

- `src/retnovation/web/session_runner.py` — next-top proposal at `done` (+ ranked refs server-side);
  `continue_session`; registry-level `_last_record`; `/converse`+`/close` read it.
- `src/retnovation/web/app.py` — `POST /api/session/{sid}/continue` (+ `_emit` passes `next_title`).
- `src/retnovation/web/static/index.html` — Continue + `other doors…` affordances; End persistence across
  segments; mode machine.
- Tests: `tests/test_session_runner.py`, `tests/test_web_api.py`.

## 8. Doctrine carried in

Engine byte-untouched; L-13 (titles only, refs server-side, no new authored surface); two-phase timing per
segment; signal purity per segment (fresh intake, clean recent); user-owned closure extended to user-owned
continuation; cadence doctrine untouched (the policy still proposes; the user still disposes).
