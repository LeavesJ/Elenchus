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
