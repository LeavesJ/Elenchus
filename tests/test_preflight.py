"""The checks that read the MACHINE, not the tree.

Every gate this project had -- format, lint, test, confidential, secret, lift-bank, ignore-leak --
reads the repository. Not one of them looks at the host. So the tree stayed green through: a beta
origin serving keyless for seventeen hours, a `.env` at mode 644, an unrelated `http.server` on
all interfaces for thirty-five hours, and a live API key replicated into iCloud. Semgrep's
security-audit and secrets rulesets over the same tree report zero findings, which is correct and
useless -- none of those defects live in the code.

Each check is fed its inputs rather than reaching for the machine itself, so the failure modes are
reproducible in a test instead of only on the laptop that has them.
"""

from elenchus import preflight


def test_a_synced_path_is_caught_even_when_the_path_string_says_nothing(tmp_path):
    """THE MISS THIS EXISTS FOR (2026-08-31). Checking whether the path CONTAINS "iCloud" or
    "Dropbox" returns a confident clean on macOS "Desktop & Documents" sync, because the working
    path stays an ordinary `~/Documents/...` while the canonical storage is a CloudDocs container.
    The repo, the `.env` holding a live paid key, and the production database were all replicated
    to Apple, and a string check said "not in an obvious sync folder".

    So membership is decided by CONTAINMENT of the resolved path, never by how it is spelled."""
    container = tmp_path / "sync-container"
    repo = container / "Documents" / "Elenchus"  # nothing in this path says "cloud"
    repo.mkdir(parents=True)
    (repo / ".env").write_text("KEY=x")

    check = preflight.sync_exposure(repo, sync_containers=[container])

    assert check.status == "fail"
    assert ".env" in check.detail


def test_a_container_that_reaches_the_repo_THROUGH_A_SYMLINK_is_still_exposure(tmp_path):
    """THE SECOND MISS, found by running the first version against the real machine (2026-08-31).

    macOS puts a SYMLINK at `com~apple~CloudDocs/Documents` pointing at `~/Documents`. The first
    implementation walked the container with `Path.rglob`, which does not follow symlinks when
    recursing, so it reported a confident `ok` over a live paid key and the production database --
    the identical false negative, one layer down, that this module was written to stop.

    So membership is decided on RESOLVED paths: is the file's real location underneath the
    container's real location, however either one is spelled or linked."""
    real_docs = tmp_path / "Documents"
    repo = real_docs / "Elenchus"
    repo.mkdir(parents=True)
    (repo / ".env").write_text("KEY=x")

    container = tmp_path / "Mobile Documents" / "com~apple~CloudDocs"
    container.mkdir(parents=True)
    (container / "Documents").symlink_to(real_docs)  # exactly what macOS does

    check = preflight.sync_exposure(repo, sync_containers=[container])

    assert check.status == "fail", "rglob does not follow symlinks; resolve the paths instead"
    assert ".env" in check.detail


def test_an_unsynced_repo_passes(tmp_path):
    container = tmp_path / "CloudDocs" / "Documents"
    container.mkdir(parents=True)
    repo = tmp_path / "code" / "Elenchus"
    repo.mkdir(parents=True)
    (repo / ".env").write_text("KEY=x")

    assert preflight.sync_exposure(repo, sync_containers=[container]).status == "ok"


def test_a_group_or_world_readable_secret_fails(tmp_path):
    """`.env` shipped at 644 and the tenant database and log with it, so every local process and
    every backup could read a live paid key and a learner's transcript."""
    env = tmp_path / ".env"
    env.write_text("KEY=x")
    env.chmod(0o644)

    check = preflight.file_modes([env])

    assert check.status == "fail"
    assert "644" in check.detail and ".env" in check.detail


def test_owner_only_modes_pass(tmp_path):
    env = tmp_path / ".env"
    env.write_text("KEY=x")
    env.chmod(0o600)

    assert preflight.file_modes([env]).status == "ok"


def test_a_missing_file_is_not_silently_a_pass(tmp_path):
    """A typo'd path reporting 'ok' is the failure this whole module exists to stop: a check that
    quietly inspects nothing looks exactly like a check that found nothing wrong."""
    check = preflight.file_modes([tmp_path / "does-not-exist"])

    assert check.status == "warn"
    assert "not found" in check.detail.lower()


_LSOF = """\
COMMAND     PID   USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
Python    44880 a14808    4u  IPv6  0x49eb      0t0  TCP *:8795 (LISTEN)
Python    88150 a14808    6u  IPv4  0x1234      0t0  TCP 127.0.0.1:9401 (LISTEN)
cloudflar 88151 a14808    9u  IPv4  0x5678      0t0  TCP 127.0.0.1:20241 (LISTEN)
"""


