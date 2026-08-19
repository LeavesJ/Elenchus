"""Deterministic checks against a running preview.

Two static suites in this repo — test_renderer_pipeline_static.py and
test_wx_law_static.py — open by saying "the browser smoke supplies the
behavioural teeth". That smoke was a person running scripts/smoke_server.py and
clicking, referenced by no gate and no workflow, so the teeth were a manual
process nobody had to perform and nothing recorded. A guard whose behavioural
half is somebody's habit is a guard with a stated dependency on nothing.

These run against a real HTTP server holding the real FastAPI app, wired to the
scripted FakeModel, so they cost no tokens and are deterministic. They are the
step the guidebook puts downstream of a preview: something that can actually
fail after the thing is stood up, rather than before.

Marked `preview` and skipped unless PREVIEW_URL is set, following the `live`
marker convention. The gate does not boot a server; CI does, and points this at
it.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.preview

PREVIEW_URL = os.environ.get("PREVIEW_URL", "").rstrip("/")

pytest_skip = pytest.mark.skipif(
    not PREVIEW_URL, reason="no PREVIEW_URL; this needs a running preview server"
)


def _get(path: str, timeout: float = 10.0) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(PREVIEW_URL + path, headers={"User-Agent": "elenchus-preview"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — fixed local URL
            return r.status, r.read(), {k.lower(): v for k, v in r.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read(), {k.lower(): v for k, v in e.headers.items()}


@pytest_skip
def test_the_front_door_is_reachable():
    status, body, _ = _get("/")
    assert status == 200, f"GET / returned {status}"
    assert b"<title>" in body, "the shell rendered no title"


@pytest_skip
def test_the_shell_names_itself():
    _, body, _ = _get("/")
    assert b"Elenchus" in body, "the served page does not name the product"


@pytest_skip
def test_every_script_the_shell_references_resolves():
    """The failure this catches is a renamed or unvendored asset. The static suites
    assert the shell *references* three.js; only a running server can say whether
    the reference resolves, and a 404 here is a blank screen in a browser."""
    import re

    _, body, _ = _get("/")
    srcs = re.findall(rb'<script[^>]+src="([^"]+)"', body)
    assert srcs, "the shell references no scripts at all"
    missing = []
    for src in srcs:
        path = src.decode()
        if path.startswith("http"):
            continue
        status, _, _ = _get(path if path.startswith("/") else "/" + path)
        if status != 200:
            missing.append(f"{path} -> {status}")
    assert not missing, "referenced but not served: " + ", ".join(missing)


@pytest_skip
def test_static_assets_are_not_cached_by_the_preview():
    """A preview that serves stale assets tests the previous commit."""
    _, body, _ = _get("/")
    import re

    srcs = [s.decode() for s in re.findall(rb'<script[^>]+src="(/[^"]+)"', body)]
    if not srcs:
        pytest.skip("no local scripts to check")
    _, _, headers = _get(srcs[0])
    cache = headers.get("cache-control", "")
    assert "no-store" in cache or "no-cache" in cache or "max-age=0" in cache, (
        f"preview served {srcs[0]} with cache-control={cache!r}"
    )
