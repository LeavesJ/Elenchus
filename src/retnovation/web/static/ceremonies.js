/* WXCeremony — the settle-cascade + confluence drift, in the named slot (Spec-2 §5/§4/§7, Phase C
 * T3). Consumes terrain3d.js's `_handles` shape (Phase C T2, review-pinned) and WXLaw's pure
 * bearing/orbit constants (Phase B T1) to play two witnessed playbacks:
 *   - playLanding: a new judgment's arrival — Vera travels to the landing isle, its new facets
 *     bloom, the RELIGHT ripples seed-ward through every monolith the isle has ever earned, the
 *     parastichy shimmer flashes once, she returns home.
 *   - playConfluence: a merge — the younger cluster's meshes drift home as one rigid unit while
 *     Vera visits the merged isle and relights it (reusing the same primitive as playLanding).
 * Motion only: this file ships zero user-facing strings and zero unseeded randomness — every beat
 * is a pure function of elapsed time plus the frozen `_handles`/WXLaw data — and no rhythm/spread
 * branching (cascade parity with terrain3d.js, a static guard enforces both files equally). `clock`
 * is an injectable time source (defaults to Date.now) so a test can drive the whole playback
 * deterministically without real wall-clock waits.
 */
window.WXCeremony = (function () {
  "use strict";

  // ---- durations (binding, Phase C T3 brief) --------------------------------------------------
  var VERA_TRAVEL_MS = 1100; // Vera's travel leg, each way, eased
  var BLOOM_MS = 500; // a new facet's scale-up
  var BLOOM_STAGGER_MS = 250; // between successive new facets on the same isle
  var RELIGHT_STAGGER_MS = 120; // between successive monoliths in the RELIGHT ripple
  var RELIGHT_DECAY_MS = 400; // one monolith's emissive decay back to its resting intensity
  var RELIGHT_MULT = 1.8; // the RELIGHT's peak emissive multiplier
  var SHIMMER_MS = 2000; // the parastichy shimmer's full 0->0.5->0 window
  var DRIFT_MS = 1600; // the confluence rigid-group drift to zero
  var VERA_HOVER = 1.6; // she arrives just above the tallest monolith tip she's visiting
  var VERA_ARC_LIFT = 6; // the traveling polyline's midpoint rises this far above both endpoints

  function ease(t) { return 1 - Math.pow(1 - t, 3); }
  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }

  var _active = false;
  var _rafId = null;
  var _restoreHome = null; // {group, home} of the playback currently in flight — cancel()'s target

  function active() { return _active; }

  function cancel() {
    if (_rafId != null && window.cancelAnimationFrame) window.cancelAnimationFrame(_rafId);
    _rafId = null;
    if (_restoreHome) { _restoreHome.group.position.copy(_restoreHome.home); _restoreHome = null; }
    _active = false;
  }

  // one-time per-mesh material clone: terrain3d.js shares monolith materials by bucket and facet
  // materials by isle.slot%6 (draw-call budget) — mutating emissiveIntensity in place would pulse
  // every OTHER mesh sharing that cached instance. Cloning once, lazily, keeps a ceremony's flash
  // scoped to exactly the mesh it targets.
  function ownMaterial(mesh) {
    if (!mesh.userData.__ceremonyOwnMat) {
      mesh.material = mesh.material.clone();
      mesh.userData.__ceremonyOwnMat = true;
      mesh.userData.__ceremonyBaseEmissive = mesh.material.emissiveIntensity || 0;
    }
    return mesh.material;
  }

  // review C1 fix: the rise/bloom beats must animate to a mesh's own BUILT rest scale, never a
  // hardcoded 1.0 — terrain3d.js's hidden-state step stamps it into userData.restScale before
  // zeroing (a seed monolith is built at SEED_SCALE=0.35; an isle facet/monolith at 1.0 — reading
  // it back out here is what keeps isle meshes byte-identical to before this fix).
  function restScalar(mesh) {
    return mesh.userData && mesh.userData.restScale ? mesh.userData.restScale.x : 1;
  }

  // ---- beat builders: each returns {start, dur, run(easedProgress), after?} -------------------
  function beatFacetBloom(mesh, start, dur) {
    var rest = restScalar(mesh);
    return { start: start, dur: dur, run: function (e) { mesh.scale.setScalar(0.01 + (rest - 0.01) * e); } };
  }

  function beatMonolithRise(mesh, start, dur) {
    var rest = restScalar(mesh);
    var finalY = mesh.position.y; // untouched by the hidden-state step — already the resting value
    var h = (mesh.geometry && mesh.geometry.parameters && mesh.geometry.parameters.height) || 0;
    var startY = finalY - (h * rest) / 2; // grounded flush with the facet's top face, at the SCALED height
    return {
      start: start, dur: dur,
      run: function (e) {
        mesh.scale.setScalar(0.01 + (rest - 0.01) * e);
        mesh.position.y = startY + (finalY - startY) * e;
      },
    };
  }

  function beatThreadDraw(line, start, dur) {
    if (!line) return null; // sparse isles build no thread line at all — guarded, never assumed
    var resting = line.material ? line.material.opacity : 0.55;
    line.material = line.material.clone(); // never mutate the cross-isle SHARED thread material
    line.material.opacity = 0; // start hidden — synchronous, before the first tick ever runs
    line.visible = true;
    return { start: start, dur: dur, run: function (e) { line.material.opacity = resting * e; } };
  }

  function beatRelightPulse(mesh, start, dur) {
    var mat = ownMaterial(mesh);
    var base = mesh.userData.__ceremonyBaseEmissive;
    return {
      start: start, dur: dur,
      run: function (e) { mat.emissiveIntensity = base + base * (RELIGHT_MULT - 1) * (1 - e); },
    };
  }

  function beatVeraTravel(group, from, mid, to, start, dur) {
    return {
      start: start, dur: dur,
      run: function (e) {
        var seg = e < 0.5 ? e * 2 : (e - 0.5) * 2;
        var a = e < 0.5 ? from : mid, b = e < 0.5 ? mid : to;
        group.position.set(a.x + (b.x - a.x) * seg, a.y + (b.y - a.y) * seg, a.z + (b.z - a.z) * seg);
      },
    };
  }

  function beatShimmer(overlay, start, dur) {
    if (!overlay || !overlay.length) return null;
    var mat = overlay[0].material; // one shared material across this isle's edge overlays, by design
    return {
      start: start, dur: dur,
      run: function (e) { mat.opacity = e < 0.5 ? e : 1 - e; }, // 0 -> 0.5 -> 0
      after: function () {
        for (var i = 0; i < overlay.length; i++) if (overlay[i].parent) overlay[i].parent.remove(overlay[i]);
      },
    };
  }

  // the RELIGHT primitive: every monolith the isle has ever earned, walked seed-ward in reverse
  // arrival order (isle.thread is already reversed by terrain3d.js's _handles). Shared verbatim by
  // playLanding (the landing isle) and playConfluence (the merged isle) — "press N relights all N."
  function relightIsle(isle, handles, startOffset) {
    var beats = [], thread = isle.thread || [];
    for (var k = 0; k < thread.length; k++) {
      var hh = handles.houses[thread[k]];
      if (hh && hh.monoMesh) beats.push(beatRelightPulse(hh.monoMesh, startOffset + k * RELIGHT_STAGGER_MS, RELIGHT_DECAY_MS));
    }
    var dur = thread.length ? (thread.length - 1) * RELIGHT_STAGGER_MS + RELIGHT_DECAY_MS : 0;
    return { beats: beats, dur: dur };
  }

  function buildShimmerOverlay(isle, handles) {
    var THREE = window.THREE, overlay = [];
    if (!THREE || !THREE.EdgesGeometry || !THREE.LineSegments) return overlay;
    var mat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
    for (var k in handles.houses) {
      if (!Object.prototype.hasOwnProperty.call(handles.houses, k)) continue;
      var hh = handles.houses[k];
      if (hh.isleSlot === isle.slot && hh.facetMesh) {
        var edges = new THREE.LineSegments(new THREE.EdgesGeometry(hh.facetMesh.geometry), mat);
        edges.position.copy(hh.facetMesh.position);
        edges.rotation.copy(hh.facetMesh.rotation);
        handles.world.add(edges);
        overlay.push(edges);
      }
    }
    return overlay;
  }

  // where Vera arrives for a given set of houses on an isle: its center, hovering just above the
  // tallest monolith tip among them (their FINAL resting y — the hidden-state step never touches
  // position, only scale, so this is already the real value even mid-ceremony-setup).
  function isleArrivalPoint(isle, houseIndices, handles) {
    var maxY = null;
    for (var i = 0; i < houseIndices.length; i++) {
      var hh = handles.houses[houseIndices[i]];
      if (hh && hh.monoMesh && (maxY === null || hh.monoMesh.position.y > maxY)) maxY = hh.monoMesh.position.y;
    }
    if (maxY === null) maxY = 0;
    return { x: isle.center.x, y: maxY + VERA_HOVER, z: isle.center.z };
  }

  function midpointAbove(from, to) {
    return { x: (from.x + to.x) / 2, y: Math.max(from.y, to.y) + VERA_ARC_LIFT, z: (from.z + to.z) / 2 };
  }

  // the shared scheduler: a single rAF-driven timeline over `beats`, run(1)-finalized exactly once
  // at `totalDur` so frame-timing jitter never leaves a beat a hair short of its pinned end state.
  function runTimeline(beats, totalDur, clock, onDone) {
    function finalize() {
      for (var i = 0; i < beats.length; i++) {
        beats[i].run(1);
        if (beats[i].after && !beats[i]._done) { beats[i]._done = true; beats[i].after(); }
      }
    }
    if (totalDur <= 0) { finalize(); _active = false; _rafId = null; onDone(); return; }
    _active = true;
    var t0 = clock();
    function tick() {
      var elapsed = clock() - t0;
      if (elapsed >= totalDur) { finalize(); _active = false; _rafId = null; onDone(); return; }
      for (var i = 0; i < beats.length; i++) {
        var b = beats[i];
        if (elapsed >= b.start) {
          var raw = b.dur > 0 ? clamp01((elapsed - b.start) / b.dur) : 1;
          b.run(ease(raw));
          if (raw >= 1 && b.after && !b._done) { b._done = true; b.after(); }
        }
      }
      _rafId = window.requestAnimationFrame(tick);
    }
    _rafId = window.requestAnimationFrame(tick);
  }

  // playLanding: the settle-cascade. newIndices is the raw ceremony payload (index.html's stashed
  // range); grouping is review-pinned: absent-from-handles indices are skipped, isleSlot===null
  // (seed-hosted) gets the reduced beat, isleSlot!==null groups play the full beat per isle,
  // sequentially, Vera visiting in ascending slot order.
  function playLanding(handles, newIndices, clock, done) {
    clock = clock || Date.now; done = done || function () {};
    if (_active) cancel();
    newIndices = newIndices || [];

    var byIsleSlot = {}, seedGroup = [];
    for (var i = 0; i < newIndices.length; i++) {
      var hh = handles.houses[newIndices[i]];
      if (!hh) continue; // skipped index — never entered the scene at all
      if (hh.isleSlot === null || hh.isleSlot === undefined) { seedGroup.push(newIndices[i]); continue; }
      (byIsleSlot[hh.isleSlot] = byIsleSlot[hh.isleSlot] || []).push(newIndices[i]);
    }
    var isleSlots = [];
    for (var s in byIsleSlot) if (Object.prototype.hasOwnProperty.call(byIsleSlot, s)) isleSlots.push(Number(s));
    isleSlots.sort(function (a, b) { return a - b; }); // Vera visits in slot order
    seedGroup.sort(function (a, b) { return a - b; });

    if (!isleSlots.length && !seedGroup.length) { done(); return; } // nothing earned — no-op

    var beats = [];
    // the reduced beat: seed-hosted new houses, monolith rise only — not on Vera's itinerary
    for (var sg = 0; sg < seedGroup.length; sg++) {
      var shh = handles.houses[seedGroup[sg]];
      if (shh && shh.monoMesh) beats.push(beatMonolithRise(shh.monoMesh, sg * BLOOM_STAGGER_MS, BLOOM_MS));
    }

    var t = 0, veraFrom = handles.vera.home;
    for (var si = 0; si < isleSlots.length; si++) {
      var slot = isleSlots[si], isle = null, isleIdx = -1;
      for (var k = 0; k < handles.isles.length; k++) {
        if (handles.isles[k].slot === slot) { isle = handles.isles[k]; isleIdx = k; break; }
      }
      if (!isle) continue; // defensive — the grouping guarantees a match on a real payload

      var group = byIsleSlot[slot].slice().sort(function (a, b) { return a - b; }); // arrival order
      var arrival = isleArrivalPoint(isle, group, handles);
      beats.push(beatVeraTravel(handles.vera.group, veraFrom, midpointAbove(veraFrom, arrival), arrival, t, VERA_TRAVEL_MS));

      var bloomStart = t + VERA_TRAVEL_MS;
      for (var gi = 0; gi < group.length; gi++) {
        var ghh = handles.houses[group[gi]];
        var st = bloomStart + gi * BLOOM_STAGGER_MS;
        if (ghh.facetMesh) beats.push(beatFacetBloom(ghh.facetMesh, st, BLOOM_MS));
        if (ghh.monoMesh) beats.push(beatMonolithRise(ghh.monoMesh, st, BLOOM_MS));
      }
      var bloomTotal = (group.length - 1) * BLOOM_STAGGER_MS + BLOOM_MS;

      var tb = beatThreadDraw(handles.threadLines[isleIdx], bloomStart, bloomTotal);
      if (tb) beats.push(tb);

      var relightStart = bloomStart + bloomTotal;
      var rl = relightIsle(isle, handles, relightStart);
      beats = beats.concat(rl.beats);

      var shimmerStart = relightStart + rl.dur;
      var overlay = buildShimmerOverlay(isle, handles);
      var sb = beatShimmer(overlay, shimmerStart, SHIMMER_MS);
      if (sb) beats.push(sb);

      t = shimmerStart + (overlay.length ? SHIMMER_MS : 0);
      veraFrom = arrival;
    }

    var totalDur;
    if (isleSlots.length) {
      beats.push(beatVeraTravel(handles.vera.group, veraFrom, midpointAbove(veraFrom, handles.vera.home), handles.vera.home, t, VERA_TRAVEL_MS));
      totalDur = t + VERA_TRAVEL_MS;
    } else {
      totalDur = 0;
      for (var fb = 0; fb < beats.length; fb++) totalDur = Math.max(totalDur, beats[fb].start + beats[fb].dur);
    }

    _restoreHome = { group: handles.vera.group, home: handles.vera.home };
    runTimeline(beats, totalDur, clock, function () {
      handles.vera.group.position.copy(handles.vera.home); // playback ends restoring home EXACTLY
      _restoreHome = null;
      done();
    });
  }

  // playConfluence: the merge drift. The from_slot cluster (facets/rings/monoliths frozen at that
  // slot, now hosted on the elder toSlot isle) starts displaced by the rigid delta between its
  // ORIGINAL standalone bearing (WXLaw.bearing(fromSlot) at R_ORBIT) and where the elder isle's own
  // cluster offset actually placed it (elder center + OFF_RETIRED toward that same bearing), then
  // tweens that delta to zero as one unit. Vera visits the merged isle once, reusing the RELIGHT.
  function playConfluence(handles, fromSlot, toSlot, clock, done) {
    clock = clock || Date.now; done = done || function () {};
    if (_active) cancel();
    var WXLaw = window.WXLaw;
    var elderIsle = null;
    for (var i = 0; i < handles.isles.length; i++) {
      if (handles.isles[i].slot === toSlot) { elderIsle = handles.isles[i]; break; }
    }
    if (!elderIsle || !WXLaw) { done(); return; } // nothing to merge into — defensive no-op

    var groupHouses = [];
    for (var k in handles.houses) {
      if (!Object.prototype.hasOwnProperty.call(handles.houses, k)) continue;
      var hh = handles.houses[k];
      if (hh.isleSlot === toSlot && hh.clusterSlot === fromSlot) groupHouses.push(Number(k));
    }

    var fromB = WXLaw.bearing(fromSlot);
    var startWorld = { x: Math.cos(fromB) * WXLaw.R_ORBIT, z: Math.sin(fromB) * WXLaw.R_ORBIT };
    var elderOffsetWorld = {
      x: elderIsle.center.x + Math.cos(fromB) * WXLaw.OFF_RETIRED,
      z: elderIsle.center.z + Math.sin(fromB) * WXLaw.OFF_RETIRED,
    };
    var delta = { x: startWorld.x - elderOffsetWorld.x, z: startWorld.z - elderOffsetWorld.z };

    var members = [];
    for (var g = 0; g < groupHouses.length; g++) {
      var ghh = handles.houses[groupHouses[g]];
      var meshes = [ghh.facetMesh, ghh.ringMesh, ghh.monoMesh];
      for (var m = 0; m < meshes.length; m++) {
        if (meshes[m]) members.push({ mesh: meshes[m], finalX: meshes[m].position.x, finalZ: meshes[m].position.z });
      }
    }
    for (var mi = 0; mi < members.length; mi++) { // the rigid start, applied synchronously
      members[mi].mesh.position.x = members[mi].finalX + delta.x;
      members[mi].mesh.position.z = members[mi].finalZ + delta.z;
    }

    var beats = [{
      start: 0, dur: DRIFT_MS,
      run: function (e) {
        for (var i2 = 0; i2 < members.length; i2++) {
          members[i2].mesh.position.x = members[i2].finalX + delta.x * (1 - e);
          members[i2].mesh.position.z = members[i2].finalZ + delta.z * (1 - e);
        }
      },
    }];

    var home = handles.vera.home;
    var arrival = isleArrivalPoint(elderIsle, elderIsle.thread || [], handles);
    beats.push(beatVeraTravel(handles.vera.group, home, midpointAbove(home, arrival), arrival, 0, VERA_TRAVEL_MS));

    var relightStart = Math.max(DRIFT_MS, VERA_TRAVEL_MS);
    var rl = relightIsle(elderIsle, handles, relightStart);
    beats = beats.concat(rl.beats);

    var returnStart = relightStart + rl.dur;
    beats.push(beatVeraTravel(handles.vera.group, arrival, midpointAbove(arrival, home), home, returnStart, VERA_TRAVEL_MS));

    var totalDur = returnStart + VERA_TRAVEL_MS;
    _restoreHome = { group: handles.vera.group, home: handles.vera.home };
    runTimeline(beats, totalDur, clock, function () {
      handles.vera.group.position.copy(handles.vera.home); // playback ends restoring home EXACTLY
      _restoreHome = null;
      done();
    });
  }

  return { playLanding: playLanding, playConfluence: playConfluence, active: active, cancel: cancel };
})();
