"""Static source guards over the pure placement law (Spec-2 §5): wx_law.js is the determinism
boundary — no Math.random, no THREE, no DOM; mulberry32 is the only randomness; the lattice and
law constants exist with their pinned values. (Behavioral determinism — double-run identity — is
the Phase-C browser smoke's tooth, per the spec's §13 split.)"""

import re
from pathlib import Path

SRC = Path("src/retnovation/web/static/wx_law.js")


def _js_fn(src: str, name: str) -> str:
    """Extract a function body using brace-depth counting.
    Handles mixed indentation and complex nesting reliably."""
    i = src.index("function " + name)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        depth += src[k] == "{"
        depth -= src[k] == "}"
        if depth == 0:
            return src[i : k + 1]
    raise AssertionError(f"unterminated function {name}")


def _src() -> str:
    return SRC.read_text()


def test_wx_law_exists_and_is_pure():
    s = _src()
    assert "Math.random" not in s  # the ban has no exceptions in THIS file
    assert "THREE" not in s and "document." not in s and "window.addEventListener" not in s


def test_wx_law_declares_the_pinned_constants():
    s = _src()
    for token in [
        "K = 24",
        "R_ORBIT = 46",
        "R_ROCK = 13",
        "R_DOME_MAX = 10",
        "QUAY_W = 3",
        "137.50776",
        "R0 = 1.5",
        "STACK_DR = 0.55",
        "STACK_DH = 1.1",
    ]:
        assert token in s, token


def test_wx_law_has_mulberry32_and_layout():
    s = _src()
    assert "function mulberry32" in s and "function layout" in s and "function bearing" in s


def test_wx_law_carries_no_banned_copy_tokens():
    # the law file ships no learner-facing strings at all — belt-and-suspenders
    s = _src().lower()
    for tok in ["solved", "mastered", "correct", "streak", "interleave", "innovation"]:
        assert tok not in s, tok


# ---- Phase B T2: the archipelago scene scaffold (dusk sky, dock, camera, contract) -------------


def test_terrain3d_loads_wx_law_and_keeps_the_contract():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    assert "WXLaw.layout" in s and "houseScreenXY" in s and "teardown" in s
    assert "litHouses" in s and "ptrMoved" in s


def test_index_html_loads_wx_law_before_terrain3d():
    h = Path("src/retnovation/web/static/index.html").read_text()
    assert h.index("wx_law.js") < h.index("terrain3d.js")


def test_ambient_randomness_is_marked_in_terrain3d():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    # every Math.random use sits under an explicit ambient-FX marker within 3 lines above it
    # (one marker per use, not per block — review-pinned)
    lines = s.split("\n")
    for n, ln in enumerate(lines):
        if "Math.random" in ln:
            ctx = "\n".join(lines[max(0, n - 3) : n + 1])
            assert "ambient FX" in ctx, f"unmarked Math.random at line {n + 1}"


def test_new_static_copy_carries_no_banned_tokens():
    combined = (
        Path("src/retnovation/web/static/terrain3d.js").read_text()
        + Path("src/retnovation/web/static/index.html").read_text()
    ).lower()
    for tok in ["solved", "mastered", "streak", "interleave", "mix your domains", "innovation"]:
        assert tok not in combined, tok


# ---- Phase B T3: the isles — facets, monoliths, terraces, thread, ghost -------------------------


def test_terrain3d_builds_isle_structures():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    for token in ["clickableMonoliths", "houseIndex", "thread", "ghost", "rings"]:
        assert token in s, token


def test_thread_is_per_isle_never_cross_isle():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    # the thread builder must iterate isle.thread, never a global houses list
    assert "isle.thread" in s or "isles[k].thread" in s


# ---- Phase B T4: interaction — monolith clicks, isle close-orbit, pick priority -----------------


