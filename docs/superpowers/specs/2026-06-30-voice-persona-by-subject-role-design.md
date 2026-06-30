# Vera's voice — persona by subject, register by role (a content-resolved voice seam)

Date: 2026-06-30
Status: design, pending implementation plan
Builds on: the engaged-agent Concierge (`voice.py` authors every visible turn over the byte-untouched engine).
Lessons in force: L-1 (doctrine is data), L-13 (frame-blind surfaces — *semantic*, not just literal), L-12,
L-15 (trust per-finding verification), L-19 (`PYTHONPATH=src`).

Ground-truthed against the merged tree (content_loader, aim, the maps, the rubrics, voice.py, model.py,
session_runner.py) and hardened by an adversarial 3-lens review (1 critical + 6 important folded in; §12).

## 1. Problem — the rigidity is a symptom; the disease is a hardcoded voice

A founder browser-dogfood (`irreversible_anchor`, Chinese then English) exposed a voice failure the
automated tests can't see: **every Vera turn is the same five-beat machine** — [acknowledge] → em-dash
pivot → [set-aside/counter] → [re-frame the choice] → [the same closing demand, "pick one and tell me X"].
Em-dashes hinge every turn; the closing demand repeats nearly verbatim across turns. It reads as a
**stubborn AI voice** — one sentence-shape, one move, on a loop. A real beta user reported the same.
**Rigidity in tone and syntax is the defect.**

Two roots, and the fix must address both:
- **Voice is a hardcoded global constant.** `concierge.md` opens "You are Vera, a Socratic instructor…" —
  one string, one voice, zero axes of variation. The *same* property blocks the roadmap: the experience set
  is expanding beyond generic founder chat (CS-technical, subcategories, more personas), and the voice must
  **vary by subject, by role, and by experience**, which a constant cannot do.
- **The comprehension gear hardened a template.** The gear shipped last pass (reflect-concern → *then*
  push, every turn) made the two-beat reliable. So the fix is **not** "rewrite the string" — a nicer
  constant is still a constant, and keeping the gear as a per-turn beat would relocate the template, not
  remove it. The fix needs a real **variety mechanism** (§4), not just rules and exemplars.

## 2. Decision — three composed layers, voice resolved from content (L-1)

Split the one tangled string into three layers, composed at authoring time, plus a variety mechanism:

- **D1 — Invariant craft + moat** (persona-agnostic, never varies): never name the move; press the
  reasoning; frame-blind; conclusion-agnostic; **plus the anti-rigidity craft and the comprehension gear
  as a *conditional tool*** (§4). This is relocated from `concierge.md` (not "de-duplicated" — the gear
  lives only there; §6).
- **D2 — Persona, by subject** (content): each subject owns a *named character* — identity, base register,
  and **≥4 stylistically divergent** exemplars on neutral stubs (§4). Founder = **Vera**, re-expressed as a
  dry, economical sparring partner. Resolved from the session's posture (`aim().posture`: `founder_ceo` →
  Vera; `cs_systems` → a CS persona later — blocked on a CS open-ended rubric existing, §9).
- **D3 — Role register, by experience** (content): the **world/setting idiom** of the role — *where* the
  conversation lives, never the analytical move (§5). CEO vs CTO. Resolved from a new per-experience `role`
  tag. **Frame-orthogonal by construction** and validated against every frame it touches (§5, §8).

**Composition (canonical, pinned):** `resolve_voice(posture, exp) -> persona + role_register + craft` (the
full voice string); `model.concierge_*` prepends it ahead of its task prompt, so `final = voice + task`.
The egress screen (`screen_moves`) backstops every authored turn regardless of how the prompt was built —
but egress only catches *naming/handing* the move, not idiom that *orbits* it (egress.md:11-13), which is
why D3's frame-orthogonality must be enforced by design + test, not left to the backstop.

The engine is byte-untouched; voice is display-only, so the bridge-transparency test (assessment
byte-equality) cannot be perturbed.

## 3. Data model + resolution

- **Subject → persona** from `aim().posture` (default `founder_ceo`, hardcoded in the web worker today).
  MVP mapping: founder postures → `vera`. Resolution is **graceful**: an unknown/missing posture falls back
  to `vera` + craft (the existing single-voice floor), never raising (§6, §8).
