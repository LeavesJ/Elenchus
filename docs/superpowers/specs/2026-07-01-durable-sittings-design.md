# Durable Sittings — the sitting survives reloads and restarts — Design

Date: 2026-07-01 (late)
Status: design, built from the founder's failed chained-sitting dogfood report. 3-lens adversarial
review RUN (doctrine / concurrency-state / UX-honesty) — ALL must-fixes and accepted should-fixes
FOLDED below (see §8 for the review ledger). Ready for writing-plans.
Related: chained-sittings spec (2026-07-01, built @ 76009e1); user-owned closure; Earned Landing;
the valley-as-homepage vision. This is the durability layer chained sittings was implicitly
promising.

## 0. The incident (root cause, evidenced — read this first)

The founder's report: "when the user chose to deliberately continue their session, it just
redirected her to a brand new session; she didn't get to see the old convo, Vera inherits no
memory of the old, and the same questions repeat."

Forensics (selection_log + process start time + commit timestamps; machine is UTC-7):

- 14:18 local — earlier dogfood accepted `concentrated_market_pricing_power` (the session that hit
  the classify brick). NOTE: 14:18 local is July 1 UTC; the evening sitting is July 2 UTC — the
  incident itself straddles UTC midnight, which drives the §2e window design.
- 19:09 / 19:19 local — the evening sitting's segments 1–2 (`license_fork_risk` accepted;
  `embedded_anchor_lock_in` via a menu redirect). **Chained Sittings did not exist in any running
  process yet** — its first code commit landed 20:15, the UI seam 20:18, final fixes 20:32. The
  19:19 "continue" was therefore the only continue the old build had: reload → cold menu →
  brand-new session, thread wiped.
- 20:54:07 local — the server was restarted (PID 98571, still running), presumably to pick up the
  new build. The restart **destroyed the in-memory sitting** (`_last_record`, `_sitting_done`,
  `_next_pick`, worker channels).
- 20:55:16 local — 69 seconds later, a fresh cold-start session accepted
  `concentrated_market_pricing_power` — the same problem as 14:18. "Same questions repeating,"
  literally.

Three-layer root cause:

1. **Incident layer:** the dogfooded continue moments never exercised the built in-thread seam
   (pre-CS process; then a state-destroying restart).
2. **Architecture layer — why the complaint stands even against the new build:** the sitting has
   no durable existence. The transcript lives only in the page DOM; the sitting state lives only
   in process memory; `POST /api/session` cold-starts unconditionally (no resume front door); the
   repeat guard is scoped to one process's one sitting. Any reload or restart reproduces the
   founder's exact experience. This is the "3-hour-chat amnesia" the vision doc promised would
   never return — returned through a different door.
3. **Voice layer (residual):** even within one unbroken process+page, the seam is cold —
   `voice.opening` is sitting-blind by construction, so a continued segment greets the user like
   a stranger.

## 1. Goal & scope

**Goal:** the sitting — the USER's continuous experience — becomes durable. A reload lands her in
the same room with the whole conversation visible. A server restart costs at most the in-flight
segment, honestly. The same problem is never *silently* re-proposed within a rolling day (the
window is 24h on real timestamps, NOT a UTC calendar day — the founder's own incident straddled
UTC midnight mid-evening; a date bucket would not have prevented it). The seam between segments is
*marked* (signage, not warmth — see the honest tally below).

**Honest tally against the founder's complaint:** transcript amnesia — fixed. Vera's
within-segment memory across restarts — genuinely fixed (converse works over the rebuilt record;
this is the sleeper win). Cross-segment *authored* memory — deliberately NOT fixed here: Vera's
opening stays cold pending the founder's §1-options decision below; option (b) segue-only
awareness is the natural next increment and is L-13-cheap.

