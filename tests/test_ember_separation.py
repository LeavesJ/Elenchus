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

TERRAIN = Path("src/retnovation/web/static/terrain3d.js")

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
