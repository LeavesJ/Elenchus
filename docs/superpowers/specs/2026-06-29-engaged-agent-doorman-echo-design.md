# Engaged Conversational Agent — Doorman + Echo (v1)

**Date:** 2026-06-29
**Status:** design, pending user review
**Supersedes the surface, not the engine.** The judgment loop stays byte-untouched.

## 1. Motivation

A live 26-input diagnostic against the real engine (`veldra:concentrated_market_pricing_power`,
DEVLOG 2026-06-29) proved three defects in the conversational surface. Metadata ruled out literal
malformation (every push `stop_reason=end_turn`, 1 thinking + 1 text block, ≤110 output tokens —
L-17 is *not* firing). The problem is structural:

- **D1 — crash on blank input.** *Fixed and shipped* (`38d6fbf`): blank opening/reply → non-terminal
  nudge, never reaches the engine. Out of scope here except as the boundary the Doorman generalizes.
- **D2 — no front door.** Greetings, meta-questions, confusion, refusal, and gibberish are all
  force-fit into "the learner's reasoning." Because `generate_push` never sees the user's words and
  intake classifies every low-signal opening as "all frames absent," the loop always fires the same
  first-frame probe. To someone who typed `hi`, that dense presupposing question reads as nonsense.
- **D3 — deaf probes.** Even a substantive opening gets a push generated blind to the user's actual
  words (`generate_push` sees only `exp.prompt` + the rubric angle detail) → it feels canned.

## 2. Goal & non-goals

