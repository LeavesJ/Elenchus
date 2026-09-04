"""One invitee, one process, one database file, one log — the beta's whole deployment unit.

    PYTHONPATH=src .venv/bin/python scripts/serve_invitee.py <slug> --port 9401 [--tunnel]

Boring topology, chosen on purpose (two-week plan): every instance on one machine, databases
under `<root>/<slug>/`, one quick-tunnel link per invitee, no path-prefix routing and no shared
URL a forwarded link can collapse. The isolation itself lives in `elenchus.web.runtime`, which
RAISES when the pieces are missing; this script only sets the three variables and keeps the
process's stderr, so a misconfiguration still fails loudly rather than being papered over here.

stderr goes to `<root>/<slug>/server.log`, appended. That is the S2 refusal record's retention:
`_log_refusal` reaches stderr via logging's last-resort handler, and a refusal recorded into a
scrolling terminal is only marginally better than one discarded.

The launcher SUPERVISES what it starts (2026-09-04). The beta died at 01:49 on 2026-09-03 with a
clean SIGTERM sequence in the child, no cause ever established, and nothing noticed for hours:
this script was waiting on a child that was gone, and the tunnel kept answering 302 to the world.
Now a child that exits on its own is restarted, with a backoff that doubles while it keeps dying
young and never gives up, and every restart is written into the tenant log with the exit code and
how long the child lived. `grep supervisor: <root>/<slug>/server.log` is the restart history.
What this cannot cover: the launcher itself being killed. That needs a supervisor outside this
process (launchd on this machine), which is an operator decision, not a line of code here.

`--tunnel` execs `cloudflared tunnel --url` alongside and passes its output through; the
trycloudflare hostname is random and DIES WITH THIS PROCESS — hand out the printed link, and
expect to mint a fresh one on every restart.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# The ceiling's value is defined once, in the package, and imported here rather than copied. Two
# literals for one number is the drift that put a keyless instance behind a green health check.
from elenchus.spend import DEFAULT_MAX_CALLS

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Where the key lives when it is not in the repo. Known to the code rather than exported by hand:
# a relocation that depends on an env var breaks in the next fresh shell, and the failure mode is
# a keyless launch, which this project has paid for three times. ELENCHUS_ENV_FILE overrides it.
DEFAULT_ENV_FILE = Path.home() / ".config" / "elenchus" / "env"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_LABEL = r"[a-z0-9]([a-z0-9-]*[a-z0-9])?"
_HOSTNAME_RE = re.compile(rf"^{_LABEL}(\.{_LABEL}){{1,}}$")


def resolve_slug(raw: str) -> str:
    """The slug is a path COMPONENT, never a path. Validated at the boundary because it becomes
    a directory name under the tenant root: separators, dots, spaces, uppercase and empty are
    refused before any file is touched — `../../elenchus.db` must never be creatable from an
    argument."""
    if not _SLUG_RE.match(raw):
        raise ValueError(
            f"slug {raw!r} is not [a-z0-9-] (max 64, must start alphanumeric); "
            "it names a directory under the tenant root and nothing else"
        )
    return raw


def resolve_hostname(raw: str) -> str:
    """The invite hostname becomes a DNS route on the founders' own domain -- boundary-validated
    like the slug. Lowercase FQDN only; anything else is refused before cloudflared sees it."""
    if not _HOSTNAME_RE.match(raw):
        raise ValueError(
            f"hostname {raw!r} is not a lowercase FQDN (e.g. ada.decisions.example.com)"
        )
    return raw


def resolve_key(env: dict, repo_root: Path) -> str | None:
    """The model key this launcher can actually reach, or None.

    Two real callers: `missing_key_warning`, which refuses when this returns None, and
    `build_env`, which puts the value into the environment the child is handed.

    That second caller is the whole point, and it is why this is a resolver rather than a
    predicate. The predicate form shipped first and had a hole that cost the beta link a day:
    it checked `<launcher repo root>/.env` on the stated assumption that this is "the exact file
    __main__'s dotenv load reads (same root)". The two roots are the same only when the launcher
    script and the served package come from the same checkout. On 2026-08-30 they did not --
    serve_invitee.py ran from the main checkout while PYTHONPATH resolved `elenchus` from a
    worktree -- so the guard read a .env with a key, passed, and handed the child an environment
    with no key and a root with no .env. Resolving the value here removes the assumption instead
    of refining it: the child's own root resolution can no longer matter.

    Precedence matches __main__._load_dotenv's setdefault: a real exported variable wins over
    the file.
    """
    if env.get("ANTHROPIC_API_KEY"):
        return env["ANTHROPIC_API_KEY"]
    # In order: the repo's own .env, then a file named by ELENCHUS_ENV_FILE. The out-of-tree
    # location exists because this repo lives inside macOS's Desktop & Documents sync container,
    # so a key at <repo>/.env is replicated to Apple and to every device on the Apple ID. Repo
    # first, so an existing checkout keeps behaving exactly as it does today.
    candidates = [repo_root / ".env"]
    outside = (env.get("ELENCHUS_ENV_FILE") or os.environ.get("ELENCHUS_ENV_FILE") or "").strip()
    candidates.append(Path(outside) if outside else DEFAULT_ENV_FILE)
    for dotenv in candidates:
        if not dotenv.exists():
            continue
        for raw in dotenv.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.removeprefix("export ").strip() == "ANTHROPIC_API_KEY":
                val = val.strip().strip('"').strip("'")
                if val:
                    return val
    return None


def missing_key_warning(env: dict, repo_root: Path) -> str | None:
    """None when a model key is reachable; otherwise the message main() refuses with.

    L-18, paid for three times by 2026-08-31: the zero-token front door health-checks green with
    no key, so a keyless instance looks alive and every DOOR dies on the first click -- and the
    error rides back as HTTP 200, so even the access log reads like a served turn. `resolve_key`
    now finds the value and `build_env` hands it over, so this refusal fires on the same fact the
    child will actually see rather than on a root this script guessed at.
    """
    if resolve_key(env, repo_root) is not None:
        return None
    dotenv = repo_root / ".env"
    return (
        "no ANTHROPIC_API_KEY in the environment and none in "
        f"{dotenv}.\nRefusing to serve an invitee a broken instance: the zero-token front door "
        "would health-check green while every door dies on the first click. Export the key or "
        "put it in that .env, then relaunch."
    )


def build_env(
    root: Path,
    slug: str,
    host: str,
    port: int,
    base: dict | None = None,
    repo_root: Path | None = None,
) -> dict:
    """The three isolation variables `runtime.resolve_runtime` requires, over the caller's own
    environment, PLUS the model key resolved here rather than left for the child to find.

    The db path is always `<root>/<slug>/elenchus.db`: the per-file isolation IS the privacy
    argument, so the launcher offers no way to point two slugs at one file.

    The key is carried explicitly because the child resolves its dotenv path from its OWN
    package location, which is not this script's checkout when the two live in different
    worktrees -- the exact divergence that served the beta link keyless for hours on 2026-08-30
    (see `resolve_key`). Absent when there is nothing to resolve: an empty string would turn a
    loud refusal here into a confusing auth traceback at the invitee's first click.
    """
    env = dict(base if base is not None else os.environ)
    env["ELENCHUS_DB"] = str(root / slug / "elenchus.db")
    env["ELENCHUS_HOST"] = host
    env["ELENCHUS_PORT"] = str(port)
    key = resolve_key(env, repo_root if repo_root is not None else _REPO_ROOT)
    if key is not None:
        env["ANTHROPIC_API_KEY"] = key
    # Secure by default. Nothing authenticates the invitee surface -- the hostname IS the
    # credential -- so this ceiling is what bounds a stranger with the link, and a bound that
    # waits for the operator to remember a flag is not a bound. setdefault, so a deliberate value
    # still wins.
    env.setdefault("ELENCHUS_MAX_CALLS", str(DEFAULT_MAX_CALLS))
    return env


# ---- supervision --------------------------------------------------------------------------------

_POLL_S = 0.5
_BACKOFF_FIRST_S = 1.0
_BACKOFF_MAX_S = 60.0
# A child that lived at least this long before dying was not crash-looping: its death is a new
# incident, and the next restart starts the backoff over rather than extending it.
_STABLE_S = 60.0


class _Supervised:
    """One child under supervision: what to spawn, and how many times in a row it died young.

    Two of these, the server and the tunnel, with independent counters: a tunnel that cannot
    reach Cloudflare must not slow the server's restarts, and vice versa.
    """

    def __init__(self, name: str, spawn, clock):
        self.name, self._spawn, self._clock = name, spawn, clock
        self.child = None
        self.born = 0.0
        self.fast_deaths = 0
        self.restarts = 0

    def start(self):
        self.child = self._spawn()
        self.born = self._clock()
        return self.child

    def exited(self):
        """The exit code if the child is gone, else None."""
        return self.child.poll()

    def backoff(self) -> tuple[float, float]:
        """(seconds to wait before the next start, seconds the dead child lived).

        Doubles from one second while the child keeps dying inside `_STABLE_S`, capped at a
        minute, and NEVER gives up: a keyless or half-deployed child costs nothing while it
        cannot start, and the moment the cause is fixed it should come back by itself. Giving
        up would recreate the outage this exists for, with a log line on top.
        """
        lived = self._clock() - self.born
        self.fast_deaths = self.fast_deaths + 1 if lived < _STABLE_S else 0
        wait = min(_BACKOFF_FIRST_S * 2 ** max(self.fast_deaths - 1, 0), _BACKOFF_MAX_S)
        return wait, lived


def supervise(
    spawn_server,
    spawn_tunnel,
    *,
    should_stop,
    log,
    sleep=time.sleep,
    clock=time.monotonic,
) -> int:
    """Keep one invitee served until told to stop: the launcher's run loop.

    `spawn_server` and `spawn_tunnel` (None when there is no tunnel) return Popen-like children.
    `should_stop` is the signal handler's flag: when it reads True the loop terminates every
    child and returns the server's exit code, and never restarts anything after it -- a
    deliberate stop must not turn into a fight. `log` takes one line per event.

    `sleep` and `clock` exist so tests/test_serve_invitee.py can run a crash loop in
    milliseconds against fake children; the launcher passes nothing and gets the real ones.
    """
    server = _Supervised("server", spawn_server, clock)
    tunnel = _Supervised("tunnel", spawn_tunnel, clock) if spawn_tunnel is not None else None
    server.start()
    if tunnel is not None:
        tunnel.start()
    units = [u for u in (server, tunnel) if u is not None]

    def wait(seconds: float) -> None:
        # Sliced, so a stop that lands during a 60s backoff wait is honoured within a poll.
        end = clock() + seconds
        while not should_stop():
            remaining = end - clock()
            if remaining <= 0:
                return
            sleep(min(remaining, _POLL_S))

    while not should_stop():
        for unit in units:
            code = unit.exited()
            if code is None:
                continue
            delay, lived = unit.backoff()
            unit.restarts += 1
            log(
                f"{unit.name} exited code={code} after {lived:.0f}s; "
                f"restart #{unit.restarts} in {delay:g}s"
            )
            wait(delay)
            if should_stop():
                break
            child = unit.start()
            log(f"{unit.name} restarted (pid {child.pid})")
        sleep(_POLL_S)

    for unit in reversed(units):  # tunnel first, so no new request lands on a server going down
        unit.child.terminate()
    for unit in units:
        try:
            unit.child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            unit.child.kill()
            unit.child.wait()
    return server.child.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve one invitee's isolated instance.")
    parser.add_argument("slug", help="invitee slug: [a-z0-9-], names <root>/<slug>/")
    parser.add_argument("--root", default="data/tenants", help="tenant root (default %(default)s)")
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default %(default)s)")
    parser.add_argument("--port", type=int, required=True, help="this invitee's own port")
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="also run a cloudflared QUICK tunnel to this port. Founder same-day checks only: "
        "the random hostname dies with this process and a stale link can land on carrier "
        "NXDOMAIN scareware (J's phone, 2026-08-30).",
    )
    parser.add_argument(
        "--hostname",
        default=None,
        help="serve behind a NAMED tunnel at this FQDN on the founders' own domain "
        "(e.g. ada.decisions.example.com). Stable across restarts; a dead link 404s on OUR "
        "name instead of becoming someone else's surface. Needs `cloudflared tunnel login` once.",
    )
    args = parser.parse_args()
    if args.tunnel and args.hostname:
        parser.error("--tunnel (quick, ephemeral) and --hostname (named, stable) are exclusive")

    slug = resolve_slug(args.slug)
    hostname = resolve_hostname(args.hostname) if args.hostname else None
    tunnel_name = f"elenchus-{slug}"

    refusal = missing_key_warning(dict(os.environ), _REPO_ROOT)
    if refusal is not None:
        print(refusal, file=sys.stderr)
        return 3

    if hostname is not None:
        # Preflight BEFORE any file or process exists: the login half is the founders' own
        # (browser OAuth against the Cloudflare account holding the domain) and must fail as an
        # instruction, not a traceback.
        cert = Path(os.environ.get("TUNNEL_ORIGIN_CERT", Path.home() / ".cloudflared" / "cert.pem"))
        if not cert.exists():
            print(
                f"no cloudflared origin certificate at {cert}.\n"
                "The named tunnel needs a one-time login against the Cloudflare account that "
                "holds the domain:\n\n    cloudflared tunnel login\n\n"
                "then re-run this command.",
                file=sys.stderr,
            )
            return 2
        # Idempotent setup: `create` fails if the tunnel already exists and `route dns` fails if
        # the record already exists -- both fine on a relaunch, and a GENUINE misconfiguration
        # still fails loudly at `tunnel run` below, the call that matters.
        subprocess.run(["cloudflared", "tunnel", "create", tunnel_name], check=False)
        subprocess.run(
            ["cloudflared", "tunnel", "route", "dns", tunnel_name, hostname], check=False
        )

    root = Path(args.root)
    tenant = root / slug
    tenant.mkdir(parents=True, exist_ok=True)

    env = build_env(root, slug, args.host, args.port)
    log_path = tenant / "server.log"

    with open(log_path, "ab", buffering=0) as log:

        def spawn_server():
            return subprocess.Popen(
                [sys.executable, "-m", "elenchus.web"], env=env, stdout=log, stderr=log
            )

        spawn_tunnel = None
        if hostname is not None:

            def spawn_tunnel():
                return subprocess.Popen(
                    [
                        "cloudflared",
                        "tunnel",
                        "run",
                        "--url",
                        f"http://localhost:{args.port}",
                        tunnel_name,
                    ]
                )

        elif args.tunnel:

            def spawn_tunnel():
                return subprocess.Popen(
                    ["cloudflared", "tunnel", "--url", f"http://localhost:{args.port}"]
                )

        def note(line: str) -> None:
            # Both places: the tenant log is the durable record the next person greps, and
            # stdout is whoever is watching now. Timestamped, because "restart #3" is only
            # useful next to WHEN.
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            log.write(f"{stamp} [{slug}] supervisor: {line}\n".encode())
            print(f"[{slug}] supervisor: {line}", flush=True)

        stopping = False

        def _stop(signum, frame):  # noqa: ARG001 -- signal signature
            nonlocal stopping
            stopping = True  # the loop terminates the children itself, within one poll

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        print(f"[{slug}] serving on {args.host}:{args.port}, db {env['ELENCHUS_DB']}")
        print(f"[{slug}] stderr -> {log_path}")
        if hostname is not None:
            print(f"[{slug}] named tunnel {tunnel_name}: https://{hostname}")
            print(f"[{slug}] this link is STABLE across restarts; hand out this one.")
        elif args.tunnel:
            print(
                f"[{slug}] QUICK tunnel; hand out the trycloudflare URL it prints. It dies "
                "with this process and a stale link can serve scareware -- founder checks only."
            )
        note("watching; a child that dies is restarted and written down here")
        return supervise(spawn_server, spawn_tunnel, should_stop=lambda: stopping, log=note)


if __name__ == "__main__":
    raise SystemExit(main())