- **Role → register** from `Experience.role` (`"ceo" | "cto" | None`), loaded from the rubric YAML. A `None`
  role composes no role layer (graceful default). **Decided** (was open): `role` lives on `Experience`.
- **Composition site:** `voice.py` holds `exp` on every authoring call and threads `posture`; it builds the
  full voice string and passes it to `model.concierge_*` as a keyword-only `voice: str = ""` parameter.

## 4. The rigidity fix — variety mechanism + Vera's persona (D1 + D2)

The rigidity fix is three mechanisms, not "rules + exemplars":

1. **The gear is a conditional tool, not a per-turn beat.** Relocated into the invariant craft as: *reflect
   the concern when trust needs establishing or comprehension has failed; re-anchor when the student drifts
   off the concrete problem; hard-stop and restate when they say you don't understand them.* Each fires
   **on its signal** — none is a mandatory opening every turn. Most turns are a **single** move (a question,
   a reaction, a challenge), not the full mirror-then-demand.
2. **≥4 stylistically divergent exemplars** in the persona, so the model samples a distribution, not one
   shape: a one-word reaction; a bare single question; a sit-with-it; a name-the-dodge. Authored on
   **neutral/fabricated stubs** that carry **no real frame vocabulary** (the dogfood re-voicings must be
   scrubbed of any phrase that paraphrases a `frame_detail` — exemplars are unscreened prompt text, so a
   move encoded in one biases generation silently; §8 guards this).
3. **Explicit variety doctrine + test:** craft says vary shape, length, and how you press; never run the
   same structure two turns running. @live asserts sentence-shape variety across N>2 consecutive turns (not
   merely "not repeated verbatim across two").

**Vera's persona** (D2) re-expresses her existing definition (entry.md: *"presence is directness, not
warmth,"* "you reason it; I push, I don't tell") as **economy, reaction, and variety**: a dry sparring
partner who presses because she takes your thinking seriously; reacts like a person; names the dodge
instead of re-issuing "pick one"; no em-dash hinge. The anti-rigidity rules live in the **craft** (so they
bind future personas); the persona file is Vera's *character and idiom* + the divergent exemplars.

## 5. Role registers — world, not analysis (D3) + the CEO/CTO proof

**Governing principle (the moat fix):** a role register colors **where the conversation lives** — the
setting, the people in the room, the texture of the role's day — and **never** the analytical angle. The
engine's push owns the angle (frame-bearing, voiced frame-blind by the gear); the register owns only the
idiom/world. This keeps registers **frame-orthogonal by construction**:

- **CEO register:** the boardroom, the quarter, the cap table, the customer across the table, positioning,
  reputation. The *world* of a CEO. **Not** analytical move-words.
- **CTO register:** the deploy, the on-call rotation, the shipped artifact, the customer hitting it in the
  field, the team. The *world* of a CTO. **Explicitly forbidden:** "reversible / rollback / failure-default
  / optionality" and any near-synonym — those **are** the moves on `irreversible_anchor` /
  `decision_under_stakes`, so they cannot appear in a register.

Because the spine frame `embed_credentials_as_a_list` recurs across a CTO problem (`irreversible_anchor`)
**and** a CEO problem (`continuity_lock_in`), role is **not** a proxy for distinct moves. Therefore each
register's text is validated against the `frame_detail` vocabulary of **every** problem tagged to that role
(not assumed safe from the label) — a lexical overlap guard plus an @live "does this register paraphrase
the hidden move" judge (§8).

**The proof — tag the 5 founder problems** (natural framing): CEO = `decision_under_stakes` (pricing),
`continuity_lock_in` (license terms), `license_continuity` (contract ambiguity); CTO = `irreversible_anchor`
(immutable shipped anchor), `proof_before_promise` (unproven capability). Note `continuity_lock_in` and
`license_continuity` share a `ledger_ref` (`veldra:license_fork_risk`) so only one is picker-selectable per
session (dedup, types.py); the clean CEO dogfood exemplar is **`decision_under_stakes`**. The proof is
operationalized in §8 (idiom-token divergence), not "visibly different by feel."

