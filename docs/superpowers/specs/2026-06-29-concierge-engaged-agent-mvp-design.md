# Concierge — the engaged-agent MVP (engine-fronting)

Date: 2026-06-29
Status: design, pending implementation plan
Supersedes (for the in-conversation path): `2026-06-29-engaged-agent-doorman-echo-design.md`
(the Doorman+Echo provisions fixed the front door but left in-conversation turns rigid).

## 1. Problem

A live dogfood exposed two failures the prior provisions did not fix:

1. **Zero engagement (the real one).** `generate_push(exp, kind, code, *, stress)` — the function
   that writes every push — **never receives the student's reply or the conversation**. Each push
   is generated from the rubric's next *angle* alone; the student's words only feed grading
   (`classify_response`), never the next question. So the agent marches its predetermined angles
   regardless of what the user says — including when the user explicitly objected "your question is
   irrelevant." The Doorman/Echo "engaged middle" only runs on the **entrance** turn; every
   in-conversation turn just shows the next rubric push. Result: the body is as rigid as day one,
   while the provisions add latency. Observed: user gives a data-roadmap answer → push pivots to a
   commitment/reference angle; user says it's irrelevant → next push pivots to a reversibility
   angle. None of it engages the user's actual content.
2. **UI/entrance.** The problem menu renders raw internal refs (`veldra:license_fork_risk`, …) —
   both an immersion break ("Veldra named out") **and a confidentiality leak** (those `veldra:`
   slugs are gitignored, Veldra-derived, never meant to reach a client). The model also invents a
   name for the user ("Sam"). And the UI is a stacked 4-block form, not a chat agent.

## 2. Decision

