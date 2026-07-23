/* The Archipelago — dusk-sky scene scaffold (Spec-2 §3/§6/§8, Phase B T2).
 * Terrain3D.render(container, payload, opts) consumes window.WXLaw's pure placement law
 * (WXLaw.layout — Task 1) to place isle base rocks and seed rocks on their frozen bearings. This
 * scaffold ships the dusk sky + cloud shelf, the home dock (rock, jetty, lantern, doorway glow),
 * the world group's idle sway, the camera/controls, and the render() contract — every isle/seed
 * here is an EMPTY rock mass; the facets/monoliths a convergence earns are Task 3's.
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
    0x0d0a1c, // 0  sky zenith — deep violet-black
    0x2a1a3c, // 1  sky upper — violet
    0x5c2d52, // 2  sky mid — mauve-rose
    0xb8586a, // 3  sky horizon — warm rose
    0xffb27a, // 4  sun-glow / warm horizon light
    0x4a2f52, // 5  isle & dock rock — lit dusk-violet stone
    0x1c1226, // 6  isle & dock rock — dark underside
    0x3a2440, // 7  jetty stone / lantern post
    0xffc477, // 8  the lamp — steady warm (never a sweep, never a pulse)
    0xffb066, // 9  the doorway glow — warm
    0x2e1c38, // 10 seed rock — dim lit top
    0x6a4a72  // 11 cloud shelf tint
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
    hint.textContent = "drag to orbit · scroll to zoom" + (onHouseClick ? " · click a monolith to remember" : "");
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
    var target = new THREE.Vector3(0, 4, 0);
    var az = 0.9, pol = 1.05, rad = 62, dragging = false, lx = 0, ly = 0;
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
    var jettyMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[7], roughness: 0.9 });
    var lampMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[8], emissive: DUSK_BAND[8], emissiveIntensity: 1.5 });
    var doorMat = new THREE.MeshStandardMaterial({ color: DUSK_BAND[9], emissive: DUSK_BAND[9], emissiveIntensity: 1.05, side: THREE.DoubleSide });
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

    // --- isle base rocks + seed rocks, placed on WXLaw's bearings (Task 1) — no facets yet ---
    var lay = WXLaw.layout(data);
    var isleGeoms = rockGeoms(WXLaw.R_ROCK, 8, 10);
    for (var ii = 0; ii < lay.isles.length; ii++) {
      placeRock(isleGeoms, rockLitMat, rockDarkMat, lay.isles[ii].x, lay.isles[ii].z, 1);
    }
    for (var si = 0; si < lay.seeds.length; si++) {
      placeRock(isleGeoms, seedLitMat, rockDarkMat, lay.seeds[si].x, lay.seeds[si].z, 0.35);
    }

    // controls (no auto-rotate — founder note)
    var keys = {};
    var downX = 0, downY = 0, ptrMoved = false;
    function kd(e) { keys[e.key.toLowerCase()] = true; }
    function ku(e) { keys[e.key.toLowerCase()] = false; }
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
    function dn(e) { dragging = true; introActive = false; container.style.cursor = "grabbing"; var t = e.touches ? e.touches[0] : e; lx = t.clientX; ly = t.clientY; downX = t.clientX; downY = t.clientY; ptrMoved = false; }
    function mv(e) { if (!dragging) return; var t = e.touches ? e.touches[0] : e; if (Math.abs(t.clientX - downX) + Math.abs(t.clientY - downY) > 6) ptrMoved = true; az -= (t.clientX - lx) * 0.006; pol -= (t.clientY - ly) * 0.006; pol = Math.max(0.14, Math.min(1.42, pol)); lx = t.clientX; ly = t.clientY; if (e.touches) e.preventDefault(); }
    function up() { dragging = false; container.style.cursor = "grab"; }
    cv.addEventListener("pointerdown", dn); window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    cv.addEventListener("touchstart", dn, { passive: false }); cv.addEventListener("touchmove", mv, { passive: false }); cv.addEventListener("touchend", up);
    cv.addEventListener("wheel", function (e) { rad *= (1 + (e.deltaY > 0 ? 1 : -1) * 0.08); rad = Math.max(14, Math.min(110, rad)); e.preventDefault(); }, { passive: false });
    // a CLICK (pointerup without a real drag) on a monolith opens that convergence's memory — the
    // memory endpoint (index.html owns it). Task 3 populates clickableHouses; this scaffold's
    // list stays empty, so a click never fires (described==displayed: houseTargets:0 below).
    var clickableHouses = [];
    var raycaster = onHouseClick ? new THREE.Raycaster() : null;
    function clickAt(e) {
      // !dragging rejects a gesture that STARTED off-canvas (e.g. a text-selection drag released
      // over the canvas): dn never ran, so ptrMoved is stale — the canvas-target listener fires
      // before the window-bubble up() clears dragging, so this check is reliable.
      if (!onHouseClick || !dragging || ptrMoved || !clickableHouses.length) return;
      var rect = cv.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(ndc, camera);
      var hits = raycaster.intersectObjects(clickableHouses, true);
      if (!hits.length) return;
      var o = hits[0].object;
      while (o && o.userData.houseIndex === undefined) o = o.parent;
      if (o) onHouseClick(o.userData.houseIndex);
    }
    if (onHouseClick) cv.addEventListener("pointerup", clickAt);
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
      var ige = 1;
      if (introActive) { var ig = Math.min(1, t / INTRO); ige = 1 - Math.pow(1 - ig, 3); if (ig >= 1) introActive = false; }
      world.position.y = Math.sin(t * 0.35) * 0.6; // idle sway — the world group only (Spec-2 §3)
      for (var ci2 = 0; ci2 < clouds.length; ci2++) { var cl = clouds[ci2]; cl.s.position.x = cl.bx + Math.sin(t * 0.05 + cl.ph) * 4; cl.s.position.z = cl.bz + Math.cos(t * 0.04 + cl.ph) * 4; }
      // fly-in reveal: start wide + high, ease to the resting pose (rr==rad, pp==pol once ige==1)
      var rr = rad * (1 + 0.7 * (1 - ige)), pp = pol * (0.8 + 0.2 * ige);
      camera.position.set(target.x + rr * Math.sin(pp) * Math.cos(az), target.y + rr * Math.cos(pp), target.z + rr * Math.sin(pp) * Math.sin(az));
      camera.lookAt(target);
      draw();
    })();

    // The described==displayed contract (Spec-1 founder requirement): the renderer reports how
    // many EARNED, clickable monoliths it actually placed. This scaffold places none — Task 3
    // builds the facets/monoliths; litHouses/houseTargets return 0 honestly until then.
    return {
      litHouses: 0,
      houseTargets: 0,
      houseScreenXY: function (i) { return null; },
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
