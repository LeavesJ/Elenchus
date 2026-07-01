# Earned Landing — the post-convergence wind-down + felt arrival — Design

Date: 2026-07-01
Status: design (root cause confirmed by recon; approach is the founder-chosen "earned landing" scope, a subset
of the SESSION_HANDOFF "woven stance modulation + earned landing" thread). Awaiting 3-lens adversarial review
→ founder review → writing-plans.
Related: SESSION_HANDOFF §OPEN DESIGN THREAD; DEVLOG 2026-06-29 engaged-agent "honest residuals" (the
converse-reuses-the-withhold-gear residual, flagged "watch in dogfood"); `web/voice.py`, `model.py`.

## 1. The problem (confirmed root cause, not a hypothesis)

A founder dogfood: the user converged on a pricing decision (named + committed "12 for 12"; Vera even said
"Twelve for twelve, planted"), then Vera **kept interrogating in circles** — several turns later re-demanding
*"you still haven't named the number"* (which was already named) — and the **"End session" button appeared
abruptly** at convergence. Two defects, both **voice-layer** (the engine is byte-untouched and correct — the
recon verified `_select_target`/`generate_push`/`classify_response` are **never** called after `done`):

1. **The circling.** Post-convergence, `web/voice.py:converse()` calls `turn(model, exp, "", …)` — an **empty
   push**, which routes to the RE-INVITE branch. `model.concierge_turn` then hands the model the brief
   *"The student has not taken a real position yet — acknowledge what they said and invite one."* So after
   convergence the code **literally instructs Vera that the user hasn't committed** → she re-demands a position
   they already gave. Compounded: `_render_turns` truncates to the **last 6 turns**, so the committed answer
   ages out of view and nothing counterbalances the "invite a position" instruction. And `voice_craft.md` (the
   invariant craft on every turn) carries the full press/re-anchor/withhold gear with **no wind-down** — so
   converse interrogates **indefinitely**.
2. **The abrupt End.** `index.html` shows the End button the instant `done` arrives, with **no closing beat
   before it** (the honest `close()` synthesis is deferred to `/close`, i.e. only after the user clicks End).
   Convergence produces a bare affordance, not a felt landing.

## 2. Goal & scope

**Goal:** when the engine converges, the dialogue **arrives** instead of circling — Vera acknowledges the
*movement* the user made, names the *crux* frame-blind, and lets it land; the End affordance follows that felt
beat; and if the user keeps talking, Vera **winds down** (never re-demands a position, never re-opens settled
ground). Voice-layer only; **engine byte-untouched.**

**In scope (founder-chosen "earned landing"):** the felt landing at `done`; the converse wind-down; a wider
post-convergence dialogue window so the committed answer can't age out; the End button tied to the landing;
honesty by stop-reason.

**Out of scope (the fuller thread, deferred):** within-session stance modulation across the *whole* arc
(press → acknowledge movement mid-session → crux) and the web-inferred coarse arc-position signal. This spec
lands the *ending*; the mid-session "hope to end" modulation is a follow-up.

## 3. The design

Three voice/web-layer pieces. New authoring modes are **separate task prompts** (like `concierge_close`), never
added to `voice_craft.md` — the invariant craft is prepended to *probe* turns too, and a landing/wind-down
stance there would leak into mid-session probing.

### 3a. The landing at `done` (felt arrival)

When the worker sees the engine finish (`session_runner` worker, after `run_session` returns and `ch.record` is
frozen — **web-layer, post-assessment, transparent**), author a **landing turn** and carry it in the `done`
payload; the UI shows it as Vera's turn, then the End affordance.

- **New `voice.land(model, exp, recent, stop_reason, posture) -> str`** → **`model.concierge_land(problem,
  recent, stop_reason, *, voice)`** with a new **`content/prompts/concierge_land.md`**. Egress-backstopped
  (flat), fallback a static landing (§3d).
- **Landing doctrine (`concierge_land.md`), honest by stop-reason:**
  - **converged:** acknowledge the *movement* they made (frames closed, the trade-off reckoned) — **never
    whether they're right (L-4)**; name the **crux** (the hard part of the decision) **in their own terms,
    never the move (L-13)**; and let it rest — e.g. *"you've reckoned with the real trade-off and its cost;
    there's no clean answer, and now you know why."* Do **not** ask for a position; do **not** re-open settled
    ground; do **not** grade the conclusion or hand a resolution (L-5).
  - **plateau / budget / regression / bounded_error_violation:** land **honestly** — name where the reasoning
    actually got to and what's still open, without pretending they arrived ("this is as far as this session
    goes; the piece you kept circling is X"). No forced verdict (L-16 spirit: don't claim an arrival the work
    didn't make).
- The landing sees the **full converged dialogue** (§3c), so it references the *actual* arrival, not a 6-turn
  tail.

### 3b. Converse winds down (kills the circling)

`voice.converse()` stops routing through the RE-INVITE `turn(push="")`. New path:

- **`model.concierge_converse(problem, recent, *, voice)`** with **`content/prompts/concierge_converse.md`**:
  *"The diagnostic has converged — the student has taken and committed a position and reasoned the core
  trade-off. Respond to what they now say. Do NOT ask them to take a position again; do NOT re-open settled
  ground; do NOT restart the interrogation. If there's nothing left to press, say so plainly and let it rest —
  a real person who's satisfied the point is made."* Frame-blind, one move per turn (inherits `voice_craft`'s
  variety + comprehension tools, which stay valid), egress-backstopped, fallback `SAFE_CONTRACT`.
