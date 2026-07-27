"""Earned-vs-unearned separation, and the ember's form (Spec-3 §5b/§5c, P2a).

The world is a mirror of judgment, so what it spends light on IS its statement about what
matters. Measured post-P0: a monolith holding ONE memory reaches luminance 0.527; the ghost bud
marking NOTHING reaches 0.473 at its pulse peak — 1.102:1, against a required 3:1. And P0's own
bloom retune (threshold 0.62 -> 0.46, so a single memory would finally glow) pulled the ghost
over the line as well, so the emptiness marker blooms and, because its pulse crosses the
threshold mid-cycle, flickers. The world was animating its emptiness and leaving its rewards
static. These guards are the arithmetic, pinned."""

import re
from pathlib import Path

# _js_fn / _strip_comments are imported, never re-implemented: a second copy of the
# comment-stripper is a second place for a guard to silently stop guarding. The bare module name
# (not `tests.`) is what resolves here — `tests/` is not a package (no __init__.py), and pytest's
# default prepend import mode puts the conftest's own directory on sys.path.
from test_renderer_pipeline_static import _js_fn, _strip_comments

TERRAIN = Path("src/retnovation/web/static/terrain3d.js")
CEREMONIES = Path("src/retnovation/web/static/ceremonies.js")

# --- the render pipeline, replicated exactly enough to assert on (see test_renderer_pipeline_static
# for why: three r128 has no ColorManagement, so authored hexes are decoded by srgb() at build
# time, then ACES-tone-mapped at toneMappingExposure before reaching the screen).
_IN = [[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]]
_OUT = [[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]]


def _mul(m, v):
    return [sum(m[r][c] * v[c] for c in range(3)) for r in range(3)]


def _rrt(v):
    return [
        (x * (x + 0.0245786) - 0.000090537) / (x * (0.983729 * x + 0.432951) + 0.238081) for x in v
    ]


def _aces(c, exposure):
    c = [x * (exposure / 0.6) for x in c]
    c = _mul(_IN, c)
    c = _rrt(c)
    return [min(max(x, 0.0), 1.0) for x in _mul(_OUT, c)]


