/* The Kindled Valley — 3D reward terrain renderer.
 * Terrain3D.render(container, payload) builds a WebGL valley from the L-13 wire payload:
 *   each rendered region -> a village (elevation bucket -> terraces, vitality bucket -> brightness);
 *   each seed region     -> a dark ember waiting to be kindled.
 * Village POSITIONS are a function of the public ordinal ONLY (never frame identity). Requires the
 * vendored global THREE (+ optional EffectComposer/UnrealBloomPass for bloom); degrades to a note if absent.
 * Served ONLY at the close (two-phase L-13 timing). No frame_code / veldra: ref is ever consumed.
 */
window.Terrain3D = (function () {
  "use strict";
  function rgba(r, g, b, a) { return "rgba(" + r + "," + g + "," + b + "," + a + ")"; }
  function rnd(a, b) { return a + Math.random() * (b - a); }

  function normalize(payload) {
    var regions = Array.isArray(payload) ? payload : (payload && payload.regions) || [];
    var transfer = (payload && payload.transfer) || []; // reserved for the connection layer; unused in V1
    return { regions: regions, transfer: transfer };
  }

  // Positional layout: a deterministic phyllotaxis spiral keyed by the PUBLIC ordinal only (L-13).
  function pos(ordinal) {
    var golden = 2.399963, r = 9 + ordinal * 7.4;
    return { x: Math.cos(ordinal * golden) * r, z: Math.sin(ordinal * golden) * r };
  }

  function render(container, payload) {
    var THREE = window.THREE;
    var data = normalize(payload);
    if (!THREE) { return; } // index.html keeps a text note as the no-WebGL fallback

    var W = container.clientWidth || 680, H = container.clientHeight || 460;
    var cv = document.createElement("canvas");
    container.appendChild(cv);
    var hint = document.createElement("div");
    hint.style.cssText = "position:absolute;left:14px;bottom:11px;font:12px system-ui,sans-serif;color:#e6a860;opacity:.75;pointer-events:none";
    hint.textContent = "drag to orbit · scroll to zoom · WASD to roam";
    if (getComputedStyle(container).position === "static") container.style.position = "relative";
    container.appendChild(hint);

    var renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x04060c, 1);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.82; // lowkey baseline (founder note): restrained when kicking off
    var scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x08111f, 0.0118);
    var camera = new THREE.PerspectiveCamera(46, W / H, 0.1, 900);

    function th(x, y) {
      var d2 = x * x + y * y, r = Math.sqrt(d2);
      var basin = -7 * Math.exp(-d2 / 760);
      var hills = 2.2 * Math.sin(x * 0.1) * Math.cos(y * 0.09) + 1.6 * Math.sin(x * 0.05 + 1.3) * Math.sin(y * 0.07) + 1.0 * Math.cos(x * 0.17 + y * 0.12) + 0.5 * Math.sin(x * 0.31 + y * 0.25);
      var ridge = 5.2 * Math.exp(-Math.pow(r - 56, 2) / 460);
      return basin + hills + ridge;
    }
    function wh(X, Z) { return th(X, -Z); }

    // frame the placed villages
    var maxR = 12;
    for (var ri = 0; ri < data.regions.length; ri++) { var p = pos(ri); maxR = Math.max(maxR, Math.sqrt(p.x * p.x + p.z * p.z)); }
    var target = new THREE.Vector3(0, wh(0, 0) + 4, 0);
    var az = 0.9, pol = 1.14, rad = Math.min(78, 26 + maxR * 1.1), dragging = false, lx = 0, ly = 0;
    var introActive = true, INTRO = 2.0; // reveal beat: fly-in + villages kindle up as the camera arrives
    scene.add(new THREE.HemisphereLight(0x18314c, 0x04060c, 0.28));
    scene.add(new THREE.AmbientLight(0x091320, 0.16));
    var moon = new THREE.DirectionalLight(0x8fb0d8, 0.32); moon.position.set(-46, 54, -30); scene.add(moon);
    var world = new THREE.Group(); scene.add(world);

    function radial(st) {
      var c = document.createElement("canvas"); c.width = c.height = 128;
      var g = c.getContext("2d"), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      for (var i = 0; i < st.length; i++) gr.addColorStop(st[i][0], st[i][1]);
      g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c);
    }
    var warmTex = radial([[0, rgba(255, 196, 120, 0.9)], [0.45, rgba(255, 140, 64, 0.32)], [1, rgba(255, 140, 64, 0)]]);
    var coreTex = radial([[0, rgba(255, 224, 164, 0.95)], [0.5, rgba(255, 176, 104, 0.45)], [1, rgba(255, 168, 96, 0)]]);
    var fogTex = radial([[0, rgba(150, 192, 226, 0.55)], [0.55, rgba(104, 150, 198, 0.28)], [1, rgba(104, 150, 198, 0)]]);
    var emberTex = radial([[0, rgba(255, 140, 74, 0.7)], [1, rgba(255, 140, 74, 0)]]);
    function sprite(t, s, x, y, z, o, bl) {
      var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, blending: bl || THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: o == null ? 1 : o }));
      sp.scale.set(s, s, 1); sp.position.set(x, y, z); world.add(sp); return sp;
    }

    // sky + moon
    (function () {
      var c = document.createElement("canvas"); c.width = 8; c.height = 256;
      var g = c.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, "#060a18"); gr.addColorStop(0.5, "#0a1226"); gr.addColorStop(0.75, "#131d34"); gr.addColorStop(0.9, "#20223a"); gr.addColorStop(1, "#2c2440");
      g.fillStyle = gr; g.fillRect(0, 0, 8, 256);
      var sky = new THREE.Mesh(new THREE.SphereGeometry(460, 32, 20), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), side: THREE.BackSide, fog: false, depthWrite: false }));
      scene.add(sky);
      var moonS = new THREE.Sprite(new THREE.SpriteMaterial({ map: coreTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.8 }));
      moonS.scale.set(11, 11, 1); moonS.position.set(-170, 160, -280); world.add(moonS);
    })();

    // terrain
    var seg = 170, gs = 230;
    var geo = new THREE.PlaneGeometry(gs, gs, seg, seg), gp = geo.attributes.position, cols = [];
    var cLow = new THREE.Color(0x07130e), cMid = new THREE.Color(0x0d2215), cHigh = new THREE.Color(0x152632), cwm = new THREE.Color(0x261a0e), cdark = new THREE.Color(0x03060b);
    for (var i = 0; i < gp.count; i++) {
      var x = gp.getX(i), y = gp.getY(i), r = Math.sqrt(x * x + y * y), h = th(x, y);
      gp.setZ(i, h);
      var hn = Math.max(0, Math.min(1, (h + 7) / 13));
      var col = cLow.clone().lerp(cMid, Math.min(1, hn * 1.5));
      col.lerp(cHigh, Math.max(0, (hn - 0.55) * 2.2));
      col.lerp(cwm, Math.min(0.34, Math.exp(-(x * x + y * y) / 700) * 0.42));
      col.lerp(cdark, Math.max(0, Math.min(1, (r - 50) / 30)) * 0.94);
      cols.push(col.r, col.g, col.b);
    }
    geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3)); geo.computeVertexNormals();
    var terrain = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.98, metalness: 0.02 }));
    terrain.rotation.x = -Math.PI / 2; world.add(terrain);

    // shared materials + geometry
    var wallMat = new THREE.MeshStandardMaterial({ color: 0x1b2431, roughness: 0.9, metalness: 0.08, emissive: 0x1c1206, emissiveIntensity: 0.14 });
    var fieldMat = new THREE.MeshStandardMaterial({ color: 0x263a20, roughness: 1 });
    var cropMat = new THREE.MeshStandardMaterial({ color: 0x3c5a2c, roughness: 1, emissive: 0x0a1604, emissiveIntensity: 0.3 });
    var postMat = new THREE.MeshStandardMaterial({ color: 0x231a10, roughness: 0.9 });
    var roofM = new THREE.MeshStandardMaterial({ color: 0x1a120b, roughness: 0.85 });
    var timber = new THREE.MeshStandardMaterial({ color: 0x2e2116, roughness: 0.9 });
    var dB = new THREE.MeshStandardMaterial({ color: 0x0d121c, roughness: 0.95 });
    var dR = new THREE.MeshStandardMaterial({ color: 0x0b0f17, roughness: 0.9 });
    var chimMat = new THREE.MeshStandardMaterial({ color: 0x241a12, roughness: 0.95 });
    var orbGeo = new THREE.SphereGeometry(0.2, 8, 8), postGeo = new THREE.CylinderGeometry(0.08, 0.1, 1.5, 5);
    var beacons = [], lightSites = [], litMats = [];

    function litWinMat(bright) { var m = new THREE.MeshStandardMaterial({ color: 0x1a1208, emissive: 0xffc470, emissiveIntensity: 1.0 + 1.8 * bright }); litMats.push({ m: m, base: m.emissiveIntensity }); return m; }
    function orbMat(bright) { var m = new THREE.MeshStandardMaterial({ color: 0x1a1206, emissive: 0xffc06a, emissiveIntensity: 1.0 + 1.6 * bright }); litMats.push({ m: m, base: m.emissiveIntensity }); return m; }

    function gTier(cx, cz, vb, rT, rB, h, localCy, rot, bright) {
      var g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(rT, rB, h, 6), wallMat));
      var top = new THREE.Mesh(new THREE.CylinderGeometry(rT * 0.96, rT * 0.96, 0.35, 6), fieldMat); top.position.y = h / 2 + 0.17; g.add(top);
      for (var cx2 = -rT * 0.6; cx2 <= rT * 0.6; cx2 += 1.35) {
        var half = Math.sqrt(Math.max(0, Math.pow(rT * 0.6, 2) - cx2 * cx2)); if (half < 0.7) continue;
        var cr = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.42, half * 1.9), cropMat); cr.position.set(cx2, h / 2 + 0.5, 0); g.add(cr);
      }
      var om = orbMat(bright);
      for (var a = 0; a < 6.28; a += 6.28 / 5) {
        var lx2 = Math.cos(a) * (rT * 0.9), lz2 = Math.sin(a) * (rT * 0.9);
        var post = new THREE.Mesh(postGeo, postMat); post.position.set(lx2, h / 2 + 0.75, lz2); g.add(post);
        var orb = new THREE.Mesh(orbGeo, om); orb.position.set(lx2, h / 2 + 1.6, lz2); g.add(orb);
        var gl = new THREE.Sprite(new THREE.SpriteMaterial({ map: warmTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.18 + 0.22 * bright }));
        gl.scale.set(1.5, 1.5, 1); gl.position.set(lx2, h / 2 + 1.6, lz2); g.add(gl);
      }
      g.position.set(cx, vb + localCy, cz); g.rotation.y = rot; world.add(g);
    }

    function house(x, y, z, s, lit, bright) {
      var g = new THREE.Group();
      var b = new THREE.Mesh(new THREE.BoxGeometry(1.7 * s, 1.4 * s, 1.7 * s), lit ? timber : dB); b.position.y = 0.7 * s; g.add(b);
      var rf = new THREE.Mesh(new THREE.ConeGeometry(1.5 * s, 1.2 * s, 4), lit ? roofM : dR); rf.position.y = 1.4 * s + 0.58 * s; rf.rotation.y = Math.PI / 4; g.add(rf);
      var ch = new THREE.Mesh(new THREE.BoxGeometry(0.28 * s, 0.7 * s, 0.28 * s), chimMat); ch.position.set(0.5 * s, 1.7 * s, 0.3 * s); g.add(ch);
      if (lit) {
        var wm = litWinMat(bright);
        var w = new THREE.Mesh(new THREE.BoxGeometry(0.5 * s, 0.5 * s, 0.06), wm); w.position.set(0, 0.66 * s, 0.86 * s); g.add(w);
        var w2 = w.clone(); w2.position.set(0, 0.66 * s, -0.86 * s); g.add(w2);
      }
      g.position.set(x, y, z); g.rotation.y = Math.random() * 6.28; world.add(g);
    }
    function houseRing(cx, cz, vb, n, r, localY, s, lit, bright) {
      for (var k = 0; k < n; k++) { var a = k / n * 6.28; house(cx + Math.cos(a) * r + rnd(-1, 1), vb + localY, cz + Math.sin(a) * r + rnd(-1, 1), s, lit, bright); }
    }

    // A village: elevation bucket (1..3) -> number of rising terraces; vitality bucket (1..3) -> brightness.
    function buildVillage(cx, cz, elev, vit) {
      var vb = wh(cx, cz), bright = Math.max(1, vit) / 3, tiers = Math.max(1, Math.min(3, elev));
      var rTs = [11.6, 8.0, 4.9], rBs = [12.8, 9.0, 5.7], cy = [0.9, 2.75, 4.7], rots = [0, 0.52, 0.2];
      for (var k = 0; k < tiers; k++) gTier(cx, cz, vb, rTs[k], rBs[k], 1.85, cy[k], rots[k], bright);
      // houses ring per built terrace, brightness by vitality
      houseRing(cx, cz, vb, 6, 9.7, 2.15, 1.05, true, bright);
      if (tiers >= 2) houseRing(cx, cz, vb, 4, 6.3, 4.0, 0.95, true, bright);
      if (tiers >= 3) houseRing(cx, cz, vb, 2, 2.7, 6.0, 0.8, true, bright);
      houseRing(cx, cz, vb, 6, 15.6, 0.5, 1.0, false, bright);
      // beacon on the top built terrace
      var by = vb + (tiers >= 3 ? 6.0 : tiers === 2 ? 4.1 : 2.3);
      var post = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.5, 4.6, 8), new THREE.MeshStandardMaterial({ color: 0x2a2016, roughness: 0.7 })); post.position.set(cx, by + 2.3, cz); world.add(post);
      var brazier = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 0.4, 0.6, 8), new THREE.MeshStandardMaterial({ color: 0x241a10, roughness: 0.7, emissive: 0x3a1e08, emissiveIntensity: 0.5 })); brazier.position.set(cx, by + 4.5, cz); world.add(brazier);
      var flame = new THREE.Mesh(new THREE.IcosahedronGeometry(0.66, 0), new THREE.MeshStandardMaterial({ color: 0x160b04, emissive: 0xff8a2c, emissiveIntensity: 0.7 + 0.9 * bright })); flame.position.set(cx, by + 5.1, cz); world.add(flame);
      var bl = new THREE.PointLight(0xffab54, 0.7 + 1.1 * bright, 40, 2.1); bl.position.set(cx, by + 5.2, cz); world.add(bl);
      var gc = sprite(coreTex, 2.6, cx, by + 5.1, cz, 0.3 + 0.3 * bright), gb = sprite(warmTex, 10, cx, by + 4.9, cz, 0.2 + 0.2 * bright);
      var sh = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 0.5, 20, 18, 1, true), new THREE.MeshBasicMaterial({ color: 0xffbf72, transparent: true, opacity: 0.01 + 0.016 * bright, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide })); sh.position.set(cx, by + 12, cz); world.add(sh);
      beacons.push({ flame: flame, bl: bl, gc: gc, gb: gb, base: bright, ph: Math.random() * 6.28 });
      lightSites.push({ x: cx, z: cz, y: vb });
    }

    function buildEmber(cx, cz) {
      var vb = wh(cx, cz);
      house(cx + 1.2, vb, cz, 0.9, false, 0); house(cx - 1.4, vb, cz + 1.6, 0.85, false, 0);
      sprite(emberTex, 2.6, cx, vb + 1.1, cz, 0.3);
      var pl = new THREE.PointLight(0xff8a4a, 0.22, 16); pl.position.set(cx, vb + 1.4, cz); world.add(pl);
    }

    // place regions by ordinal
    for (var rgi = 0; rgi < data.regions.length; rgi++) {
      var reg = data.regions[rgi], pp = pos(rgi);
      if (reg && reg.render === "rendered") buildVillage(pp.x, pp.z, reg.elevation || 1, reg.vitality || 1);
      else buildEmber(pp.x, pp.z);
    }

    // forest + rocks on the slopes (avoid the placed sites + the basin centre)
    var trunkGeo = new THREE.CylinderGeometry(0.16, 0.26, 1.5, 6), cone1 = new THREE.ConeGeometry(1.35, 2.3, 7), cone2 = new THREE.ConeGeometry(1.02, 1.9, 7), cone3 = new THREE.ConeGeometry(0.62, 1.4, 7);
    var trunkMat = new THREE.MeshStandardMaterial({ color: 0x2a1c12, roughness: 0.95 }), pineMat = new THREE.MeshStandardMaterial({ color: 0x1b3823, roughness: 1, flatShading: true }), pineMat2 = new THREE.MeshStandardMaterial({ color: 0x21432a, roughness: 1, flatShading: true });
    var rockGeo = new THREE.IcosahedronGeometry(1, 0), rockMat = new THREE.MeshStandardMaterial({ color: 0x28303c, roughness: 1, flatShading: true });
    function nearSite(x, z, rr) {
      for (var s = 0; s < lightSites.length; s++) { var dx = x - lightSites[s].x, dz = z - lightSites[s].z; if (dx * dx + dz * dz < rr * rr) return true; }
      for (var r2 = 0; r2 < data.regions.length; r2++) { var q = pos(r2); if ((x - q.x) * (x - q.x) + (z - q.z) * (z - q.z) < rr * rr) return true; }
      return false;
    }
    function tree(x, z, s) {
      var y = wh(x, z), g = new THREE.Group();
      var t0 = new THREE.Mesh(trunkGeo, trunkMat); t0.position.y = 0.75 * s; t0.scale.setScalar(s); g.add(t0);
      var pm = Math.random() < 0.5 ? pineMat : pineMat2;
      var a = new THREE.Mesh(cone1, pm); a.position.y = 1.7 * s; a.scale.setScalar(s); g.add(a);
      var b = new THREE.Mesh(cone2, pm); b.position.y = 2.7 * s; b.scale.setScalar(s); g.add(b);
      var c = new THREE.Mesh(cone3, pm); c.position.y = 3.5 * s; c.scale.setScalar(s); g.add(c);
      g.position.set(x, y, z); g.rotation.y = Math.random() * 6.28; world.add(g);
    }
    var forestR = Math.max(26, maxR + 8);
    for (var t = 0; t < 120; t++) { var a = Math.random() * 6.28, r = rnd(forestR - 8, 58); var x = Math.cos(a) * r, z = Math.sin(a) * r; if (nearSite(x, z, 18)) continue; tree(x, z, rnd(0.85, 1.8)); }
    for (var t2 = 0; t2 < 30; t2++) { var a = Math.random() * 6.28, r = rnd(forestR - 10, 60); var x = Math.cos(a) * r, z = Math.sin(a) * r; if (nearSite(x, z, 15)) continue; var m = new THREE.Mesh(rockGeo, rockMat); m.position.set(x, wh(x, z) + 0.1, z); var sc = rnd(0.6, 1.7); m.scale.set(sc, sc * rnd(0.6, 0.9), sc); m.rotation.set(Math.random(), Math.random() * 6.28, Math.random()); world.add(m); }

    // fog frontier — REAL scatter (additive) at CUT intensity (founder note: real, not shiny)
    var fogWall = [];
    for (var fw = 0; fw < 56; fw++) { var a = fw / 56 * 6.28; var R = 60 + Math.sin(a * 4) * 3; var fx = Math.cos(a) * R, fz = Math.sin(a) * R; var s = sprite(fogTex, rnd(30, 44), fx, wh(fx, fz) + rnd(2, 6), fz, rnd(0.12, 0.2)); fogWall.push({ s: s, ph: Math.random() * 6.28, b: s.material.opacity }); }
    for (var sh2 = 0; sh2 < 16; sh2++) { var a = Math.random() * 6.28, R = 72 + Math.random() * 22; var hx = Math.cos(a) * R, hz = Math.sin(a) * R; var m2 = new THREE.Mesh(new THREE.ConeGeometry(10 + Math.random() * 8, 14 + Math.random() * 11, 5), new THREE.MeshStandardMaterial({ color: 0x05080f, roughness: 1 })); m2.position.set(hx, -2, hz); world.add(m2); }
    var mist = [];
    for (var mi = 0; mi < 9; mi++) { var mx = rnd(-50, 50), mz = rnd(-50, 50); var sp = sprite(fogTex, rnd(30, 46), mx, wh(mx, mz) + 2.2, mz, rnd(0.08, 0.15)); mist.push({ s: sp, bx: mx, ph: Math.random() * 6.28 }); }
    // fireflies near lit villages
    var flies = [];
    for (var f = 0; f < Math.min(18, 4 + beacons.length * 5); f++) {
      var site = lightSites.length ? lightSites[f % lightSites.length] : { x: 0, z: 0, y: wh(0, 0) };
      var a = Math.random() * 6.28, r = rnd(3, 12);
      var s = sprite(warmTex, 0.8, site.x + Math.cos(a) * r, site.y + 2 + Math.random() * 4, site.z + Math.sin(a) * r, 0.7);
      flies.push({ s: s, bx: s.position.x, bz: s.position.z, y0: site.y + 2 + Math.random() * 3, amp: rnd(1.6, 4), ph: Math.random() * 6.28, sp: rnd(0.3, 0.7) });
    }
    (function () {
      var g = new THREE.BufferGeometry(), n = 520, p = new Float32Array(n * 3);
      for (var i = 0; i < n; i++) { var r = 150 + Math.random() * 120, t = Math.random() * 6.28, ph = Math.acos(2 * Math.random() - 1); p[i * 3] = r * Math.sin(ph) * Math.cos(t); p[i * 3 + 1] = Math.abs(r * Math.cos(ph)) * 0.75 + 18; p[i * 3 + 2] = r * Math.sin(ph) * Math.sin(t); }
      g.setAttribute("position", new THREE.BufferAttribute(p, 3));
      scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xaec2e6, size: 0.6, transparent: true, opacity: 0.75 })));
    })();

    // controls (no auto-rotate — founder note)
    var keys = {};
    window.addEventListener("keydown", function (e) { keys[e.key.toLowerCase()] = true; });
    window.addEventListener("keyup", function (e) { keys[e.key.toLowerCase()] = false; });
    function dn(e) { dragging = true; introActive = false; container.style.cursor = "grabbing"; var t = e.touches ? e.touches[0] : e; lx = t.clientX; ly = t.clientY; }
    function mv(e) { if (!dragging) return; var t = e.touches ? e.touches[0] : e; az -= (t.clientX - lx) * 0.006; pol -= (t.clientY - ly) * 0.006; pol = Math.max(0.14, Math.min(1.42, pol)); lx = t.clientX; ly = t.clientY; if (e.touches) e.preventDefault(); }
    function up() { dragging = false; container.style.cursor = "grab"; }
    cv.addEventListener("pointerdown", dn); window.addEventListener("pointermove", mv); window.addEventListener("pointerup", up);
    cv.addEventListener("touchstart", dn, { passive: false }); cv.addEventListener("touchmove", mv, { passive: false }); cv.addEventListener("touchend", up);
    cv.addEventListener("wheel", function (e) { rad *= (1 + (e.deltaY > 0 ? 1 : -1) * 0.08); rad = Math.max(14, Math.min(110, rad)); e.preventDefault(); }, { passive: false });
    container.style.cursor = "grab";

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
      requestAnimationFrame(loop);
      var t = (Date.now() - t0) / 1000;
      var mvx = 0, mvz = 0;
      if (keys["w"] || keys["arrowup"]) mvz += 1; if (keys["s"] || keys["arrowdown"]) mvz -= 1;
      if (keys["a"] || keys["arrowleft"]) mvx -= 1; if (keys["d"] || keys["arrowright"]) mvx += 1;
      if (mvx || mvz) { var fx = Math.cos(az), fz = Math.sin(az); target.x += (-fx * mvz + fz * mvx) * 0.8; target.z += (-fz * mvz - fx * mvx) * 0.8; var lim = 54, d = Math.sqrt(target.x * target.x + target.z * target.z); if (d > lim) { target.x *= lim / d; target.z *= lim / d; } target.y = wh(target.x, target.z) + 4; }
      var ige = 1;
      if (introActive) { var ig = Math.min(1, t / INTRO); ige = 1 - Math.pow(1 - ig, 3); if (ig >= 1) introActive = false; }
      var kindle = 0.12 + 0.88 * ige; // villages "catch fire" as the reveal settles in
      for (var bi = 0; bi < beacons.length; bi++) {
        var bc = beacons[bi], fl = 0.7 + 0.3 * Math.sin(t * 6.5 + bc.ph) + 0.12 * Math.sin(t * 15 + bc.ph);
        bc.bl.intensity = (0.7 + 1.1 * bc.base) * (0.8 + 0.25 * fl) * kindle;
        bc.flame.material.emissiveIntensity = (0.7 + 0.9 * bc.base) * (0.75 + 0.4 * fl) * kindle;
        bc.flame.scale.setScalar(0.9 + 0.14 * fl);
        bc.gc.material.opacity = (0.3 + 0.3 * bc.base) * (0.8 + 0.3 * fl) * kindle;
      }
      for (var li = 0; li < litMats.length; li++) litMats[li].m.emissiveIntensity = litMats[li].base * kindle;
      for (var i = 0; i < flies.length; i++) { var ff = flies[i]; ff.s.position.y = ff.y0 + (Math.sin(t * ff.sp + ff.ph) * 0.5 + 0.5) * ff.amp; ff.s.position.x = ff.bx + Math.sin(t * 0.4 + ff.ph) * 1.5; ff.s.position.z = ff.bz + Math.cos(t * 0.35 + ff.ph) * 1.5; ff.s.material.opacity = 0.3 + 0.4 * Math.abs(Math.sin(t * 1.3 + ff.ph)); }
      for (var m = 0; m < mist.length; m++) mist[m].s.position.x = mist[m].bx + Math.sin(t * 0.06 + mist[m].ph) * 9;
      for (var g2 = 0; g2 < fogWall.length; g2++) fogWall[g2].s.material.opacity = fogWall[g2].b * (0.85 + 0.15 * Math.sin(t * 0.5 + fogWall[g2].ph));
      // fly-in reveal: start wide + high, ease to the resting pose (rr==rad, pp==pol once ige==1)
      var rr = rad * (1 + 0.7 * (1 - ige)), pp = pol * (0.8 + 0.2 * ige);
      camera.position.set(target.x + rr * Math.sin(pp) * Math.cos(az), target.y + rr * Math.cos(pp), target.z + rr * Math.sin(pp) * Math.sin(az));
      camera.lookAt(target);
      draw();
    })();
  }

  return { render: render, _pos: pos, _normalize: normalize };
})();