def test_a_listener_on_all_interfaces_is_caught():
    """The 35-hour `python -m http.server 8795` on campus wifi, serving strategy documents to
    anyone on the segment. Loopback listeners are fine; a bind to `*` or `0.0.0.0` is the whole
    finding."""
    check = preflight.open_listeners(_LSOF.splitlines())

    assert check.status == "fail"
    assert "8795" in check.detail
    assert "9401" not in check.detail  # loopback, and the one we meant to run
    assert "20241" not in check.detail


def test_loopback_only_listeners_pass():
    lines = [ln for ln in _LSOF.splitlines() if "*:8795" not in ln]

    assert preflight.open_listeners(lines).status == "ok"


def test_the_unauthenticated_public_surface_is_reported_as_a_launch_blocker():
    """The audit's blocker: every route is unauthenticated, so the hostname IS the credential.
    An empty POST to /api/session returns the previous learner's whole transcript, and the same
    door spends the founders' key. Nothing in the app can fix this cheaply -- Cloudflare Access in
    front of the hostname can -- so the check's job is to refuse to let it go unnoticed."""
    check = preflight.public_surface(access_configured=False)

    assert check.status == "fail"
    assert "access" in check.detail.lower()


def test_declaring_access_is_configured_downgrades_it_to_a_warn():
    """Preflight cannot reach Cloudflare's control plane, so this is an ATTESTATION, not a
    measurement, and it says so rather than printing a green it did not earn (Invariant 7)."""
    check = preflight.public_surface(access_configured=True)

    assert check.status == "warn"
    assert "attested" in check.detail.lower() or "not verified" in check.detail.lower()


def test_the_report_keeps_every_axis_and_does_not_collapse_to_a_verdict():
    """L-28: a go/no-go that projects a multi-axis gate onto a pass-bool misreads itself and
    discards exactly the signal the gate exists to surface. Every check must appear by name with
    its own status, including the ones that passed."""
    checks = [
        preflight.Check("a", "ok", "fine"),
        preflight.Check("b", "warn", "known"),
        preflight.Check("c", "fail", "broken"),
    ]

    out = preflight.report(checks)

    for name in ("a", "b", "c"):
        assert name in out
    assert "fine" in out and "known" in out and "broken" in out
    assert preflight.launch_blocked(checks) is True
    assert preflight.launch_blocked(checks[:2]) is False  # a warn never blocks


def test_the_script_runs_against_a_real_tree_and_blocks_on_a_loose_mode(tmp_path):
    """End to end, the way it will be run before each of Friday's launches."""
    import subprocess
    import sys
    from pathlib import Path

    repo = tmp_path / "repo"
    (repo / "data" / "tenants" / "ada").mkdir(parents=True)
    env = repo / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-x\n")
    env.chmod(0o644)  # the defect
    (repo / "data" / "tenants" / "ada" / "elenchus.db").write_bytes(b"")

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "preflight.py"), "--repo", str(repo)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"},
        timeout=90,
    )

    assert out.returncode == 1, out.stdout + out.stderr
    assert "file-modes" in out.stdout
    assert "DO NOT SEND A LINK" in out.stdout
    assert "sync-exposure" in out.stdout  # every axis is printed, including the ones that passed


_NOISY_LSOF = """\
COMMAND     PID   USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
rapportd    622 a14808   10u  IPv4  0xd731      0t0  TCP *:50616 (LISTEN)
ControlCe   710 a14808    9u  IPv4  0x91e0      0t0  TCP *:7000 (LISTEN)
Spotify    1708 a14808   97u  IPv4  0xf555      0t0  TCP *:57621 (LISTEN)
Python    44880 a14808    4u  IPv6  0x49eb      0t0  TCP *:8795 (LISTEN)
"""


def test_known_macos_services_do_not_drown_the_finding_that_matters():
    """The project's own secret-scan carries the rule: "A scanner that cries wolf is turned off
    within a week, so the exclusions are the load-bearing half." The first run of this check
    reported AirPlay, Spotify and rapportd as blockers alongside the real one, which is how a
    check gets ignored. macOS's own services are named and demoted; anything unrecognised still
    blocks."""
    check = preflight.open_listeners(_NOISY_LSOF.splitlines())

    assert check.status == "fail"
    assert "8795" in check.detail  # the stray directory server still blocks
    for benign in ("Spotify", "rapportd", "ControlCe"):
        assert benign not in check.detail.split("also listening")[0], (
            f"{benign} is presented as a blocker and will train the reader to ignore this check"
        )


