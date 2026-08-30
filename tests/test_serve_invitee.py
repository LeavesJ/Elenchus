"""The per-invitee launcher: one process, one database file, one log, one link.

Deployment is the plan's named schedule killer -- the only item with no mechanism in the tree.
The topology is deliberately boring: every instance on one machine, databases under
`<root>/<slug>/`, one quick-tunnel link per invitee, no shared URL a forwarded link can collapse.
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC.parent / "scripts"))

from serve_invitee import build_env, resolve_slug  # noqa: E402 -- needs the insert above


def test_a_slug_is_a_path_component_not_a_path(tmp_path):
    """Input validation at the system boundary: the slug names a directory UNDER the root, and
    anything that could escape it -- separators, dots, an absolute path -- is refused before a
    file is touched. `data/tenants/../../elenchus.db` must never be creatable from an argument."""
    for bad in ("", "a/b", "../up", ".", "..", "a b", "A", "slüg", "x" * 65):
        with pytest.raises(ValueError):
            resolve_slug(bad)
    assert resolve_slug("ada-1") == "ada-1"


def test_the_env_pins_all_three_isolation_variables(tmp_path):
    """The whole safety argument is one process + one file per invitee, and runtime.resolve_runtime
    raises when the pieces are missing -- so the launcher must set all three, and the db path must
    sit under the slug's own directory."""
    env = build_env(tmp_path, "ada", "0.0.0.0", 9410, base={"PATH": "/usr/bin"})
    assert env["ELENCHUS_DB"] == str(tmp_path / "ada" / "elenchus.db")
    assert env["ELENCHUS_HOST"] == "0.0.0.0"
    assert env["ELENCHUS_PORT"] == "9410"
    assert env["PATH"] == "/usr/bin", "the base environment must survive"


def _wait_health(port: int, deadline_s: float = 25.0) -> bytes:
    deadline = time.monotonic() + deadline_s
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001 -- retrying a booting server
            last = exc
            time.sleep(0.25)
    raise AssertionError(f"server never became healthy: {last}")


def test_the_launcher_boots_an_isolated_instance_and_retains_stderr(tmp_path):
    """The real invocation, as a subprocess: the database lands under the tenant directory, the
    app answers health on the chosen port, and stderr is RETAINED in the tenant's server.log --
    the S2 residual: a refusal logged to a scrolling terminal is only marginally better than one
    discarded."""
    port = 8481
    proc = subprocess.Popen(
        [
            sys.executable,
            str(SRC.parent / "scripts" / "serve_invitee.py"),
            "ada",
            "--root",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        body = _wait_health(port)
        assert b'"ok":true' in body or b'"ok": true' in body
        assert (tmp_path / "ada" / "elenchus.db").exists(), "the tenant db did not land"
        log = tmp_path / "ada" / "server.log"
        assert log.exists(), "stderr is not being retained"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and b"Uvicorn running" not in log.read_bytes():
            time.sleep(0.25)
        assert b"Uvicorn running" in log.read_bytes(), (
            "the server's stderr stream is not reaching the tenant log"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=10)
