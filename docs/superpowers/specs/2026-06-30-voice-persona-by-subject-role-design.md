# Vera's presentation identity — persona / subject / role, across voice AND visual

Date: 2026-06-30
Status: design, pending implementation plan
Builds on: the engaged-agent Concierge (`voice.py` authors every visible turn over the byte-untouched
engine); the Cartographer UI/UX (`2026-06-28-uiux-cartographer-design.md`) — the terrain/world artifact.
Lessons in force: L-1 (doctrine is data), L-13 (frame-blind surfaces — *semantic*, not just literal), L-12,
L-15, L-19.

Ground-truthed against the merged tree (content_loader, aim, the maps, the rubrics, voice.py, model.py,
session_runner.py, web/static/index.html) and hardened by an adversarial 3-lens review of the voice facet
(1 critical + 6 important folded; §13). Elevated from voice-only to cross-channel after a founder steer:
"this is a flashy product — the frontend must be represented, not only the backend tones."

## 1. Problem — rigidity is a symptom; the disease is a hardcoded, voice-only identity

A founder dogfood (`irreversible_anchor`) exposed a **rigid, stubborn AI voice** — every Vera turn the same
five-beat machine (em-dash hinge, repeated "pick one and tell me X"). A real beta user reported the same.
But the fix splits into three roots, and the third is what makes this a *product* design, not a prompt tweak:

- **Voice is a hardcoded global constant.** `concierge.md` opens "You are Vera…" — one string, one voice,
  zero variation. The same property blocks the roadmap: the experience set is expanding (CS-technical,
  subcategories, more personas), and the agent must **vary by subject, role, and experience**.
- **The comprehension gear hardened a template.** The reflect-concern→then-push gear became a per-turn beat,
  so the fix needs a real **variety mechanism** (§4), not just rules and exemplars.
- **Identity is voice-only, and the product is visual.** This is a flashy, premium artifact (the
  Cartographer: a cultivated world of your judgment), not a utilitarian tool. The Cartographer as specced is
  **subject-blind** — one world regardless of domain — so a beautifully-themed *voice* would float over a
  subject-agnostic *world*. Persona / subject / role is a **cross-channel presentation identity** that must
  be *seen*, not only *heard*.

## 2. Decision — a resolved presentation profile with two facets (voice + visual)

The resolution axis (`posture → subject → persona`, `exp → role`) resolves a **presentation profile** with
two content-resolved facets off the *same* axis:

- **Voice facet** — register + exemplars (the model authors text in it). §4–§5.
- **Visual facet** — a presentation *theme* (the frontend renders the surface/world in it). §6.

One axis, two channels, so the register you *hear* and the atmosphere you *see* are always coherent. Both
facets are **content** (L-1), resolved server-side; the voice facet feeds `model.concierge_*`, the visual
facet (a small, public theme object) is served to the frontend. The engine is byte-untouched; the egress
backstops every voice; and — load-bearing — **the entire presentation identity sits *above* the hidden
frame** (§6), so theming carries zero moat cost.

## 3. Data model + resolution

- **Subject → persona** from `aim().posture` (default `founder_ceo`). MVP: founder postures → `vera`.
  Graceful: unknown/missing posture falls back to `vera` (the single-voice floor), never raising.
- **Role → register + atmosphere** from a new `Experience.role` (`"ceo" | "cto" | None`), loaded from the
  rubric YAML. `None` composes the base persona, no role layer.
- **The profile** = `{ voice: <composed system text>, visual: <theme object> }`, resolved once per
  (posture, exp). **Decided** (was open): `role` lives on `Experience`.

## 4. The voice facet — rigidity fix + Vera's persona (the variety mechanism)

The rigidity fix is three mechanisms, not "rules + exemplars":

1. **The gear is a conditional tool, not a per-turn beat.** Relocated into the invariant craft as: reflect
   the concern *when trust needs establishing or comprehension has failed*; re-anchor *when the student
   drifts off the concrete problem*; hard-stop and restate *when they say you don't understand them*. Each
   fires **on its signal** — none is a mandatory opening. Most turns are a *single* move (a question, a
   reaction, a challenge).