- `voice.converse` becomes: `text = model.concierge_converse(exp.prompt, recent+[("student",user_text)],
  voice=v); return SAFE_CONTRACT if (not text or not egress_safe_reply(...)) else text`.

### 3c. Keep the committed answer in view

`model._render_turns` gains a `limit: int | None = 6` param (default preserves every existing caller
byte-for-byte). The **post-convergence** callers (`concierge_land`, `concierge_converse`) pass a wider window
(the full frozen `recent`, or a generous tail e.g. 20) so the committed position + the arc stay visible and Vera
cannot forget what was decided. Probe turns (`concierge_turn`) keep the 6-turn default unchanged.

### 3d. The End button follows the landing (UI)

`index.html` `advance()`: on `r.kind==='done'`, first **render the landing turn** (`r.landing` — a Vera bubble),
*then* `showComposer(true)` + `endButton()`. So the beat is: converge → Vera lands it → the End affordance
appears under a felt arrival. `/close` (End click) is unchanged — it still serves the closing synthesis +
the **terrain reveal** (the world payoff). Two distinct beats: the **dialogue lands** at convergence; the
**world reveals** when the user chooses to end. (Static fallbacks: `_STATIC_LAND` for the landing;
existing `_STATIC_CLOSE` for the close.)

## 4. Moat / invariants (load-bearing)

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, the three graded model methods —
  empty diff vs `main`. The landing is authored in the worker **after** `run_session`/assessment (transparent);
  `test_runner_assessment_equals_direct_run_session` stays green.
- **L-4 (never grade the conclusion):** the landing rewards *movement/arrival/rigor*, never "you got it right."
- **L-13 (never name the move):** the crux is named in the user's own terms / world idiom, never the frame.
  Every landing + converse turn is **egress-backstopped** (`egress_safe_reply` / `screen_moves`) exactly as
  today; on leak/empty/refusal → the static fallback.
- **L-5 (disband rules):** no handing the answer, no naming the frame, no softening, no removing effort. The
  landing is honest ("no clean answer"), not validating.
- **Two-phase timing unchanged:** terrain still only at `/close`. The landing is *dialogue*, at convergence.

## 5. Testing

- **Structural (FakeModel / offline):**
  - `voice.converse` no longer calls the re-invite path: assert it routes to `concierge_converse` (not
    `concierge_turn(push="")`) — e.g. a FakeModel records which brief/method was used.
  - `_render_turns(recent, limit=None)` returns the full dialogue; `_render_turns(recent)` unchanged (6).
  - The `done` payload carries a `landing` string; `app._emit`/`index.html` shape includes it.
  - Existing no-leak/L-13 web assertions extended to the landing + converse turns (no `frame_code`/`veldra:`).
- **@live (key-gated):** after convergence, (a) the landing acknowledges arrival + names a crux **without**
  re-demanding a position and **without** naming the move; (b) a follow-up converse turn does **not** re-open
  settled ground / re-demand a position; (c) a non-converged stop (plateau/budget) lands **honestly** (no false
  "you arrived"). The existing engagement / no-name / no-leak moat suite stays green.
- **Regression:** the exact dogfood shape — user commits a number, keeps talking — no longer loops back to
  "name the number."
- **Health smoke:** documented launch boots; `/api/health`, `/`, close flow intact.

## 6. Honest residuals

- **Model-authored, fallback-guarded.** The landing/converse are Anthropic-authored; on refusal/empty/leak they
  fall back to static text (a landing that's safe but generic). The *quality* of the felt arrival is a live
  behavior — verified @live + dogfood, asserted structurally offline (fakes can't judge tone).
- **Within-session modulation still deferred.** This lands the ending; the mid-session "press → acknowledge
  movement → crux" arc (the fuller handoff design) is a follow-up. If the ending-only landing doesn't make the
  session *feel* like it has "hope to end" throughout, that thread is next.
- **Stop-reason honesty depends on the record carrying `stop_reason`.** `ch.record` already freezes the
  assessment; the landing reads `assessment.stop_reason`. If a stop reason is missing/unknown, the landing
  degrades to the honest-generic fallback, never the false-arrival text.

## 7. Files touched (all voice/web-layer; engine untouched)

- `content/prompts/concierge_land.md` (new), `content/prompts/concierge_converse.md` (new).
- `src/retnovation/model.py` — `concierge_land`, `concierge_converse`, `_render_turns(limit=…)`.
- `src/retnovation/web/voice.py` — `land(...)`, rewrite `converse(...)`, `_STATIC_LAND`.
- `src/retnovation/web/session_runner.py` — author + carry the landing in the `done` payload (worker,
  post-assessment).
- `src/retnovation/web/app.py` — `_emit` passes `landing` through on `done`.
- `src/retnovation/web/static/index.html` — render the landing before the End affordance.
- Tests: `tests/test_web_api.py`, `tests/test_voice*.py` (structural), `@live` suite.

## 8. Doctrine carried in

Conclusion-agnostic (L-4); never name the move (L-13); judgment-loop disband rules (L-5); no forced verdict
(L-16 spirit — honest by stop-reason); engine byte-untouched (load-bearing); egress backstops every visible turn.