## 6. Composition + threading (engine untouched)

- **Prompt refactor (a RELOCATION, with inventory):** the gear lives *only* in `concierge.md` (reflect-
  concern, re-anchor, hard-stop) — `concierge_open.md`/`concierge_close.md` have a shorter task preamble and
  **no gear**. So this is not a de-dup. Enumerate the exact gear blocks and assert each appears in the new
  `voice_craft.md` after the move; assert the composed **turn AND converse** prompts contain all three gear
  behaviors (string-presence tests). Confirm open/close carried no gear that is now lost. Reduce
  `concierge*.md` to task-only.
- New content: `content/prompts/voice_craft.md` (invariant craft + moat + gear-as-tool); `content/personas/
  vera.md` (character + divergent exemplars); `content/voice/role_ceo.md`, `role_cto.md` (world idiom).
- `voice.py`: `resolve_voice(posture, exp) -> persona(subject(posture)) + role_register(exp.role) + craft`
  (graceful on unknown posture/role). `turn`/`open`/`close`/`converse` pass the composed string to the model
  methods.
- `model.py`: `concierge_turn`/`open`/`close` gain **keyword-only `voice: str = ""`**, prepended to the
  loaded task prompt. This ripples to the **Model Protocol (model.py:73-75)**, **FakeModel (:131-139)**, and
  the **~8 test-double overrides** in `tests/test_voice.py` + `tests/test_session_runner.py`; the default
  keeps them compiling and structurally enforces the graceful floor. The "voice reaches the request" test
  targets `AnthropicModel` (or a spy), not `FakeModel`.
- `content_loader.py`: thin `load_prompt`-style readers for personas/role-registers/craft; `load_experience`
  reads the new `role` field; the persona key on the posture map (lean) is read via `dict.get` so
  `load_map`/`load_path_type` ignore it.
- `types.py`: `Experience.role: str | None = None` (additive; does not touch `_regime_payload_invariant`).
- `session_runner.py`: bind `a = aim()` in the worker; thread `a.posture` into the `present()`/`respond()`
  `voice.*` calls; **add `posture` to `ch.record`** (session_runner.py:122-127) so the post-convergence
  `converse()`/`close()` (which run engine-free off the record) resolve the **same** persona — otherwise the
  voice flips at the convergence boundary or `resolve_voice` is called without a posture.

Frame-blindness is preserved *semantically*, not just literally: persona/role/craft carry no `frame_code`
**and** no paraphrase of a `frame_detail` (§8 enforces both). The bridge-transparency equivalence test is
unaffected: `FakeModel.concierge_turn` echoes the push regardless of `voice`, so the assessment is
byte-identical (state this as the transparency guard).

## 7. Invariants that must not drift

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, `classify_intake`/
  `generate_push`/`classify_response`. All changes are in `content/`, the voice authors, the loaders, and
  `Experience.role`.
- **Comprehension gear preserved (no regression):** the three gear behaviors must remain reachable on the
  turn **and** converse paths after relocation — string-presence tests, not hope.
- **Moat / L-13 (semantic):** every composed voice routes through the egress; persona/role/craft carry no
  `frame_code` and no paraphrase of any `frame_detail` they touch; role registers are world-idiom only.
- **Bridge transparency:** `test_runner_assessment_equals_direct_run_session` stays green.
- **Graceful floor:** a `None` role and an unknown/missing posture compose a valid prompt (persona + craft +
  task), never an error.

## 8. Validation plan

- **Offline (plumbing + safety):**
  - `Experience.role` loads from a rubric YAML; a `None` role composes persona+craft+task with no role layer.
  - `resolve_voice` is graceful: an unknown posture falls back to `vera` + craft (a real test, not an
    unreachable branch).
  - **Gear-presence:** the composed turn AND converse prompts contain all three gear behaviors.
  - **Semantic frame-blindness guards (hard, not soft):** no `frame_code` in any composed prompt; **no
    role-register or persona/exemplar text shares a content-word with any `frame_detail` of a problem it
    touches** (lexical overlap guard over the full tagged set, including the shared
    `embed_credentials_as_a_list` problems).
  - `model.concierge_*` accept `voice` and it reaches the request (spy/AnthropicModel); bridge-transparency
    + egress tests stay green.
