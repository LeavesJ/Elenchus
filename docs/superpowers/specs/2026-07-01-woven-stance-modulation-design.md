# Woven Stance Modulation — the within-session press → acknowledge → narrow arc — Design

Date: 2026-07-01
Status: design (founder-approved direction: author-judged movement + free worker arc-hint; implicit
tone-easing only; craft fixes bundled). Awaiting 3-lens adversarial review → founder review → writing-plans.
Related: the Earned Landing (built — this is the deferred other half of the 2026-06-30 "woven stance
modulation + earned landing" decision); `content/prompts/voice_craft.md`; `web/voice.py`; `web/session_runner.py`;
DEVLOG 2026-07-01 (the felt dogfood that confirmed the gap).

## 1. The problem (dogfood-confirmed, 2026-07-01)

A full founder session was diagnostically sharp but **felt like an interrogation, not an interaction**:
across five engine-path probe turns there was **zero acknowledgment** of genuinely strong moves (quantified
bargain math, a real segmentation, a necessity thesis). Every acknowledgment beat in the session lived in the
NEW Earned-Landing surfaces (wind-down "You've got the rest", the door comment, the close) — the mid-session
probe path has none. Compounding craft defects, same dogfood: turns stacking 2–3 questions; the dismissive
"Fine." tic (3×); the same point pressed twice in a row (the last probe demanded the ceiling; the landing
re-named it). The result is the known "no positive-progress channel" treadmill: even a user reasoning well
gets nothing back until the very end, and nothing mid-session signals that the process has an arc and an end
("no hope to end").

## 2. Goal & scope

**Goal:** the session should *feel* like it is going somewhere while it happens — press hard early, give
**earned** (never rhythmic) recognition when the user genuinely moves, and physically ease/narrow as the arc
approaches its end, so convergence arrives as a felt trajectory rather than an ambush. Voice-layer only;
**engine byte-untouched**.

**In scope:** a stance-across-the-arc doctrine in `voice_craft.md` (probe turns); a free, frame-blind arc
hint threaded from the worker into the probe author's brief; the craft bundle (one question per turn, no
dismissive tics, no immediate re-press); offline plumbing tests + `@live` behavioral tests.

**Out of scope:** any UI/visual arc indicator (founder chose implicit tone-easing only); changes to the
landing/converse/close stances (built, own doctrines); the door/re-invite path (pre-engine, no arc); any
engine or terrain change; explicit position markers ("that's my last angle") — implicit easing only.

## 3. The design

### 3a. The stance arc (doctrine, `voice_craft.md` — probe turns only)

A new section, slotted after "How you speak", governing the press across the diagnostic arc:

- **Early arc (pushes 1–2): full friction.** Press hard and cold; no warmth owed; the contract is the press.
- **Earned movement acknowledgment (anywhere in the arc):** when the student's LATEST reply genuinely moved —
  conceded a cost, named a number, dropped a hedge, took the harder fork of their own dilemma — open the next
  press with ONE clause that names that movement **in their own concrete terms**, then press on. When the
  reply merely restates, defends, or decorates: **no warmth — silence on the progress channel is a signal
  too.** Never acknowledge two turns running out of politeness; recognition that fires every turn is noise.
- **The L-4 boundary (hard, worked):** acknowledgment DESCRIBES the movement, never RATES it or the person,
  and never passes a verdict on the conclusion.
  - GOOD (describes, their terms): "You've stopped defending the number and started pricing what it costs
    you when it's wrong — so take the next step: …"
  - BAD (rates / verdicts): "Good — exactly right." / "Now you're getting it." / "That's the correct frame."
- **Late arc (per the brief's arc line — push 3 onward, easing progressively; sessions rarely run past 5
  even though the cap is 8):** turns get SHORTER; open **no new fronts**;
  narrow toward the single most alive tension in the student's own words. The press eases in shape, not in
  honesty — a late turn is one tight question, not a lecture and not a fresh interrogation lane. Position is
  never stated to the student.

### 3b. The arc signal (plumbing — free, frame-blind, engine-untouched)

- `web/session_runner.py`: the `respond(push)` closure runs exactly once per engine push — a local counter
  increments there. Each probe display call becomes `voice.turn(model, exp, push, recent, posture,
  arc=(n, MAX_PUSHES))`.
- `MAX_PUSHES` is imported **read-only** from `retnovation.assessment.judgment_loop` (value 8 — the hard cap;
  the loop stops earlier on convergence/plateau). Importing a constant leaves the engine empty-diff.
- `web/voice.py:turn(...)` gains keyword-only `arc: tuple[int, int] | None = None` and passes it through.
- `model.py:concierge_turn(...)` gains keyword-only `arc: tuple[int, int] | None = None` (Protocol, FakeModel,
  AnthropicModel — default None keeps every existing caller/fake byte-compatible). When present AND the brief
  is a probe (push non-empty), one line is appended to the brief:
  `Arc: this is push {n}; the diagnostic never runs past {cap} pushes and usually resolves well before that.`
  The doctrine, not the data line, carries the easing bands (past ~half the typical arc = late). The re-invite
  path (`push == ""`) never carries an arc line (pre-engine turns have no arc).
- **Frame-blind by construction:** the hint is two integers; no rubric, no outcome, no correctness.

### 3c. The craft bundle (same `voice_craft.md` rewrite — hard rules, dogfood-sharpened)