def test_only_known_services_exposed_is_a_warn_not_a_failure():
    """A laptop with AirPlay on is not a launch blocker. It is worth SAYING, because these are
    reachable from the same wifi as the invitee link, so it is a warn rather than silence."""
    lines = [ln for ln in _NOISY_LSOF.splitlines() if "Python" not in ln]

    check = preflight.open_listeners(lines)

    assert check.status == "warn"
    assert "Spotify" in check.detail


def test_known_service_names_are_matched_the_way_lsof_actually_prints_them():
    """Pre-merge review: macOS lsof truncates COMMAND to 9 characters, so three of the seven
    allowlist entries could never match -- the list did not exempt the services its comment said
    it did. Match on what lsof prints, not on the full binary name."""
    lines = [
        "COMMAND     PID   USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME",
        "ControlCe   710 a14808    9u  IPv4  0x91e0      0t0  TCP *:7000 (LISTEN)",
        "AirPlayXP   712 a14808    9u  IPv4  0x91e1      0t0  TCP *:7001 (LISTEN)",
        "identitys   713 a14808    9u  IPv4  0x91e2      0t0  TCP *:7002 (LISTEN)",
    ]

    check = preflight.open_listeners(lines)

    assert check.status == "warn", check.detail
    assert "AirPlayXP" in check.detail and "identitys" in check.detail


def test_a_failed_lsof_is_a_warn_never_a_clean_ok(tmp_path, monkeypatch):
    """Pre-merge review: scripts/preflight.py never checked lsof's exit status, so an lsof that
    failed or printed nothing reported '[ok] every listener is loopback-only'. A check that could
    not run is not a check that passed -- the same rule the surrounding code already applies to
    a missing file."""
    import subprocess
    import sys
    from pathlib import Path

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "lsof").write_text("#!/bin/sh\nexit 1\n")
    (fake_bin / "lsof").chmod(0o755)
    repo = tmp_path / "repo"
    (repo / "data" / "tenants").mkdir(parents=True)
    (repo / ".env").write_text("ANTHROPIC_API_KEY=sk-x\n")
    (repo / ".env").chmod(0o600)

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "preflight.py"), "--repo", str(repo)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src), "PATH": f"{fake_bin}:/usr/bin:/bin"},
        timeout=90,
    )

    assert "[WARN] open-listeners" in out.stdout, out.stdout
    assert "[ok  ] open-listeners" not in out.stdout


def test_the_out_of_tree_key_file_is_covered_by_the_mode_check(tmp_path, monkeypatch):
    """Pre-merge review: the branch moved the key to ~/.config/elenchus/env, and preflight's
    file-modes list did not know. On the real launch root a deliberate .env symlink carries the
    check onto it, so it was refuted as a blocker -- but a root with no symlink is one preflight
    away from '[ok]' over a world-readable paid key. The list should name the file directly."""
    outside = tmp_path / "cfg" / "env"
    outside.parent.mkdir()
    outside.write_text("ANTHROPIC_API_KEY=sk-x\n")
    outside.chmod(0o644)
    repo = tmp_path / "repo"
    repo.mkdir()

    check = preflight.file_modes(preflight.sensitive_files(repo, key_file=outside))

    assert check.status == "fail"
    assert "env is 644" in check.detail


# --- the origin axis: "tunnel up, origin dead" must not read green -------------------------------

_SERVING = ["ELENCHUS_DB=data/tenants/rehearsal/elenchus.db ELENCHUS_PORT=9401 PATH=/usr/bin"]


def test_a_served_origin_that_answers_is_ok():
    check = preflight.origin_reachable(_SERVING, probe=lambda port: 200)

    assert check.status == "ok"
    assert "rehearsal" in check.detail


def test_a_served_slug_whose_ORIGIN_IS_DEAD_fails_even_though_the_tunnel_answers():
    """THE OUTAGE THIS AXIS EXISTS FOR (2026-09-03 01:49:56). All three processes died. The public
    URL still returned 302, because Cloudflare Access serves its login page whether or not anything
    is behind it -- so an invitee would authenticate, receive a one-time PIN, sign in, and only
    then meet a dead origin. Every external signal said healthy.

    `public_surface` cannot catch this: it is an operator ATTESTATION about Access, and Access was
    genuinely up. The origin is a separate fact and must be measured separately, on loopback."""
    check = preflight.origin_reachable(_SERVING, probe=lambda port: None)

    assert check.status == "fail"
    assert "rehearsal" in check.detail and "9401" in check.detail