2. **≥4 stylistically divergent exemplars** in the persona, on **neutral/fabricated stubs** carrying no real
   frame vocabulary (a one-word reaction; a bare question; a sit-with-it; a name-the-dodge) — the model
   samples a distribution, not one shape.
3. **Explicit variety doctrine + test:** never run the same structure two turns running; @live asserts
   sentence-shape variety across N>2 consecutive turns.

**Vera's persona** re-expresses her existing definition (entry.md: *"presence is directness, not warmth"*)
as **economy, reaction, and variety**: a dry sparring partner who presses because she takes your thinking
seriously; reacts like a person; names the dodge instead of re-issuing "pick one"; no em-dash hinge. The
anti-rigidity rules live in the **craft** (so they bind future personas); the persona file is Vera's
*character and idiom* + the divergent exemplars.

## 5. Role registers — world, not analysis (the moat-safe variation) + the CEO/CTO proof

**Governing principle:** a role register colors **where the conversation lives** — the setting, the people
in the room, the texture of the role's day — and **never** the analytical angle. The engine's push owns the
angle (frame-bearing, voiced frame-blind); the register owns only the idiom/world. Frame-orthogonal by
construction:

- **CEO register:** the boardroom, the quarter, the cap table, the customer across the table, positioning.
- **CTO register:** the deploy, the on-call rotation, the shipped artifact, the customer hitting it in the
  field. **Forbidden:** "reversible / rollback / failure-default / optionality" and near-synonyms — those
  **are** the moves on `irreversible_anchor` / `decision_under_stakes`.

Because the spine frame `embed_credentials_as_a_list` recurs across a CTO problem (`irreversible_anchor`)
and a CEO problem (`continuity_lock_in`), role is **not** a proxy for distinct moves — each register's text
is validated against the `frame_detail` vocabulary of **every** problem tagged to its role (lexical guard +
@live paraphrase judge, §9).

**The proof — tag the 5 founder problems:** CEO = `decision_under_stakes`, `continuity_lock_in`,
`license_continuity`; CTO = `irreversible_anchor`, `proof_before_promise`. (`continuity_lock_in` and
`license_continuity` share a `ledger_ref`, so the clean CEO dogfood exemplar is `decision_under_stakes`.)

## 6. The visual facet — presentation theme across the stack (the flashy layer, staged)

The visual facet is the **same identity, seen**. It stacks across three scopes, built in stages that match
the Cartographer's own ("nascent seed now, rich world later"):

- **Persona = the guide's constant mark (now).** A small, consistent visual identity for Vera (mark,
  typographic voice) so you always know who you're talking to — invariant across roles.
- **Role = the room's atmosphere (now, light).** The chat surface is themed by the role's atmosphere — an
  accent ramp + ambient palette (CEO = warm/boardroom; CTO = cool/systems) — pure CSS, driven by the
  resolved theme object the API serves. This is the "build it now" layer (the founder-approved mockup:
  one persona, two role-worlds, voice + atmosphere coherent).
- **Subject = the world's biome (later, with the terrain).** As the Cartographer matures, the *world* themes
  by subject — your founder-strategy territory vs your CS-systems territory as distinct biomes, so
  multi-domain breadth becomes a felt, ownable artifact. **Now**, a light hook only: the nascent-seed
  terrain reveal is tinted by the session's subject. The rich subject-biome 3D world is a later increment.

**The theme object (public, served to the frontend).** `resolve_presentation(...).visual` returns a small
JSON theme: `{ persona_mark, accent_ramp, surface_tints, atmosphere_label }` — palette/identity only. The
frontend (`web/static/index.html`) applies it via CSS variables. No engine call; no rubric; no frame.

**L-13 layering (why the flashy layer is free).** The hidden thing is the **frame** (the move). Persona,
subject, and role are **public**: the learner picks their domain; the problem prompt already reveals its
setting (a shipping problem *is* a CTO setting); the persona is branding. They sit **above** the protected
layer. So theming the surface by role and the world by subject **reveals nothing about the move** — the
frame stays inside the lossy terrain projection + the egress. This is the *same* principle that keeps the
voice register safe (world/setting = public; the move = hidden): the presentation identity is the *skin*,
the frame is the *secret*. The visual facet therefore layers **on top of** the Cartographer's existing L-13
protections (which guard the frame via the lossy projection + the per-region density guard, §4 of the
Cartographer spec), never into them. Zero moat cost.

