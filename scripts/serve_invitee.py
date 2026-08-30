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
from pathlib import Path

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


def build_env(root: Path, slug: str, host: str, port: int, base: dict | None = None) -> dict:
    """The three isolation variables `runtime.resolve_runtime` requires, over the caller's own
    environment. The db path is always `<root>/<slug>/elenchus.db`: the per-file isolation IS the
    privacy argument, so the launcher offers no way to point two slugs at one file."""
    env = dict(base if base is not None else os.environ)
    env["ELENCHUS_DB"] = str(root / slug / "elenchus.db")
    env["ELENCHUS_HOST"] = host
    env["ELENCHUS_PORT"] = str(port)
    return env


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
    children: list[subprocess.Popen] = []

    with open(log_path, "ab", buffering=0) as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "elenchus.web"], env=env, stdout=log, stderr=log
        )
        children.append(server)
        print(f"[{slug}] serving on {args.host}:{args.port}, db {env['ELENCHUS_DB']}")
        print(f"[{slug}] stderr -> {log_path}")

        if hostname is not None:
            tunnel = subprocess.Popen(
                [
                    "cloudflared",
                    "tunnel",
                    "run",
                    "--url",
                    f"http://localhost:{args.port}",
                    tunnel_name,
                ]
            )
            children.append(tunnel)
            print(f"[{slug}] named tunnel {tunnel_name}: https://{hostname}")
            print(f"[{slug}] this link is STABLE across restarts; hand out this one.")
        elif args.tunnel:
            tunnel = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{args.port}"]
            )
            children.append(tunnel)
            print(
                f"[{slug}] QUICK tunnel; hand out the trycloudflare URL it prints. It dies "
                "with this process and a stale link can serve scareware -- founder checks only."
            )

        def _stop(signum, frame):  # noqa: ARG001 -- signal signature
            for child in children:
                child.terminate()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)
        code = server.wait()
        for child in children[1:]:
            child.terminate()
            child.wait(timeout=10)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
