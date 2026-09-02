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


@pytest.fixture(autouse=True)
def _no_operator_key_file(request, tmp_path_factory, monkeypatch):
    """Point DEFAULT_ENV_FILE at a path that does not exist, for every test in this file.

    Once the key moved out of the synced repo, `resolve_key` gained a real default location --
    and the moment a developer has one installed, every test asserting "no key is reachable"
    starts reading the OPERATOR'S OWN key and passing or failing on machine state. A suite whose
    green depends on whether the person running it happens to have a key installed is not a
    suite. `serve_invitee` is imported by path, so patch the module object directly."""
    import serve_invitee

    if "real_default_env_file" in request.keywords:
        return  # this one test is ABOUT the shipped default, so it must see the real value
    monkeypatch.setattr(
        serve_invitee, "DEFAULT_ENV_FILE", tmp_path_factory.mktemp("no-key") / "absent"
    )


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
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin", "ANTHROPIC_API_KEY": "sk-test-fake"},
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
            "ANTHROPIC_API_KEY": "sk-test-fake",  # the key refusal fires FIRST; this test is the cert one
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
            "ANTHROPIC_API_KEY": "sk-test-fake",
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


def test_a_keyless_invitee_launch_warns_before_it_serves_broken_doors(tmp_path, capsys):
    """L-18, paid for again on 2026-08-30: the origin was launched from a worktree whose root
    had no .env, the zero-token front door health-checked green, and every DOOR died on the
    first click -- from the founder's own phone. The launcher cannot know whether __main__'s
    dotenv load will find a key at ITS root, but it can check the two places one could come
    from (the environment it passes, and <script repo root>/.env) and shout when both are
    empty, at launch time instead of first-click time."""
    from serve_invitee import missing_key_warning

    # neither source has a key -> the warning names both places
    msg = missing_key_warning({"PATH": "/usr/bin"}, repo_root=tmp_path)
    assert msg is not None
    assert "ANTHROPIC_API_KEY" in msg and ".env" in msg
    assert "front door" in msg.lower(), "the warning must explain WHY health checks will lie"

    # key in the environment -> quiet
    assert missing_key_warning({"ANTHROPIC_API_KEY": "sk-x"}, repo_root=tmp_path) is None

    # key only in the repo root's .env -> quiet (that is where __main__ loads from)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-x\n")
    assert missing_key_warning({"PATH": "/usr/bin"}, repo_root=tmp_path) is None


def test_the_launcher_hands_the_child_the_key_instead_of_hoping_it_finds_one(tmp_path):
    """L-18's THIRD occurrence, found live 2026-08-31 on the running beta link.

    The guard above checks `<launcher's repo root>/.env` and its docstring asserts that is "the
    exact file __main__'s dotenv load reads (same root)". That is FALSE whenever the launcher
    script and the served package resolve to different checkouts -- which is precisely the
    worktree case the guard was written for. On 2026-08-30 serve_invitee.py ran from the MAIN
    checkout (whose .env has a key, so the guard passed) while PYTHONPATH resolved `elenchus`
    from a WORKTREE (whose root has no .env, so __main__ loaded nothing). The instance served
    keyless for hours: front door 200, every door {"kind":"error"}, and because that error is
    returned with HTTP 200 the access log recorded four "POST /say 200 OK" lines for four turns
    that never reached the model.

    The fix is not a better guess about which root the child will read. It is to stop guessing:
    resolve the key HERE and put it in the environment the child is handed, so the child's own
    root resolution cannot matter.
    """
    from serve_invitee import build_env

    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-from-the-launchers-root\n")
    env = build_env(tmp_path, "ada", "0.0.0.0", 9410, base={"PATH": "/usr/bin"}, repo_root=tmp_path)

    assert env.get("ANTHROPIC_API_KEY") == "sk-from-the-launchers-root", (
        "the child was launched with no key and will serve broken doors behind a green health check"
    )


def test_a_real_exported_key_beats_the_dotenv_file(tmp_path):
    """Same precedence __main__._load_dotenv already uses (setdefault): an operator who exported
    a key on purpose is not overridden by a stale file checked into their checkout."""
    from serve_invitee import build_env

    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-stale-file\n")
    env = build_env(
        tmp_path,
        "ada",
        "0.0.0.0",
        9410,
        base={"PATH": "/usr/bin", "ANTHROPIC_API_KEY": "sk-exported"},
        repo_root=tmp_path,
    )

    assert env["ANTHROPIC_API_KEY"] == "sk-exported"


def test_build_env_adds_no_key_when_there_is_none_to_add(tmp_path):
    """No invented value: with nothing to resolve the variable stays ABSENT, so
    missing_key_warning's refusal is the thing that fires, not a launch carrying an empty string
    that anthropic would reject with a confusing auth error at first click."""
    from serve_invitee import build_env

    env = build_env(tmp_path, "ada", "0.0.0.0", 9410, base={"PATH": "/usr/bin"}, repo_root=tmp_path)

    assert "ANTHROPIC_API_KEY" not in env


