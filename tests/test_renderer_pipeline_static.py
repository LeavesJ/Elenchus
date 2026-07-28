"""Static source guards over the render pipeline (Spec-3 §3, P0).

terrain3d.js runs on vendored three r128, which has no ColorManagement: an authored sRGB hex
handed to a material or a light is consumed as a LINEAR radiance value and renders far too
bright, hardest at the dark end. Every structural colour must therefore pass through the one
`srgb()` conversion seam. These guards are textual by necessity (there is no JS test runner in
this repo); the browser smoke supplies the behavioural teeth."""

import re
from pathlib import Path

TERRAIN = Path("src/elenchus/web/static/terrain3d.js")
CEREMONIES = Path("src/elenchus/web/static/ceremonies.js")
SHELL = Path("src/elenchus/web/static/index.html")


def _js_fn(src: str, name: str) -> str:
    """Extract a function body by brace-depth counting — indentation-agnostic, so a guard
    cannot silently pass or fail on whitespace. Mirrors the helper in test_wx_law_static.py."""
    i = src.index("function " + name)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        depth += src[k] == "{"
        depth -= src[k] == "}"
        if depth == 0:
            return src[i : k + 1]
    raise AssertionError(f"unterminated function {name}")


def _strip_comments(src: str) -> str:
    """Strip JS `//` line comments and `/* ... */` block comments before a guard asserts
    against the text.

    A guard that pattern-matches raw source (comments included) is not actually testing that a
    fix is live: commenting out the fix — `/* convertSRGBToLinear */` or `// scene.fog = ...` —
    leaves every token the guard looks for sitting right there in the text, so the guard is
    "satisfied" by code that no longer runs. A guard a commented-out fix can still pass is not a
    guard. Every assertion in this file must therefore run against comment-stripped text, never
    the raw file contents — strip at the point of assertion, not on disk.

    Block comments are stripped first (so a `//` that happens to sit inside a `/* ... */` block
    is not treated as a second, independent delimiter that truncates the strip early); line
    comments are stripped second.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def test_srgb_conversion_seam_exists():
    s = _strip_comments(TERRAIN.read_text())
    assert "function srgb(" in s, "terrain3d.js must declare the one sRGB->linear conversion seam"
    body = _js_fn(s, "srgb")
    # Statement-form, not identifier-presence: convertSRGBToLinear() must be the thing that gets
    # RETURNED. A bare `"convertSRGBToLinear" in body` check is satisfied by the identifier
    # surviving anywhere in the function — including a dropped, never-invoked reference — while
    # the actual return value stays unconverted.
    assert re.search(r"return\s+new THREE\.Color\([^)]*\)\.convertSRGBToLinear\(\)\s*;", body), (
        "srgb() must RETURN new THREE.Color(n).convertSRGBToLinear() — r128 has no "
        "ColorManagement, and a bare mention of convertSRGBToLinear that isn't what's actually "
        "returned (dead code, a comment, a dropped chain) must fail this guard"
    )


def test_no_raw_hex_reaches_a_material_or_light():
    # Every colour-consuming site takes srgb(...), never a bare DUSK_BAND[i] or 0x literal.
    # Canvas PAINT (cssHex/rgbaHex) is deliberately excluded: those are 2D-canvas strings whose
    # decode is handled at the texture level (see test_canvas_textures_declare_srgb_encoding).
    #
    # This is a NEGATIVE guard (it asserts absence), so comment-stripping cuts the other way from
    # every other guard in this file: an unstripped scan would false-FAIL on a merely-discussed
    # or commented-out example like `// color: DUSK_BAND[5]`, even though nothing dead reaches a
    # material. We still strip, deliberately: stripping first means only LIVE offenders are ever
    # counted, including one exposed by commenting out just an srgb(...) wrapper while leaving
    # the raw value it wrapped live and reachable — `color: /*srgb(*/DUSK_BAND[5]/*)*/ ` becomes
    # the very much live `color: DUSK_BAND[5]` once stripped, and must still be caught.
    s = _strip_comments(TERRAIN.read_text()) + "\n" + _strip_comments(CEREMONIES.read_text())
    offenders = []
    for m in re.finditer(r"(color|emissive)\s*:\s*([^,}\n]+)", s):
        val = m.group(2).strip()
        if val.startswith("srgb(") or val.startswith("VERA_CYAN_LIN"):
            continue
        if "DUSK_BAND" in val or re.match(r"0x[0-9a-fA-F]{6}", val):
            offenders.append(m.group(0).strip())
    for m in re.finditer(r"new THREE\.(Hemisphere|Ambient|Directional|Point)Light\(\s*([^,)]+)", s):
        val = m.group(2).strip()
        if val.startswith("srgb(") or val.startswith("VERA_CYAN_LIN"):
            continue
        offenders.append(m.group(0).strip())
    assert not offenders, "unconverted colour reaching a material/light: " + "; ".join(offenders)


def test_canvas_textures_declare_srgb_encoding():
    # A 2D canvas is painted with sRGB colour strings, but CanvasTexture defaults to
    # LinearEncoding in r128 — the same over-brightening as an unconverted material colour.
    # Funnel every construction through one helper so the encoding cannot be forgotten.
    s = _strip_comments(TERRAIN.read_text())
    assert "function canvasTex(" in s, "canvas textures must be built through one seam"
    body = _js_fn(s, "canvasTex")
    assert re.search(r"\.encoding\s*=\s*THREE\.sRGBEncoding", body), (
        "canvasTex() must set encoding = THREE.sRGBEncoding"
    )
    assert s.count("new THREE.CanvasTexture(") == 1, (
        "CanvasTexture may only be constructed inside canvasTex(); found "
        f"{s.count('new THREE.CanvasTexture(')} sites"
    )


def test_bloom_blit_does_not_tone_map_twice():
    # RenderPass already tone-maps the scene INTO the composer buffer; UnrealBloomPass then
    # blits that buffer to screen through a MeshBasicMaterial whose shader includes
    # <tonemapping_fragment>, so ACES runs a second time and crushes chroma at the bright end
    # — precisely where the reward vocabulary lives.
    s = _strip_comments(TERRAIN.read_text())
    assert re.search(r"\.basic\.toneMapped\s*=\s*false", s), (
        "the UnrealBloomPass screen blit must set basic.toneMapped = false"
    )


def test_scene_has_fog_tinted_to_the_sky():
    # No fog means no aerial perspective: a 2.9x depth spread renders at identical contrast,
    # so floating lands have nothing to float in. The colour must come from the dusk band via
    # the srgb() seam, not an invented grey. Pinned to linear THREE.Fog specifically (not
    # THREE.FogExp2): a silent swap to exponential fog would change the depth falloff shape
    # and must fail this guard, not slip through a loose \w* wildcard.
    s = _strip_comments(TERRAIN.read_text())
    m = re.search(r"scene\.fog\s*=\s*new THREE\.Fog\(\s*([^,)]+)", s)
    assert m, "scene.fog must be assigned using linear THREE.Fog(...)"
    assert m.group(1).strip().startswith("srgb(DUSK_BAND["), (
        f"fog colour must come from the dusk band through srgb(), got {m.group(1).strip()}"
    )


def test_keyboard_camera_ignores_typing():
    # w/a/s/d + arrows pan the camera and Escape re-homes it, bound at window level. The world
    # is visible while the composer has focus at the front door, so every keystroke of a typed
    # situation drove the camera.
    s = _strip_comments(TERRAIN.read_text())
    kd_code = _js_fn(s, "kd")
    assert re.search(r"if\s*\(\s*_typing\(\s*e\s*\)\s*\)\s*return\s*;", kd_code), (
        "kd() must bail out with an early `return` guarded by _typing(e), not just mention it"
    )
    typing = _js_fn(s, "_typing")
    for token in ["INPUT", "TEXTAREA", "isContentEditable"]:
        assert token in typing, f"_typing() must recognise {token}"


def test_close_render_passes_the_memory_click_handler():
    # The post-landing render must make the just-earned monolith openable. Without this the
    # memory is inert until a page reload, and the click falls through to the isle pick layer
    # (it moves the camera instead of opening the memory).
    s = _strip_comments(SHELL.read_text())
    m = re.search(r"function renderTerrain\(.*?\n\}", s, re.S)
    assert m, "renderTerrain must exist in index.html"
    body = m.group(0)
    assert "Terrain3D.render(" in body
    assert re.search(r"onHouseClick\s*:", body), (
        "renderTerrain must pass onHouseClick so a just-earned memory is clickable"
    )