def test_only_the_dead_slug_is_named_when_several_are_served():
    envs = [
        "ELENCHUS_DB=data/tenants/ada/elenchus.db ELENCHUS_PORT=9402",
        "ELENCHUS_DB=data/tenants/bo/elenchus.db ELENCHUS_PORT=9403",
    ]

    check = preflight.origin_reachable(envs, probe=lambda port: 200 if port == 9402 else None)

    assert check.status == "fail"
    assert "bo" in check.detail and "9403" in check.detail
    assert "ada" not in check.detail


def test_an_origin_answering_non_200_is_a_failure_not_a_pass():
    """A process that is up but broken serves the invitee an error, which is the same experience as
    a dead one. `{"ok": true}` or it is not healthy."""
    check = preflight.origin_reachable(_SERVING, probe=lambda port: 500)

    assert check.status == "fail"
    assert "500" in check.detail


def test_nothing_served_is_a_WARN_never_an_ok():
    """A preflight run on a machine serving nobody has not verified an origin; it has verified
    nothing. Reporting ok would let 'no instances running' read identically to 'every instance
    healthy' -- the same rule file_modes already applies to a missing file."""
    check = preflight.origin_reachable([], probe=lambda port: 200)

    assert check.status == "warn"
    assert "no invitee" in check.detail.lower() or "nothing" in check.detail.lower()


def test_the_axis_probes_LOOPBACK_and_never_the_public_hostname():
    """The public hostname is exactly the signal that lied. Whatever this axis reports must come
    from the origin itself, so the probe is handed a port and nothing else -- there is no hostname
    for it to accidentally consult."""
    import inspect

    seen = []
    preflight.origin_reachable(_SERVING, probe=lambda port: seen.append(port) or 200)

    # The axis hands the probe a PORT and no hostname, so there is nothing for it to consult.
    assert seen == [9401]

    # And the function that actually dials builds a loopback URL only. Asserted on `probe_origin`
    # rather than on `origin_reachable`, whose docstring names the public URL in prose to explain
    # the outage -- prose is not a consultation, and grepping the wrong function is how a guard
    # ends up measuring its own comments.
    dialer = inspect.getsource(preflight.probe_origin)
    assert "127.0.0.1" in dialer
    assert "elenchuslab" not in dialer and "https://" not in dialer


def test_one_missed_probe_is_retried_before_a_launch_is_blocked():
    """A single refused connection on a loopback health endpoint is weak evidence that an origin
    is down, and this axis BLOCKS a launch. I saw exactly one FAIL against a beta that the tenant
    log later proved had been up continuously either side of it, and could not reproduce it — so
    the axis retries once before it convicts. Two spaced failures is strong evidence; one is not.

    A genuinely dead origin fails both probes and is still caught (the test below)."""
    calls = []

    def flaky(port):
        calls.append(port)
        return None if len(calls) == 1 else 200

    check = preflight.origin_reachable(_SERVING, probe=flaky, retry_wait=0)

    assert check.status == "ok", "a transient blocked a launch"
    assert len(calls) == 2, "the axis did not retry"


def test_a_genuinely_dead_origin_fails_both_probes_and_is_still_caught():
    calls = []

    def dead(port):
        calls.append(port)
        return None

    check = preflight.origin_reachable(_SERVING, probe=dead, retry_wait=0)

    assert check.status == "fail"
    assert len(calls) == 2, "a dead origin must be probed twice, not once"


def test_the_loopback_probe_ignores_proxy_environment_variables(monkeypatch):
    """THE FALSE POSITIVE THIS FIXES (2026-09-03). The axis reported FAIL five times running
    against a beta the tenant log proved was up throughout, then ok ten times running minutes
    later. `urllib.request.urlopen` consults http_proxy/https_proxy/ALL_PROXY and will route even
    a 127.0.0.1 request through a proxy, so the probe returned None while the origin answered 200.
    Tool invocations inherit proxy variables inconsistently, which is exactly what made it flap.

    A loopback health check must never traverse a proxy. Verified against a REAL server on a real
    port, with the variables set, rather than by asserting on the opener's shape."""
    import http.server
    import threading

    class _Quiet(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Quiet)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        # a proxy that could not possibly serve this request
        for var in ("http_proxy", "https_proxy", "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY"):
            monkeypatch.setenv(var, "http://127.0.0.1:9")

        assert preflight.probe_origin(port) == 200, (
            "the loopback probe went through the proxy and reported a live origin as dead"
        )
    finally:
        srv.shutdown()
