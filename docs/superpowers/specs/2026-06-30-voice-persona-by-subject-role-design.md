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
backstops every voice; and **the entire presentation identity sits *above* the per-problem move** — it
reveals "which world," never "which move on this problem." That is a **bounded, corpus-dependent
domain-location leak** of the Cartographer §4d family (the accepted-leak class), not zero — honest framing,
detailed in §6.

## 3. Data model + resolution

- **Subject → persona** from `aim().posture` (default `founder_ceo`). MVP: founder postures → `vera`.
  Graceful: unknown/missing posture falls back to `vera` (the single-voice floor), never raising.
- **Role → register + atmosphere** from a new `Experience.role` (`"ceo" | "cto" | None`), loaded from the
  rubric YAML. `None` composes the base persona, no role layer.
- **The profile** = `{ voice: <composed system text>, visual: <theme object> }`, resolved in **two
  phases** because role is only known after a problem is picked: **persona + subject at menu time**
  (`posture` known, no `exp` yet), **+ role at problem-entry** (`exp`/`role` bound in `present()`). The menu
  surface is therefore correctly persona/subject-themed and role-neutral; the role atmosphere arrives as you
  enter a problem. **Decided** (was open): `role` lives on `Experience`.

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

- **Persona = the guide's constant mark (build now).** A small, consistent visual identity for Vera (mark,
  typographic voice) so you always know who you're talking to — invariant across roles.
- **Role = the room's atmosphere (build now, light).** The chat surface is themed by the role's atmosphere —
  an accent ramp + ambient palette (CEO = warm/boardroom; CTO = cool/systems) — **pure frontend CSS over the
  served theme; it touches only the chat surface, never the terrain.** This is the founder-approved mockup:
  one persona, two role-worlds, voice + atmosphere coherent.
- **Subject = the world's biome (STAGED, with the terrain — not now).** As the Cartographer matures, the
  *world* themes by subject — your founder-strategy territory vs your CS-systems territory as distinct
  biomes, so multi-domain breadth becomes a felt, ownable artifact. **Deferred from the now-layer**, for two
  reasons the review surfaced: (a) at user-zero there is one subject and one nascent seed, so a subject tint
  is a cosmetically **inert no-op wash** (consistent with §8a "don't glamour-shot the empty state"); (b)
  "tint the reveal by subject" risks an implementer threading subject *per-region* through `terrain.py`,
  re-opening the invertibility the just-shipped hardening (positional ids, bucketed vitality,
  rename-invariance) closed. When it lands: a **session-level frontend wash keyed on the public `posture`**
  is safe; any **per-region/biome** tint must pass the Cartographer §4b per-region density guard first
  (mirroring the §5#5 hazard-cluster treatment) and the wire payload gains no subject/biome field.

**The theme object (public, served to the frontend).** `resolve_presentation(...).visual` returns a small
JSON theme: `{ persona_mark, accent_ramp, surface_tints, atmosphere_label }` — palette/identity only.
`atmosphere_label` is drawn from a **fixed enum of world tokens** authored in `role_*.md` (e.g. `boardroom`,
`systems`), never derived from a rubric/`frame_detail`. The frontend (`web/static/index.html`) applies it via
CSS variables. **Delivered through the single `_emit` egress whitelist, built from `posture`/`role` only —
never sourced from `ch.record`** (which holds the rubric); two-phase (§3): persona+subject on the
session-start/menu payload, role atmosphere on the first `say` after `choose`.

**L-13 layering — the honest bound (NOT zero).** The hidden thing is the **frame** (the move on a problem).
Persona, subject, and role are **public**: the learner picks their domain; the problem prompt already reveals
its setting (a shipping problem *is* a CTO setting); the persona is branding. They sit **above** the
per-problem move that L-13 protects on the live read — so the theme reveals nothing about the move on the
problem in front of you, the same way the voice register does (world = public; the move = hidden). **But it
is not zero-leak.** The role atmosphere is a *stable, machine-applied* 2-way signal (warm/cool) an observer
can read **across** a session history without reading prompts — and on the thin current corpus that signal
**correlates with frame-membership-sets** (e.g. `lead_with_what_you_refuse_to_do` and
`commit_under_the_deadline` appear only under CEO-tagged problems, so "cool" is a negative signal for them).
This is exactly the Cartographer's §4a corpus-dependence hazard on the role axis: a **bounded,
corpus-dependent domain-location leak** of the §4d accepted-leak family — it reveals "which world / which
frame-bucket," never "which move on this problem," and it **strengthens toward non-invertible as both role
buckets fill with shared frames.** The honest claim is therefore the Cartographer's, not "free": the leak is
bounded below the rate of genuine learning and shrinks with corpus growth. (The voice register's
frame-orthogonality guard, §5, is the *voice* dual of this; §9 adds the *visual* dual.)

**Coherence with the Cartographer.** The terrain's frame-protection (lossy projection, density guard,
two-phase timing) is **byte-untouched** — the now-layer visual is chat-surface-only and never reaches
`terrain.py`/`learner_view()`. Subject-theming (the staged layer) adds a *public* dimension (which biome) on
top, like §4d's "depth-location public, move-identity hidden," and is gated by §4b when per-region. Every
future interactive feature inherits the resolved profile, so persona/subject/role coherence carries across
the roadmap.

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
- `web/app.py` + `web/static/index.html`: the API serves the `visual` theme **through the single `_emit`
  egress whitelist**, built from `posture`/`role` only and **never sourced from `ch.record`** (which holds
  the rubric). Two-phase: **persona + subject** on the session-start/menu payload (`posture` known); **role
  atmosphere** on the first `say` after `choose` (where `exp` is bound in `present()`). The frontend applies
  the theme via CSS variables to the **chat surface only** (persona mark + role atmosphere). **The
  now-layer does NOT touch the terrain reveal** — `terrain.py`/`learner_view()`/the wire payload are
  byte-unchanged; subject/biome tint is the staged layer (§6).