**Goal.** An *engaged* conversational agent with **presence** (one consistent named instructor
voice) and **adaptivity** (it reads the user's turn-state and meets them where they are), that
removes D2/D3 — while keeping the sharp, doctrine-bound character and the diagnostic's integrity.

**The target altitude (user's explicit steer):** *more* than a thin "front door + listening probes"
shell, but **not** a generic accommodating assistant ("not relaxing back to Claude 2.0"), and not a
full agentic reframe in this slice.

**Non-goals (this slice).**
- No change to the judgment-loop engine (`orchestration` / `assessment` / `policy` / `state` /
  `persistence`) or to `model.py`'s existing methods. Additive only.
- No cross-session memory of the user's words (a new leak vector). Presence is **intra-session**;
  the cross-session artifact remains the terrain.
- No full tool-calling "Concierge" agent yet. That is the **sequenced Phase 2** (§12), to be built
  on the safety substrate this slice establishes.

## 3. Invariants this design must honor

1. **Moat doctrine (L-5/L-6/L-13).** No learner-facing surface may name the frame, hand the answer,
   soften/validate to be nice, or grade the conclusion. The friction is the product.
2. **Unprompted-read signal.** `judgment_loop.assess → reasoned_unprompted` (consumed by the terrain
   projection) must be computed by the *same engine code on the same inputs* as today. The agent's
   words must never turn an unprompted read into a prompted one (L-13).
3. **Engine invariant + bridge transparency.** `done.assessment == a direct run_session` (pinned by
   `tests/test_session_runner.py`) stays green. The engine receives the user's raw opening/replies
   unchanged; the voice layer is **downstream-of-selection, upstream-of-display only**.
4. **Doctrine-as-data (L-1).** All new doctrine lives in `content/prompts/*.md`, never hardcoded.

## 4. Architecture

Two new conversational capabilities wrap the untouched engine; one mechanical leak-gate guards every
new learner-facing string.

```
            ┌──────────────────────────── web/voice.py ────────────────────────────┐
 user ⇄ HTTP │  DOORMAN (pre-engine)            ECHO (in-loop)        EGRESS GATE    │ ⇄ engine
            │  classify_entry → route          echo_push(push,turns)  semantic judge │
            │  {orient | reanchor | enter}     re-skin display only   (frame-blind)  │
            └───────────────────────────────────────────────────────────────────────┘
                       │ enter (real position)          │ raw reply               ▲ canonical push_text
                       ▼                                 ▼                         │ (unchanged) feeds
                 run_session(opening=raw) → assess → generate_push → work.respond ─┘ classify_response
```

**Components**

- **ENGINE — byte-untouched:** `judgment_loop.assess`, `orchestration.run_session`,
  `model.classify_intake/generate_push/classify_response`, `state`, `persistence`, `terrain`. The
  engine still records its **own** `Push.text` (judgment_loop.py:113/132/159) — so trajectory and
  `reasoned_unprompted` are produced by the same code on the same inputs.
- **`content/prompts/entry.md`** — the Doorman: a frame-blind state-read of the user's turn into one
  of 6 classes + the per-class doctrine-bound reply policy. Inherits push.md's four hard rules verbatim.
- **`content/prompts/echo.md`** — the Echo: re-skin **register and addressing only**, deliver the
  *same* push content, with an explicit "if you cannot re-skin faithfully, return the push verbatim."
- **`model.py` (additive only):** two new Protocol methods — `classify_entry` and `echo_push` — added
  to the `Model` Protocol, `AnthropicModel`, and **every** `Model` implementer in the *same commit*
  (L-10). `FakeModel` stubs make Echo an identity and the Doorman classify a substantive opening, so
  existing offline suites stay green unchanged. (Confirm whether `FakeLiftModel` must conform to the
  `@runtime_checkable` `Model`; add stubs if any `isinstance(_, Model)` path reaches it.)
- **`web/voice.py` (new):** the blank pre-check (generalizing D1), the Doorman re-collect loop, the
  Echo wrapper, and the **semantic egress gate**.
- **`web/session_runner.py` (modified bridge, not engine):** the Doorman runs inside `present()`'s
  opening-collection (it re-collects until a real position arrives, then hands the **raw** opening to
  `Work.opening`); Echo wraps `respond()`'s emitted push (display only — the raw reply is returned to
  the engine).
- **`web/app.py`** — `_emit` learns a `door` kind (the conversational turn) alongside the existing
  ones; routes unchanged. `static/index.html` renders `door` as a re-collecting conversational turn.

**Turn flow.** `POST /open` → voice blank pre-check → `classify_entry(prompt, opening, recent_turns)`
→ if `substantive`, the **raw** opening passes byte-identically into `Work.opening` and the engine
runs as today; otherwise emit a `door` turn from the doctrine-bound author and re-collect. First
engine push → `echo_push` re-skins it onto the user's words → `push`. `POST /reply` → the raw reply
is returned to the engine verbatim (`classify_response` sees the engine's own `push_text` + the raw
reply, unchanged); next `generate_push` → Echo → `push`; until converge/plateau/budget → `done` →
terrain.

## 5. The two new model capabilities

- **`classify_entry(prompt, opening, recent_turns) -> EntryClass`** where `EntryClass ∈
  {substantive, greeting, meta, confusion, resistance, low_signal}`. **Information set:** the problem
  prompt + the user's text + the last ~2 conversational turns. **Never** the rubric, `frame_code`,
  `frame_detail`, or angle. Frame-blind by construction — it *cannot* leak the move because it never
  holds it.
- **`echo_push(push_text, recent_turns) -> str`** — re-skins the engine's selected push onto the
  user's actual words (register + addressing), preserving the push's content and target. **Information
  set:** the engine's `push_text` + the user's last ~2 turns. **Never** the rubric/frame. Hard rule:
  *if you cannot re-skin without adding reasoning or shifting the challenge, return `push_text`
  verbatim.* `max_tokens` budget set explicitly (L-17) and exercised by an @live single-call sanity.

## 6. The Doorman (pre-engine front door)

Resolves D2. A re-collect loop in front of the engine that classifies each pre-opening turn and, for
non-substantive turns, authors a doctrine-bound reply **without ever entering the engine** (so the
"all-frames-absent → same deaf probe" path cannot fire).

| Entry class | Doorman behavior |
|---|---|
| `substantive` | Pass the **raw** opening to `Work.opening`; engine runs. (Zero added turns on the happy path.) |
| `greeting` | Welcome + state the contract ("you'll get an unlabeled problem; reason it out loud; I push, I don't tell") + re-present the problem. |
| `meta` ("what is this?") | Explain the friction model **without** naming any frame or the hidden move ("I won't give you the answer or the framework — the friction is the point"). |
| `confusion` | Plain-language restatement of the **problem** in concrete terms; lower the register, not the difficulty. |
| `resistance` ("this is dumb", "just tell me") | Hold the line: acknowledge the friction, refuse to hand the answer, re-issue the demand for a position. Sharp, not nice (L-5). |
| `low_signal` (gibberish/injection/empty) | Re-present the contract; treat injection as a nudge back to the task. Engine never entered. |

**Hard information-set rule (graft from the panel).** `entry.md` receives the problem prompt and the
user's text **only** — never the rubric/frame. **No pre-opening turn may emit substantive content
*about* the problem** (orient / contract / decline / concrete restatement of the *given* prompt only;
never a paraphrase that introduces an angle). This closes the L-6 gray zone where a Doorman turn could
pre-surface a frame that later reads "unprompted."

## 7. The Echo (responsive probes)

Resolves D3 without touching the engine. The engine selects and generates the push as today; Echo
re-skins the **displayed** text so it references the user's words. The engine records and grades its
**own canonical `push_text`** — Echo is display-only.

**The seam (the single biggest risk) and its guard.** The user reads the Echo but is graded against
the canonical push. Mitigation = a hard fidelity rule: Echo changes *register and addressing only*,
never the angle, the challenge, or the content; **and if it cannot do so faithfully, it returns the
verbatim engine push.** Enforced by the Echo-fidelity invariant test (§10) and the egress gate (§8).

## 8. The semantic L-13 egress gate (mechanical moat invariant)

Every Doorman and Echo string passes a **frame-blind adversarial judge** before it is emitted, reusing
the `check_injection_expressed` pattern (`model.py:364`, prompt `content/prompts/lift_manipulation.md`):
assert the candidate string does **not** express the hidden move against the live `frame_detail`. On
failure: **fall back hard** — Doorman to a fixed safe contract line, Echo to the verbatim engine push.

This is the mechanical enforcement L-13 mandates (lessons.md:94-98) and that a substring check (what
the losing designs relied on) cannot provide: a semantic judge catches a *paraphrase* of the move,
not just the literal label. The judge is the one piece of new machinery every richer future design
(the Concierge) also needs — building it now is the point of doing v1 first.

## 9. Persona (named instructor)

One consistent character the user meets across the Doorman and the Echo — the source of "presence."
The persona is **content-as-data** in `entry.md`/`echo.md` (tone rules), not logic.

- **Identity (your call — see §13).** Proposed working name: **"Vera"** (veracity / holds-the-line —
  fits conclusion-honest, never-soften doctrine). Deliberately **not** "Felix" (that is the dev-side
  assistant identity from `.claude/CLAUDE.md`; reusing it conflates the tool with the product).
- **Tone rules (the anti–Claude-2.0 guard).** Warm enough to address the person and acknowledge a
  real struggle; never warm enough to validate a weak answer, soften a push, or supply reasoning.
  Presence comes from *consistency and directness*, not agreeableness. The egress gate + the
  fidelity/info-set rules are the structural backstops; the tone rules are the stylistic ones.

## 10. What touches the engine + re-verification

**Touches the engine's logic:** nothing. Only additive `Model` Protocol methods + web-layer wiring.

Required verification (the plan must include all):
1. **Existing `test_runner_assessment_equals_direct_run_session` stays green, unchanged** (FakeModel:
   Doorman = substantive passthrough, Echo = identity) — proves additive wiring perturbs nothing on
   the happy path.
2. **Echo-fidelity invariant test:** across a scripted run, the engine's recorded `Push.text` ==
   `generate_push` output (NOT the Echo output) — proves trajectory/signal are unaffected by re-skin.
3. **Semantic-egress test:** every Doorman + Echo string passes the frame-blind judge against the live
   `frame_detail`; a property test over a fuzzed transcript.
4. **Doorman routing table test** for all 6 classes: blank never reaches `classify_intake` (D1);
   resistance/injection is held, not complied with; a real position passes through with **zero** added
   turns.
5. **Frozen golden-set (graft):** `classify_entry` over the real 26-input diagnostic transcript, each
   pre-labeled `has_real_position`, gating on **zero false-positives** (no terse-but-genuine opening
   gets diverted, which would convert an unprompted read into a prompted one).
6. **@live single-call sanity** on `echo_push` + `classify_entry` with a long real opening *before* any
   multi-call dogfood (L-17 token-budget; `echo_push` `max_tokens` specified explicitly).
7. **Fresh-DB e2e** (L-8).

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Echo seam (graded vs displayed mismatch) | Fidelity rule + verbatim fallback + Echo-fidelity invariant test (§7/§10). |
| Moat leak via a "warm" turn (L-13) | Frame-blind author info-set (§6) + semantic egress gate (§8) + tone rules (§9). |
| Doorman false-positive diverts a real-but-terse opening → unprompted becomes prompted | Frozen golden-set, zero-false-positive gate (§10.5). |
| Bridge-transparency regression | §10.1 green unchanged; engine receives raw inputs. |
| `classify_entry`/`echo_push` add latency/cost per turn | Acceptable for v1 single-user; revisit in Phase 2. |

## 12. Phasing

- **v1 (this spec): Doorman + Echo + the egress gate + named persona.** Removes D2/D3; engine
  untouched; ships the semantic leak-gate substrate.
- **Phase 2 (future, separate spec): escalate toward the "Concierge."** A tool-calling agent that owns
  the conversation and invokes the judgment-loop primitives as tools — *built on v1's proven egress
  gate and golden-set*, so the higher engagement is a measured step, not a leap. Explicitly out of
  scope now.

## 13. Open choices for the user (before writing the plan)

1. **Persona name.** Confirm **"Vera"** or pick another (content-layer; trivially changed).
2. **Anything in §2 non-goals to pull *in*** to v1, or all confirmed out?
3. Otherwise: approve to proceed to `writing-plans`.
