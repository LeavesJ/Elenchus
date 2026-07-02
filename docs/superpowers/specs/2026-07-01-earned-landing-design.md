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

When the worker sees the engine finish (`session_runner` worker, **after** `run_session` returns and the
assessment is frozen), author a **landing turn** and carry it in the `done` payload; the UI shows it as Vera's
turn, then the End affordance. **Authoring is strictly downstream of the frozen assessment and never re-enters
any graded call** (the session is terminal — `ch.terminal=True` — so there is no path back into the engine).

- **`stop_reason` availability (review-corrected):** the landing is authored **in the worker, where the live
  `assessment` (hence `assessment.stop_reason`) is in scope** — `ch.record` does *not* carry the assessment.
  For symmetry + the wind-down (§3b), **also persist `"stop_reason": assessment.stop_reason` into `ch.record`**
  so the converse continuation stays convergence-aware. (Corrects §6's earlier draft.)
- **`voice.land(model, exp, recent, stop_reason, posture) -> str`** → **`model.concierge_land(problem, recent,
  stop_reason, *, voice)`** with a new **`content/prompts/concierge_land.md`**. **The egress screen is
  load-bearing here:** `voice.land()` applies `egress_safe_reply(model, exp, text)` in the worker and returns
  `_STATIC_LAND` on leak/empty/refusal — **exactly as `voice.close()` does** (voice.py:85-86). Raw model text
  MUST NOT reach the `done` payload unscreened.
- **The landing is the *felt, in-the-moment arrival* — short, present-tense** ("you've landed it"), a distinct
  beat/register from the retrospective `/close` synthesis (§3d).
- **Landing doctrine (`concierge_land.md`), honest by stop-reason — with the hard prohibitions the egress
  screen CANNOT enforce:**
  - **The egress screen backstops L-13 (performing a move) but is BLIND to L-4 (grading the conclusion)** — an
    author can say "you got the call right" while naming no frame, and `screen_moves` passes it. So
    `concierge_land.md` MUST carry (like `concierge_close.md`'s explicit prohibitions): **(i) a hard "do NOT
    grade, score, validate, or pass any verdict on the conclusion — reward the reckoning, never the answer"
    line (L-4);** and **(ii) a worked contrast — name the crux *in the user's own concrete terms* (GOOD: "the
    hard part is the thing protecting you is the thing you can't take back") vs. *naming the move/frame* (BAD:
    restating the principle they were meant to find) (L-13).** The crux is the closest-to-the-line turn in the
    product; the prompt gets an operational test, not just the abstract rule.
  - **converged:** acknowledge the *movement* (frames closed, the trade-off reckoned) — never whether they're
    right; name the crux **in their own terms**; let it rest — e.g. *"you've reckoned with the real trade-off
    and its cost; there's no clean answer, and now you know why."*
  - **plateau / budget / regression / bounded_error_violation:** land **honestly**, with the same
    **anti-flattery discipline as `concierge_close.md`**: if they never took a real position on the concrete
    choice (stayed in an analogy, flailed to `budget`), **say that plainly — do NOT manufacture an "arrival
    narrative" or imply they were "circling a real thing"** when they weren't. No forced verdict (L-16 spirit).
- The landing sees a **bounded wider window** (§3c), so it references the *actual* arc, not a 6-turn tail.
- **Strictly the `done` path:** if the worker throws (`error`, not `done`), no landing fires — correct, no gap.
  `captured` (hence a coherent `recent`) is always populated when `done` fires (`present()` sets it before
  `run_session` returns), so the landing never authors over an empty dialogue.

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

`model._render_turns` gains a `limit: int = 6` param (default preserves every existing caller byte-for-byte —
verified: `concierge_turn`/`concierge_close`/`classify_entry` all call it with no second arg). The
**post-convergence** callers (`concierge_land`, `concierge_converse`) pass a **bounded wider window
(`limit=20`)** so the committed position + the arc stay visible and Vera cannot forget what was decided, while
capping growth if a user converses for many turns. Probe turns (`concierge_turn`) keep the 6-turn default.

### 3d. The End button follows the landing (UI)

`index.html` `advance()`: on `r.kind==='done'`, first **render the landing turn** (`r.landing` — a Vera bubble),
*then* `showComposer(true)` + `endButton()`. So the beat is: converge → Vera lands it → the End affordance
appears under a felt arrival. `/close` (End click) is unchanged — it still serves the closing synthesis +
the **terrain reveal** (the world payoff). Two distinct beats: the **dialogue lands** at convergence; the
**world reveals** when the user chooses to end. (Static fallbacks: `_STATIC_LAND` for the landing;
existing `_STATIC_CLOSE` for the close.)

To avoid a **dull echo** when End is clicked right after the landing (0 converse turns), the two beats keep
**distinct registers**: the **landing** is the in-the-moment felt arrival (short, present-tense, "you've landed
it"); the **close** is the retrospective synthesis tied to the terrain reveal (the world payoff).
`concierge_close.md` gains a one-line steer toward that retrospective/world register so it never merely
re-voices the landing.

## 4. Moat / invariants (load-bearing)

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, the three graded model methods —
  empty diff vs `main`. The landing is authored **strictly downstream of the frozen assessment and never
  re-enters any graded call**; the `done` payload gains an **additive** `landing` key, so
  `test_runner_assessment_equals_direct_run_session` (which reads `assessment` by key) is unaffected.
- **L-4 (never grade the conclusion):** the landing rewards *movement/arrival/rigor*, never "you got it right."
  **The egress screen does NOT catch L-4** (it screens performed moves, not verdicts) — so the *only* backstop
  is `concierge_land.md`'s explicit prohibition (§3a) and the @live "no evaluative verdict" assertion (§5).
- **L-13 (never name the move):** the crux is named in the user's own terms / world idiom, never the frame.
  Every landing + converse turn is **egress-backstopped** (`egress_safe_reply` / `screen_moves`) — for the
  landing this runs inside `voice.land()` in the worker *before* the text reaches the `done` payload; on
  leak/empty/refusal → the static fallback.
  **AMENDED 2026-07-01 (founder call, live evidence):** the FLAT screen killed every good landing 3-for-3
  (the crux mirror inevitably touches the move's territory; the judge is noisy on borderline mirrors — it
  flagged a landing whose flagged sentence was a near-verbatim mirror of an unflagged student sentence). The
  landing's gate is now **added-revelation vs the STUDENT's own dialogue** (it may perform only moves they
  already performed — you cannot hand someone what they already hold), with **one retry** under a
  no-mechanism steer before the static fallback. See `voice.land`/`_RETRY_STEER`.
- **L-5 (disband rules):** no handing the answer, no naming the frame, no softening, no removing effort. The
  landing is honest ("no clean answer"), not validating.
- **Two-phase timing unchanged:** terrain still only at `/close`. The landing is *dialogue*, at convergence.

## 5. Testing

- **Structural (FakeModel / offline):**
  - `voice.converse` no longer calls the re-invite path: assert it routes to `concierge_converse` (not
    `concierge_turn(push="")`) — e.g. a FakeModel records which brief/method was used.
  - `_render_turns(recent, limit=20)` returns up to 20 turns; `_render_turns(recent)` unchanged (6).
  - The `done` payload carries a `landing` string; `app._emit`/`index.html` shape includes it.
  - Existing no-leak/L-13 web assertions extended to the landing + converse turns (no `frame_code`/`veldra:`).
- **@live (key-gated):** after convergence, (a) the landing acknowledges arrival + names a crux **without**
  re-demanding a position, **without** naming the move (L-13), and **without any evaluative verdict on the
  conclusion** — no "right/correct/well done/score" (L-4, the assertion the egress screen cannot make); (b) a
  follow-up converse turn does **not** re-open settled ground / re-demand a position; (c) a non-converged stop
  (plateau/budget), and a user who never engaged the concrete choice, lands **honestly** — no false "you
  arrived" and no manufactured "arrival narrative". The existing engagement / no-name / no-leak moat suite stays green.
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
- **Stop-reason source (review-corrected).** The landing reads `assessment.stop_reason` from the **live
  `assessment` in the worker** — `ch.record` does NOT carry the assessment (only model/posture/exp/recent/
  terrain). §3a **adds `stop_reason` to `ch.record`** so the wind-down (`converse`) can also stay
  convergence-aware. If a stop reason is ever missing/unknown, the landing degrades to the honest-generic
  fallback, never the false-arrival text.

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
