# The Kindled Valley — Reward Terrain (3D) + Connection Seams — Design

Date: 2026-06-30
Status: design (brainstormed with the founder, concept browser-verified). Awaiting founder review of this
spec → writing-plans.
Related: `2026-06-28-uiux-cartographer-design.md` (the Cartographer vision this realizes), the reward /
"hope-to-end" thread (SESSION_HANDOFF §OPEN DESIGN THREAD, 2026-06-30), `retnovation-ui-ux-vision` memory.
Supersedes nothing; it is the **visual/felt realization** of the Cartographer terrain, escalated from the
DOM-circle MVP to a real-time 3D world, plus the *connection* extension's seams.

## 1. Problem & goal

Two problems, one surface:

1. **The reward / hope-to-end gap.** A pure Socratic withhold has no positive-progress channel; the session
   feels like an endless "something's missing" treadmill even when the user reasons well (SESSION_HANDOFF).
   The terrain is the *end-payoff*: knowing a beautiful world grows when you converge is the "hope to end."
   (The *within-turn* half — woven stance modulation — is a **separate, later** voice thread; out of scope here.)
2. **The commercial-surface gap.** This is a B2C product whose value is illegible until *felt*. The surface is
   half the engine: the dialogue is the *conversion* moment ("it read my reasoning"), the world is the
   *appeal + retention* moment ("I want this, and I want to grow it"). The current terrain — flat DOM circles
   glowing by vitality bucket — undersells the engine catastrophically. It must look like a premium game.

**Goal:** replace the DOM-circle terrain reveal with a **real-time 3D world — "The Kindled Valley"** — that
(a) renders the engine's diagnosis as a *felt*, ownable, screenshot-shareable world, (b) delivers the reward
beat (a dark valley you *ignite*), (c) stays strictly inside the L-13 / L-4 moat, and (d) is architected so the
future *connection* layer (roads between regions, a traversing figure) is an additive increment, not a rewrite.

