# Retnovation UI/UX — The Cartographer — Vision + MVP Design

Date: 2026-06-28
Status: design (vision + thin MVP slice). Review folded (§8a trial/guard tension resolved; per-region guard;
§4c honest scoping; hazard-leak resolved by inheriting §4; stepper-equivalence test required). One item OPEN:
positioning (§9). Awaiting user confirm of the §8a wedge decision → writing-plans.
Related: `retnovation-ui-ux-vision` memory; P3 (the diagnostic-progression interactive surface with injectable seams).

## 1. The problem

Everything the engine computes — frame strength (weak→forming→strong), drives, the unprompted-read,
`unprompted_breadth`/transfer, reversible decay + savings, the friction trajectory, the trap gallery — is
**invisible**. If the surface is a chatbox, the user experiences "a chatbot that asks hard questions,"
indistinguishable from ChatGPT-with-a-system-prompt, and the engine's sophistication is worthless *as a
product*. The surface must make the invisible engine **felt**, be **distinctive** (not a chatbox, not
Duolingo-gamified, not flashcards), and **sell** — while honoring the no-name-the-frame doctrine (L-13).

## 2. Market white space (light scan, 4 categories)

Four parallel researchers (decision/judgment sims; AI coaching/roleplay; spaced-repetition/mastery-viz;
narrative/branching) found the **same four absences**: (a) everyone grades the *conclusion/outcome*, never
reasoning quality; (b) everyone *names the framework upfront*; (c) the diagnosis is hidden behind a score or
chat transcript — nobody shows *where you are on a move* as a visible object; (d) nobody surfaces *transfer*
or *reversible decay* as a felt arc. The unclaimed triple: **open free-text reasoning + live engine diagnosis
of the move + a spatial metaphor that externalizes trajectory without labeling it.** Our engine already does
the first two; the UI is the third.

**Methodological caveat (recorded):** all four researchers were given the same lens (our mechanics), so the
"convergence" is partly the prompt reflected back. The *empirical* absences are real (the products are what
they are); the rhetorical weight of "4/4 convergence" is discounted accordingly.

## 3. The concept — the Cartographer: a cultivated world under a constellation sky

The visible, ownable artifact is **a living world of your judgment** that grows across sessions, blending
three felt registers:

- **Build/city register — height = accreted, durable strength.** You raise the land by reasoning; elevation
  accretes and persists across sessions (the `evidence_count`/`breadth` axis).
- **Garden register — surface glow = current vitality.** The surface lives, *fades* (reversible decay when
  untended), and *rebounds* (savings effect — springs back richer on one re-exposure).
- **Constellation register — the sky = transfer.** When the same move surfaces unprompted in a distant,
  differently-dressed problem, a thread arcs between regions up into a star-field; broad transfer reads as a
  shared sky, not a ground-web.

**Two axes, deliberately separated** (height vs. glow): so "deep but fading" (tall + grey) reads differently
from "new but fresh" (short + bright) — the single most useful distinction a one-number "mastery bar" cannot
show.

## 4. The doctrinal crux and its resolution (felt vs. don't-name-the-frame)

The hard constraint: the surface must be *felt* yet must never let the learner decode the map into the
forbidden move-label — and this must hold **across sessions**, where reveal-timing alone does not protect.

Four moves resolve it:

1. **Read-only mirror, not a navigable menu.** You never click "work on region X" (that would require
   labeling X). You pick a *problem* (the existing no-frame problem menu — problems, never moves); the terrain
   only *reflects* where reasoning has and hasn't held. The map is a consequence, not a control panel.
2. **Two-phase timing — the within-session L-13 mechanism.** *During* a session: only the unlabeled problem +
   the friction-dialogue on screen; no terrain, no labels — the unprompted read stays clean. The terrain is
   revealed *after* the read is locked ("return to the map"). A reveal cannot reach back into a captured read.