The existing soft phrasings ("one move per turn is usually enough", "do not re-issue the same demand")
demonstrably did not hold under a real session. Sharpened to hard rules:

- **At most ONE question per turn.** A probe turn contains a single question mark. If two things burn, pick
  the sharper; the other keeps.
- **No dismissive interjections.** Never wave a reply off ("Fine.", "Sure.", "Whatever the case") — engage
  what they said or move through it; dismissal is not press, it is contempt.
- **Never re-press what your previous turn just pressed.** If the student dodged it, either come at the same
  ground THROUGH their newest words, or leave it — the landing names un-taken calls honestly. Verbatim
  re-demand two turns running reads as a stuck loop, not rigor.

### 3d. What the author sees (unchanged L-4 structure)

The probe author's inputs remain: problem + dialogue + the safe push + (new) two arc integers. Correctness,
rubric outcomes, and engine classifications are still **never** supplied — the author judges "did they move"
from the dialogue text alone, under the §3a worked discipline. The landing/converse/close paths are untouched
by this thread (their stances are built and reviewed).

## 4. Moat / invariants (load-bearing)

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, graded methods — empty diff.
  The counter lives at the bridge; `MAX_PUSHES` is imported, not moved or modified. Bridge transparency
  (`test_runner_assessment_equals_direct_run_session`) stays green — the arc rides the DISPLAY path
  (`voice.turn`), never the engine inputs (raw opening/reply are what the engine grades, unchanged).
- **L-4:** acknowledgment rewards MOTION, never rightness — enforced structurally (correctness never supplied)
  + by the §3a worked contrast + the `@live` no-verdict assertions. The egress screen remains blind to L-4;
  the prompt discipline and live tests are the backstops, exactly as with `concierge_land.md`.
- **L-13:** nothing new reaches the wire — the arc line lives in the model REQUEST, not the reply; every
  visible turn keeps the existing added-revelation egress gate (probe) untouched.
- **L-5:** acknowledgment must never shade into softening the press or handing direction; the late-arc
  narrowing follows the STUDENT's most alive tension, never steers toward the rubric's frame.
- **Two-phase timing untouched:** no terrain, no position markers, nothing new user-visible except Vera's
  manner.

## 5. Testing

- **Offline (structural):** a recording FakeModel asserts `voice.turn(..., arc=(3, 8))` threads the arc into
  `concierge_turn` and that the brief carries "push 3"; `arc=None` (default) renders no arc line and keeps
  every existing test byte-green; the re-invite path never carries an arc line; bridge-transparency + egress
  suites unchanged.
- **`@live` (key-gated, the behavioral teeth):**
  1. A reply with real movement (concedes a cost + names a number) draws an opening acknowledgment clause
     containing **no verdict token** (`_VERDICT_TOKENS`) and no move-name (egress `_performed == set()`).
  2. A pure-restatement reply draws **no** acknowledgment clause (anti-flattery — the earned gate is real).
  3. A late-arc turn (`arc=(5, 8)`) is materially shorter than an early-arc turn (`arc=(1, 8)`) over the same
     dialogue and opens no new front (no second question mark, no new topic token).
  4. Craft: authored probe turns carry ≤1 "?"; no dismissive-tic tokens ("Fine.", "Sure.").
- **Regression (the dogfood shape):** the same-point-twice sequence — a probe pressing X followed by a dodge —
  must not produce a second verbatim X-demand in the next authored turn.
- **Health smoke:** documented launch boots; a full FakeModel session still converges with arcs threaded.

## 6. Honest residuals

- **Author-judged movement is unanchored** — the model may under- or over-fire acknowledgment; mitigations
  are the worked contrast, the earned-gate live test, and the founder dogfood. If it over-flatters in
  practice, the escalation path is the independent movement classifier (rejected for now: +1 call/turn, L-20).
- **The arc hint is position, not progress** — push 3 after two dodges ≠ push 3 after two closures; the
  doctrine's easing is honest about pace, not achievement. The read-only engine seam (true closure events)
  remains the future option if position-only easing feels false; it was deliberately rejected to keep the
  engine byte-untouched and the L-4 surface minimal.
- **`MAX_PUSHES` drift:** if the engine cap ever changes, the import keeps the hint truthful automatically;
  the "usually resolves well before that" clause keeps the doctrine honest at any cap.
- **Prompt-only craft rules can regress** — the `@live` craft assertions are the only teeth (offline fakes
  can't judge tone); they are cheap single-call tests.

## 7. Files touched (all voice/web-layer; engine untouched)

- `content/prompts/voice_craft.md` — the stance-arc section + sharpened craft rules (§3a, §3c).
- `src/retnovation/model.py` — `concierge_turn(..., arc=None)` (Protocol, FakeModel, AnthropicModel; brief line).
- `src/retnovation/web/voice.py` — `turn(..., arc=None)` pass-through.
- `src/retnovation/web/session_runner.py` — the push counter + `arc=(n, MAX_PUSHES)` at the probe display call;
  read-only `MAX_PUSHES` import.
- Tests: `tests/test_voice.py` (plumbing), `tests/test_voice_live.py` (behavioral), `tests/test_session_runner.py`
  (arc-at-bridge + transparency unchanged).

## 8. Doctrine carried in

Conclusion-agnostic (L-4: describe movement, never rate); never name the move (L-13); disband rules (L-5: no
softening, no steering); engine byte-untouched; egress on every visible turn; implicit easing only (founder's
call); earned-not-rhythmic recognition (the founder's anti-flattery bar).
