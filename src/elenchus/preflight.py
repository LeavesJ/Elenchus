"""What is true of the MACHINE at the moment a link goes out.

The gate reads the repository. Everything that has actually broken this deployment was true of the
host instead: a keyless origin, a world-readable key, a stray directory server on the wifi, a
production tree replicated to iCloud. A clean tree said nothing about any of them, and neither did
semgrep, correctly -- none of those defects are in the code.

Reported per axis and never collapsed to a bool (L-28: a go/no-go that projects a multi-axis gate
onto a pass-bool discards exactly the signal the gate exists to surface). `fail` means do not send
this link. `warn` means known and accepted; it is printed, and it does not stop a launch.
"""

from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from pathlib import Path

# The macOS "Desktop & Documents Folders" container. Membership here is what matters, never how a
# path is spelled -- see tests/test_preflight.py for the miss that produced this rule.
DEFAULT_SYNC_CONTAINERS = (Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs",)

# Files whose exposure is not recoverable by rotating something cheap.
_SENSITIVE = (".env", "elenchus.db", "server.log")


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str


def sync_exposure(repo: Path, sync_containers=DEFAULT_SYNC_CONTAINERS) -> Check:
    """Is a sensitive file from `repo` inside a cloud-sync container?

    Decided on RESOLVED paths, for two reasons that each produced a false clean here:

    * Spelling. macOS "Desktop & Documents" sync leaves the working path as an ordinary
      `~/Documents/...`, so testing whether the path CONTAINS "iCloud" returns a confident clean
      over a live paid key.
    * Symlinks. The container reaches the real tree through a symlink
      (`com~apple~CloudDocs/Documents -> ~/Documents`), and `Path.rglob` does not follow symlinks
      while recursing -- so walking the container finds nothing at all.

    Resolving both sides answers the only question that matters: does this file's real location
    sit underneath a container's real location, however either is spelled or linked.
    """
    # The container itself AND each immediate child, both resolved: on macOS the entry that
    # reaches the real tree is a symlink one level DOWN
    # (`com~apple~CloudDocs/Documents -> ~/Documents`), so resolving only the container top finds
    # nothing and reports a clean.
    real_containers = []
    for container in sync_containers:
        c = Path(container)
        if not c.exists():
            continue
        real_containers.append(c.resolve())
        try:
            real_containers.extend(child.resolve() for child in c.iterdir())
        except OSError:
            pass  # unreadable container: the entries below still cover the direct case

    exposed = []
    for name in _SENSITIVE:
        for candidate in [
            repo / name,
            *repo.glob(f"data/{name}"),
            *repo.glob(f"data/tenants/*/{name}"),
        ]:
            if not candidate.exists():
                continue
            real = candidate.resolve()
            if any(real == c or c in real.parents for c in real_containers):
                exposed.append(candidate.name)

    if not exposed:
        return Check("sync-exposure", "ok", "no sensitive file resolves inside a sync container")
    return Check(
        "sync-exposure",
        "fail",
        f"replicated to a cloud sync container: {', '.join(sorted(set(exposed)))}. A key there is "
        "on every device on the Apple ID; a tenant database there breaks the front door's own "
        "privacy promise.",
    )


def file_modes(paths) -> Check:
    """Owner-only, or say which file is not and what its mode actually is.

    A file that is MISSING is a `warn`, never an `ok`: a typo'd path that inspects nothing reads
    identically to a path that was inspected and found clean, and only one of those means the
    check ran.
    """
    loose, missing = [], []
    for p in paths:
        p = Path(p)
        if not p.exists():
            missing.append(str(p))
            continue
        mode = stat.S_IMODE(p.stat().st_mode)
        if mode & 0o077:
            loose.append(f"{p.name} is {mode:o}")
    if loose:
        return Check("file-modes", "fail", "group/world readable: " + ", ".join(loose))
    if missing:
        return Check(
            "file-modes", "warn", "not found, so nothing was checked: " + ", ".join(missing)
        )
    return Check("file-modes", "ok", "every named file is owner-only")


# An lsof LISTEN line's address sits in the NAME column: `*:8795`, `127.0.0.1:9401`, `[::1]:20241`.
_LISTEN = re.compile(r"(\S+):(\d+)\s+\(LISTEN\)")
_LOOPBACK = ("127.0.0.1", "[::1]", "localhost")


# macOS and consumer apps bind these to every interface by design. They are named rather than
# hidden -- they ARE reachable from the same wifi as an invitee link -- but they do not block a
# launch. The project's own secret-scan carries the rule this follows: "A scanner that cries wolf
# is turned off within a week, so the exclusions are the load-bearing half." The first run of this
# check reported AirPlay, Spotify and rapportd beside the real finding, which is how a check gets
# ignored.
_KNOWN_SERVICES = frozenset(
    {"rapportd", "ControlCe", "ControlCenter", "Spotify", "sharingd", "AirPlayXPCH", "identityse"}
)


def open_listeners(lsof_lines) -> Check:
    """Anything bound off loopback is reachable by everyone on the current network.

    Takes the lines rather than shelling out, so the interesting case is reproducible in a test
    instead of only on a laptop that happens to have a stray server running on it.
    """
    unknown, known = [], []
    for line in lsof_lines:
        m = _LISTEN.search(line)
        if not m:
            continue
        addr, port = m.group(1), m.group(2)
        if addr in _LOOPBACK:
            continue
        command = line.split()[0] if line.split() else "?"
        (known if command in _KNOWN_SERVICES else unknown).append(f"{command} on {addr}:{port}")

    tail = ""
    if known:
        tail = (
            " (also listening, known system services, not blocking: "
            + ", ".join(sorted(set(known)))
            + ")"
        )
    if unknown:
        return Check(
            "open-listeners",
            "fail",
            "reachable by anyone on this network: " + ", ".join(sorted(set(unknown))) + tail,
        )
    if known:
        return Check(
            "open-listeners",
            "warn",
            "only known system services are off loopback: " + ", ".join(sorted(set(known))),
        )
    return Check("open-listeners", "ok", "every listener is loopback-only")


def public_surface(access_configured: bool) -> Check:
    """Whether anything stands between the hostname and the learner's room.

    Every route in `web/app.py` is unauthenticated and `_SID` is the constant "single", so an
    empty `POST /api/session` returns the live sitting -- the previous learner's whole transcript
    -- to whoever asks, and the same door spends the founders' key on every turn. The hostname is
    the only credential, and hostnames get forwarded, land in browser sync, and appear in
    certificate transparency logs.

    This cannot reach Cloudflare's control plane, so a True here is an ATTESTATION and is reported
    as a warn rather than an ok. A green this function did not measure would be exactly the
    gate-times-distribution error Invariant 7 names.
    """
    if not access_configured:
        return Check(
            "public-surface",
            "fail",
            "no authentication in front of the hostname: an empty POST /api/session returns the "
            "live transcript, and every turn spends the paid key. Put Cloudflare Access "
            "(one-time PIN to the invitee's email) on this hostname before sending the link.",
        )
    return Check(
        "public-surface",
        "warn",
        "Cloudflare Access attested by the operator, NOT verified here -- this check cannot reach "
        "the Cloudflare control plane. Confirm in the Zero Trust dashboard.",
    )


def launch_blocked(checks) -> bool:
    return any(c.status == "fail" for c in checks)


_MARK = {"ok": "ok  ", "warn": "WARN", "fail": "FAIL"}


def report(checks) -> str:
    """Every axis by name, including the ones that passed. A reader who cannot see what was
    checked cannot tell a clean run from a run that skipped the interesting half."""
    lines = ["PREFLIGHT — what is true of this machine right now", ""]
    for c in checks:
        lines.append(f"  [{_MARK.get(c.status, c.status)}] {c.name}")
        lines.append(f"         {c.detail}")
    lines.append("")
    if launch_blocked(checks):
        lines.append("DO NOT SEND A LINK: at least one axis is FAIL above.")
    else:
        lines.append("No blocking axis. WARN lines are known and accepted, not measured clean.")
    return "\n".join(lines)