3. **Lossy, non-invertible projection — the cross-session safety.** The engine knows fine-grained per-frame
   strength; the map deliberately renders a *coarser* aggregate (vitality per problem-cluster/region) through a
   defined `terrain_projection: fine per-frame state → coarse region vitality` that is **non-invertible by
   construction** (many moves and problems fold into one region's vitality). The coarseness *is* the safety,
   and it is what gives the map its soft, map-like feel.
4. **The frame-level layer stays the author's.** The `SelectionReceipt`/drive/frame decomposition (which
   *does* name frames) remains the async instructor log, never rendered to the learner — exactly as P3 already
   enforces.

**The honest bound (not zero-leak):** the claim is the leak is *bounded below the rate of genuine learning* —
because the field is lossy and content-delocalized, the cheapest way to brighten a region is to actually reason
well across its varied problems, so **exploiting the map converges to learning the move.** The design succeeds
exactly when "game the map" and "learn the reasoning" are the same action.

### 4a. Corpus-dependence (the safety is strongest late, weakest now)

Non-invertibility is a property of the projection **× the content distribution**, not the projection alone. At
user-zero (≈2 owned problems + embed as the one new frame) a region may hold one dominant move — formally lossy
but practically invertible. **The safety claim strengthens as content grows and is weakest at the start.** An
early clean read does not certify the projection; an early leak may indict corpus sparsity, not design. There
is a real **coarseness floor**: past some coarseness the map stops being felt, so the safe-vs-felt tension is
tightest when content is thinnest (now).

### 4b. The non-invertibility guard = a PER-REGION corpus-density gate

Encode the precondition as a test/guard (the `assert_intake_equivalence` pattern from the elicitation work): a
**region renders only when its OWN vitality draws on ≥N distinct frames across ≥M problems**; below that
threshold the region stays in the pre-map **seed/fog** state rather than rendering decodable vitality. The gate
is **regional, not global.** Corpus grows unevenly — a heavily-worked region is dense/many-to-one while a
barely-touched one is one dominant move — so a single global render-or-refuse either blocks the whole map until
the *thinnest* region matures (wasting the density already earned in the dense one) or renders the sparse region
while it is still invertible. Per-region gating instead makes the Cartographer **grow unevenly the way the
corpus does** — dense regions become real terrain, sparse ones stay seeds — which is both safer and a more
honest picture of where the learner actually has breadth. "Safety strengthens with content" is thus *enforced
per region*; at user-zero every region is sub-threshold (all seeds), which is exactly the nascent-seed MVP state
(§8). `N`, `M` are calibration parameters tuned to corpus size.

### 4c. The falsification test (paired, not single)

"Strong-on-familiar, weak-on-novel" is equally the signature of *genuine non-transfer* (the true state the
engine exists to detect), so a single held-out novel problem cannot distinguish a gamed map from honest
non-transfer. The discriminating test is **paired**: read the same region's problem **with the terrain shown**
vs. **with it hidden** (a true clean-room read). Strong-with / weak-without = the terrain is inflating;
weak-in-both = honest non-transfer, map innocent. **Be honest about what this does and doesn't cover:** the
live-terrain increment is the *smaller* leak. The *larger* one — the **cross-session memory prime** (what the
learner carries into the next opening read from having seen the map) — is **blind to the paired test**, because
both arms run on a learner with the *same* memory. That memory prime is the leak the entire lossy projection
exists to bound, and in the MVP it is **defended-by-projection but not tested** — its adequacy is asserted, not
measured. A real test of it needs a **between-cohort design** (saw-the-map vs. never-saw) on matched novel
problems — a later-corpus experiment, not a user-zero one. The paired test is also **run per region** against
that region's density (§4b): a leak in a sparse region and a dense region mean opposite things.

### 4d. The rebound leak (accepted)

The savings-effect visual (rebound faster than first growth) is the most-legible element, but it decodes to
"where am I durably deep" (depth-location), not "which move" (move-identity). That is the one piece of
self-knowledge we *want* the learner to have — an accepted, noted, bounded leak.

## 5. The encodings (stress-tested)

Five problems surfaced and shaped the design:

1. **Glow was overloaded** (vitality, transfer, rebound all "bright"). → Separate channels: vitality = surface
   color; transfer = a thread in the *sky*; rebound = *motion*; slip = a red *shape*.
