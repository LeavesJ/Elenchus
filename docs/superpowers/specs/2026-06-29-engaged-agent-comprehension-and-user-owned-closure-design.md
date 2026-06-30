# Engaged agent — comprehension/grounding gear + user-owned closure (+ terrain at the close)

Date: 2026-06-29
Status: design, pending implementation plan
Builds on: `2026-06-29-concierge-engaged-agent-mvp-design.md` (the Concierge fronts the byte-untouched engine).
Reuses: `2026-06-28-uiux-cartographer-design.md` (terrain projection + the non-invertibility gate).
Lessons in force: L-13 (frame-blind surfaces), L-20 (call-count is the latency lever), L-12 (verify against merged code), L-15 (trust per-finding verification over synthesis), L-19 (`PYTHONPATH=src`).

All code references below were ground-truthed against the merged tree by a 10-way read-only
verification pass and then an adversarial 3-lens spec review (moat/L-13, architecture/invariants,
scope/ambiguity) — both before this revision. Findings are folded in (§13 records them).

## 1. Problem — the founder's dogfood critique

The Concierge fix worked: Vera now tracks the user's words and the engagement regression is gone.
But a real session — the `irreversible_anchor` problem (a baked-in trust anchor that cannot be
rotated), where the user answered with an elaborate **gene-editing / stem-cell analogy** and never
engaged the actual decision — exposed a deeper, **stance-level** failure. Seven observations,
two clusters, one root.

**Cluster A — the withhold-and-push mechanic fails on a confident / off-track user.**
1. **Follows the user into the wrong frame instead of re-grounding.** Probes 2–3 climbed back into
   the fantasy. "Ground in the user's words" *reinforces a wrong model* when the words are a fantasy.
2. **No comprehension-repair gear.** The doctrine assumes the user is in the real problem-space and
   just reasons poorly. It has no path for "the user has misread the PROBLEM itself."
3. **Reads as DODGING + DUMB-AT-DOMAIN (the deepest bug).** Withholding only feels like a *wise
   teacher* if the user trusts the agent understood them. It withholds **without first demonstrating
   understanding**. **Cardinal sin:** at turn 5 the user said *"I don't think you're understanding my
   anchor"* — the one job there was to STOP and prove comprehension; it barreled into the next push,
   *confirming* "you don't understand me."
4. **Prompt altitude too abstract for a cold user.** Moat-protecting vagueness gave no foothold and
   *invited* the fantasy.
5. **Ended unresolved; the close mirrored the fantasy back.** It named the real gap while accepting
   "stem cells as your anchor" — half-validating the misread.
6. **The diagnostic signal is corrupted.** A user who *misunderstood the problem* is graded as if
   they *reasoned within it*, poisoning the progression data we want to display.

**Cluster B — control (pace + closure) belongs to the USER, not the engine.**
7. **The engine unilaterally closes the session.** It hit its internal "done" and terminated
   **mid-argument**. The composer is hidden on `done` — the user literally cannot continue.

**Root.** We built a faithful diagnostic *instrument* and wrapped it in chat. A *product* must
(a) **earn the withhold** by demonstrating it understood the person, (b) **repair comprehension**
when they are off-track instead of pushing a wrong model, and (c) **hand pace + closure to the
person**. "The engine drives, the user rides" must reverse: **the user drives, the engine serves.**

## 2. Decision

**Reverse the stance from the outside.** Every fix lands in the **voice/Concierge layer**
(`content/prompts/*` + `model.concierge_*` + `web/voice.py`) and the **session-loop/UI seam**
(`web/session_runner.py`, `web/app.py`, `web/static/index.html`), plus a small **view-layer**
hardening to `terrain.py`/`types.py`. The **judgment engine stays byte-untouched** (§7); the
bridge-transparency equivalence test stays green; the moat (L-13) holds because every new behavior
reflects only the **user's own material**, never the hidden move.

Six settled decisions (founder-chosen during brainstorm), plus the terrain addition:

- **D1 — Anchor:** layer on the intact engine; move the byte-untouched *engine* line only if proven
  necessary. (It is not — closure is achieved layer-only; §5.)
