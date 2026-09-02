"""Delete one invitee, on their request.

    PYTHONPATH=src .venv/bin/python scripts/forget_invitee.py <slug> --root data/tenants/..
    PYTHONPATH=src .venv/bin/python scripts/forget_invitee.py <slug> --confirm

Prints what would go and deletes NOTHING unless `--confirm` is passed. Refuses outright while
anything still holds that invitee's database open.

The `--root` is the directory CONTAINING `tenants/` (and `backups/`), not the tenants directory
itself -- on this machine that is `~/.local/share/elenchus/data`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from elenchus.forget import StillServing, execute, plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete one invitee's data, on request.")
    parser.add_argument("slug", help="the invitee's slug")
    parser.add_argument(
        "--root",
        default=str(Path.home() / ".local" / "share" / "elenchus" / "data"),
        help="directory containing tenants/ and backups/ (default %(default)s)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="actually delete. Without this the run is a dry run and touches nothing.",
    )
    args = parser.parse_args()

    try:
        p = plan(Path(args.root), args.slug)
    except (ValueError, FileNotFoundError) as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2

    print(f"FORGET {p.slug}")
    print(f"  transcript turns on record: {p.turns}")
    print("  files that would be deleted:")
    for path in p.paths:
        print(f"    {path}")
    print(f"    {p.tenant_dir}/  (the directory itself)")
    print()
    print("  THIS SCRIPT CANNOT DO THESE -- do them by hand:")
    for step in p.by_hand:
        print(f"    - {step}")
    print()

    if not args.confirm:
        print("DRY RUN: nothing was deleted. Re-run with --confirm to actually delete.")
        return 0

    try:
        removed = execute(p)
    except StillServing as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 3

    print(f"DELETED {len(removed)} file(s) and {p.tenant_dir}")
    print("The by-hand steps above are still outstanding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
