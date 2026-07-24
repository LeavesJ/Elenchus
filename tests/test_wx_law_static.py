"""Static source guards over the pure placement law (Spec-2 §5): wx_law.js is the determinism
boundary — no Math.random, no THREE, no DOM; mulberry32 is the only randomness; the lattice and
law constants exist with their pinned values. (Behavioral determinism — double-run identity — is
the Phase-C browser smoke's tooth, per the spec's §13 split.)"""
import re
from pathlib import Path

SRC = Path("src/retnovation/web/static/wx_law.js")


def _src() -> str:
    return SRC.read_text()


def test_wx_law_exists_and_is_pure():
    s = _src()
    assert "Math.random" not in s  # the ban has no exceptions in THIS file
    assert "THREE" not in s and "document." not in s and "window.addEventListener" not in s


def test_wx_law_declares_the_pinned_constants():
    s = _src()
    for token in ["K = 24", "R_ORBIT = 46", "R_ROCK = 13", "R_DOME_MAX = 10", "QUAY_W = 3",
                  "137.50776", "R0 = 1.5", "STACK_DR = 0.55", "STACK_DH = 1.1"]:
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
            ctx = "\n".join(lines[max(0, n - 3):n + 1])
            assert "ambient FX" in ctx, f"unmarked Math.random at line {n + 1}"


def test_new_static_copy_carries_no_banned_tokens():
    combined = (Path("src/retnovation/web/static/terrain3d.js").read_text()
                + Path("src/retnovation/web/static/index.html").read_text()).lower()
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
