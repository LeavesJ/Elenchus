"""Static source guards over the render pipeline (Spec-3 §3, P0).

terrain3d.js runs on vendored three r128, which has no ColorManagement: an authored sRGB hex
handed to a material or a light is consumed as a LINEAR radiance value and renders far too
bright, hardest at the dark end. Every structural colour must therefore pass through the one
`srgb()` conversion seam. These guards are textual by necessity (there is no JS test runner in
this repo); the browser smoke supplies the behavioural teeth."""

import re
from pathlib import Path

TERRAIN = Path("src/retnovation/web/static/terrain3d.js")
CEREMONIES = Path("src/retnovation/web/static/ceremonies.js")
SHELL = Path("src/retnovation/web/static/index.html")


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


def test_srgb_conversion_seam_exists():
    s = TERRAIN.read_text()
    assert "function srgb(" in s, "terrain3d.js must declare the one sRGB->linear conversion seam"
    m = re.search(r"function srgb\([^)]*\)\s*\{(.*?)\}", s, re.S)
    assert m, "srgb() must be a single-expression helper"
    assert "convertSRGBToLinear" in m.group(1), (
        "srgb() must use THREE.Color.convertSRGBToLinear — r128 has no ColorManagement"
    )


def test_no_raw_hex_reaches_a_material_or_light():
    # Every colour-consuming site takes srgb(...), never a bare DUSK_BAND[i] or 0x literal.
    # Canvas PAINT (cssHex/rgbaHex) is deliberately excluded: those are 2D-canvas strings whose
    # decode is handled at the texture level (see test_canvas_textures_declare_srgb_encoding).
    s = TERRAIN.read_text() + CEREMONIES.read_text()
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
    s = TERRAIN.read_text()
    assert "function canvasTex(" in s, "canvas textures must be built through one seam"
    body = _js_fn(s, "canvasTex")
    assert "sRGBEncoding" in body, "canvasTex() must set encoding = THREE.sRGBEncoding"
    assert s.count("new THREE.CanvasTexture(") == 1, (
        "CanvasTexture may only be constructed inside canvasTex(); found "
        f"{s.count('new THREE.CanvasTexture(')} sites"
    )


def test_bloom_blit_does_not_tone_map_twice():
    # RenderPass already tone-maps the scene INTO the composer buffer; UnrealBloomPass then
    # blits that buffer to screen through a MeshBasicMaterial whose shader includes
    # <tonemapping_fragment>, so ACES runs a second time and crushes chroma at the bright end
    # — precisely where the reward vocabulary lives.
    s = TERRAIN.read_text()
    assert re.search(r"\.basic\.toneMapped\s*=\s*false", s), (
        "the UnrealBloomPass screen blit must set basic.toneMapped = false"
    )


def test_scene_has_fog_tinted_to_the_sky():
    # No fog means no aerial perspective: a 2.9x depth spread renders at identical contrast,
    # so floating lands have nothing to float in. The colour must come from the dusk band via
    # the srgb() seam, not an invented grey. Pinned to linear THREE.Fog specifically (not
    # THREE.FogExp2): a silent swap to exponential fog would change the depth falloff shape
    # and must fail this guard, not slip through a loose \w* wildcard.
    s = TERRAIN.read_text()
    m = re.search(r"scene\.fog\s*=\s*new THREE\.Fog\(\s*([^,)]+)", s)
    assert m, "scene.fog must be assigned using linear THREE.Fog(...)"
    assert m.group(1).strip().startswith("srgb(DUSK_BAND["), (
        f"fog colour must come from the dusk band through srgb(), got {m.group(1).strip()}"
    )


def test_keyboard_camera_ignores_typing():
    # w/a/s/d + arrows pan the camera and Escape re-homes it, bound at window level. The world
    # is visible while the composer has focus at the front door, so every keystroke of a typed
    # situation drove the camera.
    s = TERRAIN.read_text()
    kd_code = re.sub(r"//[^\n]*", "", _js_fn(s, "kd"))  # strip comments: a guard must be a real
    # statement, not merely an identifier mentioned in passing (including inside a comment)
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
    s = SHELL.read_text()
    m = re.search(r"function renderTerrain\(.*?\n\}", s, re.S)
    assert m, "renderTerrain must exist in index.html"
    body = re.sub(r"//[^\n]*", "", m.group(0))  # strip comments, same discipline as the guard
    # test above: the handler must be PASSED, not merely named in the comment beside the call
    assert "Terrain3D.render(" in body
    assert re.search(r"onHouseClick\s*:", body), (
        "renderTerrain must pass onHouseClick so a just-earned memory is clickable"
    )
