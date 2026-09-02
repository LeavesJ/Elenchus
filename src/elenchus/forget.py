"""Honoring "please delete what I wrote".

There was no mechanism: no endpoint, no export, no script. Honoring a request meant the founder
removing a directory from memory and hoping nothing else held a copy.

This does not contradict Invariant 4 ("decay demotes, never deletes"). That governs how the ENGINE
treats learner state inside the loop, where forgetting is retrieval failure rather than erasure. A
person asking to be forgotten is a different act: an operator, on request, on that person's own
data.

Deletion is tractable here only because of the per-invitee isolation the beta already rests on --
one process, one directory, one database per person. The whole of someone is two files.

Two real callers: `scripts/forget_invitee.py` and `tests/test_forget.py`.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# The slug is a path COMPONENT, never a path -- and this module DELETES what it resolves to, so
# the rule is load-bearing here in a way it is not in the launcher. Kept identical to
# `serve_invitee.resolve_slug`; if a third caller appears, hoist it rather than copy it again.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class StillServing(RuntimeError):
    """Raised rather than deleting a database something still holds open."""


@dataclass
class ForgetPlan:
    slug: str
    root: Path
    tenant_dir: Path
    paths: list[Path]
    turns: int
    in_use: bool
    by_hand: list[str] = field(default_factory=list)


def _turns(db: Path) -> int:
    """How much of this person is here, for the operator to see BEFORE agreeing to destroy it.
    Best effort: a database too new to have the table, or unreadable, reports 0 rather than
    blocking a deletion the person asked for."""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    try:
        return con.execute("select count(*) from web_sitting_turn").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def _lock_held(db: Path) -> bool:
    """Is a transaction in flight on this database right now?

    NOT sufficient on its own, and the first version of this module thought it was: the server
    opens a connection per call and closes it, so between requests nothing holds a lock at all
    and BEGIN EXCLUSIVE succeeds against a database that is very much being served. Kept as a
    second signal for the case the process scan cannot see.
    """
    try:
        con = sqlite3.connect(db, timeout=0)
    except sqlite3.Error:
        return True  # cannot even open it: treat as in use rather than delete blind
    try:
        con.execute("begin exclusive")
        con.rollback()
        return False
    except sqlite3.OperationalError:
        return True
    finally:
        con.close()


def _process_envs() -> list[str]:
    """Every process's environment on this machine, one process per line. macOS and Linux `ps`
    both print the environment after the command with `-E`/`e`; own-user processes only, which is
    the only user the beta runs as. Unavailable -> empty, and the caller treats empty as "could not
    check" rather than "nothing is serving"."""
    try:
        out = subprocess.run(
            ["ps", "-axEww", "-o", "command="],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return out.splitlines()


_ENV_DB = re.compile(r"ELENCHUS_DB=(\S+)")


def _serving(db: Path, slug: str, process_envs) -> bool:
    """Is a process running whose ELENCHUS_DB names this tenant's database?

    This is the question that actually means "is this invitee being served". Matched two ways:
    the value resolved to a real path equal to ours, OR the value ending in
    `tenants/<slug>/elenchus.db` -- because the live launcher passes a RELATIVE path and a
    process's cwd is not in its environment. The slug is validated to [a-z0-9-], so the suffix is
    unambiguous.
    """
    suffix = f"tenants/{slug}/elenchus.db"
    target = db.resolve()
    for line in process_envs:
        for raw in _ENV_DB.findall(line):
            if raw.endswith(suffix):
                return True
            try:
                if Path(raw).resolve() == target:
                    return True
            except OSError:
                continue
    return False


def plan(root: Path, slug: str, process_envs=None) -> ForgetPlan:
    """What deleting this person would remove, computed before anything is touched.

    `process_envs` is injectable so the "a server is live" case is reproducible in a test; None
    means scan this machine."""
    if not _SLUG_RE.match(slug or ""):
        raise ValueError(
            f"slug {slug!r} is not [a-z0-9-] (max 64, must start alphanumeric). It names a "
            "directory under the tenant root, and this operation deletes what it resolves to."
        )
    root = Path(root)
    tenant = root / "tenants" / slug
    if not tenant.is_dir():
        raise FileNotFoundError(
            f"no tenant directory at {tenant}. Refusing to report a deletion that removed "
            "nothing -- check the slug against the allocation table."
        )

    paths = sorted(p for p in tenant.iterdir() if p.is_file())
    # A tenant database copied into backups during an operational move still holds the person's
    # transcript. A deletion that leaves it there is not a deletion.
    backups = root / "backups"
    if backups.is_dir():
        paths += sorted(p for p in backups.iterdir() if p.is_file() and f"-{slug}." in p.name)

    db = tenant / "elenchus.db"
    envs = _process_envs() if process_envs is None else process_envs
    in_use = db.exists() and (_serving(db, slug, envs) or _lock_held(db))
    return ForgetPlan(
        slug=slug,
        root=root,
        tenant_dir=tenant,
        paths=paths,
        turns=_turns(db) if db.exists() else 0,
        in_use=in_use,
        by_hand=[
            f"Remove the Cloudflare Access application for {slug}.elenchuslab.dev -- it carries "
            "this person's EMAIL ADDRESS in its policy, and this script cannot reach it.",
            "Delete the invite email from your sent folder if it named them.",
            f"Remove {slug} from the invitee allocation table in the session handoff.",
        ],
    )


def execute(plan: ForgetPlan) -> list[Path]:
    """Delete what the plan names. Refuses while anything still holds the database open."""
    if plan.in_use:
        raise StillServing(
            f"{plan.slug}'s database is still open -- stop that invitee's server before deleting, "
            "or you unlink the file out from under a live process and leave it writing to nothing."
        )
    removed = []
    for p in plan.paths:
        if p.exists():
            p.unlink()
            removed.append(p)
    # The directory goes too: an empty tenant dir still looks like a served invitee to the launcher.
    if plan.tenant_dir.is_dir() and not any(plan.tenant_dir.iterdir()):
        plan.tenant_dir.rmdir()
    return removed