- **@live (the real register/variety proof):**
  - **CEO/CTO divergence, operationalized:** run the SAME student turn against a CEO-tagged
    (`decision_under_stakes`) and a CTO-tagged (`irreversible_anchor`) experience; assert the two authored
    turns have **disjoint idiom-token sets** (CEO: capital/market/board/customer; CTO: deploy/on-call/
    artifact/field) and **neither leaks a frame paraphrase** (an @live judge: "does this turn point at the
    hidden move?").
  - **Variety:** across N>2 consecutive turns, sentence-shape varies (no single template); the closing
    demand is not repeated; em-dash-as-hinge is absent.
  - **Converse cumulative leak:** exercise multi-turn engine-free converse under each role and judge for
    *cumulative* frame leak (the least-bounded path), not just single-turn no-leak.
- **Founder re-dogfood:** `irreversible_anchor` (CTO) and `decision_under_stakes` (CEO) — does Vera sound
  like a person (not a loop), and do the two sound meaningfully different in *world* while unmistakably the
  same Vera, with no steer toward the move.

## 9. Out of scope / notes

- **CS-technical persona** and any non-founder subject: blocked on a CS *open-ended* rubric existing
  (`cs_systems` is `path_type: domain`, no rubric to author over) — not just persona content.
- **`entry.md` is a 4th hardcoded "You are Vera"** but its authored reply is **discarded** on the web path
  (`voice.gate` reads only `.entry_class`), so it's safe to leave out of scope this pass; noted so the
  "one hardcoded voice" claim is precise and the seam is documented for the CS expansion.
- Per-experience persona *override* (only role varies per experience; persona varies per subject);
  re-authoring the problem *prompts* (only voice/register changes); a post-filter for voice stickiness
  (future, if the prompt mechanism proves insufficient).

## 10. Open design choice (one, for the plan)

- **Where subject→persona resolution lives:** a `persona:` key on the posture map (`founder_ceo.yaml`),
  vs. a small posture→persona resolver in `voice.py`. The map key is more L-1; the resolver is fewer parts
  for a one-entry MVP. (Lean: the map key — confirmed safe, `load_map`/`load_path_type` ignore extra keys.)
  *Decided (were open): `role` on `Experience`; gear behaviors are craft.*

## 11. Risks

- **Voice stickiness / template relocation:** mitigated by the *mechanism* (conditional gear + divergent
  exemplars + variety test), not just exemplars; the @live variety check across N turns is the gate. A
  post-filter is the fallback if the prompt can't hold variety.
- **Register too weak (ignored) or too strong (caricature) or frame-orbiting:** the offline lexical guard +
  @live idiom-divergence + paraphrase-judge calibrate all three; world-not-analysis is the design rule that
  keeps it frame-orthogonal.
- **Refactor drops the gear:** the relocation inventory + gear-presence tests on turn AND converse.

## 12. Review trail (what the adversarial pass changed)

3 lenses, all ship-with-fixes (architecture sound). Folded in: **[important moat]** role registers are
world/setting idiom, frame-orthogonal by construction, validated against every frame they touch (CTO idiom
no longer paraphrases the move); **[important]** the rigidity fix gains a real variety mechanism (gear as a
conditional tool + ≥4 divergent exemplars + N-turn variety test) instead of circular "exemplars fix
stickiness"; **[critical]** the prompt refactor is a gear *relocation* with a verbatim inventory + presence
tests, not a de-dup (the gear lives only in `concierge.md`); **[important]** `posture` added to `ch.record`
so post-convergence converse/close keep the persona; **[important]** `voice: str = ""` keyword-default
enumerated across Protocol + FakeModel + ~8 doubles; **[important]** the CEO/CTO proof operationalized
(idiom-token divergence + paraphrase judge), not "visibly different by feel"; **[minor]** graceful resolver
+ test; exemplars on neutral stubs scrubbed of frame vocabulary; composition order pinned canonically;
`entry.md`/`cs_systems`/`ledger_ref`-aliasing noted. The architecture and the founder's decisions did not
change.