**Coherence with the Cartographer.** The terrain's frame-protection (lossy projection, density guard,
two-phase timing) is untouched. Subject-theming adds a *public* dimension (which biome) on top — like the
Cartographer's accepted "depth-location is public, move-identity is hidden" (§4d there). Every future
interactive feature inherits the resolved profile, so persona/subject/role coherence carries across the
roadmap for free.

## 7. Composition + threading (engine untouched)

- **Voice composition (a RELOCATION, with inventory):** the gear lives *only* in `concierge.md`
  (reflect-concern, re-anchor, hard-stop) — `concierge_open.md`/`concierge_close.md` have no gear. So this
  is not a de-dup: enumerate the exact gear blocks, assert each appears in the new `voice_craft.md`, and
  assert the composed **turn AND converse** prompts contain all three gear behaviors (string-presence
  tests). Reduce `concierge*.md` to task-only.
- New content: `content/prompts/voice_craft.md` (invariant craft + moat + gear-as-tool); `content/personas/
  vera.md` (character + divergent exemplars + the persona mark/theme base); `content/voice/role_ceo.md`,
  `role_cto.md` (world idiom + the role atmosphere theme).
- `voice.py`: `resolve_presentation(posture, exp) -> {voice, visual}` where
  `voice = persona(subject(posture)) + role_register(exp.role) + craft` (graceful) and `visual` is the
  public theme object. `turn`/`open`/`close`/`converse` pass `voice` to the model methods.
- `model.py`: `concierge_turn`/`open`/`close` gain **keyword-only `voice: str = ""`**, prepended to the
  loaded task prompt. Ripples to the Model Protocol (model.py:73-75), FakeModel (:131-139), and ~8
  test-double overrides; the default keeps them compiling and enforces the graceful floor. The "voice
  reaches the request" test targets `AnthropicModel` (or a spy), not `FakeModel`.
- `content_loader.py`: thin readers for personas/role-registers/craft + the theme; `load_experience` reads
  `role`; the `persona:` key on the posture map (lean) is read via `dict.get`.
- `types.py`: `Experience.role: str | None = None` (additive; untouched `_regime_payload_invariant`).
- `session_runner.py`: bind `a = aim()`; thread `a.posture`; **add `posture` to `ch.record`** so the
  post-convergence `converse()`/`close()` resolve the **same** profile (voice + visual) — otherwise the
  identity flips at the convergence boundary.
- `web/app.py` + `web/static/index.html`: the API serves the `visual` theme (on `menu`/`say`/`close`
  payloads, or once at session start); the frontend applies it via CSS variables (persona mark + role
  atmosphere) and tints the nascent-seed terrain reveal by subject. Public theme only; no frame.

Frame-blindness is *semantic*: persona/role/craft carry no `frame_code` and no paraphrase of a
`frame_detail` they touch; the visual theme carries only palette/identity. Bridge transparency is
unaffected (`FakeModel.concierge_turn` echoes the push regardless of `voice`).

## 8. Invariants that must not drift

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, the three graded Model
  methods. All changes are content, the voice authors, the loaders, `Experience.role`, the API theme, and
  the frontend.
- **Comprehension gear preserved** on the turn AND converse paths (string-presence tests).
- **Moat / L-13 (semantic, both channels):** voice carries no frame paraphrase; the visual theme is
  palette/identity only — persona/subject/role are public, above the frame; the terrain's frame-protection
  is untouched.
- **Persona mark constant** across roles within a subject (the guide is recognizable).
- **Bridge transparency:** `test_runner_assessment_equals_direct_run_session` stays green.
- **Graceful floor:** a `None` role / unknown posture composes a valid profile (voice + a default theme),
  never an error.

## 9. Validation plan

