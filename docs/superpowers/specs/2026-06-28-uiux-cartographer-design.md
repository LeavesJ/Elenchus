# Retnovation UI/UX — The Cartographer — Vision + MVP Design

Date: 2026-06-28
Status: design (vision + thin MVP slice; two items OPEN — see §9). Awaiting user review → writing-plans.
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

### 4b. The non-invertibility guard = the corpus-density gate

Encode the precondition as a test/guard (the `assert_intake_equivalence` pattern from the elicitation work):
**every region's vitality must draw on ≥N distinct frames across ≥M problems**, or the guard fails. At
user-zero it likely fails — and that is correct: it **refuses to render an invertible thin-corpus map.** So
"safety strengthens with content" becomes *enforced*, not hoped: the guard decides *when* the Cartographer is
allowed to get rich. The early surface therefore leans on the friction-trial (§7), and the map matures as the
corpus grows.

### 4c. The falsification test (paired, not single)

"Strong-on-familiar, weak-on-novel" is equally the signature of *genuine non-transfer* (the true state the
engine exists to detect), so a single held-out novel problem cannot distinguish a gamed map from honest
non-transfer. The discriminating test is **paired**: read the same region's problem **with the terrain shown**
vs. **with it hidden** (a true clean-room read). Strong-with / weak-without = the terrain is inflating;
weak-in-both = honest non-transfer, map innocent. **Bound:** at n=1 the terrain-hidden control still carries
the learner's *memory* of prior reveals, so the paired test isolates the *live*-terrain marginal leak, not the
cross-session memory prime — which is defended only by the lossy projection (§4, §4a).

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
5. **OPEN — the slip/hazard leak.** A consistent "you keep hitting this" marker can be decoded into a named
   anti-move, the same failure as region-decoding. **Unresolved:** either give hazards the lossy treatment
   (cluster traps; don't pin one marker to one `trap_code`) or accept a bounded depth-location leak like
   rebound. See §9.

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
  of *new* engine-adjacent code.
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
  pre-map, not as a readable terrain.)
- **Out of scope (later increments):** the rich 3D terrain over a mature corpus; transfer trails; the full
  garden decay/rebound animation; multi-session map accretion at scale. These earn their way in as the corpus
  grows (§4a–4b).
- **Why not "rich terrain now":** it would be the glamour shot over near-empty state, and the guard would gate
  it.

## 9. Open items (carry into the plan, do not block the vision)

1. **The hazard/slip leak (§5 #5):** lossy-cluster traps vs. accept a bounded depth-location leak. A doctrine
   sub-question to settle before the trap gallery is rendered.
2. **Positioning (§6):** B2C-vs-enterprise go-to-market — parked by the user.

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
