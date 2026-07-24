/* The Archipelago — dusk-sky scene (Spec-2 §3/§5/§6/§8, Phase B T2+T3).
 * Terrain3D.render(container, payload, opts) consumes window.WXLaw's pure placement law
 * (WXLaw.layout — Task 1) to place isle base rocks and seed rocks on their frozen bearings, then
 * populates each isle with its earned facets/monoliths/strata rings, one per-isle arrival-thread,
 * and one uniform ghost invitation; seed rocks earn their own small housed monoliths. This file
 * ships the dusk sky + cloud shelf, the home dock (rock, jetty, lantern, doorway glow), the world
 * group's idle sway, the camera/controls, and the render() contract.
 * The prior Kindled-Valley terrain (heightfield, villages, per-convergence houses, forest, fog
 * wall) is retired outright: the world is now a home dock and its orbiting isles, not a valley.
 * Requires the vendored global THREE (+ optional EffectComposer/UnrealBloomPass for bloom) and
 * window.WXLaw (index.html loads it immediately before this file); degrades to a note if either
 * is absent.
 */
window.Terrain3D = (function () {
  "use strict";
  var activeTeardown = null; // one live scene at a time: a re-render stops the prior loop + listeners

  // DUSK_BAND — the violet -> rose dusk palette (Spec-2 §8): every structural material color is
  // indexed from here, including dim/patina states, so hue/saturation never drifts outside the
  // band — no desaturated grey-family entry (equal R/G/B channels) is allowed into this list.
  var DUSK_BAND = [
    0x241b3a, // 0  sky zenith — pinned stop (plan-ratified)
    0x3a2c5c, // 1  sky upper — pinned stop (plan-ratified)
    0x6b4a7a, // 2  sky mid — pinned stop (plan-ratified)
    0xc98a8a, // 3  sky horizon — pinned stop (plan-ratified)
    0xe6b58a, // 4  sun-glow / warm horizon light — pinned stop (plan-ratified)
    0x4a2f52, // 5  isle & dock rock — lit dusk-violet stone
    0x1c1226, // 6  isle & dock rock — dark underside
    0x3a2440, // 7  jetty stone / lantern post
    0xffc477, // 8  the lamp — steady warm (never a sweep, never a pulse)
    0xffb066, // 9  the doorway glow — warm
    0x2e1c38, // 10 seed rock — dim lit top
    0x6a4a72, // 11 cloud shelf tint
    // 12-17: the facet hue ramp (Phase B T3, Spec-2 §5) — six shared instances, indexed by
    // isle.slot % 6, a green -> violet ramp that stays inside this same dusk band (no grey entry:
    // every stop below has three distinct channels).
    0x3d6b4e, // 12 facet hue 0 — moss green
    0x4f7a52, // 13 facet hue 1 — leaf green
    0x6c7a5a, // 14 facet hue 2 — olive-green (transitional)
    0x6b6a92, // 15 facet hue 3 — blue-violet (transitional)
    0x7a5a92, // 16 facet hue 4 — violet
    0x5c3a78, // 17 facet hue 5 — deep violet
    0xcac2e6, // 18 the ghost bud — pale lavender, IDENTICAL on every isle
    0xbfae9e  // 19 strata ring — stone-pale
  ];

  function hx(n) { return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function rgba(r, g, b, a) { return "rgba(" + r + "," + g + "," + b + "," + a + ")"; }
  function rgbaHex(n, a) { var c = hx(n); return rgba(c[0], c[1], c[2], a); }
  function cssHex(n) { var s = n.toString(16); while (s.length < 6) s = "0" + s; return "#" + s; }
  // ambient FX — outside the determinism boundary (spec §5): the sole unseeded-randomness
  // primitive in this file, funneled through one helper so nothing structural (isle/seed/dock
  // placement — all of it WXLaw's pure output) ever calls it directly.
  function rnd(a, b) { return a + Math.random() * (b - a); }

  function normalize(payload) {
    var regions = Array.isArray(payload) ? payload : (payload && payload.regions) || [];
    var transfer = (payload && payload.transfer) || []; // reserved for the connection layer; unused in V1
    var houses = (payload && payload.houses) || [];
    return { regions: regions, transfer: transfer, houses: houses };
  }

  function render(container, payload, opts) {
    var THREE = window.THREE;
    var WXLaw = window.WXLaw;
    var data = normalize(payload);
    var onHouseClick = opts && typeof opts.onHouseClick === "function" ? opts.onHouseClick : null;
    if (!THREE || !WXLaw) { return; } // index.html keeps a text note as the no-WebGL/no-law fallback
    if (activeTeardown) { activeTeardown(); activeTeardown = null; } // stop any prior scene first
    while (container.firstChild) container.removeChild(container.firstChild); // a re-render must not stack a dead canvas under the live one

    var W = container.clientWidth || 680, H = container.clientHeight || 460;
    var cv = document.createElement("canvas");
    container.appendChild(cv);
    var hint = document.createElement("div");
    hint.style.cssText = "position:absolute;left:14px;bottom:11px;font:12px system-ui,sans-serif;color:#e6a860;opacity:.75;pointer-events:none";
    hint.textContent = "drag to orbit · scroll to zoom · click an isle to look closer" + (onHouseClick ? " · click a monolith to remember" : "");
    if (getComputedStyle(container).position === "static") container.style.position = "relative";
    container.appendChild(hint);

    var renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x04060c, 1);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.82; // restrained baseline (spec §8): bloom spends only at landing moments
    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(46, W / H, 0.1, 900);

    // dock-anchored home framing (Spec-2 §9): the whole orbit sits in frame at rest
    var HOME_TARGET_Y = 4, HOME_RAD = 62; // Esc / wheel-zoom-out-past-55 tween back to these values
    var CLOSE_ORBIT_RAD = 26, CLOSE_ORBIT_MS = 800; // isle close-orbit tween targets (Spec-2 §9, binding)
    var target = new THREE.Vector3(0, HOME_TARGET_Y, 0);
    var az = 0.9, pol = 1.05, rad = HOME_RAD, dragging = false, lx = 0, ly = 0;
    var introActive = true, INTRO = 2.0; // reveal beat: fly-in as the camera arrives

    scene.add(new THREE.HemisphereLight(DUSK_BAND[2], DUSK_BAND[6], 0.34));
    scene.add(new THREE.AmbientLight(DUSK_BAND[1], 0.16));
    var duskLight = new THREE.DirectionalLight(DUSK_BAND[3], 0.38);
    duskLight.position.set(-42, 52, -26); scene.add(duskLight);
    var world = new THREE.Group(); scene.add(world); // idle sway applies to this group only

    function radial(st) {
      var c = document.createElement("canvas"); c.width = c.height = 128;
      var g = c.getContext("2d"), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      for (var i = 0; i < st.length; i++) gr.addColorStop(st[i][0], st[i][1]);
      g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c);
    }
    var warmTex = radial([[0, rgba(255, 205, 140, 0.9)], [0.5, rgbaHex(DUSK_BAND[8], 0.35)], [1, rgbaHex(DUSK_BAND[8], 0)]]);
    var cloudTex = radial([[0, rgbaHex(DUSK_BAND[11], 0.55)], [0.6, rgbaHex(DUSK_BAND[11], 0.22)], [1, rgbaHex(DUSK_BAND[11], 0)]]);
    function sprite(t, s, x, y, z, o, bl) {
      var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, blending: bl || THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: o == null ? 1 : o }));
      sp.scale.set(s, s, 1); sp.position.set(x, y, z); world.add(sp); return sp;
    }

    // --- sky: a BackSide sphere painted with a vertical gradient through the dusk stops ---
    (function () {
      var c = document.createElement("canvas"); c.width = 8; c.height = 256;
      var g = c.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, cssHex(DUSK_BAND[0]));
      gr.addColorStop(0.32, cssHex(DUSK_BAND[1]));
      gr.addColorStop(0.62, cssHex(DUSK_BAND[2]));
      gr.addColorStop(0.85, cssHex(DUSK_BAND[3]));
      gr.addColorStop(1, cssHex(DUSK_BAND[4]));
      g.fillStyle = gr; g.fillRect(0, 0, 8, 256);
      var sky = new THREE.Mesh(new THREE.SphereGeometry(460, 32, 20), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), side: THREE.BackSide, fog: false, depthWrite: false }));
      scene.add(sky); // sky stays outside the world group's sway (Spec-2 §3: "everything but sky/stars")
    })();

    // a low warm sun-glow near the horizon — ambient backdrop, not a light source
    sprite(warmTex, 130, -210, 10, -300, 0.4);

    // stars — kept from the prior valley scene, unchanged in spirit
    (function () {
      var g = new THREE.BufferGeometry(), n = 420, p = new Float32Array(n * 3);
      for (var i = 0; i < n; i++) {
        // ambient FX — outside the determinism boundary (spec §5)
        var r = 150 + rnd(0, 130), th = rnd(0, 6.28), ph = Math.acos(2 * rnd(0, 1) - 1);
        p[i * 3] = r * Math.sin(ph) * Math.cos(th);
        p[i * 3 + 1] = Math.abs(r * Math.cos(ph)) * 0.7 + 22;
        p[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
      }
      g.setAttribute("position", new THREE.BufferAttribute(p, 3));
      scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xcac2e6, size: 0.6, transparent: true, opacity: 0.72 })));
    })();

    // --- the cloud shelf: 8-12 soft sprites drifting below the isles, never inside the reserved
    // air shells (radius kept clear of [R_ORBIT*1.12, R_ORBIT*1.40], y kept below y_rim+14) ---
    var cloudGapLo = WXLaw.R_ORBIT * 1.12, cloudGapHi = WXLaw.R_ORBIT * 1.40;
    var clouds = [];
    var CLOUD_N = 10;
    for (var ci = 0; ci < CLOUD_N; ci++) {
      // ambient FX — outside the determinism boundary (spec §5)
      var inner = rnd(0, 1) < 0.62;
      var cr = inner ? rnd(10, cloudGapLo - 3) : rnd(cloudGapHi + 5, cloudGapHi + 42);
      var ca = rnd(0, 6.28), cy = rnd(-19, -5);
      var cx = Math.cos(ca) * cr, cz = Math.sin(ca) * cr;
      var cs = sprite(cloudTex, rnd(15, 29), cx, cy, cz, rnd(0.16, 0.3));
      clouds.push({ s: cs, bx: cx, bz: cz, ph: rnd(0, 6.28) });
    }

    // --- shared rock materials + geometry (the WX Corolla base: a flat-shaded double cone — lit
    // top half, dark underside — whose rim sits at y_rim=0 in world space) ---
    var rockLitMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[5], flatShading: true, roughness: 0.95 });
    var rockDarkMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[6], flatShading: true, roughness: 1 });
    var seedLitMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[10], flatShading: true, roughness: 0.95 });
    function rockGeoms(radius, litH, darkH) {
      return { top: new THREE.ConeGeometry(radius, litH, 8, 1, false), bot: new THREE.ConeGeometry(radius, darkH, 8, 1, false), litH: litH, darkH: darkH };
    }
    function placeRock(geoms, litMat, darkMat, x, z, scale) {
      var g = new THREE.Group();
      var top = new THREE.Mesh(geoms.top, litMat); top.position.y = geoms.litH / 2; g.add(top);
      var bot = new THREE.Mesh(geoms.bot, darkMat); bot.rotation.x = Math.PI; bot.position.y = -geoms.darkH / 2; g.add(bot);
      g.scale.setScalar(scale == null ? 1 : scale);
      g.position.set(x, 0, z); // the rim stays at y_rim=0 regardless of scale (uniform scale about the origin)
      world.add(g);
      return g;
    }

    // --- the dock: constant geometry, never grows (Spec-2 §6) ---
    var HOME_R = 6.2;
    var jettyMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[7], roughness: 0.9, flatShading: true });
    var lampMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[8], emissive: DUSK_BAND[8], emissiveIntensity: 1.5, flatShading: true });
    var doorMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[9], emissive: DUSK_BAND[9], emissiveIntensity: 1.05, side: THREE.DoubleSide, flatShading: true });
    var homeGeoms = rockGeoms(HOME_R, 2.6, 3.4);
    placeRock(homeGeoms, rockLitMat, rockDarkMat, 0, 0, 1); // the home rock: a squat 8-sided double cone, dusk-violet stone

    var jettyLen = 16, jettyX0 = HOME_R * 0.7;
    var jetty = new THREE.Mesh(new THREE.BoxGeometry(jettyLen, 0.85, 2.6), jettyMat);
    jetty.position.set(jettyX0 + jettyLen / 2, 0.08, 0); world.add(jetty); // a thin stone pier extending toward +x

    var postX = jettyX0 + jettyLen;
    var post = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.4, 4.2, 8), jettyMat);
    post.position.set(postX, 2.1, 0); world.add(post);
    var lamp = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.68, 0.68), lampMat);
    lamp.position.set(postX, 4.5, 0); world.add(lamp);
    sprite(warmTex, 4.2, postX, 4.5, 0, 0.55); // the lamp's soft halo — steady, never animated
    var lampLight = new THREE.PointLight(DUSK_BAND[8], 1.1, 30, 2.0);
    lampLight.position.set(postX, 4.6, 0); world.add(lampLight);
    // the lamp is STEADY (Spec-2 §6: never a sweeping beam) — its emissive intensity and
    // lampLight.intensity are set once above and never touched again anywhere in the render loop

    var doorway = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 2.3), doorMat);
    doorway.position.set(-4.3, 1.25, 3.5); doorway.rotation.y = 0.5; world.add(doorway); // the lit doorway the front door rises from

    // --- isle base rocks + seed rocks, placed on WXLaw's bearings (Task 1) ---
    var lay = WXLaw.layout(data);
    var isleGeoms = rockGeoms(WXLaw.R_ROCK, 8, 10);
    var SEED_SCALE = 0.35;
    // No height-field survives from the old valley (T2 review, Adjudication 2): the isle "top" is
    // pinned at the rock's own apex so the earned structures always clear the rock mass rather
    // than clip into its sloped flank — a floating crown at the isle's peak, not a buried plaza.
    var ISLE_TOP_Y = isleGeoms.litH;
    var SEED_TOP_Y = isleGeoms.litH * SEED_SCALE;
    var CLOSE_ORBIT_Y = ISLE_TOP_Y + 3; // close-orbit target height — centered on the facet/monolith crown
    var clickableIsles = []; // second-priority pick layer (Task 4): a hit starts the close-orbit tween
    for (var ii = 0; ii < lay.isles.length; ii++) {
      var isleRock = placeRock(isleGeoms, rockLitMat, rockDarkMat, lay.isles[ii].x, lay.isles[ii].z, 1);
      isleRock.userData.isleCenter = { x: lay.isles[ii].x, z: lay.isles[ii].z }; // world-space center for closeOrbit()
      clickableIsles.push(isleRock);
    }
    for (var si = 0; si < lay.seeds.length; si++) {
      placeRock(isleGeoms, seedLitMat, rockDarkMat, lay.seeds[si].x, lay.seeds[si].z, SEED_SCALE);
    }

    // --- Phase B T3: facets, monoliths, strata rings, per-isle thread, ghost bud ----------------
    // Every position below is a pure function of WXLaw's layout() output (facet.x/z/y/r/sides/rot,
    // bucket, houseIndex) plus plain index arithmetic (k, houseIndex, lap) — no unseeded randomness
    // touches any structural placement here (the determinism boundary, Spec-2 §5).
    var FACET_FR = 1.35;               // facet dome radius (binding)
    var GHOST_R = FACET_FR;            // the ghost outline reads as a facet-sized invitation

    var facetGeomCache = {}, monoGeomCache = {}, monoMatCache = {};
    function facetGeomFor(sides) {
      if (!facetGeomCache[sides]) facetGeomCache[sides] = new THREE.CylinderGeometry(FACET_FR, FACET_FR * 1.08, 0.9, sides);
      return facetGeomCache[sides];
    }
    function monoGeomFor(bucket) {
      if (!monoGeomCache[bucket]) monoGeomCache[bucket] = new THREE.BoxGeometry(0.32, 1.6 + 0.5 * bucket, 0.32);
      return monoGeomCache[bucket];
    }
    function monoMatFor(bucket) {
      // warm glow family only: color/emissive always DUSK_BAND[9] (the doorway's warm hue); only
      // intensity moves with bucket — bucket null->0 still reads as a dim ember, never grey.
      if (!monoMatCache[bucket]) monoMatCache[bucket] = new THREE.MeshStandardMaterial({
        color: DUSK_BAND[9], emissive: DUSK_BAND[9], emissiveIntensity: 0.6 + 0.5 * bucket,
        flatShading: true, roughness: 0.55,
      });
      return monoMatCache[bucket];
    }
    // the six shared facet materials (isle.slot % 6) — never a per-facet material (draw-call budget)
    var facetMats = [];
    for (var fm = 0; fm < 6; fm++) {
      facetMats.push(new THREE.MeshStandardMaterial({ color: DUSK_BAND[12 + fm], flatShading: true, roughness: 0.88 }));
    }
    // one shared strata-ring geometry/material — fr is a fixed constant, so every ring is congruent
    var ringGeo = new THREE.TorusGeometry(FACET_FR * 1.15, 0.05, 8, 20);
    var ringMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[19], flatShading: true, roughness: 0.9 });
    var threadMat = new THREE.LineBasicMaterial({ color: DUSK_BAND[9], transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });

    function hexLoopGeometry(r) {
      var g = new THREE.BufferGeometry(), n = 6, p = new Float32Array(n * 3);
      for (var k = 0; k < n; k++) { var a = k * (Math.PI / 3); p[k * 3] = Math.cos(a) * r; p[k * 3 + 1] = 0; p[k * 3 + 2] = Math.sin(a) * r; }
      g.setAttribute("position", new THREE.BufferAttribute(p, 3));
      return g;
    }
    // shared ghost geometry/material: IDENTICAL parameters on every isle — only position differs,
    // so the one shared material's opacity pulse (the animation loop, below) drives every isle at once
    var ghostGeo = hexLoopGeometry(GHOST_R);
    var ghostMat = new THREE.LineBasicMaterial({ color: DUSK_BAND[18], transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false });

    var clickableMonoliths = [];
    var litHouses = 0;

    for (var ik = 0; ik < lay.isles.length; ik++) {
      var isle = lay.isles[ik];
      var tipByHouse = {}; // houseIndex -> this isle's built monolith tip, world-space

      for (var ck = 0; ck < isle.clusters.length; ck++) {
        var cluster = isle.clusters[ck];
        for (var fk = 0; fk < cluster.facets.length; fk++) {
          var facet = cluster.facets[fk];
          var baseY = ISLE_TOP_Y + facet.y; // the facet's base plane (terrace lift + stack run)
          var wx = isle.x + facet.x, wz = isle.z + facet.z; // facet.x/z are isle-local (cluster offset already applied)

          var facetMesh = new THREE.Mesh(facetGeomFor(facet.sides), facetMats[isle.slot % 6]);
          facetMesh.position.set(wx, baseY + 0.45, wz);
          facetMesh.rotation.y = facet.rot;
          world.add(facetMesh);

          if (facet.rings > 0) {
            var ring = new THREE.Mesh(ringGeo, ringMat);
            ring.position.set(wx, baseY, wz); // centered on the base plane: half above, half sunk
            // organically tilted by facet.rot (tree-ring vocabulary) — a perfectly flat, identical
            // series would read as a mechanical stamp, not a grown terrace
            ring.rotation.x = Math.PI / 2 + (facet.rot - Math.PI) * 0.12;
            world.add(ring);
          }

          var bucket = facet.bucket == null ? 0 : facet.bucket;
          var monoH = 1.6 + 0.5 * bucket;
          var facetTopY = baseY + 0.9;
          var monoMesh = new THREE.Mesh(monoGeomFor(bucket), monoMatFor(bucket));
          monoMesh.position.set(wx, facetTopY + monoH / 2, wz);
          monoMesh.userData.houseIndex = facet.houseIndex; // the GLOBAL house index (Task 4's raycast target)
          world.add(monoMesh);
          clickableMonoliths.push(monoMesh);
          litHouses++;
          tipByHouse[facet.houseIndex] = { x: wx, y: facetTopY + monoH, z: wz };
        }
      }

      // the arrival-thread: isle.thread order, through the built monolith tips, PER ISLE ONLY —
      // never a global houses list, never crossing into another isle's thread
      var threadPts = [];
      for (var th2 = 0; th2 < isle.thread.length; th2++) {
        var tip = tipByHouse[isle.thread[th2]]; // skip seed-hosted/skipped indices absent as facets here
        if (tip) threadPts.push(tip);
      }
      if (threadPts.length >= 2) {
        var tg = new THREE.BufferGeometry(), tp = new Float32Array(threadPts.length * 3);
        for (var tpk = 0; tpk < threadPts.length; tpk++) { tp[tpk * 3] = threadPts[tpk].x; tp[tpk * 3 + 1] = threadPts[tpk].y; tp[tpk * 3 + 2] = threadPts[tpk].z; }
        tg.setAttribute("position", new THREE.BufferAttribute(tp, 3));
        world.add(new THREE.Line(tg, threadMat));
      }

      // the ghost bud: the outward invitation, one per isle, identical shape/material everywhere
      if (isle.ghost) {
        var ghostLoop = new THREE.LineLoop(ghostGeo, ghostMat);
        ghostLoop.position.set(isle.x + isle.ghost.x, ISLE_TOP_Y + isle.ghost.y, isle.z + isle.ghost.z);
        world.add(ghostLoop);
      }

      // ONE warm point light per isle, at its center — never per monolith (draw-call budget)
      var isleLight = new THREE.PointLight(DUSK_BAND[9], 1.0, 40, 2.0);
      isleLight.position.set(isle.x, ISLE_TOP_Y + 2.2, isle.z);
      world.add(isleLight);
    }

    // seed monoliths: small, on the seed rock, deterministic TIGHT RING positions by their list
    // order — index arithmetic only, no randomness
    var SEED_RING_R = 0.55, SEED_RING_STEP = Math.PI / 3; // a hex step; a 7th+ entry laps outward
    for (var sk = 0; sk < lay.seeds.length; sk++) {
      var seed = lay.seeds[sk];
      for (var mk = 0; mk < seed.monoliths.length; mk++) {
        var houseIndex = seed.monoliths[mk];
        var house = data.houses[houseIndex];
        var sBucket = (house && house.bucket != null) ? house.bucket : 0;
        var lap = Math.floor(mk / 6), ang = (mk % 6) * SEED_RING_STEP;
        var ringR = SEED_RING_R * (1 + lap * 0.6);
        var sx = seed.x + Math.cos(ang) * ringR, sz = seed.z + Math.sin(ang) * ringR;
        var sMonoH = (1.6 + 0.5 * sBucket) * SEED_SCALE;
        var sMono = new THREE.Mesh(monoGeomFor(sBucket), monoMatFor(sBucket));
        sMono.scale.setScalar(SEED_SCALE);
        sMono.position.set(sx, SEED_TOP_Y + sMonoH / 2, sz);
        sMono.userData.houseIndex = houseIndex; // the GLOBAL house index
        world.add(sMono);
        clickableMonoliths.push(sMono);
        litHouses++;
      }
    }

    // controls (no auto-rotate — founder note)
    var keys = {};
    var downX = 0, downY = 0, ptrMoved = false;
    // the close-orbit tween: a deterministic time-eased interpolation of target/rad, driven every
    // frame in the animation loop below — no library, no unseeded input anywhere in it. A fresh
    // call OVERWRITES this object outright (a new tween cancels whatever was in flight, Spec-2 §9);
    // real drag input clears it to null (the user wins — see mv() below).
    var tween = null;
    function startTween(tx, ty, tz, tr) {
      tween = { fx: target.x, fy: target.y, fz: target.z, tx: tx, ty: ty, tz: tz, fr: rad, tr: tr, t0: Date.now() };
    }
    function goHome() { startTween(0, HOME_TARGET_Y, 0, HOME_RAD); } // Esc / zoom-out-past-55 land here
    // the isle close-orbit (Spec-2 §9): target tweens to the isle's own center, rad tightens to
    // CLOSE_ORBIT_RAD, eased over CLOSE_ORBIT_MS — no other camera behavior lives in this function.
    function closeOrbit(center) { startTween(center.x, CLOSE_ORBIT_Y, center.z, CLOSE_ORBIT_RAD); }
    function kd(e) {
      keys[e.key.toLowerCase()] = true;
      if (e.key === "Escape") goHome(); // Esc always returns to the home framing, from anywhere
    }
    function ku(e) { keys[e.key.toLowerCase()] = false; }
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
    function dn(e) { dragging = true; introActive = false; container.style.cursor = "grabbing"; var t = e.touches ? e.touches[0] : e; lx = t.clientX; ly = t.clientY; downX = t.clientX; downY = t.clientY; ptrMoved = false; }
    function mv(e) {
      if (!dragging) return;
      tween = null; // drag input during a tween cancels it outright — the user wins (Spec-2 §9)
      var t = e.touches ? e.touches[0] : e; if (Math.abs(t.clientX - downX) + Math.abs(t.clientY - downY) > 6) ptrMoved = true; az -= (t.clientX - lx) * 0.006; pol -= (t.clientY - ly) * 0.006; pol = Math.max(0.14, Math.min(1.42, pol)); lx = t.clientX; ly = t.clientY; if (e.touches) e.preventDefault();
    }
    function up() { dragging = false; container.style.cursor = "grab"; }
    cv.addEventListener("pointerdown", dn); window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    cv.addEventListener("touchstart", dn, { passive: false }); cv.addEventListener("touchmove", mv, { passive: false }); cv.addEventListener("touchend", up);
    cv.addEventListener("wheel", function (e) {
      var nextRad = rad * (1 + (e.deltaY > 0 ? 1 : -1) * 0.08);
      if (nextRad > 55) { goHome(); } // wheel-zoom-out past rad>55 tweens back to the home framing
      else { tween = null; rad = Math.max(14, Math.min(110, nextRad)); } // manual zoom — user wins
      e.preventDefault();
    }, { passive: false });

    // pick priority: monolith > (reserved: vessel) > (reserved: station) > isle > dock
    // A CLICK (pointerup without a real drag) resolves against exactly one layer, in that order.
    // A monolith hit fires onHouseClick(houseIndex) — the memory endpoint (index.html owns it; this
    // file performs no network I/O of any kind, here or anywhere else). Failing that, the isle base
    // rocks are raycast next and a hit starts the close-orbit tween. Vessel and station are named
    // placeholders only — Phase B builds neither pick layer, so those two rungs always fall through.
    // The dock itself has no click behavior defined at any priority.
    var raycaster = new THREE.Raycaster();
    function clickAt(e) {
      // !dragging rejects a gesture that STARTED off-canvas (e.g. a text-selection drag released
      // over the canvas): dn never ran, so ptrMoved is stale — the canvas-target listener fires
      // before the window-bubble up() clears dragging, so this check is reliable.
      if (!dragging || ptrMoved) return;
      var rect = cv.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(ndc, camera);

      if (onHouseClick && clickableMonoliths.length) {
        var mHits = raycaster.intersectObjects(clickableMonoliths, true);
        if (mHits.length) {
          var mo = mHits[0].object;
          while (mo && mo.userData.houseIndex === undefined) mo = mo.parent;
          if (mo) { onHouseClick(mo.userData.houseIndex); return; }
        }
      }
      // (reserved: vessel) — no vessel pick layer exists yet
      // (reserved: station) — no station pick layer exists yet
      if (clickableIsles.length) {
        var iHits = raycaster.intersectObjects(clickableIsles, true);
        if (iHits.length) {
          var io = iHits[0].object;
          while (io && io.userData.isleCenter === undefined) io = io.parent;
          if (io) { closeOrbit(io.userData.isleCenter); return; }
        }
      }
      // dock: reserved lowest priority — no gesture is defined for it
    }
    cv.addEventListener("pointerup", clickAt);
    container.style.cursor = "grab";
    var stopped = false;
    activeTeardown = function () { stopped = true; window.removeEventListener("keydown", kd); window.removeEventListener("keyup", ku); window.removeEventListener("pointermove", mv); window.removeEventListener("pointerup", up); };

    var composer = null;
    if (window.ResizeObserver) new ResizeObserver(function () { var w = container.clientWidth, h = container.clientHeight; if (!w || !h) return; renderer.setSize(w, h); if (composer) composer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); }).observe(container);
    try {
      if (THREE.EffectComposer && THREE.RenderPass && THREE.UnrealBloomPass) {
        composer = new THREE.EffectComposer(renderer);
        composer.addPass(new THREE.RenderPass(scene, camera));
        composer.addPass(new THREE.UnrealBloomPass(new THREE.Vector2(W, H), 0.55, 0.5, 0.62)); // lowkey bloom
      }
    } catch (e) { composer = null; }
    function draw() { if (composer) composer.render(); else renderer.render(scene, camera); }

    var t0 = Date.now();
    (function loop() {
      if (stopped) return; // a newer render (or teardown) took over
      requestAnimationFrame(loop);
      var t = (Date.now() - t0) / 1000;
      var mvx = 0, mvz = 0;
      if (keys["w"] || keys["arrowup"]) mvz += 1; if (keys["s"] || keys["arrowdown"]) mvz -= 1;
      if (keys["a"] || keys["arrowleft"]) mvx -= 1; if (keys["d"] || keys["arrowright"]) mvx += 1;
      if (mvx || mvz) { var fx = Math.cos(az), fz = Math.sin(az); target.x += (-fx * mvz + fz * mvx) * 0.8; target.z += (-fz * mvz - fx * mvx) * 0.8; var lim = 54, d = Math.sqrt(target.x * target.x + target.z * target.z); if (d > lim) { target.x *= lim / d; target.z *= lim / d; } }
      if (tween) {
        // deterministic time-eased interpolation (ease-out cubic, t-only — no library): while a
        // tween is in flight it OWNS target/rad, overriding any WASD delta computed just above.
        var te = Math.min(1, (Date.now() - tween.t0) / CLOSE_ORBIT_MS);
        var ee = 1 - Math.pow(1 - te, 3);
        target.x = tween.fx + (tween.tx - tween.fx) * ee;
        target.y = tween.fy + (tween.ty - tween.fy) * ee;
        target.z = tween.fz + (tween.tz - tween.fz) * ee;
        rad = tween.fr + (tween.tr - tween.fr) * ee;
        if (te >= 1) tween = null; // arrived — discard, don't leave it dangling at ee==1 forever
      }
      var ige = 1;
      if (introActive) { var ig = Math.min(1, t / INTRO); ige = 1 - Math.pow(1 - ig, 3); if (ig >= 1) introActive = false; }
      world.position.y = Math.sin(t * 0.35) * 0.6; // idle sway — the world group only (Spec-2 §3)
      for (var ci2 = 0; ci2 < clouds.length; ci2++) { var cl = clouds[ci2]; cl.s.position.x = cl.bx + Math.sin(t * 0.05 + cl.ph) * 4; cl.s.position.z = cl.bz + Math.cos(t * 0.04 + cl.ph) * 4; }
      // the ghost bud's pulse: deterministic, time-based (t only), 0.35<->0.85, IDENTICAL on every
      // isle because every isle's LineLoop shares this ONE material — one assignment drives them all
      ghostMat.opacity = 0.6 + 0.25 * Math.sin(t * 1.3);
      // fly-in reveal: start wide + high, ease to the resting pose (rr==rad, pp==pol once ige==1)
      var rr = rad * (1 + 0.7 * (1 - ige)), pp = pol * (0.8 + 0.2 * ige);
      camera.position.set(target.x + rr * Math.sin(pp) * Math.cos(az), target.y + rr * Math.cos(pp), target.z + rr * Math.sin(pp) * Math.sin(az));
      camera.lookAt(target);
      draw();
    })();

    // The described==displayed contract (Spec-1 founder requirement): the renderer reports how
    // many EARNED, clickable monoliths it actually placed — isle facet monoliths + seed monoliths,
    // every one of them clickable (litHouses === clickableMonoliths.length by construction).
    return {
      litHouses: litHouses,
      houseTargets: clickableMonoliths.length,
      houseScreenXY: function (i) {
        // test hook: the CURRENT screen position of monolith payload-index i (for the zero-token
        // smoke to dispatch a REAL pointer event through the production raycast path)
        for (var k = 0; k < clickableMonoliths.length; k++) {
          if (clickableMonoliths[k].userData.houseIndex === i) {
            var v = new THREE.Vector3();
            clickableMonoliths[k].getWorldPosition(v);
            v.project(camera);
            var rect = cv.getBoundingClientRect();
            return { x: rect.left + ((v.x + 1) / 2) * rect.width, y: rect.top + ((1 - v.y) / 2) * rect.height };
          }
        }
        return null;
      },
      isleCount: lay.isles.length,
      seedCount: lay.seeds.length,
      skipped: lay.skipped,
    };
  }

  // teardown: stop the active scene's loop + listeners (a re-render or a saga start tears it down).
  return {
    render: render,
    teardown: function () { if (activeTeardown) { activeTeardown(); activeTeardown = null; } },
    _normalize: normalize,
  };
})();