- **D2 — What the gear reflects:** the user's underlying **concern, re-pointed to the concrete
  problem** (mirror intent, drop the analogy, re-ground). Frame-blind.
- **D3 — Gear rhythm:** the **first model-authored response turn** (after the user's opening reply)
  **fuses reflect-then-withhold** — demonstrate understanding before the first withhold lands —
  then push crisply. Two reactive triggers: **hard stop on explicit challenge**, **re-anchor on
  detected off-track**. (Turn 0 is the scenario, not a withhold; see §4.)
- **D4 — Opening altitude:** **concretize in the voice layer** — a new `voice.open(model, exp)`
  authors a vivid, specific scenario (frame hidden), replacing the current static opening string.
- **D5 — Closure + read:** **freeze the diagnostic read at convergence; the user owns the exit.**
  The engine's "done" becomes an internal signal; the Concierge keeps the conversation alive
  (frame-blind, no grading) until the user ends. The read reflects the learner's cumulative state
  as of this convergence (§6).
- **D6 — The close:** an **honest, frame-blind sign-off** (authored at user-close from the full
  dialogue) that reflects where the user landed without ratifying a wrong model; a fuller read only
  if the user asks.
- **D7 — Terrain at the close:** re-surface `project_terrain().learner_view()` as the visual payoff
  of the user-owned close (no longer premature — D2/D3/D5 de-corrupt the signal), with the
  non-invertibility hardening §6 specifies.

## 3. Architecture

```
 Browser (chat thread) ──HTTP──▶ FastAPI app (app.py) ──queue──▶ worker thread (session_runner)
        ▲                          │  /say → reg.step (UNCHANGED; terminal-guarded)   │
        │  say / done(terminal)    │  /converse → reg.converse  ┐                     ▼
        │  converse / close+terrain│  /close    → reg.close     │       run_session(...) [ENGINE — UNTOUCHED]
        │                          │                            │        • objective selection + grading
        │                          ▼                            │        • conclusion-agnostic
        │                  SessionRegistry                      │   present()/respond() ← bridge seam (web)
        │                   • _Channel per sid (live worker)    │                            │
        │                   • SessionRecord per sid ◀───persist (BEFORE done + store.close)──┘
        │                       exp(+rubric, server-side only), recent(live), frozen state, terrain
        │                  CONCIERGE (voice.py): open/turn/converse/close — egress on EVERY visible turn
        │
        └── on user "End session": author close from record.recent → close bubble → terrain element
```

Two seams change, both web-only:

- **The turn seam (Cluster A).** `concierge_turn(problem, push, recent)` already receives problem +
  full dialogue + the engine's safe push and nothing from the rubric (verified frame-blind). The
  gear is a **prompt-doctrine change to `content/prompts/concierge.md`** — no new inputs, no extra
  per-turn model call (L-20). Plus a new `voice.open` author for the concrete turn 0 (§4).
- **The closure seam (Cluster B).** The engine thread **dies at convergence** (verified: `assess`
  breaks its loop on `converged` before the next `respond`; the worker queues `done`, sets
  `ch.terminal=True`, runs `store.close()` in `finally`, and exits). Post-convergence conversation is
  served **engine-free** from a persisted `SessionRecord`, via registry methods that never call
  `step()` (§5).

## 4. Cluster A — the comprehension / grounding gear

A doctrine change to `content/prompts/concierge.md`, detection folded into the existing
`concierge_turn` call, plus a new `voice.open` for turn 0.

1. **Concrete opening (D4, obs #4) — needs a new author.** Today turn 0 is a *static* string the
   worker emits (`exp.prompt + _INVITE` in `present`, session_runner.py:76) — not model-authored.
   To concretize *in the voice layer* (the founder's choice over a content rewrite), `present` calls
   a new **`voice.open(model, exp)`** that authors a vivid, specific scenario, **drawing its
   specifics from the problem text only — never the rubric**, frame hidden. Flat egress
   (`egress_safe_reply`); fallback to the static `exp.prompt + _INVITE` on refusal/empty/leak, so the
   foothold never silently collapses without notice (covered by an @live "opening performs no move"
   assertion, §9).
2. **Front-loaded understanding (D3, obs #3 root).** The **first model-authored response turn**
   (after the user's opening reply) **reflects the user's concern before/fused-with the first
   withhold** — trust before friction. Turn 0 carries no withhold (the user hasn't spoken yet).
   Thereafter, push crisply.
3. **Two reactive gears, frame-blind:**
   - **Re-anchor on off-track (obs #1).** If the reply substitutes an analogy / leaves the concrete
     problem, the turn **mirrors the underlying concern, drops the analogy, and re-points to the
     concrete problem** — not Socratically pushing the fantasy. Detection is frame-blind: did the
     reply engage *this* problem, or substitute its own object? (Judgeable from problem text + reply.)
   - **Hard stop on explicit challenge (obs #3 cardinal sin).** On *"you're not understanding me,"*
     the turn spends itself on **restate-and-confirm** — holding the push — before anything else.

**What "demonstrate understanding" means (D2, the razor's edge).** Reflect the user's underlying
*concern/intent* and re-point it at the concrete problem — never restate the analogy as if correct
(obs #5's error). Shape: *"You want an anchor nothing can quietly tamper with — so look at this
specific one: [concrete detail]"* — proves comprehension, re-grounds, endorses nothing.

**Why L-13-safe.** The Concierge sees only problem + dialogue + the engine's safe push; reflecting
the user's *own* words names no move. The engine still grades the raw reply against the canonical
push (transparency intact); the gear only changes how the turn is *voiced*. The egress backstop
(`voice.turn`/`voice.open` → `_performed` → batched `screen_moves`) gates every gear turn.

## 5. Cluster B — user-owned closure (engine-free, layer-only)

The engine thread **dies at convergence**, and `ch.terminal=True` makes every subsequent
`reg.step()` short-circuit to `("error", …)` (session_runner.py:141; guarded by
`test_step_after_done_returns_error_and_does_not_hang`). That guard stays **exactly as-is** — the
worker really is dead. Post-convergence lives on a separate, terminal-guard-free path:

1. **Persist a `SessionRecord` BEFORE the worker exits (normative ordering).** The worker writes a
   record into `SessionRegistry` — `{exp (full Experience incl. rubric), recent (the dialogue),
   frozen state, projected hardened terrain}` — **before it queues `done` and before
   `store.close()`**, so the record is live the instant the client first sees `terminal:true`. The
   record **retains the rubric server-side** (the converse/close egress `_performed` → `screen_moves`
   needs `exp.rubric…frame_detail`) and is **never serialized to the client**. The worker no longer
   pre-authors the close (it moves to step 4).
2. **`done` no longer closes the visible session.** `_emit`'s done branch returns
   `{"kind":"say","terminal":true, …}` (or a dedicated kind) **without** hiding the composer. The
   frontend, on `terminal:true`, switches to **converse mode** (problem selection disabled, composer
   stays open, an explicit **"End session"** affordance) and **routes subsequent input to
   `/converse`, not `/say`**. The static "Your read is recorded." copy and the `showComposer(false)`
   call in the current done-branch (index.html:71) are removed.
3. **Post-convergence turns are served engine-free.** A new endpoint `POST /api/session/{sid}/
   converse` calls a new registry method `reg.converse(sid, text)` — which **never calls `step()`
   and never consults `ch.terminal`** — that reads the record and calls a new
   **`voice.converse(model, exp, recent, user_text)`**. `converse` authors a frame-blind continued
   turn from problem + dialogue only (no push; engine-free), **reuses the `_BLANK_NUDGE` blank-input
   guard** at the HTTP boundary (same D1 400-brick risk), is **egress-backstopped** (flat
   `egress_safe_reply`, fallback `SAFE_CONTRACT`), appends both turns to `record.recent`, and
   **mutates no state and never invokes `run_session`/judgment**. Post-convergence is **unbounded**
   (the user owns pace).
4. **The user owns the exit.** "End session" calls `POST /api/session/{sid}/close` →
   `reg.close(sid)` (also `step()`-free), which authors the honest close from `record.recent` (the
   *full* dialogue, including post-convergence turns) and returns `{"kind":"close", "close":…,
   "terrain":…}` (terrain from the frozen record). The frontend renders the close bubble, then the
   terrain element.

**The close (D6, obs #5).** `voice.close(model, exp, recent)` → `concierge_close(problem, recent)`
(no push param; substance comes from the dialogue) authors a short sign-off that **honestly reflects
where the user landed without ratifying a wrong model and without naming the move**, voicing the
substance of the gap as it surfaced in the dialogue, e.g. "you stayed with the analogy and didn't
engage the concrete decision about X." Flat egress; fallback `_STATIC_CLOSE` on refusal/empty/leak.

**Read on ask (D5/D6).** The `close` endpoint receives the user's final message; a **frame-blind
intent check** (folded into `concierge_close`, no rubric input) decides whether to emit a *fuller
read*. The fuller read is still authored by `concierge_close` **from `recent` only**, routes through
the **same `egress_safe_reply`/`_STATIC_CLOSE` backstop**, names no move, and reflects only dialogue
material — identical L-13 rule to every other surface.

## 6. Terrain at the close

The visual payoff of the user-owned close, reusing the Cartographer machinery.

- **Cumulative, frozen at this convergence; rendered at user-close.** `project_terrain(state, now)
  .learner_view()` runs on the converged `state` — which is the learner's **cumulative cross-session
  state** after this session's assessment is folded in (`run_session` → `STATE_UPDATERS` →
  `store.save_state`), not a session-local read. The ≥2-problems gate uses cross-session `breadth`,
  so a region can light from frames accreted across *different* sessions — desired. "Frozen at
  convergence" means *this session's contribution* is final at convergence (post-convergence
  conversation never grades). Stored in the record at convergence; rendered only when the **user**
  ends.
- **The element.** After the close bubble: regions as **anonymous glowing nodes** sized/lit by
  bucketed vitality, plus a forward note — *"a seed was planted — it grows as you work more"* when
  young; *"N areas have taken shape"* when regions render. A first session legitimately shows a
  sparse seed (the cross-session gate); the note frames it forward.

**The moat — gate holds; the wire surface is hardened (L-13 / L-15).** The non-invertibility *gate*
(`region_clears_guard`: `≥2 frames AND ≥2 problems`, else seed/`vitality=None`, terrain.py:10-16)
works as designed — a rendered region always **blends ≥2 frames**, so its vitality can never be read
back to one move. That blend, **not** any coarseness, is the load-bearing defense. But terrain has
**no egress backstop** — structural non-invertibility is its only defense — and the adversarial
review found three on-wire leak vectors `learner_view()` must close:

- **Frame-derived `region_id`.** `region_id` is currently `abs(hash(tuple(comp))) % 100000` zero-
  padded (terrain.py:61) — a deterministic function of the frame set. **Fix:** `region_id` carries
  **no frame information** (an opaque token / per-view ordinal assigned *after* render order is set).
- **Frame-order-derived position.** Regions are projected in `sorted(frames)` order (terrain.py:21)
  and `regions_to_view` sorts by `region_id` (terrain.py:72); a naïve ordinal would re-encode the
  secret frame codes' alphabetical order as node position. **Fix:** order the wire list by the
  **public bucketed vitality** (frame-independent tiebreak), so neither id nor position is a function
  of the secret frame set, and the order is **stable across repeated `learner_view()` calls** on the
  same view.
- **Raw-float `vitality`.** The exact mean over `_VITALITY={0.2,0.6,1.0}` leaks the strength
  distribution. **Fix:** emit a **coarse bucket** (level count chosen for the renderer, §12) — an
  improvement, not the load-bearing defense (the blend is).

**Accepted residual (honest, like §8).** The **number** of rendered nodes and its **growth across
sessions** leaks the coarse *shape* of rubric coverage. The ≥2/≥2 gate prevents single-move
inversion but does not bound count. For the MVP (narrow library, single learner) this is an
**accepted residual**, enumerated in the non-invertibility test as a known-uncovered channel; a
future option is to cap/coarsen node count.

This hardening edits `terrain.py`/`types.py` — a small **view-layer** change. The judgment *engine*
stays byte-untouched (§7); this is an explicit, review-justified deviation from "terrain.py
untouched."

## 7. Invariants that must not drift (verified anchors)

- **Engine byte-untouched** (corrected paths): `orchestration.py`, `assessment/judgment_loop.py`,
  and the Model methods `classify_intake` / `generate_push` / `classify_response`. (The web egress
  uses the batched `screen_moves`, **not** `check_injection_expressed`; `check_injection_expressed`
  is the lift harness's screen-of-record and is unrelated to the new converse/close surfaces.)
- **Bridge transparency:** `test_runner_assessment_equals_direct_run_session` stays green.
  Post-convergence conversation is engine-free and mutates no state, so it cannot perturb the
  assessment by construction.
- **L-13 frame-blind:** the gear/open/converse/close reflect only the user's own words; terrain
  renders only `learner_view` + the ≥2/≥2 gate + the opaque-id / public-order / bucketed-vitality
  hardening + its test.
- **Egress everywhere:** every visible turn — `open`, `turn` (probe/re-invite/re-anchor/hard-stop),
  `converse`, `close` — routes through `voice.py`'s `_performed` / `egress_safe_reply` screen,
  fallback `SAFE_CONTRACT`/`_STATIC_CLOSE`.
- **L-20:** the **gear** adds no extra call on the existing diagnostic per-turn path. `voice.open`
  (one call at session start) and `voice.converse` (one call per post-convergence turn) are *new,
  inherent* interactions, not added calls on the diagnostic path — not a regression of the latency
  lever.
- **Confidentiality:** no `veldra:` refs and no rubric on the wire; the `SessionRecord` holds the
  rubric server-side only.
- **State semantics:** state is frozen at convergence; post-convergence never grades or mutates it.

## 8. obs #6 — honest mitigation, not a cure

The gear re-anchors off-track users *before* they drift further, so problem-confusion is far less
likely to be graded as the diagnostic gap; freeze-at-convergence keeps the read honest; and the
≥2/≥2 gate means a *single* corrupted reply can never light a region. **Residual, stated plainly:**
an off-track reply already graded *before* the re-anchor is not retroactively un-graded — the engine
grades each raw reply as it arrives. Trajectory grading absorbs the recovery, but the signal is not
perfectly clean. Perfect cleanliness would require touching the engine's grading, which is out of
scope (D1). A guard test (§9) pins that the mitigation (re-anchor fires on an off-track reply) does
not silently regress.

## 9. Validation plan

- **Re-dogfood the original failure** — the `irreversible_anchor` gene-editing-analogy session — and
  feel each fix: concrete opening, front-loaded understanding, re-anchor instead of fantasy-push,
  hard-stop on *"you're not understanding me,"* composer-stays-open, honest non-validating close,
  terrain payoff. (`PYTHONPATH=src .venv/bin/python -m retnovation.web`.)
- **@live** (extends the current 7): concrete opening performs no move (real foothold, not silent
  fallback); front-loaded understanding; re-anchor on off-track; hard-stop on explicit challenge; no
  move leak; no fantasy-validation in the close.
- **Offline:**
  - **Terrain non-invertibility test** (concrete): `learner_view()` payload keys are exactly
    `{region_id, render, vitality}`; `region_id` matches the opaque/ordinal form (not the hash);
    `vitality ∈` the bucket set; **order-independence** — permuting/renaming input frame codes does
    not change the wire ordering in a frame-recoverable way; **stable order** across repeated
    `learner_view()` on the same view; and an explicit comment that node-count/accretion is a known
    residual.
  - **Engine-free converse:** `reg.converse` leaves `state`/assessment untouched and never invokes
    `run_session`/judgment; `reg.converse`/`reg.close` succeed on a session whose worker thread has
    provably exited; **and `step()` still errors after `done`** (the two paths coexist).
  - **Closure UI/wire:** user-owned close renders close → terrain from the record; **flip**
    `test_web_api.py::test_full_session_and_l13_surface` (currently asserts `"terrain" not in r` at
    line 51 → assert terrain *present* + frame-blind); converse blank-input nudge + `SAFE_CONTRACT`
    fallback.
  - **Gear guard:** a test that re-anchor / hard-stop behavior is exercised (@live acceptable) so
    obs #6's mitigation can't silently vanish.
  - **Unchanged-green:** `test_runner_assessment_equals_direct_run_session`,
    `test_step_after_done_returns_error_and_does_not_hang`.

## 10. Out of scope (deliberate)

A persistent / openable "your terrain" view (future — needs stable opaque ids); capping the node-
count side channel; an explicit problems-worked counter; the `cs_technical` regime on the web (a
separate phase); any change to the judgment engine's grading or termination logic.

## 11. File-by-file change map (grounded in §verification + §review)

- `content/prompts/concierge.md` — the gear doctrine: concrete-opening guardrail (specifics from
  problem text only), front-load understanding, reflect concern re-pointed to the problem, re-anchor
  on off-track, hard stop on explicit challenge.
- `content/prompts/concierge_close.md` — honest non-validating close; read-on-ask (frame-blind,
  dialogue-only).
- `src/retnovation/web/voice.py` — new `open(model, exp)` and `converse(model, exp, recent,
  user_text)` (both egress-backstopped, engine-free); `close` authored at user-close time.
- `src/retnovation/web/session_runner.py` — `present` authors turn 0 via `voice.open`; on
  convergence, persist the `SessionRecord` (exp+recent+frozen state+terrain) into the registry
  **before** queuing `done`/`store.close()`; new registry methods `converse(sid, text)` and
  `close(sid)` that do **not** call `step()` / consult `ch.terminal`; the `step()` terminal guard is
  untouched.
- `src/retnovation/web/app.py` — `_emit` done returns `terminal:true` (no composer-hide); new
  `/converse` and `/close` endpoints with the `_BLANK_NUDGE` guard on `/converse`; enumerated wire
  kinds: `{kind:'say', terminal:true}` (done), converse `{kind:'say'}`, `{kind:'close', close,
  terrain}`.
- `src/retnovation/web/static/index.html` — converse mode (composer stays, selection disabled), "End
  session" affordance, route post-`terminal` input to `/converse`, drop the `done`-branch
  `showComposer(false)` + "Your read is recorded." copy (line 71), terrain renderer on the close
  response.
- `src/retnovation/terrain.py` / `src/retnovation/types.py` — opaque frame-independent `region_id`,
  public-vitality wire ordering (stable per view), bucketed wire vitality; `regions_to_view` sort key
  updated off the id.
- `tests/` — the §9 set: @live gear/opening tests; terrain non-invertibility test; engine-free
  converse + coexistence-with-terminal-guard tests; flipped deferred-terrain assertion; converse
  blank/fallback; gear guard.

## 12. Open risks / notes

- **Desync vs coherence.** The engine marches its objective while the Concierge adapts; the gear
  widens this (re-anchor / hard-stop turns may not advance the push). Safety is unaffected (egress +
  transparency); coherence is a soft property to watch in dogfood.
- **Vitality bucket count** must still read as "sized/lit by vitality" in the UI; pick the count with
  the renderer in view (no moat consequence — the blend carries it, §6).
- **Record memory.** The `SessionRecord` (with rubric) lives server-side for the session's lifetime
  on a long-lived single-session server — acceptable for the MVP; revisit for multi-user.
- **ANTHROPIC_API_KEY** in `.env` is flagged for rotation (2026-06-22); unrelated to this work.

## 13. Review trail (what the adversarial pass changed)

3 lenses, all "ship-with-fixes" (decisions sound, build-readiness gaps). Folded in: **[critical]**
terrain wire-ordering leak → opaque id + public-vitality order + order-independence test (§6);
**[critical]** converse vs the terminal guard → separate `step()`-free registry methods + endpoint,
guard untouched (§5); **[important]** record store + persist-before-exit made normative (§5);
terrain is cumulative cross-session, not session-local (§6); D3/D4 disambiguated, `voice.open` added
for turn 0 (§4); read-on-ask mechanism specified (§5); converse blank-guard + fallback + unbounded
(§5); §9 test gaps closed. **[minor]** engine module paths corrected, `check_injection_expressed`
vs `screen_moves` clarified (§7); count/accretion residual stated honestly (§6); bucketing not
over-claimed (§6); wire kinds + frontend line-71 edits enumerated (§11). The six decisions did not
change.
