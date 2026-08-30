"""The beta's number, read off the tenant files.

    PYTHONPATH=src .venv/bin/python scripts/retention_report.py data/tenants [--gap-hours 6]

Walks `<root>/<slug>/elenchus.db`, gap-clusters each invitee's `web_sitting_turn.at` stamps into
visits, and prints the D1/D7 curve with its caveats attached. The threshold is a flag because it
IS the analysis: `elenchus.retention.report` prints whatever value was chosen and says it was
chosen post hoc, which is the honest shape of this number (Invariant 7).

Read-only by construction: `read_visit_starts` opens every file `mode=ro`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from elenchus.retention import report


def main() -> int:
    parser = argparse.ArgumentParser(description="Visit clustering + D1/D7 over tenant files.")
    parser.add_argument("root", help="directory holding <slug>/elenchus.db per invitee")
    parser.add_argument(
        "--gap-hours",
        type=float,
        default=6.0,
        help="visit-clustering threshold (default %(default)s; the report discloses it)",
    )
    args = parser.parse_args()

    root = Path(args.root)
    dbs = sorted(str(p) for p in root.glob("*/elenchus.db"))
    if not dbs:
        print(f"no <slug>/elenchus.db files under {root}", file=sys.stderr)
        return 2
    print(report(dbs, timedelta(hours=args.gap_hours), (1, 7)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