def _eotf(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _linear(hex6):
    return [_eotf(int(hex6[i : i + 2], 16) / 255) for i in (0, 2, 4)]


def _lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _bloom_luma(c):
    # UnrealBloomPass's prefilter metric, on the tone-mapped buffer.
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _src():
    return TERRAIN.read_text()


def _num(name, src=None):
    """Read a pinned numeric constant out of the source so the guard tracks the real value."""
    s = src if src is not None else _src()
    m = re.search(rf"\b{name}\s*=\s*([0-9.]+)", s)
    assert m, f"{name} must be a named constant in terrain3d.js"
    return float(m.group(1))


def _band(index):
    m = re.search(r"DUSK_BAND\s*=\s*\[(.*?)\]", _src(), re.S)
    hexes = re.findall(r"0x([0-9a-fA-F]{6})", m.group(1))
    return hexes[index]


def _bloom_threshold():
    m = re.search(r"UnrealBloomPass\(.*?,\s*[0-9.]+\s*,\s*[0-9.]+\s*,\s*([0-9.]+)\s*\)", _src())
    assert m, "the bloom threshold must be readable from the UnrealBloomPass construction"
    return float(m.group(1))


def _exposure():
    return _num("toneMappingExposure")


def test_the_unearned_marker_never_blooms():
    # The ghost bud marks NOTHING EARNED. Light is this world's reward vocabulary; spending bloom
    # on the placeholder spends the vocabulary on absence. Checked at the pulse PEAK, because a
    # marker that blooms only part of its cycle flickers, which is worse than steady.
    peak = _num("GHOST_OPACITY") + _num("GHOST_PULSE_AMP")
    tm = _aces([x * peak for x in _linear(_band(18))], _exposure())
    assert _bloom_luma(tm) < _bloom_threshold(), (
        f"the ghost bud blooms at its pulse peak (luma {_bloom_luma(tm):.3f} >= "
        f"threshold {_bloom_threshold():.3f}) — the world would be blooming its own emptiness"
    )


def test_earned_outshines_unearned_by_at_least_three_to_one():
    # The invariant (§5c). A single convergence — the most common memory anyone holds, and the
    # FIRST on every isle — must be unmistakably brighter than the marker for nothing at all.
    peak = _num("GHOST_OPACITY") + _num("GHOST_PULSE_AMP")
    ghost = _aces([x * peak for x in _linear(_band(18))], _exposure())
    m = re.search(r"emissiveIntensity:\s*([0-9.]+)\s*\+\s*([0-9.]+)\s*\*\s*bucket", _src())
    assert m, "the monolith's emissive ramp must stay readable as `base + step * bucket`"
    bucket1 = float(m.group(1)) + float(m.group(2)) * 1
    mono = _aces([x * bucket1 for x in _linear(_band(9))], _exposure())
    ratio = (max(_lum(mono), _lum(ghost)) + 0.05) / (min(_lum(mono), _lum(ghost)) + 0.05)
    assert ratio >= 3.0, (
        f"earned-vs-unearned is {ratio:.3f}:1, below the 3:1 floor — one memory must not read "
        f"as the same thing as no memory"
    )


def test_the_ember_is_a_group_whose_core_is_what_ceremonies_animate():
    # ceremonies.js calls mesh.material.clone() and mutates emissiveIntensity in place. A Group
    # has no .material, so handing it the group would throw at the first landing. The core mesh
    # is also the RIGHT thing to animate: the cascade should kindle the flame, not inflate stone.
    s = _strip_comments(_src())
    assert "function emberFor(" in s, "the ember must be built through one seam"
    body = _js_fn(s, "emberFor")
    assert "THREE.Group" in body, "the ember is a group: plinth + ribs + core"
    assert re.search(r"return\s*\{[^}]*\bcore\b", body), (
        "emberFor must return its core mesh separately — that is what monoMesh binds to"
    )
    assert "monoMesh: " in s or "monoMesh =" in s


def test_the_ember_group_is_the_pick_target_and_carries_the_house_index():
    # The raycast walks up parents for userData.houseIndex, so stamping it on the GROUP makes
    # every part of the ember clickable — stone included, not just the bright core.
    s = _strip_comments(_src())
    assert re.search(r"\.userData\.houseIndex\s*=", s)
    assert "clickableMonoliths.push(" in s


def test_the_ember_core_is_the_only_emissive_part():
    # Structure is unlit; the earning is the light. If the plinth or ribs were emissive the
    # object would read as a glowing lump rather than a vessel holding something.
    s = _strip_comments(_src())
    body = _js_fn(s, "emberFor")
    assert body.count("emissive:") == 1, (
        "exactly one part of the ember may be emissive — the core. Lighting the stone destroys "
        "the read of a container with something inside it"
    )


def test_the_ember_stands_on_the_surface_instead_of_floating_half_its_height_above_it():
    # A BoxGeometry mesh is centred on its own origin, which is the only reason both build sites
    # used to position at `top + height/2`. The ember GROUP's origin is its BASE — every child
    # sits at a positive local y — so carrying that arithmetic over launches every ember into
    # the air. Both sites must place the group ON the surface it stands on.
    s = _strip_comments(_src())
    assert re.search(r"\.group\.position\.set\(\s*wx\s*,\s*facetTopY\s*,\s*wz\s*\)", s), (
        "the isle ember's group must sit AT facetTopY — its origin is its base, not its centre"
    )
    assert re.search(r"\.group\.position\.set\(\s*sx\s*,\s*SEED_TOP_Y\s*,\s*sz\s*\)", s), (
        "the seed ember's group must sit AT SEED_TOP_Y (scaling the group keeps the base put)"
    )
    assert re.search(r"\.group\.scale\.setScalar\(\s*SEED_SCALE\s*\)", s), (
        "SEED_SCALE must ride the whole ember — scaling only the core would shrink the flame and "
        "leave the stone full size"
    )
    assert "monoH" not in s, (
        "the retired box height must be gone from both build sites — a surviving `+ monoH / 2` "
        "is exactly the half-height float this guard exists to catch"
    )


def test_the_arrival_thread_attaches_to_the_embers_real_tip():
    # tipByHouse feeds the per-isle arrival thread — the line that says these memories belong to
    # one another. It used to record the BOX's top (facetTopY + monoH, 2.6 units up at bucket 2);
    # the ember's top is under 0.9, so leaving it alone strands every thread ~1.8 units above the
    # embers it joins. The replacement is derived from the SAME constants emberFor builds with,
    # never a copied literal, so the thread cannot drift when the geometry moves.
    s = _strip_comments(_src())
    assert "function emberTipY(" in s, "the ember's tip must be one named, derived seam"
    tip = _js_fn(s, "emberTipY")
    assert "EMBER_CORE_Y" in tip and "EMBER_CORE_R" in tip and "bucket" in tip, (
        "emberTipY must derive from the named core geometry, not restate a literal"
    )
    body = _js_fn(s, "emberFor")
    assert "EMBER_CORE_Y" in body and "EMBER_CORE_R" in body, (
        "emberFor must BUILD from the same constants emberTipY reads — two copies of 0.56 drift "
        "apart the first time anyone resizes the core"
    )
    m = re.search(r"tipByHouse\[[^\]]+\]\s*=\s*\{[^}]*y:\s*([^,}]+)", s)
    assert m and "emberTipY(" in m.group(1), (
        f"the thread's attach point must be emberTipY(bucket) above the facet top, got "
        f"{m.group(1).strip() if m else 'no tipByHouse assignment'}"
    )
    # The arithmetic, not merely the names. Bucket 3 is the wire's maximum (types._vitality_bucket),
    # so this is the tallest ember that can exist. Measured against the vendored r128, the built
    # group's bounding box tops out at exactly this value — IcosahedronGeometry(r, 0) is a
    # polyhedron, so its highest VERTEX is EMBER_CORE_POLE * r above the centre, never r.
    tip3 = _num("EMBER_CORE_Y", s) + _num("EMBER_CORE_POLE", s) * (
        _num("EMBER_CORE_R", s) + _num("EMBER_CORE_R_STEP", s) * 3
    )
    assert 0.56 < tip3 < 1.0, (
        f"the tallest ember's tip derives to {tip3:.3f}, outside its own body — the ribs arc from "
        f"0.340 to 0.675 and the whole object stands under a unit tall. The retired box reached "
        f"3.1 at this bucket, and a thread still pinned up there floats over the memories it joins"
    )


def test_the_confluence_drift_moves_the_ember_body_never_the_nested_core():
    # playConfluence slides a merging isle's objects in from their old bearing by adding a WORLD
    # delta to each mesh's `.position`. facetMesh and ringMesh are direct children of `world`, so
    # that is right for them. monoMesh is NOT: it is the core nested inside the ember group, and a
    # nested mesh's `.position` is a local offset — driving it directly slides the lit core
    # sideways out of its own plinth and ribs for the whole drift, then restores it. The final
    # state is correct and nothing throws, so this defect is invisible to every runtime check and
    # to the suite; a static guard is the only thing that can hold it.
    c = _strip_comments(CEREMONIES.read_text())
    body = _js_fn(c, "playConfluence")
    m = re.search(r"var\s+meshes\s*=\s*\[([^\]]*)\]", body)
    assert m, "playConfluence must still build its drift list as one readable `meshes` array"
    drift = m.group(1)
    assert "monoMesh" not in drift, (
        "the confluence drift list must not carry monoMesh — it is the core nested inside the "
        "ember group, so a world-space delta applied to it slides the flame off its own stone. "
        f"Drift the group (monoMesh.parent) instead. Got: [{drift.strip()}]"
    )
    assert re.search(r"\.parent\b", body), (
        "the drift must reach the ember GROUP through monoMesh.parent — the child of `world` that "
        "shares a coordinate space with facetMesh and ringMesh"
    )


def test_vera_arrives_over_the_embers_world_height_not_its_local_offset():
    # ceremonies.js:isleArrivalPoint puts Vera "just above the tallest monolith tip she's
    # visiting", on BOTH ceremony paths. `.position` is always LOCAL, and monoMesh is now the
    # core nested inside the ember group, so it reads 0.56 instead of the isle's real 10-17 —
    # she would descend to sea level during the coming-home cascade, and nothing would throw to
    # say so. World space is a requirement of the nesting, not a preference.
    c = _strip_comments(CEREMONIES.read_text())
    body = _js_fn(c, "isleArrivalPoint")
    assert "getWorldPosition(" in body, (
        "isleArrivalPoint must read the mesh's WORLD position — a nested core's .position.y is "
        "a local offset, and reading it silently drops Vera to sea level"
    )
    assert not re.search(r"monoMesh\.position\.y", body), (
        "no local .position.y read may survive in isleArrivalPoint"
    )
    assert re.search(r"var\s+_arrivalScratch\s*=\s*null", c), (
        "the world-position scratch vector must be module-scope and lazily allocated (THREE may "
        "be absent entirely — this module degrades rather than throwing at load)"
    )
    loop = body[body.index("for (") :]
    assert "new " not in loop, (
        "isleArrivalPoint runs per house on every ceremony — no allocation inside its loop"
    )