- **Offline (voice + safety):** `Experience.role` loads; `None` role composes no role layer; the resolver
  is graceful (unknown posture → vera, a real test); the composed turn AND converse prompts contain all
  three gear behaviors; **no `frame_code` and no role/persona/exemplar content-word shares with any
  `frame_detail` it touches** (lexical guard over the full tagged set); `model.concierge_*` accept `voice`
  and it reaches the request; egress + transparency stay green.
- **Offline (visual):** `resolve_presentation(...).visual` returns a theme with the expected public keys and
  **no frame_code / no rubric / no `veldra:` ref**; the persona mark is identical across a CEO-tagged and a
  CTO-tagged experience (constant guide); a CEO vs CTO experience yields **different** atmospheres; the
  frontend renders the theme (a thin DOM/CSS-variable assertion or an index.html shape check).
- **@live (the real proof):** CEO vs CTO authored turns have **disjoint idiom-token sets** and neither leaks
  a frame paraphrase (judge); sentence-shape **variety** across N>2 turns; multi-turn engine-free converse
  judged for *cumulative* leak under each role.
- **Founder re-dogfood:** `irreversible_anchor` (CTO) and `decision_under_stakes` (CEO) — Vera sounds like a
  person (not a loop), the two worlds *look and sound* meaningfully different while unmistakably the same
  Vera, and the surface theme matches the register with no steer toward the move.

## 10. Scope — build now vs. stage

- **Build now:** the voice facet (rigidity fix + persona + CEO/CTO registers) AND the **light visual layer**
  (persona mark + role atmosphere themed surface from the served theme; subject-tinted nascent-seed reveal).
- **Stage for later (with the terrain's maturation):** the subject-themed 3D world (founder vs CS biomes),
  transfer/constellation theming, richer persona presence (avatar/motion). The CS persona is blocked on a CS
  *open-ended* rubric existing (`cs_systems` is `path_type: domain`, no rubric).
- **Out of scope:** per-experience persona override; re-authoring the problem prompts; a voice post-filter
  (future fallback). `entry.md` is a 4th hardcoded "Vera" but its reply is discarded on the web path
  (`voice.gate` reads only `.entry_class`) — safe to leave, noted for the CS expansion.

## 11. Open design choice (one, for the plan)

- **Where subject→persona resolution lives:** a `persona:` key on the posture map vs. a resolver in
  `voice.py`. Lean: the map key (L-1; `load_map`/`load_path_type` ignore extra keys). *Decided (were open):
  `role` on `Experience`; gear behaviors are craft.*

## 12. Risks

- **Voice stickiness / template relocation:** mitigated by the *mechanism* (conditional gear + ≥4 divergent
  exemplars + N-turn variety test), not just exemplars; a post-filter is the fallback.
- **Register frame-orbiting:** the offline lexical guard + @live paraphrase judge; world-not-analysis keeps
  it orthogonal.
- **Refactor drops the gear:** the relocation inventory + gear-presence tests on turn AND converse.
- **Visual over-reach:** the now-layer is CSS theming only; the rich subject-world is explicitly staged, so
  we don't ship a glamour shot over near-empty state (the Cartographer's own §8 discipline).

## 13. Review trail

Voice facet: 3 lenses, all ship-with-fixes — folded: registers are world/setting idiom (frame-orthogonal,
validated against every frame); the variety mechanism (conditional gear + ≥4 divergent exemplars + N-turn
test) replaces circular "exemplars fix stickiness"; the refactor is a gear *relocation* with inventory +
presence tests; `posture` added to `ch.record`; `voice: str = ""` keyword-default across Protocol +
FakeModel + ~8 doubles; CEO/CTO proof operationalized (idiom-token divergence + paraphrase judge); graceful
resolver; exemplars on neutral stubs; composition order pinned; `entry.md`/`cs_systems`/`ledger_ref`-aliasing
noted. **Cross-channel elevation (founder steer):** the design now resolves a presentation *profile* (voice
+ visual facets) off one axis; the visual facet (persona mark + role atmosphere now, subject-themed world
later) is L-13-safe because persona/subject/role sit above the frame (the same world-not-the-move principle
as the register), layering on top of the Cartographer's frame-protection, not into it. Architecture and the
founder's decisions unchanged.
