"""What is true of this machine right now, run before a link goes out.

    PYTHONPATH=src .venv/bin/python scripts/preflight.py [--repo .] [--access-configured]

The project's gate reads the repository and every one of its checks passed while the beta served
keyless for seventeen hours, a live paid key sat at mode 644 and inside iCloud, and an unrelated
directory server published strategy documents to the campus wifi for thirty-five hours. Semgrep's
security-audit and secrets rulesets over the same tree report zero findings, correctly: none of
those defects are in the code. This is the missing tier.

Exit 1 when any axis is FAIL. A WARN is printed and does not block.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # serve_invitee lives beside this

from elenchus.preflight import (  # noqa: E402
    Check,
    file_modes,
    launch_blocked,
    open_listeners,
    public_surface,
    report,
    sensitive_files,
    sync_exposure,
)


def key_reachable(repo: Path) -> Check:
    """Can a launch from HERE actually reach a key? Uses the launcher's OWN resolver rather than
    a second copy of the logic -- two copies of "where does the key come from" is precisely how
    the beta came up keyless: the guard read one root and the child read another."""
    from serve_invitee import resolve_key

    import os

    if resolve_key(dict(os.environ), repo) is None:
        return Check(
            "key-reachable",
            "fail",
            f"no ANTHROPIC_API_KEY in the environment and none in {repo}/.env. A launch from here "
            "health-checks green and every door dies on the first click.",
        )
    return Check("key-reachable", "ok", "a launch from this directory resolves a key")


def main() -> int:
    parser = argparse.ArgumentParser(description="Host-state checks before an invitee link.")
    parser.add_argument("--repo", default=".", help="repo root the launcher will run from")
    parser.add_argument(
        "--access-configured",
        action="store_true",
        help="attest that Cloudflare Access fronts the invitee hostnames. NOT verified here.",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    import os

    from serve_invitee import DEFAULT_ENV_FILE

    key_file = Path(os.environ.get("ELENCHUS_ENV_FILE") or DEFAULT_ENV_FILE)
    sensitive = sensitive_files(repo, key_file=key_file if key_file.exists() else None)

    try:
        proc = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            # lsof exits non-zero when it fails AND when it simply found nothing; either way
            # its output is not a measurement (pre-merge review, 2026-09-02). Loud, never ok.
            raise subprocess.SubprocessError(f"lsof exited {proc.returncode}")
        listeners = open_listeners(proc.stdout.splitlines())
    except (OSError, subprocess.SubprocessError) as exc:
        # A check that could not run is not a check that passed.
        listeners = Check(
            "open-listeners", "warn", f"could not run lsof, so nothing was checked: {exc}"
        )

    checks = [
        sync_exposure(repo),
        file_modes(sensitive),
        listeners,
        key_reachable(repo),
        public_surface(args.access_configured),
    ]
    print(report(checks))
    return 1 if launch_blocked(checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