Frame-blindness is *semantic*: persona/role/craft carry no `frame_code` and no paraphrase of a
`frame_detail` they touch; the visual theme carries only palette/identity. Bridge transparency is
unaffected (`FakeModel.concierge_turn` echoes the push regardless of `voice`).

## 8. Invariants that must not drift

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, the three graded Model
  methods. All changes are content, the voice authors, the loaders, `Experience.role`, the API theme, and
  the frontend.
- **Comprehension gear preserved** on the turn AND converse paths (string-presence tests).
- **Moat / L-13 (semantic, both channels):** voice carries no frame paraphrase; the visual theme is
  palette/identity only (no `frame_code`/rubric/`veldra:` ref; `atmosphere_label` from a fixed enum) —
  persona/subject/role are public, above the per-problem move. The residual role-atmosphere↔frame-set
  correlation is an **accepted, corpus-dependent, shrinking** leak (§6), not zero.
- **Terrain byte-untouched in the now-layer:** the role/persona theme is applied **frontend-only** to the
  chat surface; `terrain.py`, `regions_to_view`, `learner_view()`, and the wire payload gain no
  subject/biome field. (The staged per-biome tint, when it lands, passes the §4b density guard.)
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
- **Offline (visual):** `resolve_presentation(...).visual` keys are exactly
  `{persona_mark, accent_ramp, surface_tints, atmosphere_label}` with **no `frame_code` / no rubric / no
  `veldra:` ref**, `atmosphere_label` ∈ the fixed enum, and the theme is **not sourced from `ch.record`**
  (no rubric/exp field reachable); the **persona mark is identical** across a CEO- and a CTO-tagged
  experience (constant guide); the theme is **two-phase** (menu payload carries persona+subject, no role;
  the post-`choose` `say` carries role). Note: that a CEO vs CTO experience yields *different* atmospheres is
  the intended behavior — it is **not** asserted as "safe," because that divergence *is* the bounded §6 leak;
  the safety assertion is the frame-free/enum/whitelist checks above, plus the visual dual of the lexical
  guard: **no theme field is a function of `frame_code`** (trivially true since it keys on `role`), recorded
  alongside the accepted role↔frame-set residual.
- **@live (the real proof):** CEO vs CTO authored turns have **disjoint idiom-token sets** and neither leaks
  a frame paraphrase (judge); sentence-shape **variety** across N>2 turns; multi-turn engine-free converse
  judged for *cumulative* leak under each role.
- **Founder re-dogfood:** `irreversible_anchor` (CTO) and `decision_under_stakes` (CEO) — Vera sounds like a
  person (not a loop), the two worlds *look and sound* meaningfully different while unmistakably the same
  Vera, and the surface theme matches the register with no steer toward the move.

## 10. Scope — build now vs. stage

- **Build now:** the voice facet (rigidity fix + persona + CEO/CTO registers) AND the **light visual layer**
  — persona mark + role atmosphere themed onto the **chat surface only**, from the served theme. (No terrain
  touch.)
- **Stage for later (with the terrain's maturation):** the **subject-themed world** (founder vs CS biomes) —
  deferred from now because it's inert at user-zero and risks the per-region terrain coupling (§6); a
  session-level wash is safe when it lands, per-biome tint passes the §4b guard. Plus transfer/constellation
  theming and richer persona presence (avatar/motion). The CS persona is blocked on a CS *open-ended* rubric
  existing (`cs_systems` is `path_type: domain`, no rubric).
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
- **Visual over-reach:** the now-layer is chat-surface CSS only; the subject-world is staged, so we don't
  ship a glamour shot over near-empty state (the Cartographer's §8 discipline).
- **Role-atmosphere domain leak (accepted):** the warm/cool tint correlates with frame-sets on a thin corpus
  (§6) — bounded, corpus-dependent, shrinking; framed honestly (not "zero"), the §4d-family residual.

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
as the register), layering on top of the Cartographer's frame-protection, not into it. **Visual-facet
review (1 focused lens, SHIP-WITH-FIXES) folded:** dropped the overclaimed "zero moat cost" for an honest
bounded/corpus-dependent domain-location leak (the role-atmosphere↔frame-set correlation, §4a/§4d family);
**deferred the subject-tint** from the now-layer (inert at user-zero + per-region terrain-coupling risk),
making the now-layer chat-surface-only; theme delivered via the `_emit` whitelist from public fields,
**two-phase** (persona+subject at menu, role at problem-entry); `atmosphere_label` constrained to a fixed
enum; an explicit "terrain byte-untouched, tint frontend-only" invariant; the §9 offline check no longer
*certifies* the CEO/CTO divergence as safe. Architecture and the founder's decisions unchanged.