## 2. Decisions carried in from the brainstorm (all founder-confirmed)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Reward lives at the close / between sessions**, never live mid-dialogue | Preserves the two-phase L-13 timing (Cartographer §4 move #2). A live "you're getting warmer" glow would leak the move and become a correctness signal (L-4-forbidden). |
| D2 | **Terrain-only scope.** Woven-stance voice modulation is a separate later thread | Cleanest blast radius; the terrain is frontend-isolated + one small `terrain.py` change. |
| D3 | **Art direction: "The Kindled Valley"** — a dark twilight valley you *ignite* | On-theme (Ret·novation = the spark of insight that *endures*); warmer/more-human than a metropolis; the verb "ignite" gives agency; fuses garden (lantern-glow) + valley (terrain) + constellation (sky). Browser-verified as premium. |
| D4 | **Two-axis world** — terraces *rise* with accretion (height) separate from vitality (glow) | The single most useful distinction a one-number bar can't show (Cartographer §3): "deep but fading" vs "new but fresh". Requires a `terrain.py` change + a fresh non-invertibility proof (§7). |
| D5 | **Connection hierarchy**: house = session · village = region · road = transfer · valley = your whole judgment | Scales cleanly and stays moat-safe; roads = the existing transfer/constellation register rendered on the ground. |
| D6 | **Vera as a gliding lamplighter wisp** (future) | Fuses the chat persona with the world; embodies the ignite ritual and makes transfer legible; cheap to animate (glides — no limbs/walk-cycle/IK, per the founder's own production shortcut). |
| D7 | **First-person** = an optional "walk your valley" treat *later*, not the primary lens | The god's-eye view is what makes judgment legible at a glance and screenshot-shareable (the B2C acquisition engine). |
| D8 | **Connection layer = design the seams now, build later** | At user-zero there is one region and nothing to connect; V1 ships the single valley. The architecture must add roads/villages/Vera without a rewrite. |

## 3. Scope

**V1 (this spec's build target):**
- A **Three.js / WebGL** renderer replacing the DOM-circle terrain, consuming the (extended) wire payload,
  shown **at the close** (frozen in the session record, exactly as today).
- **`terrain.py` change:** add an `elevation` (accretion) bucket to the projection + `learner_view`, with a
  fresh non-invertibility proof. This is the *only* engine-adjacent change. Engine
  (`orchestration.py`, `assessment/judgment_loop.py`, the graded model methods) stays **byte-untouched**.
- The Kindled Valley scene: **each rendered region → a village** (terraces = elevation, beacon+windows =
  vitality); **each seed region → a dark ember**; positional (non-frame-derived) layout; twilight palette;
  bloom + atmosphere (fog, forest, sky, fireflies); orbit/zoom/roam camera (no auto-rotate).
- A simple **ignite / reveal reward beat** at the close (§10).
- **Honest at user-zero:** 0–1 villages + a few embers on a beautiful, mostly-dark valley — the emergence
  aesthetic *is* the wow (Cartographer §8a), not density.

**Designed-but-not-built (seams — §12):** transfer-edge wire field (reserved, empty in V1) → roads; Vera the
wisp; first-person mode; the dusk→dawn maturity arc; the decay/rebound animation (the `now` time-axis is
already reserved in `project_terrain`). The N-village scene graph is *inherent* in V1 (it renders N regions),
so multi-village is free; only the *edges between* them are the reserved seam.

## 4. The world model (how the metaphor maps to engine signals)

| World element | Engine signal | Moat note |
|---|---|---|
| **Valley** | the whole `LearnerState` terrain projection | — |
| **Village** = a **region** | a connected component of frames (shared-problem linkage), guard-gated | Region id is **positional** (`r0…`), never frame-derived (L-13). |
| **Terrace height / count** | `elevation` = coarse **accretion** bucket (breadth × frame count) | Rename-invariant (counts, not identity); guard-gated; a bounded depth-location residual (§11, Cartographer §4d family). |
| **Beacon + lit windows brightness** | `vitality` = coarse mean-strength bucket (existing) | Existing non-invertible bucket. |
| **Dark ember** = a **seed** | a sub-`§4b`-threshold region (`render=seed`, vitality/elevation `None`) | Nothing to decode — "your world begins here." |
| **Lit house** = a **session** (future granularity) | a representative, coarse count tied to the elevation bucket — **not** exact breadth | House-count is a *cue*, not a readout; bounded residual (§11). |
| **Road / thread of light** = **transfer** (future) | a genuine unprompted cross-region transfer edge (reserved wire field) | Positional region ids only; only real transfers draw (kills O(N²) spaghetti, Cartographer §5#3). |
| **Vera the wisp** (future) | the lamplighter presence; kindles beacons, walks transfer roads | Read-only ritual; **never** a work-selector (§12). |
| **Dusk→dawn / decay / rebound** (future) | the reversible-decay + savings time-axis (`now`, reserved) | Recency, not move-identity. |

## 5. The moat is the whole point (L-13 / L-4, medium-independent)

Every learner-facing surface, in any medium, must **withhold the move** (L-13). The 3D world is a surface, so
the same discipline that governs the DOM view governs it:

- **Nothing on the wire names or encodes a frame/move.** No `frame_code`, no `veldra:` ref, no rubric, no
  per-move biome. Village *theme* (warm lantern twilight) is uniform — it carries no move information.
- **Position carries no secret.** Village layout is a deterministic function of the **public positional
  ordinal** (`region_id`), never of the frame set — a frame-code rename must leave the whole scene identical.
- **The §4b density guard still governs render.** A region renders a decodable village (with vitality AND
  elevation) only when it clears `region_clears_guard`; below threshold it is an ember. Elevation is gated by
  the *same* guard as vitality — a sparse region reveals neither.
- **Two-phase timing (D1).** The world is a *between/after-session* artifact; during a session only the
  problem + dialogue are on screen. A reveal cannot reach back into a captured unprompted read.
- **Conclusion-agnostic (L-4).** The world reflects *rigor/breadth/trajectory* the engine already measures,
  never correctness. Growth = "you reasoned across more ground," never "you got it right."

## 6. Data contract (the wire)

`TerrainView.learner_view()` today returns per region:
`{ "region_id": "r0", "render": "seed"|"rendered", "vitality": null|1|2|3 }`.

**V1 adds one field** — `elevation`:
`{ "region_id": "r0", "render": "seed"|"rendered", "vitality": null|1|2|3, "elevation": null|1|2|3 }`

- `elevation` is `null` for seeds (sub-threshold — nothing to decode), and a coarse bucket (3 levels, same
  spirit as `_vitality_bucket`) for rendered regions.
- Ordering + positional ids are **unchanged** (`regions_to_view`), so a rename still leaves the payload
  byte-identical (the existing rename-invariance test is extended to assert the `elevation` key too).

**Reserved for the connection layer (NOT emitted in V1):** a sibling `transfer` field —
`[{ "a": "r0", "b": "r2" }, …]` — positional region-id pairs for genuine cross-region transfers. Designing the
`learner_view` return as an object rather than growing the list keeps this additive:

> V2 shape (reserved): `{ "regions": [ …as above… ], "transfer": [ {"a","b"}, … ] }`.
> **V1 decision:** keep `learner_view()` returning the **list** (back-compat with `test_web_api` /
> `test_terrain`), and add the `transfer` seam only when the connection layer is built — at which point the
> web layer wraps the list. The renderer is written to accept either (list → `{regions:list, transfer:[]}`).

## 7. The `terrain.py` change + non-invertibility re-proof (the one engine-adjacent edit)

**Change:** compute a per-region `accretion` scalar in `project_terrain` (for regions that clear the guard),
carry it on `Region`, and bucket it in `learner_view` as `elevation`. Seeds get `elevation=None`.

- **`accretion` definition (contract; exact thresholds calibrated in the plan):** a monotone function of the
  region's **counts** — `len(frame_codes)` and `len(problems)` (breadth) — i.e. "how much durable evidence you
  have accreted here." It is **independent of frame identity** by construction.
- **Bucketing:** a coarse `_elevation_bucket(accretion) -> None|1|2|3` mirroring `_vitality_bucket`.
- **Non-invertibility re-proof (required, ships with the change):**
  1. **Rename-invariance:** extend `test_learner_view_is_non_invertible_under_frame_rename` to assert the
     payload — now including `elevation` — is byte-identical under a frame-code rename. (Elevation is a
     function of counts, so this holds by construction; the test *proves* it.)
  2. **Key-set lock:** extend the "exactly these keys" assertion to `{region_id, render, vitality, elevation}`.
  3. **Guard coupling:** assert `elevation is None` whenever `render == seed` (a sub-threshold region reveals
     no accretion), i.e. elevation is gated by the *same* `region_clears_guard`.
  4. **Coarseness:** assert `elevation in (None, 1, 2, 3)` — never a raw count.
- **Honest bound (spec-stated, not zero):** elevation is a **new learner-facing channel** — a coarse
  *depth-location* signal ("where do I have durable breadth"), the same family as the accepted rebound leak
  (Cartographer §4d) and the node-count residual (§6 of that spec). It reveals *how much ground*, never *which
  move*. Bucketing + count-derivation + the §4b guard bound it below the rate of genuine learning; it shrinks
  as the corpus fills. This is recorded as an accepted residual, not a solved one.
- **Isolation:** `orchestration.py`, `assessment/judgment_loop.py`, and the three graded model methods remain
  **byte-untouched** (empty diff vs main). The bridge-transparency test
  (`test_runner_assessment_equals_direct_run_session`) must stay green — the change is projection-only, never
  touches assessment.

## 8. Frontend architecture

- **Renderer module.** A self-contained `src/retnovation/web/static/terrain3d.js` (plain ES, no framework, no
  build step — matches the repo's no-bundler discipline and L-19) that takes the wire payload and builds the
  Three.js scene. The chat shell (`index.html`) stays; it swaps `renderTerrain(regions)` (DOM circles) for
  `Terrain3D.render(container, payload)`.
- **Libraries vendored, not CDN.** Three.js r128 + the postprocessing addons (CopyShader,
  LuminosityHighPassShader, EffectComposer, RenderPass, ShaderPass, UnrealBloomPass) are **vendored under
  `static/vendor/`** and served locally — a shipping/offline B2C app must not depend on a CDN. The concept
  loaded them from CDN; the product ships them vendored. Bloom setup is guarded (falls back to plain render if
  a pass is unavailable), exactly as the verified concept.
- **Served at the close (two-phase preserved).** The terrain payload is frozen in `ch.record` and served at
  `POST /api/session/{sid}/close` — **no route change**. The renderer is instantiated only on the close
  render, never during the engine loop. No websocket, no live terrain.
- **Scene composition (from the verified concept):** procedural terrain (heightfield), a village per rendered
  region, embers for seeds, pine forest + rocks on the slopes, a twilight skydome + moon, matte fog frontier,
  fireflies/lanterns/chimney-smoke, `ACESFilmic` tone mapping + `UnrealBloomPass`, a vignette. Camera: orbit +
  scroll-zoom + WASD-roam, **no auto-rotate** (founder note). Everything is generated in code from the payload
  — no art-asset pipeline (procedural is the right fit for a data-mirroring terrain; authored `.glb` hero
  assets are a later option via `GLTFLoader`).
- **Village placement.** A deterministic layout function `pos(region_ordinal) -> (x, z)` (e.g. a seeded
  spiral/scatter over the valley floor) so villages appear at **stable positions across sessions** and the
  layout is a function of the **public ordinal only** (L-13). Elevation bucket → terrace count/height;
  vitality bucket → beacon + window emissive intensity; seed → dark ember with a faint waiting glow.
- **Performance.** Reuse shared geometries/materials (as the concept does); cap village/house counts;
  target 60fps on a laptop. Node/house count per village is a coarse cue (§11), not exact breadth.

## 9. Rendering spec (what the buckets mean visually)

- **Rendered region → village:** `elevation` 1/2/3 → 1/2/3 rising garden terraces; `vitality` 1/2/3 → beacon
  brightness + how many windows are lit + lantern glow. High-elevation/high-vitality = a tall, brightly-lit
  hill-town; low-elevation/high-vitality = a small but warmly-lit hamlet (new but fresh); high-elevation/
  low-vitality = tall terraces but dim windows (deep but fading) — **the two-axis distinction, made visible.**
- **Seed region → ember:** a single dark, unformed settlement-ember with a faint waiting glow.
- **User-zero:** honest — the valley is mostly dark with a few embers and at most one small village. The wow is
  render quality + the *first ignition*, per Cartographer §8a. No faked density.

## 10. The ignite / reward moment (the beat itself)

At the close, after the read is locked, the world reveals with a **fly-in**, then the region that grew this
session is the focal point — its **ember catches fire** and its **terraces rise** (a short, cinematic beat),
before settling into the orbitable view.

- **Which region "ignited" is inferred web-side** (engine + `terrain.py` contract untouched beyond §7): the
  web layer compares the prior close's frozen terrain (a public `learner_view` payload — no frame leak) with
  the current one, and animates the region whose `render`/`vitality`/`elevation` increased. If no prior exists
  (first session) or nothing crossed a threshold, fall back to a general "the world reveals" reveal + a
  seed-planted beat (Cartographer §8's nascent-seed). **No new engine signal; a public-payload diff only.**
- **Moat:** the beat rewards *movement/arrival* (a region grew), never correctness or the move — it fires on
  the same guard-gated public buckets, so it cannot say more than the terrain already does.

## 11. Honest residuals (accepted, recorded — not zero-leak)

- **Elevation is a new depth-location channel** (§7) — bounded, corpus-shrinking, §4d family. Accepted.
- **House-count / node-count** per village is a coarse accretion cue — the existing accepted node-count
  residual (Cartographer §6), now also expressed as house count. Kept coarse (tied to the elevation bucket,
  not exact breadth). Accepted; capping is a future option.
- **Positional layout** must be public-ordinal-derived; a layout accidentally seeded by frame identity would
  leak — the rename-invariance test guards the *payload*, and the renderer must derive positions from
  `region_id` only (a renderer-side invariant to assert in a JS/unit check or a documented contract).
- **The cross-session memory prime** (what the learner carries into the next opening read from having seen the
  world) is defended-by-projection but not tested — a between-cohort experiment, later-corpus (Cartographer
  §4c). Unchanged by this work.

## 12. Connection layer (designed, NOT built — the seams)

Built later as an additive increment; V1 must not preclude it.

- **Data:** the reserved `transfer` edges field (§6) — positional region-id pairs for genuine unprompted
  cross-region transfers. Lossy + moat-safe (ids, no move identity). Emitted only when the connection layer
  ships.
- **Roads:** a lit road drawn along the terrain between two villages **only when a transfer edge exists** — a
  road is an *event*, not decoration (kills spaghetti). Roadside lanterns; warm emissive.
- **Vera the wisp (D6):** the chat persona embodied as a gliding will-o'-wisp / hooded lantern-bearer who
  kindles beacons and travels transfer roads carrying the light. No walk cycle / IK (glides). Reserve a
  "world-presence" facet of the persona (persona is already content-resolved, L-1). The verified 2-village
  prototype demonstrates this.
- **First-person (D7):** the camera system is built so it *can* drop to ground level later as an optional
  "walk your valley" mode. Not the primary lens.
- **Maturity arc:** dusk→dawn as the valley matures; decay dims neglected villages toward twilight; rebound
  re-lights faster (the `now` time-axis, reserved). Recency, not move-identity.
- **THE GUARDRAIL (load-bearing):** the figure, roads, and world are **read-only reflections + rituals, never
  a control**. You cannot steer Vera into a village to "work on it" (that would label/decode the region and
  break Cartographer §4 move #1). You still pick **problems** in the dialogue; Vera + roads appear as a
  *consequence* of your reasoning. Fog-of-war (unexplored territory) recedes by **mastery, not navigation** —
  walking to a fogged edge never reveals it; enough breadth (the §4b guard) does.

## 13. Isolation & invariants (must not drift)

- **Engine byte-untouched:** `orchestration.py`, `assessment/judgment_loop.py`, the graded model methods —
  empty diff vs main. Bridge-transparency test green.
- **`terrain.py` change is projection-only + re-proven** (§7). No assessment path touched.
- **No route/protocol change:** terrain still served at `/close`, frozen in `ch.record`. Two-phase intact.
- **Renderer is self-contained + vendored** (no CDN, no build step). Frame-blind: no `frame_code`/`veldra:`
  ref/rubric ever reaches the client (extend `test_web_api`'s no-frame-substring assertions to the new field).
- **No `Co-Authored-By`; explicit-path staging; confidential-docs `git ls-files` check before every commit.**
  cwd may be the Veldra worktree — use absolute paths / `git -C ~/Documents/Retnovation`.

## 14. Testing (what locks the contract)

- **`terrain.py` / `types.py`:** rename-invariance incl. `elevation`; key-set lock `{region_id, render,
  vitality, elevation}`; `elevation is None` iff `render==seed`; `elevation in (None,1,2,3)`; a two-axis case
  (a tall-dim vs short-bright region) asserting the buckets diverge; guard still gates both channels.
- **Web (`test_web_api`):** full session → close returns terrain with the new shape; **no frame_code /
  `veldra:` substring** in any learner-facing payload; the close route unchanged; the index shell references
  the 3D renderer (not the DOM-circle path).
- **Isolation:** engine empty-diff assertion; bridge-transparency `…assessment_equals_direct_run_session`
  green.
- **Renderer contract (JS-level or documented):** positions derived from `region_id` only; renders over the
  list *or* the reserved object shape; bloom guarded/fallback.
- **Health smoke (L-18/L-19):** `PYTHONPATH=src .venv/bin/python -m retnovation.web` boots;
  `GET /api/health → {"ok":true}`; `GET / → 200` serving the 3D shell; the documented launch command runs.

## 15. Staging / increments (plan-level)

1. **T1 — `terrain.py` two-axis + re-proof** (elevation bucket; the non-invertibility tests). Atomic, green.
2. **T2 — vendor Three.js + addons under `static/vendor/`**; a no-op wiring test.
3. **T3 — `terrain3d.js` renderer** over the payload (the verified Kindled Valley scene: terrain, villages
   from regions, embers from seeds, forest/fog/sky/bloom, camera). Positional layout from `region_id`.
4. **T4 — cutover** `index.html`: swap `renderTerrain` → `Terrain3D.render` at the close; keep the DOM path
   only as a text/no-webgl fallback. Web tests updated.
5. **T5 — the ignite/reveal beat** (web-side prior-vs-current diff → fly-to + ember-catches + terraces-rise;
   nascent-seed fallback).
6. **T6 — health smoke + founder dogfood + DEVLOG.** (Per-task moat review on T1; whole-branch OPUS review.)

Connection layer (roads / Vera / transfer edges / first-person / maturity arc) is a **separate future spec**;
this build only reserves the seams (§6 object shape, N-village renderer, persona world-presence facet).

## 16. Open items

1. **Elevation formula + bucket thresholds** — calibrated in the plan against real content (which combo of
   `len(frames)` × `len(problems)`; where the 1/2/3 cuts fall). Contract is fixed (§7); numbers are not.
2. **Ignite-target diff** — V1 may ship the simple "reveal + brightest region" beat and defer the precise
   prior-vs-current diff to a refinement if the prior-terrain plumbing is heavier than expected (§10).
3. **Vendored Three.js size** — r128 core + addons (~600KB) served locally; acceptable for a local app,
   revisit if a hosted build wants a trimmed/tree-shaken bundle.
4. **`learner_view` list-vs-object** — V1 keeps the list (back-compat); the object wrap lands with the
   connection layer (§6). Confirm no current consumer breaks.

## 17. Visual references (ephemeral, browser-verified)

Produced live during the brainstorm (not committed assets): six 2D art-direction bands; a live WebGL "3D
district" proof; the polished single-valley Kindled Valley (garden terraces, forest, fog, bloom — verified via
browser screenshot); and the two-village + lit-road + Vera-wisp *connection* prototype (verified). The visual
language is specified in §8–§10 so it survives without the renders.

## 18. Doctrine carried in

Conclusion-agnostic (L-4); the unlabeled-problem moat (L-6); never name the frame to the learner (L-13, here a
property of *what's on the wire* + *when it's revealed* + *how lossy* — §5–§7); reversible decay + savings
(reserved time-axis); the frame-level receipt stays the author's async log; engine byte-untouched (load-bearing).