def test_interaction_pick_priority_and_close_orbit():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    assert "pick priority: monolith" in s
    assert "closeOrbit" in s or "close-orbit" in s
    # the renderer performs NO network I/O — a stronger invariant than banning a path literal
    # (review-corrected: the old `"/memory" not in s` guard collided with honest comments)
    assert "fetch(" not in s and "XMLHttpRequest" not in s


# ---- Phase B T5: wiring, craft polish, whole-phase gate -----------------------------------------


def test_index_passes_full_payload_through():
    h = Path("src/retnovation/web/static/index.html").read_text()
    assert "vessels" in h and "confluence" in h  # pass-through wired for Phase C


def test_no_per_isle_idle_motion():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    # the invariant, not the whitespace (review-corrected): exactly one sway assignment,
    # on the world group; any reset must go through the same single assignment
    assert len(re.findall(r"world\.position\.y\s*[+\-]?=", s)) == 1


def test_patina_stays_in_the_dusk_band():
    # §8's patina predicate gets static teeth (review SHOULD-FIX): dim/structural material
    # colors are drawn from a named DUSK_BAND list, and no grey-family hex (equal RGB
    # channels) appears in it — dim is calm patina, never desaturated failure-grey.
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    m = re.search(r"DUSK_BAND\s*=\s*\[(.*?)\]", s, re.S)
    assert m, "terrain3d.js must declare its structural palette as DUSK_BAND = [...]"
    for hex6 in re.findall(r"0x([0-9a-fA-F]{6})", m.group(1)):
        r, g, b = hex6[0:2], hex6[2:4], hex6[4:6]
        assert not (r == g == b), f"grey-family color 0x{hex6} in DUSK_BAND"


# ---- Phase C T1: vessels at the jetty — count-only, deterministic moorings -----


def test_vessels_render_from_count_only_and_stay_inert():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    assert "VESSEL_CAP = 20" in s and "vesselCount" in s
    body = _js_fn(s, "buildVessels")
    assert "userData" not in body and "clickableMonoliths" not in body
    assert "houses" not in body and "terrain" not in body  # count-only input


# ---- Phase C T2: Vera, Keeper of the Lamp — constant idle transform + _handles plumbing --------


def test_vera_idle_transform_is_constant():
    s = Path("src/retnovation/web/static/terrain3d.js").read_text()
    assert "vera" in s and "_handles" in s and "OFF_RETIRED" in Path(
        "src/retnovation/web/static/wx_law.js").read_text().split("return {")[-1]
    loop = _js_fn(s, "loop")
    # the loop never writes ANY vera transform channel (review-strengthened; the ceremony
    # module owns motion)
    import re
    assert not re.search(r"vera\w*\s*\.\s*(?:group\s*\.\s*)?(?:position|rotation|scale|quaternion)", loop)
    # the breathe is the NAMED sprite-material write, present in the loop
    assert "veraBreathe" in loop


# ---- Phase C T3: the ceremonies — settle-cascade + confluence, in the named slot ----------------


def test_ceremonies_module_exists_and_owns_all_structural_motion():
    c = Path("src/retnovation/web/static/ceremonies.js").read_text()
    assert "playLanding" in c and "playConfluence" in c and "active" in c
    assert "Math.random" not in c  # ceremonies are deterministic
    assert ".stack" not in c  # cascade parity: no rhythm branches
    # parity holds in terrain3d's trigger/hidden-state section too (review-extended):
    assert ".stack" not in Path("src/retnovation/web/static/terrain3d.js").read_text()
    h = Path("src/retnovation/web/static/index.html").read_text()
    assert "__preSittingHouses" in h and "ceremonies.js" in h
    # single-fire: the stash is deleted at the close render
    assert "delete window.__preSittingHouses" in h


def test_arrival_renders_never_carry_a_ceremony():
    h = Path("src/retnovation/web/static/index.html").read_text()
    import re

    rh = re.search(r"function renderHomebase\((.*?)\n\}", h, re.S).group(0)
    assert "ceremony" not in rh  # load/resume/frontdoor renders are always still
