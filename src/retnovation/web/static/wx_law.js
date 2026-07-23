/* WXLaw — the pure placement law for the floating-lands archipelago (Spec-2 §3/§5).
 *
 * DETERMINISM BOUNDARY: everything here is a pure function of the frozen wire payload plus the
 * pinned constants below. The only randomness is mulberry32 seeded by the GLOBAL house ordinal —
 * identical every load; unseeded randomness is banned in this file (pytest static guard).
 * No Three.js, no DOM: layout() returns plain data; terrain3d.js turns it into meshes.
 *
 * Houses<->terrain are NOT 1:1 (Phase-A T3 review): h.region names the HOSTING row (an index into
 * the filtered terrain list — an isle OR a housed seed rock); h.slot is the frozen
 * slot-at-arrival and keys the SUB-LAYOUT — post-confluence it may be a retired slot no terrain
 * row carries. Placement reads h.slot; hosting reads h.region.
 */
window.WXLaw = (function () {
  "use strict";

  var K = 24;                     // bearing lattice (Spec-2 §3); extension appends half-steps
  var R_ORBIT = 46;               // isle orbit radius around the dock
  var R_SEED = R_ORBIT * 1.10;    // bare seed rocks, below the innermost reserved air shell
  var R_ROCK = 13;                // isle base-rock radius
  var R_DOME_MAX = 10;            // facet dome ceiling radius
  var QUAY_W = 3;                 // the reserved quay annulus width: R_DOME_MAX..R_ROCK facet-free
  var OFF_RETIRED = R_DOME_MAX * 0.25; // retired-cluster offset; subtracted from that cluster's budget
  var SHELLS = [1.18, 1.26, 1.34]; // reserved air-shell radius factors (kept empty by the scene)
  var GOLDEN = 137.50776 * Math.PI / 180;
  var R0 = 1.5;                   // Vogel radial step scale -> 21 spreads per terrace (D-S2-3 n_cap)
  var STACK_DR = 0.55;            // stack: minimal radial advance
  var STACK_DH = 1.1;             // stack: height increment per consecutive stack in a run
  var JITTER_AZ = 6 * Math.PI / 180;
  var JITTER_R = 0.04;
  var TERRACE_H = 2.4;            // vertical lift per terrace

  function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function bearing(slot) {
    if (slot < K) return (2 * Math.PI * slot) / K;
    // K->K+8 extension: half-step insertion — existing bearings never move (Spec-2 §3).
    // Defined for slots 24-31; beyond 31 is unreachable (the server fails loud at exhaustion)
    // and slot 48 would alias — the comment stands so nobody "extends" this casually.
    return (2 * Math.PI * ((slot - K) + 0.5)) / K;
  }

  // Per-(cluster, terrace) spread bookkeeping: radius = R0 * sqrt(spreads-this-terrace).
  function layout(payload) {
    var terrain = (payload && payload.terrain) || (payload && payload.regions) || [];
    var houses = (payload && payload.houses) || [];
    var isles = [], seeds = [], skipped = 0, seedHoused = 0;
    var isleByRegion = {};   // filtered-terrain index -> isle object
    var seedByRegion = {};   // filtered-terrain index -> seed object (housed seed rocks are real)

    for (var t = 0; t < terrain.length; t++) {
      var row = terrain[t];
      if (!row || typeof row.slot !== "number") { continue; } // exhaustion edge: unslotted row
      var b = bearing(row.slot);
      if (row.render === "rendered") {
        var isle = {
          slot: row.slot,
          x: Math.cos(b) * R_ORBIT, z: Math.sin(b) * R_ORBIT,
          elevation: row.elevation || 1, vitality: row.vitality || 0,
          clusters: [], thread: [], ghost: null,
        };
        isleByRegion[t] = isle; isles.push(isle);
      } else {
        var seed = { slot: row.slot, x: Math.cos(b) * R_SEED, z: Math.sin(b) * R_SEED,
                     monoliths: [] };
        seedByRegion[t] = seed; seeds.push(seed);
      }
    }

    // clusters keyed by (hosting isle, house slot). Each cluster carries a RADIAL BUDGET _capR:
    // its offset is subtracted so no facet can ever enter the quay annulus (review MUST-FIX —
    // the keep-out holds by budget, not by the elder-only trigger).
    function clusterOf(isle, slot) {
      for (var c = 0; c < isle.clusters.length; c++)
        if (isle.clusters[c].slot === slot) return isle.clusters[c];
      var off = { x: 0, z: 0 }, capR = R_DOME_MAX - QUAY_W;
      if (slot !== isle.slot) {
        // a retired slot's sub-cluster: rigid offset toward its ORIGINAL bearing (Spec-2 §5 —
        // the younger cluster translated to the elder isle as a unit)
        var ob = bearing(slot);
        off = { x: Math.cos(ob) * OFF_RETIRED, z: Math.sin(ob) * OFF_RETIRED };
        capR = capR - OFF_RETIRED;
      }
      var cl = { slot: slot, offX: off.x, offZ: off.z, facets: [], _j: 0, _terrace: 0,
                 _spreads: [0], _runH: 0, _lastR: 0, _capR: capR };
      isle.clusters.push(cl);
      return cl;
    }

    var prevSlot = null;
    for (var i = 0; i < houses.length; i++) {
      var h = houses[i];
      var valid = h && typeof h.slot === "number" && typeof h.region === "number";
      if (valid && seedByRegion[h.region]) {
        // a housed SEED region (below the region guard but earned): its convergences render as
        // small clickable monoliths on the seed rock — every convergence stays clickable (Spec-1)
        seedByRegion[h.region].monoliths.push(i);
        seedHoused++; prevSlot = h.slot; continue;
      }
      if (!valid || !isleByRegion[h.region]) {
        skipped++; prevSlot = (h && typeof h.slot === "number") ? h.slot : null; continue;
      }
      var isle2 = isleByRegion[h.region];
      var cl2 = clusterOf(isle2, h.slot);
      var rng = mulberry32(i);
      // _j > 0 is the _lastR-defined guard; provably equivalent to the spec's repeated-slot rule on
      // reachable payloads (same slot => same cluster) — do not "fix" it into a deviation.
      var stack = prevSlot !== null && prevSlot === h.slot && cl2._j > 0;
      var terrace = cl2._terrace;
      var r, rings = 0;
      if (stack) {
        r = cl2._lastR + STACK_DR;
        rings = 1;
        cl2._runH += STACK_DH;
        if (r > cl2._capR) { // a stack on a radially-full terrace terraces up; the rolled facet
          cl2._terrace++; terrace = cl2._terrace; cl2._spreads[terrace] = 0;
          r = 0; rings = 0; cl2._runH = 0;   // GROUNDS the new terrace (review-pinned law)
        }
      } else {
        cl2._runH = 0; // a spread ends the stack run
        var nextSpread = (cl2._spreads[terrace] || 0) + 1;
        r = R0 * Math.sqrt(nextSpread);
        if (r > cl2._capR) { // radial trigger: open the next terrace (Spec-2 §5)
          cl2._terrace++; terrace = cl2._terrace;
          nextSpread = 1; r = R0;
        }
        cl2._spreads[terrace] = nextSpread;
      }
      r = r * (1 + (rng() * 2 - 1) * JITTER_R);
      cl2._lastR = r;
      var az = cl2._j * GOLDEN + (rng() * 2 - 1) * JITTER_AZ;
      cl2.facets.push({
        houseIndex: i, bucket: (h.bucket == null ? 0 : h.bucket),
        terrace: terrace, j: cl2._j,
        x: cl2.offX + Math.cos(az) * r, z: cl2.offZ + Math.sin(az) * r,
        y: terrace * TERRACE_H + cl2._runH,
        r: r, sides: 5 + Math.floor(rng() * 3), rot: rng() * Math.PI * 2,
        stack: stack, rings: rings,
      });
      cl2._j++;
      isle2.thread.push(i);
      prevSlot = h.slot;
    }

    // the ghost invitation: exactly one per rendered isle, at the ELDER cluster's next-SPREAD
    // position (the outward convention — claims nothing about the actual next arrival)
    for (var g = 0; g < isles.length; g++) {
      var gi = isles[g], elder = null;
      for (var c2 = 0; c2 < gi.clusters.length; c2++)
        if (gi.clusters[c2].slot === gi.slot) elder = gi.clusters[c2];
      var cap = elder ? elder._capR : (R_DOME_MAX - QUAY_W);
      var jNext = elder ? elder._j : 0;
      var tNext = elder ? elder._terrace : 0;
      var sNext = elder ? ((elder._spreads[tNext] || 0) + 1) : 1;
      var rNext = R0 * Math.sqrt(sNext);
      if (rNext > cap) { tNext++; rNext = R0; }
      gi.ghost = { x: Math.cos(jNext * GOLDEN) * rNext, z: Math.sin(jNext * GOLDEN) * rNext,
                   y: tNext * TERRACE_H };
    }
    return { isles: isles, seeds: seeds, skipped: skipped, seedHoused: seedHoused };
  }

  return { K: K, R_ORBIT: R_ORBIT, R_SEED: R_SEED, R_ROCK: R_ROCK, R_DOME_MAX: R_DOME_MAX,
           QUAY_W: QUAY_W, SHELLS: SHELLS, mulberry32: mulberry32, bearing: bearing,
           layout: layout };
})();
