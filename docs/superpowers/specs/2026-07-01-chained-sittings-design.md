# Chained Sittings — bounded engine sessions inside one continuous thread — Design

Date: 2026-07-01
Status: design (founder-stated vision, this session). Awaiting 3-lens adversarial review → founder review →
writing-plans.
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
segment — residual §6); any cadence-model change (the scheduler's proposal already governs what is offered
next — chaining consumes it as-is, so spaced-retention doctrine is untouched); multi-user.

## 3. The design

### 3a. The seam (UI, `index.html`)

On `done` (unchanged: landing bubble renders, End control revealed in the composer and STAYS for the rest of
the sitting):

- A new inline **Continue affordance** renders after the landing: a button
  `Continue → {next_title}` (the top proposal for the post-session state — a clean `display_title`, never a
  ref) plus a smaller `other doors…` link.
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
  the next top proposal by running the PURE policy over the post-session state (`propose_open_ended(state,
  exps, load_progression(), now).problem_menu()`), stores the ranked refs server-side, and puts the top title
  on the payload. Zero model calls; a `display_title` is already a clean surface (same as the menu). If the
  menu is empty/errors, `next_title` is `""` and the UI simply omits Continue.
- **`SessionRegistry.continue_session(sid, menu: bool)`:** starts a NEW engine session on the same sid
  (`start()` already replaces the channel) and, for the one-click path, auto-answers the new session's menu
  with the previously-offered ref (fallback: index 0 if the proposal drifted); returns the opening `say`.
  With `menu=True`, returns the new session's menu payload instead (inline picker). Auto-pick keeps the
  decide/selection_log semantics intact — the top proposal accepted = `Outcome.accepted`, exactly as if
  clicked in the picker; the user consented via the titled button.
- **End-anytime across segments:** the registry keeps the LAST CONVERGED record at registry level
  (`_last_record[sid]`, updated whenever a session converges) so `/close` works even if the user continues
  and then Ends mid-segment before the new session converges — the close/terrain serve from the last
  converged record; the unfinished segment is simply abandoned (its parked worker thread is the existing
  abandon behavior; nothing is persisted mid-session, so no state corruption). `/converse` likewise serves
  from the last converged record.

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
  starts a new session and auto-picks the offered ref (arc counter restarts at push 1 — proves a fresh
  segment); `continue_session(menu=True)` returns a menu; End-after-continue-before-convergence closes from
  the LAST converged record (terrain + close present, no error); a full two-segment chain ends with terrain
  reflecting BOTH sessions' state (fresh-db: two houses' worth of state vs one); L-13: `next_title` contains
  no `veldra:`; the segue/Continue markup carries no ref. Bridge-transparency per segment unchanged.
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
- **The auto-picked continuation is always the TOP proposal** — a user who always clicks Continue never sees
  doors 2–4 unless they use `other doors…`. Deliberate (minimal seam tax); the menu remains one tap away.

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
