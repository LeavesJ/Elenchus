# The Living Sitting — generated problems over curated rubrics — Design

Date: 2026-07-02
Status: design, founder-brainstormed live (five forks chosen: free-text front door; same-world
next pressure; earned press + adaptive difficulty; screen + regenerate-once with offline audit
deferred; "the living sitting" MVP slice). 3-lens adversarial review: PENDING.
Related: chained sittings + durable sittings (the substrate this rides on); the Cartographer
vision (valley-as-homepage — DEFERRED but design-compatible); the case-library idea (the future
territory-growth axis); frame-mining doctrine (L-6: the unlabeled problem is the moat).

## 0. Why now (founder dogfood 2026-07-02, evidenced)

The first real chained sitting on the new durable build surfaced three felt defects and one
strategic ceiling:

1. **One-turn exits.** Both segments converged on the FIRST answer. Mechanics: `_converged` runs
   at the top of the judgment loop; the founder's intake answers close every target frame, so the
   engine banks with zero presses (`recent: 1 turn, stop_reason: converged` in the sitting
   record). Correct by the engine's rules; felt as a quiz.
2. **Two convergences, one house.** The close showed "1 area has taken shape" with vitality 2.
   Mechanics: terrain REGIONS group frames by shared-problem breadth overlap
   (`terrain.py:_components`); `irreversible_anchor` and `proof_before_promise` share frames
   (`protect_the_core_lane`, `choose_the_failure_default_deliberately`), so both problems merged
   into one region. The reward loop breaks exactly where the user feels it.
3. **The close answers one question.** The close mirrors the FINAL segment only (the known
   deferred sitting-synthesis residual).
4. **The ceiling: four authored doors.** Continue means "next fixed question." The founder's
   verdict: the final format is a user choosing what to approach and the model generating the
   problem impromptu — "if we don't address that we're not going anywhere." The engine
   architecture always assumed this: `run_session` grades an `Experience` and never cares where
   `exp.prompt` came from.

## 1. Goal, premise, slice

**Goal:** a sitting is one generated WORLD. The user says what she's facing; the system maps it
to the closest curated territory and generates the scenario around HER situation; the
byte-untouched engine grades it exactly as today; Continue applies the next pressure to the same
world; End tells the whole sitting's story over a village where every convergence is a house.

**The premise that does not move:** the moat stays curated. Frames, rubrics, traps, corpus
anchors, and the anti-label gate remain authored content. What becomes generated is the SCENARIO
SURFACE. **MVP granularity is the RUBRIC, not the frame:** a forged experience reuses one whole
curated rubric (angle-complete, gated, anchored — the validator requires ≥ min_angle_count
angles, so frame-level composition is a later arc) and swaps only the prompt. The frame-mining /
case-library pipeline grows the TERRITORY library over time; this build makes every territory
infinitely re-skinnable.