2. **Vitality-as-one-number hid two signals.** → Split onto two axes: height = accreted strength, glow =
   current vitality (§3).
3. **Pairwise transfer threads are O(N²) spaghetti.** → Constellation: links in the sky; only
   genuinely-transferred pairs draw; broad transfer = a shared sky, not a ground-web.
4. **Rebound ≈ first-time growth in a still frame.** → Rebound is *animated* (springs up faster than it first
   grew; speed is the tell).
5. **The slip/hazard leak — resolved by inheriting §4.** It is the region-decoding leak in different clothes: a
   marker pinned to one `trap_code` is invertible exactly as a region pinned to one move is. So hazards take the
   *same* treatment — **cluster traps so no marker maps to one failure mode** (lossy), gated per-region (§4b) —
   and the residual is an accepted **bounded depth-location leak** like rebound (§4d). Not a separate open
   question; solving it any other way would risk inconsistency with the regions.

## 6. Positioning / go-to-market (OPEN — parked by the user)

Why the white space persists (research): **H2 commercial illegibility dominates (~60%)**, H1 tried→absorbed
(~30%), H3 newly-possible (~10%). Koru, Pymetrics, Humu, Knewton — process-level/non-outcome-grading products
that *died at the sales motion, not the product*, because enterprise L&D can't map "reasoning improved" to
Kirkpatrick/Phillips ROI. So the white space is **a graveyard for enterprise** — the same fact as the vision
memory's "hard to sell."

The way through (both research streams converge): **B2C / narrow-premium to discerning individuals who
self-evaluate** — bypassing the Kirkpatrick legibility trap. This matches "dogfood = product" (the founder is
the first discerning individual). Illegible value sells via **(A) a self-demonstrating trial** (the buyer
becomes the measurement instrument), **(B) founder/practitioner credibility**, **(C) peer/cohort filter** — A+B
are our wedge. **The terrain doubles as the B2C self-legibility bridge:** it makes progress self-legible
(vitality/trajectory) without being move-decodable (the lossy projection) — solving "legibility first" via
*self*-legibility. **Risk:** the trial only self-demonstrates for the meta-aware, so the beachhead is narrow
("people who already suspect they have a judgment problem"); broadening to enterprise before that core is proven
forces the legibility compromises that killed the precedents.

**Status: parked.** The design above does not depend on resolving B2C-vs-enterprise; it is recorded here as an
open strategic decision the user chose to revisit separately.

## 7. Medium + architecture

- **Local web app:** a *thin* **FastAPI** layer over the untouched engine + a **browser** frontend (HTML/JS;
  Three.js/WebGL for the terrain). Most sellable/distributable for the B2C path, richest visuals, and the 3D
  runs natively in-browser. (Not a desktop wrapper, not a TUI — both undershoot the felt/sellable bar.)
- **Reuses the P3 seams:** `present`/`decide`/`decide_core` become API-mediated instead of CLI `input()` — no
  rework to the judgment loop; the seams were built for this.
- **Checkpointed stepper (L-11):** you cannot block on `input()` across an HTTP boundary, so the session
  advances **one step per request**, persisting loop-state to the existing SQLite store. This is the main piece
  of *new* engine-adjacent code — and the one place the unprompted-read property could silently break: a
  step-per-request loop must reconstruct the same intake `frame_states` and `probed` set the synchronous loop
  held in memory, and a lossy reconstruction would compromise `reasoned_unprompted` at the surface after it was
  protected everywhere upstream. **Required test (elicitation-guardian pattern):** assert the stepped →
  persisted → reloaded loop produces byte-identical `frame_states`, `probed` set, and `reasoned_unprompted` to
  the in-memory loop on the same scripted inputs, so the HTTP boundary cannot change what counts as unprompted.
- **`terrain_projection`** (the lossy seam, §4) lives in the engine; the API serves its coarse output; the
  frontend renders it; the non-invertibility guard (§4b) gates whether it renders at all.

## 8. The MVP slice — "trial + nascent seed"

The first-session **self-demonstrating trial is the conversion mechanism**, and the terrain is thin/guard-gated
at user-zero. So the thin slice is:

- **In scope:** the clean-room friction-dialogue **end-to-end through the real engine**, in the browser, over
  the FastAPI stepper — propose (no-frame problem menu) → present problem → opening read → probe loop →
  converge → assess/persist. Plus a **one-seed nascent terrain reveal** afterward (a single seed appears on a
  near-empty world — "watch your world begin"), which dogfoods `terrain_projection` + the guard from day one.
  (No contradiction with §4b: the guard gates the *rich, decodable multi-region* map; a single nascent seed is
  *below* that threshold — one point is nothing to decode — so it is shown honestly as "your world begins,"
  pre-map, not as a readable terrain.) **Required:** the stepper-equivalence test (§7) ships with this slice.
- **Out of scope (later increments):** the rich 3D terrain over a mature corpus; transfer trails; the full
  garden decay/rebound animation; multi-session map accretion at scale. These earn their way in as the corpus
  grows (§4a–4b).
- **Why not "rich terrain now":** it would be the glamour shot over near-empty state, and the guard would gate
  it.

## 8a. The trial-vs-guard tension (resolved)

§8's trial is the conversion mechanism; §4b's guard withholds the rich, decodable map at user-zero — *every*
trial user's state. So the guard gates the terrain exactly when conversion would most want a wow, and the
clean-room dialogue alone is (by §1) what reads as "ChatGPT-with-a-system-prompt" to a first-timer. As first
written, §6 and §8 did not compose.

**Resolution — the wow is the dialogue, not the terrain.** The trial's self-demonstration is the **felt
diagnosis in the friction-dialogue** — the probe that catches a flaw the user would have missed (mechanism A:
"the buyer becomes the measurement instrument"). It fires in the first session, *ungated*. The **terrain is a
retention / self-legibility artifact for the *converted*** — who by definition have done sessions and grown
corpus — so gating it early (per-region, §4b) costs conversion nothing. The single nascent seed is a *teaser*
of that retention artifact, not the wow.

**Consequence — the narrow beachhead is intrinsic, not manufactured.** The narrowness ("people who already
suspect they have a judgment problem") comes from the **conversion mechanism** — felt diagnosis only lands for
the meta-aware — **not** from the guard; the guard merely *aligns* with it (both point at the same narrow
beachhead). Further, gating the flashy terrain from the unconvinced is **protective**: converting-via-flash the
users who cannot yet perceive the value is precisely how you acquire the customers who later force the
legibility compromises that killed Humu/Pymetrics (§6). So the guard is a GTM *feature*, not a tax, and the
narrow wedge is a **deliberate choice.** (Rejected the alternative — make the seed carry the wow — because a
more demonstrative seed is a more decodable seed, reopening §4.)

**Status:** a strategic commitment that connects to the parked positioning (§6, §9). Confirm before writing-plans.

## 9. Open items

1. **Positioning (§6) — parked by the user.** B2C-vs-enterprise go-to-market. Sharpened by §8a: the narrow
   beachhead is *intrinsic to the conversion mechanism*, so the open choice is *how narrow, deliberately* (and
   whether/when to attempt an enterprise legibility bridge) — not *whether* the wedge is narrow.

*(The hazard/slip leak, previously open, is resolved in §5 #5 by inheriting the §4 projection.)*

## 10. Visual references

Two concept renders were produced live in the brainstorm (ephemeral chat widgets, not committed assets): (a) a
flat annotated "return to the map" reveal; (b) an interactive 3D "cultivated world" (drag-to-orbit terrain:
height = accretion, glow = vitality, sky-thread = transfer, pulsing node = rebound, red marker = slip); (c) a
contrast triptych (sparse user-zero → mature, plus the spare in-session clean room). The visual language is
specified in words in §3–§5 so it survives without the renders.

## 11. Doctrine carried in

Conclusion-agnostic (never grade the conclusion); the unlabeled-problem moat (L-6); never name the frame to the
learner (L-13, here a property of *when* + *how-lossy* the terrain is, §4); reversible decay with savings
(§3, §4d); the frame-level receipt stays the author's async log (§4).
