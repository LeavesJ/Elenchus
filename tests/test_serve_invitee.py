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


# ---- named-tunnel mode (2026-08-30): a stale invite link must not die into scam pages ----------


def test_a_hostname_is_a_lowercase_fqdn(tmp_path):
    """Same boundary stance as the slug: the hostname becomes a DNS route on the founders' own
    domain, so anything malformed is refused before cloudflared sees it."""
    from serve_invitee import resolve_hostname

    for bad in ("", "ada", "ada..x.com", "Ada.example.com", "ada.example.com/", "a b.example.com"):
        with pytest.raises(ValueError):
            resolve_hostname(bad)
    assert resolve_hostname("ada.decisions.example.com") == "ada.decisions.example.com"


def test_named_mode_without_a_login_fails_loudly_with_the_command(tmp_path):
    """The two halves that are the founders' (domain into Cloudflare, cloudflared tunnel login)
    fail as an instruction, not a traceback -- and BEFORE any server or tunnel process starts."""
    proc = subprocess.run(
        [
            sys.executable,
            str(SRC.parent / "scripts" / "serve_invitee.py"),
            "ada",
            "--root",
            str(tmp_path),
            "--port",
            "8482",
            "--hostname",
            "ada.decisions.example.com",
        ],
        env={
            "PYTHONPATH": str(SRC),
            "PATH": "/usr/bin:/bin",
            "TUNNEL_ORIGIN_CERT": str(tmp_path / "nope" / "cert.pem"),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
    assert "cloudflared tunnel login" in proc.stderr
    assert not (tmp_path / "ada" / "elenchus.db").exists(), (
        "the server side started despite the failed tunnel preflight"
    )


def test_named_mode_creates_routes_and_runs_against_the_named_tunnel(tmp_path):
    """The full sequence with a FAKE cloudflared on PATH recording its invocations: create the
    per-invitee tunnel (tolerating 'already exists'), route the DNS name, then run it against
    this invitee's own port -- while the real server boots and answers health. One tunnel per
    invitee, no ingress file, no path routing: the boring topology, kept."""
    port = 8483
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "cloudflared.log"
    fake = bindir / "cloudflared"
    fake.write_text(
        f'#!/bin/sh\necho "$@" >> {log}\ncase "$1 $2" in\n  "tunnel run"*) sleep 600 ;;\nesac\n'
    )
    fake.chmod(0o755)
    cert = tmp_path / "cert.pem"
    cert.write_text("fake origin cert")

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
            "--hostname",
            "ada.decisions.example.com",
        ],
        env={
            "PYTHONPATH": str(SRC),
            "PATH": f"{bindir}:/usr/bin:/bin",
            "TUNNEL_ORIGIN_CERT": str(cert),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_health(port)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and "tunnel run" not in (
            log.read_text() if log.exists() else ""
        ):
            time.sleep(0.25)
        lines = log.read_text().splitlines()
        assert any(line.startswith("tunnel create elenchus-ada") for line in lines), lines
        assert any(
            line.startswith("tunnel route dns elenchus-ada ada.decisions.example.com")
            for line in lines
        ), lines
        run_lines = [line for line in lines if line.startswith("tunnel run")]
        assert run_lines and f"--url http://localhost:{port}" in run_lines[0], lines
        assert "elenchus-ada" in run_lines[0], lines
    finally:
        proc.terminate()
        proc.wait(timeout=10)