**In scope (the founder's slice, "the living sitting"):** free-text front door + mapper;
the forge (scenario generation + gates + fallback); same-world Continue; stress-probe floor on
every rubric; coarse adaptive difficulty; durable identity for generated problems; terrain
house-per-converged-problem; sitting-level close synthesis; the shell surfaces for all of it.

**Out of scope (deferred, named):** valley-as-homepage (worlds are durable rows — compatible);
the offline generator-audit harness (lift-batches against the generator); frame-level rubric
composition; fine difficulty tuning; CS regime; multi-user.

## 2. Design

### 2a. The front door (voice + mapper)

- A sitting now OPENS with Vera's front-door turn (new authored surface, static-backstopped):
  *"What are you facing right now? Describe the decision — or say 'you pick' and I'll bring you
  a problem."* Typed input replaces the picker as the default first beat; the four curated doors
  remain reachable ("you pick" → today's policy-ranked menu, unchanged).
- **The mapper** (server-side classification; sees frame codes — L-13 governs learner-facing
  surfaces, not internal calls): ONE batched `messages.parse` call in the `screen_moves` pattern
  (`_MED_PARAMS`, 4096 budget, numbered candidates, `_require` fails LOUD on truncation — L-17).
  Input: her free text + each territory's learner-safe description. Output: ranked
  `experience_id`s + a fit confidence + a one-line reflection of her situation (her words,
  reusable in the brief).
- **Honest fit:** high confidence → straight to the forge. Low confidence → Vera names it:
  *"Closest territory I can grade well: {territory description}. Work it against your situation,
  or pick a door."* No silent stretching — a mis-mapped diagnostic corrupts the felt diagnosis.
- **Territory descriptions** are new curated content: `content/territories/{experience_id}.md`
  (loader mirrors `load_role_text`), learner-safe by construction (describe the TERRITORY — the
  kind of decision — never the frames or moves; they ride the wire in the honest-fit line, so
  they pass the same no-leak tests as display titles).

### 2b. The forge (dynamic experiences)

New module `src/retnovation/forge.py` (content layer; engine untouched):

- `forge_experience(base: Experience, situation: str, brief: Brief, model) -> Experience`:
  clones the curated base rubric byte-identically (frames, traps, decision_frame, role,
  display_title) onto a new `Experience` with `experience_id = base.experience_id` (the RUBRIC
  identity — selection, dedupe, and analytics key on it), `ledger_ref = "gen:{sitting}:{n}"`
  (the PROBLEM identity), and a GENERATED prompt.
- **The generation brief is frame-blind:** it receives the territory description, her situation
  (her own words), the world-so-far (her committed positions from prior segments — text she has
  SEEN, never engine reads), the role register, and a coarse level line (§2e). It NEVER receives
  `frame_detail`, trap details, rubric text, or any engine state. Authored prompt:
  `content/prompts/forge_scenario.md` (second person, concrete stakes, one real decision, no
  advice, no move-naming — the same doctrine family as `push.md`).
- **Gates, in order (all existing machinery):**
  1. Structural: non-empty, second person, ends in a decision ask, length bounds (code checks).
  2. **Egress:** `screen_moves(moves(base), scenario)` — the generated scenario must PERFORM
     none of the base rubric's frames/traps (the L-13 teeth; one batched call).
  3. **Anti-label:** the forge runs the same anti-label validation the gated loader applies to
     curated content, against the generated scenario (the recon-confirmed bypass — passing an
     explicit `experience_id` skips `load_gated_library`'s gate — is thereby CLOSED at the forge
     boundary; a forged experience is never served ungated).
  - One failed gate → ONE steered regeneration (the failure reason in the steer, mirroring the
    landing-gate retry convention) → on second failure, fall back to the curated base experience
    verbatim (the door still opens; the sitting never bricks on generation).
- **Seeding:** before serving, the forge writes the minimal durable rows: a `LedgerEntry`
  (`gen:` ref, `owned_problem` = the generated scenario) so breadth/terrain/state joins stay
  coherent (recon: no FK constraints, but `state.frames[code].breadth` collects the ref and the
  terrain projects from it), plus the sitting store's generated-problem row (§2f).

### 2c. Same-world Continue

- The sitting store persists the WORLD: `situation` (her front-door text + the mapper's
  reflection) and, per segment, her committed position (the landing-adjacent summary she saw).
  Continue no longer offers "the next fixed door": it targets the **next territory** — the
  highest-ranked rubric (mapper relevance × policy need) whose `experience_id` has NOT converged
  within the rolling window — and forges the next pressure ON the same world.
- The one-click button reads `Continue → {a short generated pressure-title}`? NO — titles are a
  leak surface and a latency cost. The button stays plain: **"Continue — next pressure"** (the
  world is the context; the door reveal IS the opening). `other doors…` still opens the honest
  menu (curated doors + "change what we're working on" → the front door again).
- Dedupe keys on BOTH identities: `experience_id` (territory recency — don't silently re-press a
  just-converged territory within 24h) and `gen:` ref (a problem instance never re-serves).
- Mid-world honesty: if every territory is inside the window, Continue says so and offers the
  menu / a fresh situation — never a silent repeat (the founder's original complaint).

### 2d. The arc floor (content-level; engine bytes untouched)

- Every curated rubric adopts `decision_frame` (the P2 probe-gated-convergence field —
  `_converged` refuses to bank until the decision frame is in `probed`, and `_select_target`
  stress-probes a `present_reasoned` frame): an intake-complete answer now ALWAYS earns at least
  one real press before the landing. Five rubric YAML edits + the forge clones the field.
- The stress press is the "earned press" beat the founder chose: commit-under-consequences on
  the frame she already holds — rigor, not repetition (L-4/L-5 hold: the press stresses, never
  grades or names).

### 2e. Coarse adaptive difficulty

The forge brief's level line is derived from the sitting store only (never engine reads):
recent press counts and stop reasons from the persisted records — e.g. *"This user has been
resolving pressures in one to two exchanges; write the scenario one notch past that: tighter
constraints, no comfortable default."* Frame-blind, verdict-free (press count and stop reason
are process signals — the L-4 boundary already established for the landing). Fine tuning is
deferred; the lever exists from day one.

### 2f. Identity, terrain, close

- **Sitting store additions:** `web_world(sitting_id, situation, updated_at)` and
  `web_generated_problem(ref, sitting_id, experience_id, scenario, created_at)` — L-3 retained
  forever; resume re-renders generated scenarios verbatim from here (already-egressed text), and
  `_lost_context`/honesty branches work unchanged over `gen:` refs.
- **Terrain: houses are problems.** `learner_view` gains per-problem HOUSES within regions: the
  `Region` model already carries `problems` (ledger refs in the converged frames' breadth); the
  view renders one house per problem-with-vitality, ordinally positioned and bucketed exactly
  like regions today (rename-invariance preserved: no codes, no refs on the wire — houses are
  positional ids). The founder's two-convergences sitting becomes the regression test: two
  houses, whatever the region math says. The renderer places houses within their region cluster
  (Three.js layer change, same ordinal-only discipline).
- **Sitting-level close.** The close author receives the whole sitting: the situation + every
  segment's dialogue (the sitting store has them all). New authored prompt
  `content/prompts/concierge_sitting_close.md`: tell the WORLD's story — where she started, what
  each pressure cost her, what she owned by the end — retrospective register, no verdicts
  (L-4), no moves (egress-screened against the UNION of the sitting's experiences' moves — the
  union machinery shipped tonight). Static fallback preserved. This closes the deferred
  "close mirrors the final segment" residual.

### 2g. Wire and shell

- Front door: the cold payload becomes `{kind:"frontdoor", say: <Vera's ask>, menu?: …}` —
  composer active immediately; "you pick" or a menu click falls back to today's flow. Resume of
  a live world re-renders the transcript as today (no new wire surface; the world lives
  server-side).
- L-13 on the wire, unchanged discipline: `gen:` refs NEVER reach the client (the sitting-store
  turn mirror already enforces payload-projection); territory descriptions are the only new
  learner-facing text and are curated + tested with the no-leak helpers.
- Continue button copy changes; `other doors…` keeps the picker; the front-door beat is skippable
  in one tap. Latency per beat: front door ≈ mapper + forge + screen (~3 calls) before the first
  scenario; each Continue ≈ forge + screen (~2). MEASURED in the health smoke (L-20: count calls,
  time them, batch before tuning effort).

## 3. Signal integrity (the whole point)

- **The graded path is byte-identical.** Forged experiences carry curated rubrics; intake and
  responses grade against the same frames with the same classifier calls; `reasoned_unprompted`
  and breadth accrue per `gen:` problem exactly as per curated problem (breadth GROWS — distinct
  problems per frame is precisely what the transfer axis wants).
- **The scenario is the new leak surface** → three gates (§2b), fail-closed to curated content.
  The generator is frame-blind by construction; the egress screen is the teeth; the anti-label
  gate closes the recon-confirmed `experience_id` bypass.
- **Same-world carry:** the brief carries only text the user has seen (her words, her committed
  positions). Closed frames appearing as world CONTEXT are user-known (the voice-arc rule); the
  screen guards the CURRENT target's moves. Cross-segment: each segment remains a fresh engine
  session on a fresh problem (bridge transparency per segment, unchanged).
- **The mapper** sees frame codes server-side; its learner-facing output is territory
  descriptions only.
- **Residual, honest:** a generated scenario that leaks subtly PAST the screen corrupts that
  frame's unprompted signal for that user — the same residual class as every authored surface,
  now at generation scale. Mitigations: the screen (measured 6/6-0/6 solid on fixed texts), the
  regen steer, the curated fallback, and the deferred offline generator audit. Zero is not
  claimed.

## 4. Testing

- **Offline (FakeModel-scripted generation):** forge returns a gated experience (rubric
  byte-equal to base; prompt = canned generated text); a move-performing scenario is CAUGHT by
  the screen (inject a leaking fake → regen → fallback path asserted); anti-label reject path;
  structural rejects; ledger seeding (gen ref row exists; breadth accrues; terrain projects);
  mapper low-confidence → honest-fit payload; "you pick" → today's menu; stress-probe floor —
  the intake-complete fake (the founder's dogfood shape) gets ≥1 press before done on EVERY
  rubric; same-world continue targets a non-windowed territory and never re-serves a `gen:` ref;
  all-territories-windowed → honest menu; two-convergences → TWO houses (the dogfood regression);
  sitting close receives all segments (spy) and passes the union screen; resume mid-generated-
  world re-renders the scenario verbatim; L-13: no `gen:` refs / frame codes / territory leaks on
  any payload (no-leak helpers over the new surfaces).
- **Bridge transparency per segment unchanged** (existing test keeps passing — the forged
  experience path must not touch it).
- **@live (founder-gated):** one real free-text sitting end-to-end; generator quality eyeball;
  per-beat latency measurement; the no-verdict/no-move behavioral checks on the new authored
  surfaces (front door, sitting close, forged scenario).
- Engine-diff gate: `git diff -- src/retnovation/orchestration.py src/retnovation/assessment/`
  stays empty (rubric YAML `decision_frame` additions are content).

## 5. Honest residuals

- Generation quality variance is real until the offline audit harness lands; the fallback door
  and the founder's dogfood are the MVP floor.
- Five territories today — the sitting exhausts them in five convergences; the mining/case
  pipeline is the growth axis (already queued as its own thread).
- Adaptive difficulty is one coarse line; spaced re-serving of generated problems (retention
  over `gen:` refs) rides the engine's existing frame-level scheduling, not bespoke logic.
- The valley homepage is deferred; worlds are durable rows so nothing here is throwaway.
- Latency of the front-door beat (~3 calls) is measured, not assumed; if it drags, the mapper
  and forge briefs are the batching candidates (L-20).

## 6. Files touched

- NEW `src/retnovation/forge.py`; NEW `content/prompts/forge_scenario.md`,
  `content/prompts/concierge_sitting_close.md`, `content/territories/{5}.md`; NEW
  `tests/test_forge.py`.
- `content/rubrics/*.yaml` — `decision_frame` on the four rubrics lacking it.
- `src/retnovation/model.py` — `map_territories` + `forge_scenario` + `concierge_sitting_close`
  model methods (screen_moves pattern; L-17 budgets); FakeModel counterparts.
- `src/retnovation/terrain.py` + `web/static/terrain3d.js` — houses-per-problem within regions
  (rename-invariant guard extended, not weakened).
- `src/retnovation/web/session_runner.py` / `app.py` / `voice.py` / `static/index.html` — front
  door, world persistence, forge-backed continue, sitting close, wire changes.
- `src/retnovation/web/sitting_store.py` — `web_world`, `web_generated_problem`.
- Tests across `test_session_runner.py`, `test_web_api.py`, `test_terrain.py`.

## 7. Doctrine carried in

Engine byte-untouched (the arc floor is content; the forge is a new layer; grading identical).
L-1 (territories, briefs, prompts are content). L-3 (worlds and generated problems retained).
L-4 (level line and close describe process, never verdicts). L-5/L-13 (forge gates; territory
descriptions curated; refs server-side; houses positional). L-6 (the generated problem stays
unlabeled — the gates exist to keep it that way). L-8 (the anti-label gate is enforced at the
forge boundary, closing the runtime bypass). L-17 (new model calls get measured budgets).
L-20 (count calls before tuning). User-owned closure and the durable-sitting substrate ride
unchanged beneath all of it.
