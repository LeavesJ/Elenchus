"""What the model calls cost, and how often they were refused, read off the tenant logs.

    PYTHONPATH=src .venv/bin/python scripts/call_report.py data/tenants

Walks `<root>/<slug>/server.log`, parses the `model_call` timing lines and the
`model refusal in ...` lines the server wrote, and prints the per-kind latency tail plus the
refusal tally with the limits each inherits.

This is the read half of the S4 measurement: the sittings emit, this reports, and the client
timeout gets PICKED from what came out rather than guessed. The measurement is worthless without
it -- before this existed the 9am dogfood would have produced a log file nothing read.

Read-only by construction: opens every file for text reading and writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from elenchus.call_log import parse_calls, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Model-call latency + refusal tally per invitee.")
    parser.add_argument("root", help="directory holding <slug>/server.log per invitee")
    parser.add_argument(
        "--per-invitee",
        action="store_true",
        help="also print a separate block per invitee, not just the pooled one",
    )
    args = parser.parse_args()

    root = Path(args.root)
    logs = sorted(root.glob("*/server.log"))
    if not logs:
        # Loud, never a quiet zero: a typo'd root reporting "0 calls" is indistinguishable from a
        # real reading of zero, and only one of those means the measurement did not happen.
        print(f"no <slug>/server.log files under {root}", file=sys.stderr)
        return 2

    pooled = parse_calls(line for p in logs for line in p.read_text(errors="replace").splitlines())
    print(report(pooled, sources=[str(p) for p in logs]))

    if args.per_invitee:
        for p in logs:
            print()
            print(report(parse_calls(p.read_text(errors="replace").splitlines()), sources=[str(p)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