**Agent-driven Concierge, Approach A — the agent fronts the engine** (user-selected over "agent
fully drives" and "plain Socratic chat"). The diagnostic engine stays the **untouched spine**
(picks the live objective, generates the canonical push, grades the reply, stays
conclusion-agnostic). A new **Concierge** owns every *visible* turn: it reads the user's whole
message + the full conversation, **acknowledges what they actually said** (objections, confusion,
their real reasoning), and asks its probe **grounded in their words** while pursuing the engine's
live objective — **never naming the move**. The batched egress / L-13 screen still backstops every
visible turn; the raw reply still returns to the engine for grading (bridge transparency). This is
the "agent tool, terrain on top" intent: the engine becomes the diagnostic instrument the agent
plays, not the script.

Terrain visualization stays deferred (future). The diagnostic still computes underneath so terrain
has data later; the MVP's payoff is a conversational close.

## 3. Architecture

```
 Browser (chat thread)  ──HTTP──▶  FastAPI app  ──queue──▶  worker thread
                                                              │
        ┌─────────────────────────────────────────────────────┘
        ▼
  run_session(...)  [ENGINE — BYTE-UNTOUCHED]
   • classify_intake / generate_push / classify_response  (objective selection + grading)
   • conclusion-agnostic; canonical push graded vs raw reply
        │  present(exp) / Work.respond(push)  ← the bridge seam (web only)
        ▼
  CONCIERGE (bridge layer, web/voice.py)
   • authors every VISIBLE turn: open · re-invite · probe · close
   • sees only: problem prompt, full dialogue, the engine's L-13-safe push (objective brief)
   • NEVER sees rubric internals (frame_code/detail) → frame-blind, same boundary as Echo today
   • egress screen (screen_moves, batched) backstops each visible turn; raw reply → engine
```

The engine (`orchestration.run_session` and its model methods `classify_intake` / `generate_push`
/ `classify_response`) is **not modified**. The Concierge plugs in exclusively at the existing
`present` / `respond` bridge callbacks in `web/session_runner.py`. `generate_push` still runs: its
output is the **grading anchor** (`classify_response` needs it) and the Concierge's **objective
brief** — it is never shown raw.

## 4. The Concierge turn

One model call authors each visible turn. Inputs: the problem prompt, the recent dialogue
(`[(speaker, text), …]`), and — for probe turns — the engine's canonical push as the objective
brief. The push is already L-13-safe (the engine's pushes never name the frame), so passing it
keeps the Concierge frame-blind exactly like Echo. Behavior by turn kind:

| Turn | Method | Brief | Must do | Fallback on egress fail |
|---|---|---|---|---|
| **open** | (static) | — | Present the scenario verbatim + a short standing invite ("the call's yours; take a position and reason it out — I'll push, I won't hand it over"). No model call. | n/a |
| **re-invite** | `concierge_reinvite(problem, recent)` | — | Acknowledge what the user actually said (greeting / confusion / objection) and re-invite a real position, grounded in their words. Never name a move. | `SAFE_CONTRACT` (static) |
| **probe** | `concierge_probe(problem, push, recent)` | the engine's push | Acknowledge the user's reply (incl. "this is irrelevant" / confusion), then ask the next probe **grounded in their words**, pursuing the push's angle. Never name the move. | the canonical `push` (verbatim) |
| **close** | `concierge_close(problem, recent)` | — | Reflect the user's reasoning back — what they committed to, the trade-off they're betting on, where they're exposed — as a synthesis. No score, no named frame. | a short static close |

**Moat invariants (unchanged from Echo, now applied to richer turns):**
- Frame-blind: the Concierge never receives `frame_code` / `frame_detail` / `trap_detail`; only
  the safe push + dialogue. (Tests assert rubric internals never appear in the request blob.)
- Egress backstop: every visible turn passes through the batched `screen_moves` egress. `probe`
  uses **added-revelation** vs the push baseline (reuse `voice.echo`'s logic). `re-invite` /
  `close` use the **flat** check (`egress_safe_reply`: perform no move). On fail → the fallback
  column above.
- Conclusion-agnostic: never names the move, hands no answer, assigns no score.
- Never invents or assumes the user's name; addresses them as "you." (Prompt instruction; fixes
  "Sam".)

**Effort/latency:** the Concierge call **replaces** the `echo_push` call (cost-neutral per turn);
the egress is already batched (L-20). So engagement is added at ~no extra call cost — latency was
already addressed by the batching, not by this change. (Honest: this change is about engagement,
not speed.)

## 5. Bridge wiring (`web/session_runner.py`)

- `present(exp)`: emit the scenario + standing invite (open). Loop collecting the first position:
  `gate = classify_entry(prompt, text, recent)` — substantive → that text is the engine `opening`,
  break; else emit `concierge.reinvite(...)`, bounded by the existing `_DOOR_MAX_NONSUBSTANTIVE`.
- `Work.respond(push)`: emit `concierge.probe(exp, push, recent)` for **display**; return the raw
  student reply (engine grades canonical `push` vs raw reply — transparency preserved).
- On engine completion: the worker authors `concierge.close(exp, recent)` and emits it as the final
  Vera message. The engine's `(state, assessment)` is still recorded (future terrain), but the MVP
  shows the conversational synthesis, not a terrain seed.

`web/voice.py` evolves: the egress (`_moves`/`_performed`/`egress_safe_reply`/`screen_moves` usage)
**stays**; `door`/`echo` become `gate`/`probe`/`reinvite`/`close`. Keep the filename (the module is
the agent's *voice*); no rename churn.

## 6. Entry — clean picker, no leak

- Add an optional `display_title` to each rubric YAML (human-authored, e.g. "Pricing power in a
  concentrated market"); fall back to a humanized `experience_id` (`decision_under_stakes` →
  "Decision under stakes"). **Never** expose `ledger_ref` (`veldra:` slug) to the client.
- Selection is already index-based (the client posts the menu *index*; the worker does
  `menu[idx]`), so the fix is purely the **labels**: the menu payload carries `display_title`
  instead of `ledger_ref`. The `veldra:` slug never crosses the wire. (`menu_index`, the
  `ledger_ref`→index helper, is removed if it proves unused once labels no longer carry the ref.)

## 7. Chat UI (`web/static/index.html` rewrite)

Standard chat thread, replacing the stacked 4-block form:
- A scrolling message list: user turns right-aligned (teal), Vera turns left-aligned. The scenario
  and every Concierge turn are messages, not boxed forms.
- One **sticky composer** at the bottom: a textarea + send button (Enter to send, Shift+Enter
  newline). The "Vera is thinking…" indicator appears inline as a pending Vera bubble.
- Entry screen: the clean problem picker (display titles).
- Close: the Concierge synthesis appears as the final Vera message; a quiet "your read is recorded"
  line (no terrain seed in the MVP).
- Connection-error handling (re-enable composer, surface a retry line) carries over.

## 8. Testing

**Offline (deterministic doubles):**
- Concierge fakes (identity/leak/objection) exercise probe/reinvite/close + the egress fallback
  paths, reusing the `screen_moves` set-difference doubles (`_PerMoveModel` etc.).
- Bridge: `present` enters the engine on a substantive first turn; re-invites and is bounded on
  non-substantive; `respond` returns the **raw** reply (transparency) while emitting the probe;
  close is emitted on completion.
- Frame-blindness: the Concierge request blob never contains `frame_code`/`frame_detail`/`Rubric`.
- Picker: the menu payload contains `display_title` and **never** a `veldra:` substring.

**@live (real model, key-gated, marked `live`):**
- **Engagement** (the regression that started this): given a user reply, `concierge_probe`'s output
  must reference the user's actual words / objection (a grounding assertion), not ignore them.
- **Objection handling:** a "this is irrelevant" reply yields an acknowledging probe, not a blind
  pivot.
- **Moat:** the probe still passes the egress (no named move) on a faithful turn and is caught on a
  leaking one (the L-20 no-op + leak-catch pattern, retargeted at the Concierge).
- **No invented name:** the opening/probe never addresses the user by a fabricated name.

## 9. Out of scope (MVP)

- Terrain visualization (deferred — future; diagnostic data still recorded).
- Open-ended problem intake (the engine needs a pre-authored rubric per problem; the picker stays).
- Approach B (agent fully drives the trajectory) — the engine keeps objective selection + grading.
- Streaming token output (consider later; the thinking indicator covers the gap for now).

## 10. Risks & open questions

- **Trajectory still engine-ordered.** Approach A keeps the engine choosing the angle; engagement
  comes from acknowledgment + grounding, not from the agent re-routing. If a user fixates on a
  direction the engine won't pursue, the Concierge acknowledges but still steers to the live
  objective. Mitigation: a liveness bound on re-probing the same angle (don't hammer an objection);
  the Concierge may surface "let's set that aside" rather than repeating. Confirm the engine's
  existing per-angle push bound during planning.
- **Grading anchor vs visible turn.** The user replies to the Concierge's grounded probe, but the
  engine grades against the canonical push. Valid because the probe pursues the same angle (same as
  Echo today; reviewer-confirmed transparency). Watch for cases where grounding drifts the probe
  off the angle — the egress/added-revelation gate is vs the push, which also anchors topicality.
- **Close authored from dialogue only.** `concierge_close` is frame-blind (reflects reasoning, no
  frame, no score). Ensure it doesn't smuggle a verdict; egress flat-check applies.
