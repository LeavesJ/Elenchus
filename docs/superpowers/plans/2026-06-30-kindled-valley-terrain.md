# Kindled Valley 3D Reward Terrain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DOM-circle terrain reveal with a real-time 3D world ("The Kindled Valley") that renders the engine's diagnosis as a felt, moat-safe reward at the close.

**Architecture:** One projection-only `terrain.py`/`types.py` change adds a second axis (`elevation`/accretion bucket) to the L-13 wire, with a fresh non-invertibility proof. The frontend swaps its DOM terrain renderer for a self-contained, vendored Three.js renderer (`terrain3d.js`) that consumes the wire payload and builds the valley (region→village, seed→ember). The judgment engine stays byte-untouched; the close route/protocol is unchanged.

**Tech Stack:** Python 3.14 + pydantic (engine), FastAPI (web), plain ES + vendored Three.js r128 + UnrealBloomPass (frontend). No bundler / no build step.

## Global Constraints

- **Engine byte-untouched:** `src/retnovation/orchestration.py`, `src/retnovation/assessment/judgment_loop.py`, and the three graded model methods must have an empty diff vs `main`. The bridge-transparency test `tests/test_web_api.py::...` and `test_runner_assessment_equals_direct_run_session` must stay green.
- **L-13 wire:** no `frame_code`, no `veldra:` ref, no rubric ever reaches the client. `region_id` stays a positional ordinal. Renderer positions derive from `region_id` only, never frame identity.
- **Two-phase timing:** terrain is served only at `POST /api/session/{sid}/close`, frozen in `ch.record`. No live terrain, no websocket, no route change.
- **No CDN in the product:** Three.js + addons are **vendored** under `src/retnovation/web/static/vendor/` and served locally.
- **No build step:** plain ES served statically (matches repo; L-19 — launch/test with `PYTHONPATH=src`).
- **Commits:** no `Co-Authored-By`; stage explicit paths only; run the lessons.md pre-commit checklist; confidential-docs `git ls-files` guard before each commit. cwd may be the Veldra worktree — use `git -C ~/Documents/Retnovation` / absolute paths. No `timeout` on macOS.
- **Commands:** tests `PYTHONPATH=src .venv/bin/pytest -q`; format `.venv/bin/ruff format .`; lint `.venv/bin/ruff check .`; app `PYTHONPATH=src .venv/bin/python -m retnovation.web`.
- **Branch:** `feat/kindled-valley-terrain` (already created; the spec is its first commit).

---

## File Structure

- `src/retnovation/types.py` — MODIFY: add `Region.accretion`; add `_elevation_bucket`; add `elevation` to `TerrainView.learner_view()`.
- `src/retnovation/terrain.py` — MODIFY: compute per-region `accretion` in `project_terrain`.
- `tests/test_terrain.py` — MODIFY: extend the non-invertibility + add two-axis tests.
- `src/retnovation/web/static/vendor/` — CREATE: vendored `three.min.js` + 6 postprocessing addons.
- `src/retnovation/web/static/terrain3d.js` — CREATE: the Three.js Kindled Valley renderer (`Terrain3D.render`).
- `src/retnovation/web/static/index.html` — MODIFY: load `terrain3d.js` + vendor scripts; swap `renderTerrain` → `Terrain3D.render` at the close; keep a text fallback.
- `tests/test_web_api.py` — MODIFY: assert the new payload shape + no-frame-leak + the shell references the 3D renderer.
- `src/retnovation/web/app.py` and/or `session_runner.py` — MODIFY (T5 only): serve a `prev_terrain` alongside the close payload for the ignite diff (web-side, engine-untouched).
- `docs/DEVLOG.md` — MODIFY (T6): record what shipped and the honest residuals.

---

### Task 1: Two-axis terrain projection (`elevation`/accretion) + non-invertibility re-proof