def test_a_real_child_process_receives_the_key_from_the_launchers_root(tmp_path):
    """The end of the chain, exercised rather than reasoned about: `main()` hands build_env's dict
    straight to Popen, so what this test proves about that dict is what the served process gets.

    The child here has NO .env of its own anywhere near it -- which is the worktree situation
    that produced a keyless beta link -- and must still come up keyed."""
    import subprocess
    import sys

    from serve_invitee import build_env

    launcher_root = tmp_path / "launcher-checkout"
    launcher_root.mkdir()
    (launcher_root / ".env").write_text("ANTHROPIC_API_KEY=sk-only-in-the-launchers-root\n")

    env = build_env(
        tmp_path / "tenants",
        "ada",
        "127.0.0.1",
        9412,
        base={"PATH": "/usr/bin:/bin"},
        repo_root=launcher_root,
    )
    out = subprocess.run(
        [sys.executable, "-c", "import os; print(os.environ.get('ANTHROPIC_API_KEY', 'NONE'))"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert out.stdout.strip() == "sk-only-in-the-launchers-root", (
        "the served child came up without a key: front door green, every door broken"
    )


def test_every_invitee_launch_carries_a_spend_ceiling_by_default(tmp_path):
    """Secure by default. The public surface has no authentication, so the ceiling is the only
    thing bounding what a stranger with the link can spend -- and a bound that depends on the
    operator remembering a flag is not a bound. An explicit value still wins."""
    from serve_invitee import build_env
    from elenchus.spend import DEFAULT_MAX_CALLS

    env = build_env(tmp_path, "ada", "0.0.0.0", 9410, base={"PATH": "/usr/bin"}, repo_root=tmp_path)
    assert env["ELENCHUS_MAX_CALLS"] == str(DEFAULT_MAX_CALLS)

    explicit = build_env(
        tmp_path,
        "ada",
        "0.0.0.0",
        9410,
        base={"PATH": "/usr/bin", "ELENCHUS_MAX_CALLS": "50"},
        repo_root=tmp_path,
    )
    assert explicit["ELENCHUS_MAX_CALLS"] == "50"


def test_the_key_can_live_OUTSIDE_the_repo_so_it_need_not_sit_in_a_synced_folder(
    tmp_path, monkeypatch
):
    """The repo is inside macOS's Desktop & Documents sync container, so `<repo>/.env` — holding a
    live paid key — is replicated to Apple and to every device on the Apple ID. The file cannot
    move out until the launcher can find it somewhere else, so this is the code half of that move.

    Order matters and matches `_load_dotenv`'s own setdefault precedence: a real exported variable
    beats the repo file, and the repo file beats the out-of-tree one, so nothing that works today
    changes behaviour."""
    from serve_invitee import resolve_key

    outside = tmp_path / "config" / "elenchus" / "env"
    outside.parent.mkdir(parents=True)
    outside.write_text("ANTHROPIC_API_KEY=sk-from-outside-the-repo\n")
    monkeypatch.setenv("ELENCHUS_ENV_FILE", str(outside))

    repo = tmp_path / "repo"
    repo.mkdir()  # deliberately no .env here

    assert resolve_key({}, repo) == "sk-from-outside-the-repo"


def test_the_repo_env_still_wins_over_the_out_of_tree_one(tmp_path, monkeypatch):
    """Nothing that works today may change: an existing checkout with its own .env keeps behaving
    exactly as it does now, whether or not the new location is configured."""
    from serve_invitee import resolve_key

    outside = tmp_path / "outside-env"
    outside.write_text("ANTHROPIC_API_KEY=sk-outside\n")
    monkeypatch.setenv("ELENCHUS_ENV_FILE", str(outside))

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("ANTHROPIC_API_KEY=sk-in-repo\n")

    assert resolve_key({}, repo) == "sk-in-repo"


def test_the_out_of_tree_location_has_a_default_so_the_move_needs_no_configuration(
    tmp_path, monkeypatch
):
    """A relocation that only works once an env var is exported is a relocation that breaks the
    next time somebody opens a fresh shell — and the failure mode is a keyless launch, which this
    project has now paid for three times. So the default location is known to the code, and
    ELENCHUS_ENV_FILE only overrides it."""
    from serve_invitee import resolve_key

    monkeypatch.delenv("ELENCHUS_ENV_FILE", raising=False)
    monkeypatch.setattr("serve_invitee.DEFAULT_ENV_FILE", tmp_path / "cfg" / "env")
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "env").write_text("ANTHROPIC_API_KEY=sk-default-location\n")

    repo = tmp_path / "repo"
    repo.mkdir()

    assert resolve_key({}, repo) == "sk-default-location"


@pytest.mark.real_default_env_file
def test_the_shipped_default_key_location_is_outside_the_repo_and_under_home():
    """The value that actually ships, read WITHOUT the hermetic fixture masking it. The pre-merge
    review found this test did not exist: an earlier edit claimed to add it and the replace
    silently missed, so the marker the fixture advertises was used by zero tests and the constant
    commit 2ab0f4d exists to add was asserted nowhere. It must sit outside any checkout, or the
    relocation it exists for is pointless."""
    from serve_invitee import DEFAULT_ENV_FILE, _REPO_ROOT

    assert DEFAULT_ENV_FILE.is_absolute()
    assert Path.home() in DEFAULT_ENV_FILE.parents
    assert _REPO_ROOT not in DEFAULT_ENV_FILE.parents
    assert DEFAULT_ENV_FILE.name == "env"