**In scope:** web-layer persistence of the rendered transcript + sitting state (SQLite, same db
file, new tables, own module); a resume-aware front door (`POST /api/session`); registry rebuild
across restart (converse/close/continue work over the persisted landed record); a static seam
line on continued segments; rolling-24h cross-sitting dedupe for the auto-pick + honest menu
suffix; build + stale-shell hardening.

**Out of scope (unchanged / founder-gated):** engine byte-untouched (`orchestration.py`,
`assessment/`, graded methods — empty diff; `run_session` is NOT checkpointable, which is exactly
why segment-level atomicity below is the honest boundary). Sitting-level close synthesis (deferred,
founder's call). **Deep Vera cross-segment memory in AUTHORED turns** — founder picks from:
(a) none (today); (b) segue-only awareness (titles + arrival facts, no content — genuinely safer
*for a stated reason*: those facts are already user-known, so they add no primable content);
(c) sitting-scoped memory on non-graded surfaces only (converse/close) — **caution: non-graded ≠
non-priming**; anything user-visible before the next intake can prime it exactly as hard as a
probe could, so (c) still needs an overlap guard on cross-segment content; (d) full sitting memory
with a corpus-derived overlap guard. The implied safety ordering a<b<c<d is therefore false —
(c) unguarded can exceed (d) guarded. This spec ships the durability substrate all four need; it
builds none of them beyond the static seam line.

## 2. Design

### 2a. `web/sitting_store.py` (new) — the persistence module

Own module, own tables, same SQLite file (`db_path`), connections opened per operation (no shared
connection across threads; every write is one short transaction). The engine's `persistence.py` is
untouched. First open sets `PRAGMA journal_mode=WAL` (persistent — transcript reads never block
the engine writer); every per-op connection sets `PRAGMA busy_timeout=5000` and
`PRAGMA synchronous=NORMAL`. **`:memory:` db_path → the store becomes an inert no-op** (each
per-op connection would see its own empty db; the seven shell-only tests that use `:memory:` never
start sessions and keep working; durability tests use tmp files).

Tables (web namespace):

- `web_sitting(id TEXT PRIMARY KEY, status TEXT, updated_at TEXT)` — **per-sitting generated id**
  (timestamp+suffix); at-most-one-`live` enforced by a partial unique index
  (`CREATE UNIQUE INDEX ... ON web_sitting(status) WHERE status='live'`) plus the registry lock.
  `single` remains the SESSION id only — it is NOT the sitting id (a `single` PK cannot support
  close-then-new-sitting plus L-3 retention).
- `web_sitting_turn(sitting_id, seq INTEGER, kind TEXT, payload_json TEXT)` — the RENDERED
  transcript, appended in emit order. `kind` in `vera|you|muted|landing|seam`. `seq` is allocated
  SQL-side (`COALESCE(MAX(seq),0)+1` inside the INSERT's transaction, or rowid ordering) — never a
  Python counter (threadpool requests interleave). Payloads carry ONLY what the client received.
- `web_sitting_state(sitting_id PRIMARY KEY, record_json TEXT, next_pick_ref TEXT,
  next_pick_title TEXT, inflight_json TEXT, theme_json TEXT)` — the landed-segment record needed
  to rebuild converse/close/continue across restart: `experience_id`, `posture`, `recent` tuples,
  `stop_reason`, `terrain` (learner_view — already client-safe); the guarded next pick (ref
  server-side only); `inflight_json` = `{experience_id, ledger_ref}` of the CURRENT in-flight
  segment (set when its opening persists, cleared at `_on_done`) — the persisted discriminator for
  "a segment was lost." **The `continued` idempotency flag is deliberately NOT persisted** — it
  guards "a continuation is in flight *in this process*"; process liveness is a category error to
  persist (a persisted flag would brick Continue forever after a restart mid-continued-segment).
- `web_converged(sitting_id TEXT, ref TEXT, converged_at TEXT)` — converged ledger refs with full
  UTC timestamps and their sitting, appended ONLY when `stop_reason == "converged"` (F1:
  plateaued/budget/errored segments never append), NEVER deleted (L-3). Serves the rolling-24h
  dedupe across sittings, restarts, and processes.

### 2b. Write-through — at the client-payload layer, never the raw dequeue

**The projection rule (load-bearing, L-13):** persisted `payload_json` is the `_emit`-projected
CLIENT payload (share the projection, or persist the exact response fields) — never the
registry-layer tag/data. The registry's raw emits are exactly where the dirty data lives: the menu
emit carries `refs` (`veldra:` slugs) and the done emit carries raw `state`/`assessment` objects
(frame-code deltas). Those are structurally unreachable by the store: the vera/landing turns
persist text only; menus are not persisted at all (below).

The full emission/input enumeration (closed — anything not listed is NOT persisted):

- Opening / re-invite / probe / converse-reply `say` → `vera` turn (text; theme_json updated on
  theme-bearing says).
- User text into `/say` and `/converse` → `you` turn, persisted only AFTER the `_BLANK_NUDGE`
  guard and (for converse) the record-exists check — a turn the engine never saw must not replay.
- `done` → `landing` turn, only when the landing text is non-empty (mirrors the shell's
  `if(r.landing)`); `web_sitting_state` written on ANY landed stop (record_json, next_pick);
  `web_converged` row ONLY on `stop_reason=="converged"` (F1); `inflight_json` cleared.
- Continue (one-click) → `seam` turn + a `muted` "Continue → {title}" marker + the new opening
  `vera` turn — exactly what the client rendered. The internal swallowed menu (the
  `start()`→`step(idx)` hop) is never persisted (the user never saw it; persisting it would
  fabricate turns).
- `choose` → a `muted` "door chosen" marker + the chosen title as a `you` turn.
- **Unanswered menus are never persisted.** Same-process resume re-derives a pending menu from the
  LIVE channel (`ch.last_menu`); cross-restart resume serves a fresh menu. This kills the
  supersession machinery entirely.
- Worker `error` emissions are **NEVER persisted** (`repr(e)` can embed frame codes/refs — L-14's
  KeyError literally carried a frame code; a persisted error is a durable, resume-replayed L-13
  leak). If the transcript needs a marker at an errored point, persist the fixed static `muted`
  line "That door failed — it reopens fresh." Sanitizing the live error wire too is a follow-up
  ticket (pre-existing leak class).
- `nudge` is explicitly unpersisted (unreachable from the shipped shell; exists for non-shell
  clients). "Connection lost" lines are client-generated and never reach the registry — absent by
  construction.
- `close` → sitting `status='closed'`; the close text/terrain are not persisted as turns (the
  village re-serves the record's frozen `learner_view` at close, as today; each new convergence
  re-freezes it — cumulative because the ENGINE's own persisted state accumulates).
- Converse write-through **also rewrites `record_json` (recent updated) in the same short
  transaction as the vera turn** — otherwise a second restart makes Vera forget conversation
  visible on her own screen.

Write-through/render divergences, accepted and named: the client renders the `you` bubble BEFORE
posting, so a failed POST leaves a rendered-but-unpersisted turn that resume rolls back; a reload
during "thinking" misses the newest turn until the next action (the sync handler completes and
persists it — resume then shows a reply she never saw: continuity working). Single-tab
reload-during-in-flight-request races are the same family — accepted at MVP.

**The queue-handshake invariant (pin it in a worker comment):** every worker emission is dequeued
inside the HTTP request that triggered it (one `put` per consumed `get`; `done` is emitted while
the last `step()` is still blocked). Write-through therefore needs no worker-side persistence —
and any future *proactive* worker emission breaks this whole design.

### 2c. The resume front door (`POST /api/session`)

- No `live` sitting → today's behavior: cold menu (+ a new `live` sitting row). The
  check-and-create is atomic under the registry lock + the partial unique index; a racing double
  cold-start resolves to one worker (the loser resumes; a replaced non-terminal channel gets the
  poison pill).
- A `live` sitting older than **18h** (`updated_at`) is treated as abandoned: marked `closed`
  (turns retained, L-3) and the visit cold-starts. Houses are engine state — none are lost; only
  the close ceremony is skipped. A sitting is an evening, not an undying thread.
- Otherwise → `{kind:"resume", turns:[...], next_title, end_visible, mode, theme, build}`:
  - `turns`: the persisted transcript, verbatim (already-egressed text; titles only; `landing`
    renders as a vera bubble).
  - `end_visible`: true iff `record_json` exists (the segment LANDED — any stop_reason, matching
    today's End-on-done behavior; not only converged).
  - `mode`: `converse` if the tip is a landed record with no live in-flight segment past it, else
    `engine`.
  - The shell MUST set its global `nextTitle` from the payload (not from replayed landing turns,
    which render as text only — no dead buttons) so the Continue affordance survives the next
    converse re-render; it renders the transcript into a `DocumentFragment` with ONE scroll at the
    end (O(n) reflows otherwise).
  - **State machine (exhaustive).** Discriminator: `inflight_json` present = a segment is/was in
    flight past the last landing.
    1. Same-process, live worker mid-segment: queues intact — composer just works; nothing
       restarts. The common case, now free.
    2. Same-process, landed (terminal done channel): transcript + `mode:converse`, End/Continue
       as persisted.
    3. Same-process, pending menu (worker parked in `decide`): transcript + the pending menu
       re-derived from the live channel.
    4. Same-process, TERMINAL ERROR channel (errored segment): behaves as cross-restart — landed
       record → `mode:converse`; no record → honesty line + fresh inline menu. (Without this
       state the composer dead-ends into "session already ended" — the D1/D2-class brick.)
    5. Cross-restart, landed: lazy rebuild (below) → `mode:converse`, End + Continue.
    6. Cross-restart, in-flight lost (`inflight_json` set): transcript + branch-accurate honesty
       copy — landed record exists: *"The server restarted mid-problem; that door closed
       unfinished. Your conversation is saved — continue to a next door, or end to see what
       you've built."* → `mode:converse`; no record (mid-FIRST segment): *"The server restarted
       mid-problem. Your words are saved above — pick a door to keep going."* + fresh inline menu.
       If a later segment re-enters the SAME interrupted ref, the opening gains a static reopen
       variant of the invite: *"Starting this one over — restate your position, or build on what
       you wrote above."* (mechanical honesty; no model call).
    7. Cross-restart, pending menu: stale menu evaporated with the process → fresh inline menu
       (selection_log unaffected: an abandoned menu writes no row — `log_decision` runs at
       session end).
    8. Closed sitting: cold start.
  - **Lazy rebuild** (cross-restart, landed): under `self._lock`, check-and-set idempotent (two
    racing post-restart requests must not clobber each other's `recent` appends). model =
    `model_factory()`; exp = `load_library()` by `experience_id`; `recent`/`stop_reason`/
    `terrain`/`posture` from the row. `continued` initializes ABSENT (see 2a). `next_pick_ref` is
    re-validated against the rolling-24h `web_converged` window at rebuild AND at continue — a
    stale pick into a since-converged door drops to the menu (MF-3's honest path). **Rebuild
    failure** (experience id no longer resolves — restarts happen at build boundaries when the
    L-1 content library may have changed): converse/close degrade to the existing statics
    (`SAFE_CONTRACT` / static sitting close + persisted terrain) — never author unscreened, never
    500. Note the rebuilt exp is load-bearing for L-13: it carries the rubric that powers the
    egress screens.
  - **Stale-tab requests** (`/say`/`/choose`/`/converse` hitting a missing or terminal channel
    after a restart): fail SOFT with a nudge-kind payload ("This room went stale — refresh to
    pick up where you left off."), never a KeyError 500.
  - **Stale-menu clicks:** menu responses carry a server-side nonce; `choose` echoes it; a
    mismatch re-serves the current menu instead of silently opening a door the user never picked
    (selection semantics preserved; two-tab remains accepted-residual but fails closed).
- **MF-5 across restart:** `close()` consults the PERSISTED discriminator (`inflight_json`), not
  only the in-memory channel — an interrupted tail gets a static variant (*"That last door closed
  unfinished when the server restarted — here's the village you built."*) instead of authoring a
  mirrored close of the PREVIOUS problem beneath the interrupted problem's visible turns.
- **Interrupted-adjacent converse (egress blind spot):** in state 6-with-record, converse serves
  problem A's record while problem B's turns are visible and the honesty line invites discussion
  of B. The egress screen therefore checks the UNION of A's and B's moves (B's exp rebuilt from
  `inflight_json.experience_id`; one extra `screen_moves` call, only in this rare state). B was
  not converged, so it may re-offer within 24h — an unscreened converse could hand B's move and
  prime its future intake.
- **Done-never-dequeued race at close/continue:** before branching, `close`/`continue_session`
  drain `from_worker` with `get_nowait()` and run `_on_done` on a drained `done` — otherwise an
  End clicked in the window between the engine's own state commit and the `done` dequeue durably
  loses the `web_converged` row (the same-day dedupe would then re-propose a problem the engine
  banked). The residual crash window (engine-commit → `_on_done`-append) is accepted and named.
- **Posture precedence:** rebuilt surfaces use the persisted posture; the next continued segment's
  worker re-derives `aim().posture` fresh (as today) — an aim change across a restart flips
  voice/theme only at the next segment boundary, documented.

### 2d. The seam (static, non-model — signage, not warmth)

On a CONTINUED segment (one-click or other-doors), a `seam` turn renders before the new opening: a
quiet muted line — **"Same sitting — next door."** — in the same register as the menu invite (not
a Vera bubble; Vera speaks only through authors). Zero model calls, zero egress surface. It
prevents the "was I redirected?" misread and marks segment boundaries in a replayed transcript; it
does NOT warm Vera's cold opening (that is the founder-gated §1 decision).

### 2e. Rolling-24h dedupe, cross-sitting

- The auto-pick guard (`_on_done`) excludes refs with a `web_converged.converged_at` within the
  last 24 hours — read from the TABLE directly (any sitting, any process). `_sitting_done` stays
  strictly this-sitting (in-memory, unseeded) for its existing semantics and future this-sitting
  consumers; every this-sitting convergence is also in the table, so the window query subsumes it
  for the guard. F1 preserved end-to-end: only converged rows exist to exclude.
- The MENU stays intact in content and order (reordering silently corrupts proposed-vs-chosen
  selection semantics); titles converged within the window gain the plain suffix **" · just
  worked"** — a repeat becomes a visible, informed choice, never a silent re-serve. ("Worked," not
  "built": the village metaphor stays unrevealed before the first true exit. Founder may re-word.)
- When the guard leaves NO pick (`next_title=""`), the shell still renders **"other doors…"** —
  otherwise a fully-worked-today library hides both continue affordances while `continue(menu)`
  would happily serve the suffixed menu.

### 2f. Build + stale-shell visibility (incident hardening)

- `/api/health` gains `build`: best-effort `git describe --always --dirty` captured once at app
  creation (subprocess, 1s timeout, fallback `"unknown"` — never raises, works when git is
  absent).
- `build` ALSO rides the `POST /api/session` payload; the shell tucks it into `#mark`'s tooltip
  and `console.info` — one glance in the tab answers "which build am I talking to."
- `/` is served with `Cache-Control: no-store` — kills the stale-shell class structurally (the
  handoff's standing "hard-refresh the tab" warning; without this, a browser-cached shell that
  predates `kind:"resume"` renders every page load as an error line).

## 3. What the engine sees (unchanged — load-bearing)

Byte-identical graded path. Each segment remains a fresh engine session with fresh `recent=[]`;
the persisted transcript exists BESIDE the engine, never enters any graded call; the bridge
transparency property is untouched. Resume re-serves previously-egressed text — plus, on the two
restart-menu branches, a fresh standard menu (the existing L-13-clean surface). Refs, frames,
rubrics, pushes: server-side only, as today.

## 4. Testing

- **Restart simulation is the crown:** construct a NEW `SessionRegistry`/app over the same
  `db_path` (== process restart) and assert: (a) resume returns the full transcript verbatim with
  End/Continue correct (and the payload's `next_title` present); (b) converse and close work over
  the rebuilt record (honest by persisted `stop_reason`), and a converse exchange SURVIVES a
  second restart (record_json write-through); (c) continue works — the `continued` flag is
  CLEARED by rebuild (double-continue stays idempotent within a process; across a restart
  Continue works); (d) the two-house terrain gate holds ACROSS a restart; (e) mid-segment restart
  yields the branch-accurate honesty line + a usable path (landed record or fresh inline menu),
  and `close()` over an interrupted tail returns the STATIC variant, never a mirrored close of
  the previous problem; (f) the rolling-24h dedupe excludes refs converged in a PRIOR
  process/sitting within 24h (timestamps straddling a UTC date boundary included — the founder's
  incident shape), and a stale `next_pick_ref` into a since-converged door drops to the menu;
  (g) rebuild failure (unknown experience_id) degrades to statics — no 500, no unscreened author.
- **Brick regressions:** same-process errored-first-segment resume yields a usable path (no
  "session already ended" dead end); stale-tab `/say`/`/choose`/`/converse` after restart fail
  soft (nudge-kind, no KeyError); a stale menu nonce re-serves the menu instead of opening an
  unpicked door.
- **L-13 wire tests:** the resume payload and every persisted `payload_json` contain no `veldra:`
  refs and no frame codes (reuse the no-leak helpers); a worker error emission never lands in
  `web_sitting_turn` (assert on an injected raising model).
- **Same-process tests:** reload mid-segment resumes into the live worker (composer round-trip
  works); pending-menu resume re-derives the menu from the live channel; the seam turn appears
  exactly on continued segments; after resume, a converse round-trip re-renders the Continue
  affordance (global `nextTitle` restored from the payload, not from replayed landings).
- **Served-shell assertions:** `kind:"resume"` handling (DocumentFragment render, theme, End/
  Continue/mode restore); " · just worked" suffix; "other doors…" renders when `next_title` is
  empty; `Cache-Control: no-store` on `/`; `build` in health and session payloads.
- **Dedupe/F1:** plateaued segments still re-offer (no `web_converged` row); the two-house gate
  and existing CS tests stay green; `:memory:` shell tests stay green (inert store).
- Full offline suite green; engine-diff gate (`git diff -- src/retnovation/orchestration.py
  src/retnovation/assessment/`) empty. Add the resume path to the health-smoke/dogfood checklist
  (the flex-collapse lesson: served-shell string asserts can't see layout truths).

## 5. Honest residuals

- A mid-flight segment's engine progress is lost on restart — by design (the engine is not
  checkpointable and stays byte-untouched); the transcript, the branch-accurate honesty copy, and
  the reopen-invite variant preserve the user's words and dignity, not the grading.
- The seam is signage; Vera's opening remains cold — the authored, sitting-aware seam is the
  founder-gated §1 decision (option (b) is the natural next increment).
- A reload after End loses the village view until the next close — accepted MVP residual; the
  valley-as-homepage is the real fix. (Houses are engine state; nothing is ever lost but the
  ceremony.)
- The live error wire still shows `repr(e)` transiently (pre-existing); persistence excludes it.
  Sanitizing the live wire is a named follow-up ticket.
- Multi-tab concurrent resume: last-writer-wins on turns; the nonce and soft-fail paths make the
  dangerous variants fail closed. Multi-user hardening remains deferred.
- The transcript grows unbounded within a sitting; fine at MVP scale, bounded by the 18h
  staleness close.

## 6. Files touched (web layer only)

- `src/retnovation/web/sitting_store.py` — NEW: tables, pragmas, `:memory:` no-op, append/read,
  state row, converged log, all open-per-op.
- `src/retnovation/web/session_runner.py` — write-through hooks at the projection layer; resume +
  rebuild + state machine; drain-then-branch on close/continue; window dedupe; seam turn; nonce.
- `src/retnovation/web/app.py` — resume-aware `POST /api/session`; you-turn capture; nudge-soft
  fails; health/session `build`; `no-store` on `/`.
- `src/retnovation/web/static/index.html` — `kind:"resume"` rendering (fragment, nextTitle,
  mode); seam + suffix + empty-pick "other doors…"; build tuck-away.
- `tests/test_sitting_store.py` (NEW), `tests/test_session_runner.py`, `tests/test_web_api.py`.

## 7. Doctrine carried in

Engine byte-untouched; L-13 (persistence mirrors the PROJECTED wire only; errors never persisted;
refs server-side; the rebuilt exp restores the egress screens); L-4 (nothing new grades anything;
`stop_reason` remains a process signal); two-phase timing (resume never renders terrain; close
re-serves the frozen learner_view); user-owned closure (a sitting ends only at /close or the 18h
abandonment close); L-3 (converged log, closed sittings, and superseded rows retained — nothing
deleted); F1 (converged-only banking end-to-end); L-14 (error payloads can carry frame codes —
hence never persisted); L-18/L-19 launch discipline unchanged.

## 8. Review ledger (3-lens, 2026-07-01)

Doctrine lens: projection-layer write-through (MF, folded §2b); error emissions never persisted
(MF, §2b); end_visible prose fixed (§2c); converged-only `web_converged` explicit (§2a/§2b);
terrain wording fixed (§2b); supersession dropped entirely (stronger than the flag suggestion);
"worked" suffix (§2e); option-(c) priming caution (§1); interrupted-adjacent converse union screen
(§2c); converse record write-through (§2b); rebuild-failure statics (§2c); fresh-menu §3 reword;
UTC honesty (superseded by rolling window); you-turn guard ordering (§2b).

Concurrency/state lens: continued-flag not persisted + rebuild clears (MF, §2a/§2c); per-sitting
id + partial unique live index (MF, §2a); terminal-error-channel resume state + stale-tab soft
fails (MF, §2c); MF-5 persisted discriminator at close (MF, §2c); converse→record_json
write-through (MF, §2b); swallowed internal menu never persisted (§2b); error-as-static-marker /
nudge-unpersisted enumeration (§2b); done-drain at close/continue (§2c); locked idempotent rebuild
(§2c); menu nonce (§2c); atomic sitting create + poison pill on replaced channel (§2c); next_pick
re-validation (§2c); dedupe reads table directly, `_sitting_done` unseeded (§2e); empty-pick
"other doors…" (§2e); handshake invariant pinned (§2b); WAL/pragmas/`:memory:` no-op (§2a);
divergences named (§2b); posture precedence (§2c).

UX-honesty lens: rolling-24h window on timestamps, sitting-tagged (MF, §2a/§2e); continued-flag
brick (MF, dup); `_sitting_done` seeding conflation (MF, resolved via table-direct guard §2e);
MF-5 restart regression (MF, dup); branch-accurate honesty copy + reopen invite (MF, §2c);
converse record write-through (dup); 18h staleness close (§2c); village-after-End residual named
(§5); nextTitle global restore + landing-as-text (§2c/§4); no-store + build-on-payload + shell
tuck (§2f); seam-is-signage honesty (§1/§2d); suffix kept, "just worked" (§2e); fragment render +
landing→vera mapping + resume in dogfood checklist (§2c/§4); menu persistence machinery dropped
(§2b); single-tab race named (§2b/§5).