**Files:**
- Modify: `src/retnovation/types.py` (Region ~489-494; `_vitality_bucket` ~497-506; `TerrainView.learner_view` ~509-522)
- Modify: `src/retnovation/terrain.py` (`project_terrain` ~41-68)
- Test: `tests/test_terrain.py`

**Interfaces:**
- Consumes: `LearnerState`, `FrameStrength` (`.strength`, `.breadth`), the existing `region_clears_guard`, `_components`, `regions_to_view`.
- Produces: `Region.accretion: float | None`; `types._elevation_bucket(a: float | None) -> int | None`; `TerrainView.learner_view()` rows now `{"region_id","render","vitality","elevation"}`. `elevation` is `None` iff `render == "seed"`, else in `{1,2,3}`. **Definition:** `accretion = len(problems)` (the region's breadth = union of frame breadths); bucket `<=2 -> 1`, `<=4 -> 2`, `else -> 3`.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_terrain.py`:

```python
def test_learner_view_includes_bucketed_elevation():
    # A rendered region: embed(strong,[P1,P2]) + choose_failure(forming,[P1]) -> problems {P1,P2} -> accretion 2 -> elevation 1
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    row = project_terrain(state, NOW).learner_view()[0]
    assert set(row) == {"region_id", "render", "vitality", "elevation"}
    assert row["elevation"] == 1
    assert row["vitality"] in (1, 2, 3)


def test_seed_has_no_elevation():
    # 1 frame -> seed -> elevation None (nothing accreted to decode)
    state = LearnerState(frames={"embed": _fs(Strength.strong, ["P1", "P2"])})
    row = project_terrain(state, NOW).learner_view()[0]
    assert row["render"] == "seed"
    assert row["elevation"] is None
    assert row["vitality"] is None


def test_elevation_is_independent_of_vitality_two_axis():
    # TALL-DIM region: 4 weak frames chained across 5 problems -> vitality bucket 1, elevation bucket 3.
    # SHORT-BRIGHT region: 2 strong frames across 2 problems -> vitality bucket 3, elevation bucket 1.
    state = LearnerState(
        frames={
            "t_a": _fs(Strength.weak, ["P1", "P2"]),
            "t_b": _fs(Strength.weak, ["P2", "P3"]),
            "t_c": _fs(Strength.weak, ["P3", "P4"]),
            "t_d": _fs(Strength.weak, ["P4", "P5"]),
            "s_a": _fs(Strength.strong, ["Q1", "Q2"]),
            "s_b": _fs(Strength.strong, ["Q1"]),
        }
    )
    rows = project_terrain(state, NOW).learner_view()
    # regions_to_view orders by descending raw vitality: SHORT-BRIGHT (1.0) first, TALL-DIM (0.2) second
    short_bright, tall_dim = rows[0], rows[1]
    assert (short_bright["vitality"], short_bright["elevation"]) == (3, 1)
    assert (tall_dim["vitality"], tall_dim["elevation"]) == (1, 3)


def test_elevation_is_rename_invariant():
    # Extends the existing rename-invariance guarantee to the elevation channel.
    state = LearnerState(
        frames={
            "embed": _fs(Strength.strong, ["P1", "P2"]),
            "choose_failure": _fs(Strength.forming, ["P1"]),
        }
    )
    renamed = LearnerState(
        frames={
            "zzz_other": _fs(Strength.strong, ["P1", "P2"]),
            "aaa_renamed": _fs(Strength.forming, ["P1"]),
        }
    )
    assert project_terrain(state, NOW).learner_view() == project_terrain(renamed, NOW).learner_view()
```

Also **update** the existing `test_learner_view_is_non_invertible_under_frame_rename` key-set assertion (line ~110) from `{"region_id", "render", "vitality"}` to `{"region_id", "render", "vitality", "elevation"}`, and add `assert row["elevation"] in (None, 1, 2, 3)`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_terrain.py -q`
Expected: FAIL — `KeyError: 'elevation'` / key-set mismatch (`elevation` not yet emitted).

- [ ] **Step 3: Add `Region.accretion`** — in `src/retnovation/types.py`, in `class Region` (after `vitality`):

```python
class Region(BaseModel):
    region_id: str
    frame_codes: list[str]  # author-side membership — STRIPPED from the learner-facing view (L-13)
    problems: list[str]
    vitality: float | None  # None when render == seed (sub-threshold; nothing to decode)
    accretion: float | None  # breadth-count axis (§4 two-axis); None for seeds. Rename-invariant (counts).
    render: RegionRender
```

- [ ] **Step 4: Add `_elevation_bucket`** — in `src/retnovation/types.py`, next to `_vitality_bucket`:

```python
def _elevation_bucket(a: float | None) -> int | None:
    """Coarse 3-level accretion (height) bucket, gated by the same §4b guard as vitality (None for seeds).
    Derived from region breadth COUNT only, so it is rename-invariant; a bounded depth-location residual
    (Cartographer §4d family) — reveals 'how much ground', never 'which move'."""
    if a is None:
        return None
    if a <= 2:
        return 1
    if a <= 4:
        return 2
    return 3
```

- [ ] **Step 5: Emit `elevation` in `learner_view`** — update `TerrainView.learner_view()`:

```python
    def learner_view(self) -> list[dict]:
        # L-13: never expose frame_codes; only an opaque POSITIONAL id + render + COARSE vitality/elevation
        # buckets. Both are gated by region_clears_guard; both are rename-invariant (bucketed, count-derived).
        return [
            {
                "region_id": r.region_id,
                "render": r.render.value,
                "vitality": _vitality_bucket(r.vitality),
                "elevation": _elevation_bucket(r.accretion),
            }
            for r in self.regions
        ]
```

- [ ] **Step 6: Compute `accretion` in `project_terrain`** — in `src/retnovation/terrain.py`, inside the `for comp` loop, after `vitality = ...`, add and pass it to `Region(...)`:

```python
        accretion = float(len(problems)) if clears else None
        regions.append(
            Region(
                region_id="",  # assigned positionally in regions_to_view (L-13: never frame-derived)
                frame_codes=comp,
                problems=sorted(problems),
                vitality=vitality,
                accretion=accretion,
                render=RegionRender.rendered if clears else RegionRender.seed,
            )
        )
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_terrain.py -q`
Expected: PASS (all terrain tests, including the updated rename-invariance).

- [ ] **Step 8: Run the full suite + lint** — confirm nothing else references the old `Region` shape / learner_view keys.

Run: `PYTHONPATH=src .venv/bin/pytest -q && .venv/bin/ruff format . && .venv/bin/ruff check .`
Expected: full suite PASS (fix any test that constructed a `Region(...)` without `accretion` — search: `.venv/bin/rg "Region\(" tests src`), ruff clean.

- [ ] **Step 9: Adversarial moat review (core-path)** — dispatch an isolated review subagent (`isolation: "worktree"`, checked out at this commit) with the checklist: (a) is `elevation` rename-invariant and guard-gated? (b) does any learner-facing payload gain a frame-decodable channel beyond the accepted §4d depth-location residual? (c) is the engine empty-diff vs main? Fold findings before committing.

- [ ] **Step 10: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/types.py src/retnovation/terrain.py tests/test_terrain.py
git -C ~/Documents/Retnovation commit -m "feat(terrain): add elevation (accretion) axis to the L-13 wire + non-invertibility re-proof"
```

---

### Task 2: Vendor Three.js + postprocessing addons

**Files:**
- Create: `src/retnovation/web/static/vendor/three.min.js` and 6 addon files under `.../vendor/`.
- Test: `tests/test_web_api.py`

**Interfaces:**
- Produces: locally-served `/static/vendor/three.min.js`, `/static/vendor/CopyShader.js`, `LuminosityHighPassShader.js`, `EffectComposer.js`, `RenderPass.js`, `ShaderPass.js`, `UnrealBloomPass.js` (global `THREE.*`, r128).

- [ ] **Step 1: Download the vendored libraries** (r128, matched versions):

```bash
cd ~/Documents/Retnovation && mkdir -p src/retnovation/web/static/vendor && cd src/retnovation/web/static/vendor
curl -fsSL -o three.min.js https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js
B=https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js
curl -fsSL -o CopyShader.js $B/shaders/CopyShader.js
curl -fsSL -o LuminosityHighPassShader.js $B/shaders/LuminosityHighPassShader.js
curl -fsSL -o EffectComposer.js $B/postprocessing/EffectComposer.js
curl -fsSL -o RenderPass.js $B/postprocessing/RenderPass.js
curl -fsSL -o ShaderPass.js $B/postprocessing/ShaderPass.js
curl -fsSL -o UnrealBloomPass.js $B/postprocessing/UnrealBloomPass.js
ls -la  # 7 files, three.min.js ~600KB
```

- [ ] **Step 2: Write the failing test** — in `tests/test_web_api.py`:

```python
def test_vendor_three_is_served(client):
    r = client.get("/static/vendor/three.min.js")
    assert r.status_code == 200 and b"THREE" in r.content
    r2 = client.get("/static/vendor/UnrealBloomPass.js")
    assert r2.status_code == 200
```

(Use the module's existing `client` fixture pattern; if none, construct `TestClient(create_app(db_path=tmp))` as the other web tests do.)

- [ ] **Step 3: Run the test to verify it passes** (the files exist + are under the mounted `/static`):

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py::test_vendor_three_is_served -q`
Expected: PASS (static mount already serves the dir; if a subpath isn't served, confirm `StaticFiles` is mounted at `/static` on the web app — it is per `app.py`).

- [ ] **Step 4: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/web/static/vendor tests/test_web_api.py
git -C ~/Documents/Retnovation commit -m "chore(web): vendor Three.js r128 + UnrealBloom postprocessing (no CDN)"
```

---

### Task 3: The Kindled Valley renderer (`terrain3d.js`)

**Files:**
- Create: `src/retnovation/web/static/terrain3d.js`

**Interfaces:**
- Consumes: the wire payload `[{region_id, render, vitality, elevation}]` (or the future `{regions, transfer}` object — accept both).
- Produces: global `Terrain3D` with `Terrain3D.render(containerEl, payload)` — builds the scene and starts the render loop; safe to call once per close render.

**Baseline:** the browser-verified single-valley Kindled Valley scene (garden terraces, pine forest, twilight skydome + moon, matte→now-subtle fog, `UnrealBloomPass`, vignette, orbit/zoom/WASD, no auto-rotate) developed and screenshot-verified during the brainstorm (scratchpad `preview/index.html` history). This task **ports that scene into a `Terrain3D` module driven by the payload**, with the adaptations and art criteria below.

- [ ] **Step 1: Module skeleton + payload normalization.** Wrap the verified scene in:

```javascript
window.Terrain3D = (function(){
  function normalize(payload){
    var regions = Array.isArray(payload) ? payload : (payload && payload.regions) || [];
    var transfer = (payload && payload.transfer) || [];  // reserved; empty in V1
    return {regions: regions, transfer: transfer};
  }
  function pos(ordinal){ // positional layout — a function of the PUBLIC ordinal ONLY (L-13)
    var golden = 2.399963, r = 8 + ordinal * 7.5;        // deterministic spiral over the valley floor
    return {x: Math.cos(ordinal*golden)*r, z: Math.sin(ordinal*golden)*r};
  }
  function render(container, payload){ /* build scene from normalize(payload); see steps below */ }
  return {render: render};
})();
```

- [ ] **Step 2: Region→village / seed→ember mapping.** For each `regions[i]` at world `pos(i)`:
  - `render === "rendered"` → a **village**: `elevation` (1/2/3) → number of rising garden terraces; `vitality` (1/2/3) → beacon point-light intensity + count of lit windows + lantern-orb emissive. (Reuse the verified `gTier`/`houseRing`/beacon builders, parameterized by center + these two buckets.)
  - `render === "seed"` → a **dark ember** (unformed settlement with a faint waiting glow).
  - **Positions come from `pos(i)` (the ordinal) only** — never from `region_id` parsing beyond its index, never from any frame data.

- [ ] **Step 3: Apply the founder's art criteria (verify each in the browser):**
  - **Fog is real but subtle:** revert the frontier/mist sprites to `AdditiveBlending` (real light-scatter look) but at **cut intensity** — opacity ~`0.12–0.22` (not the matte `NormalBlending`, not the old shiny `0.4–0.62`). Let `scene.fog` (`FogExp2`) carry the physical distance haze.
  - **Lowkey baseline:** lower `toneMappingExposure` to ~`0.80`, `UnrealBloomPass` strength to ~`0.55`, and trim beacon/window emissive so user-zero reads restrained and moody — "not so bright when kicking off." At user-zero (0–1 villages + embers) the valley is mostly dark; the wow is render quality + the first ignition, not brightness.
  - No auto-rotate (camera static until dragged); orbit + scroll-zoom + WASD-roam.

- [ ] **Step 4: Browser-verify (the visual acceptance gate).** Serve the app and screenshot via the preview loop:

Run: `PYTHONPATH=src .venv/bin/python -m retnovation.web` then drive a session to the close, or point a static harness at a sample payload. Confirm: villages render by ordinal at stable positions; a tall-dim vs short-bright pair reads differently (terraces vs brightness); fog looks real + subtle; the baseline is lowkey; bloom present (or clean fallback). Iterate constants until it matches the verified concept + the art criteria.

- [ ] **Step 5: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/web/static/terrain3d.js
git -C ~/Documents/Retnovation commit -m "feat(web): Kindled Valley 3D renderer (payload-driven villages/embers, subtle fog, lowkey baseline)"
```

---

### Task 4: Cut the close over to the 3D renderer

**Files:**
- Modify: `src/retnovation/web/static/index.html` (the `<head>`/scripts + `renderClose`/`renderTerrain` path)
- Test: `tests/test_web_api.py`

**Interfaces:**
- Consumes: `Terrain3D.render` (Task 3); the close response `{kind:"close", close, terrain:[...]}` (unchanged).
- Produces: at the close, the terrain payload is rendered into a 3D container instead of DOM circles; a text summary remains as a no-WebGL fallback.

- [ ] **Step 1: Update the failing web test** — in `tests/test_web_api.py`, extend `test_index_html_is_a_chat_shell` (or add):

```python
def test_index_references_3d_terrain_renderer(client):
    html = client.get("/").text
    assert "terrain3d.js" in html
    assert "vendor/three.min.js" in html
    assert "Terrain3D.render" in html


def test_close_terrain_payload_has_two_axis_and_no_frame_leak(client):
    # Drive a full session to /close (reuse the existing full-session helper), then:
    #   - each terrain row has exactly {region_id, render, vitality, elevation}
    #   - no frame_code / "veldra:" substring anywhere in the close payload
    ...  # mirror the existing test_converse_and_close_endpoints flow; assert the elevation key + no-leak
```

Fill the `...` by copying the existing close-driving flow from `test_converse_and_close_endpoints`, then:
```python
    for row in close["terrain"]:
        assert set(row) == {"region_id", "render", "vitality", "elevation"}
    blob = json.dumps(close)
    assert "veldra:" not in blob
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py -q`
Expected: FAIL (`terrain3d.js` not referenced; `elevation` key assertion new).

- [ ] **Step 3: Wire the renderer into `index.html`.** In `<head>`, before the app inline script, add the vendor + renderer scripts:

```html
<script src="/static/vendor/three.min.js"></script>
<script src="/static/vendor/CopyShader.js"></script>
<script src="/static/vendor/LuminosityHighPassShader.js"></script>
<script src="/static/vendor/EffectComposer.js"></script>
<script src="/static/vendor/RenderPass.js"></script>
<script src="/static/vendor/ShaderPass.js"></script>
<script src="/static/vendor/UnrealBloomPass.js"></script>
<script src="/static/terrain3d.js"></script>
```

In `renderClose(r)` / `renderTerrain(...)`, replace the DOM-circle block with a 3D container + a text fallback:

```javascript
function renderTerrain(regions){
  var host = document.createElement('div');
  host.className = 'terrain3d';
  host.style.cssText = 'width:100%;height:460px;border-radius:16px;overflow:hidden;margin-top:12px;background:#04060c';
  thread.appendChild(host);
  var rendered = (regions||[]).filter(function(x){return x.render==='rendered';}).length;
  var note = document.createElement('div');
  note.className = 'terrain-note';
  note.textContent = rendered ? (rendered+' area(s) have taken shape.') : 'A seed was planted — your world begins.';
  thread.appendChild(note);
  try { if (window.Terrain3D) Terrain3D.render(host, regions); } catch(e) { /* text fallback stands */ }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py -q`
Expected: PASS.

- [ ] **Step 5: Browser-verify the real close** — run the app, drive `decision_under_stakes` (or a session) to convergence + close; confirm the 3D valley renders in-thread with the frozen terrain, and the text note stands if WebGL is unavailable.

- [ ] **Step 6: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/web/static/index.html tests/test_web_api.py
git -C ~/Documents/Retnovation commit -m "feat(web): render the 3D Kindled Valley at the close (DOM terrain removed; text fallback kept)"
```

---

### Task 5: The ignite / reveal reward beat

**Files:**
- Modify: `src/retnovation/web/session_runner.py` (freeze a `prev_terrain` in `ch.record`) and/or `app.py` (include it in the close response)
- Modify: `src/retnovation/web/static/terrain3d.js` (fly-in + ignite animation)
- Test: `tests/test_web_api.py`

**Interfaces:**
- Consumes: the close payload; a `prev_terrain` (the previously-frozen public learner_view, or `None` on first session).
- Produces: `Terrain3D.render` accepts an optional `{prev}` and animates: fly-in, then the region whose `render`/`vitality`/`elevation` increased vs `prev` catches fire + its terraces rise; nascent-seed reveal if none/first.

- [ ] **Step 1: Serve `prev_terrain` (web-side diff source; engine untouched).** In `session_runner.py`, when freezing `ch.record["terrain"]`, also read the prior persisted terrain for this learner (if any) into `ch.record["prev_terrain"]` (both are public learner_view payloads — no frame leak). Expose it in the `/close` response as `prev_terrain`. If prior plumbing is heavier than a small read, ship the simpler fallback (Step 3) and defer the precise diff (spec §16 open item #2).

- [ ] **Step 2: Failing test** — in `tests/test_web_api.py`:

```python
def test_close_includes_prev_terrain_key(client):
    # close response carries prev_terrain (list or null); it is itself frame-leak-free
    ...  # drive to /close; assert "prev_terrain" in close; assert no "veldra:" in json.dumps(close["prev_terrain"] or [])
```

- [ ] **Step 3: Ignite animation in `terrain3d.js`.** Compute the "just-ignited" region web-side: the first region whose `(render, vitality||0, elevation||0)` exceeds its `prev` counterpart by `region_id`; if none or no prev → pick the newest/brightest, or (first session) play the seed-planted reveal. Animate: camera fly-in to that region; ramp its beacon/flame emissive from 0; raise its terraces from flat over ~1.5s; then settle into the orbit view. Keep it moat-safe (fires on the same public buckets — says nothing the terrain doesn't).

- [ ] **Step 4: Run tests + browser-verify** the beat across two consecutive sessions (region grows → it ignites) and a first session (seed reveal).

Run: `PYTHONPATH=src .venv/bin/pytest tests/test_web_api.py -q` (PASS) + browser confirm.

- [ ] **Step 5: Commit**

```bash
git -C ~/Documents/Retnovation add src/retnovation/web/session_runner.py src/retnovation/web/app.py src/retnovation/web/static/terrain3d.js tests/test_web_api.py
git -C ~/Documents/Retnovation commit -m "feat(web): ignite/reveal reward beat at the close (web-side prev-terrain diff; nascent-seed fallback)"
```

---

### Task 6: Health smoke, whole-branch review, DEVLOG

**Files:**
- Modify: `docs/DEVLOG.md`

- [ ] **Step 1: Full suite + lint + format**

Run: `PYTHONPATH=src .venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: all green.

- [ ] **Step 2: Documented-launch health smoke (L-18/L-19)**

Run: `PYTHONPATH=src .venv/bin/python -m retnovation.web` (background), then `curl -s 127.0.0.1:8000/api/health` → `{"ok":true}`, `curl -s -o /dev/null -w "%{http_code}" 127.0.0.1:8000/` → `200`, and `curl -s -o /dev/null -w "%{http_code}" 127.0.0.1:8000/static/vendor/three.min.js` → `200`. Stop the server.

- [ ] **Step 3: Engine byte-untouched assertion**

Run: `git -C ~/Documents/Retnovation diff --stat main -- src/retnovation/orchestration.py src/retnovation/assessment/judgment_loop.py`
Expected: empty (no engine changes).

- [ ] **Step 4: Whole-branch OPUS review** — dispatch an isolated reviewer over the whole branch vs `main`: moat (no frame leak, elevation bounded), two-phase timing intact, engine + close-route untouched, renderer positions ordinal-only, no CDN. Fold findings.

- [ ] **Step 5: Update `docs/DEVLOG.md`** — a dated entry: the 3D Kindled Valley reward terrain shipped; the one `terrain.py` two-axis change + re-proof; honest residual (elevation = bounded depth-location leak, §4d family); connection layer designed-but-not-built (seams reserved). Confidential-docs `git ls-files` guard.

- [ ] **Step 6: Commit**

```bash
git -C ~/Documents/Retnovation add docs/DEVLOG.md
git -C ~/Documents/Retnovation commit -m "docs(devlog): Kindled Valley 3D reward terrain (two-axis wire + renderer + ignite beat)"
```

---

## Self-Review

**Spec coverage:** §3 scope → T1–T5; §6 wire (elevation add, object-shape reserved) → T1 + T3 normalize; §7 terrain.py change + re-proof → T1 (incl. the 4 required proofs) + T1 Step 9 review; §8 frontend (vendored, no-CDN, served-at-close, positional layout) → T2–T4 + Global Constraints; §9 rendering (two-axis visual) → T3; §10 ignite beat → T5; §11 residuals → T1 review + T6 DEVLOG; §12 connection seams (transfer field, N-village renderer) → T3 `normalize` (accepts object + `transfer`) + `pos(ordinal)` (N villages); §13 isolation → Global Constraints + T6 Step 3; §14 testing → T1/T2/T4/T5 tests + T6 smoke. All covered.

**Placeholder scan:** the two `...` in T4 Step 1 and T5 Step 2 are explicitly "copy the existing close-driving flow from `test_converse_and_close_endpoints`" with the concrete new assertions given — an instruction to reuse a named existing helper, not a vague gap. T3's scene body references the browser-verified concept (a real artifact) plus exact adaptation code and art constants — the renderer is tuned against a visual acceptance gate, not frozen line-by-line.

**Type consistency:** `Region.accretion: float | None` (T1 Step 3) → `_elevation_bucket` (T1 Step 4) → `learner_view` `elevation` key (T1 Step 5), asserted in T1 tests, T4 tests, and the T3 renderer's bucket consumption. `Terrain3D.render(container, payload)` consistent across T3/T4/T5. `pos(ordinal)` ordinal-only consistent with the L-13 constraint.

## Execution Handoff

See the offer below.
