"""Where this process serves from, and which learner's database it opens.

Split out of `__main__` because that module builds the app at import time, so its constants can
only be read by reloading it -- which would open the real production database inside a test run.
Two callers: `__main__` at startup, and `tests/test_web_runtime_config.py`.

The beta ships one process and one database file per invitee. That makes `_SID = "single"`
(app.py:14), the `ux_web_sitting_live` partial index and the unscoped store reads all CORRECT
rather than broken, because "the live sitting" is unambiguous when the file holds one person. It
is also why a misconfiguration here is not a degraded experience but a privacy incident: two
people on one file are one learner, and neither of them can be separated out afterwards.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger("elenchus.web.runtime")

_ROOT = Path(__file__).resolve().parents[3]

# The founder's own instance must not move when this lands: the variables are override-only.
DEFAULT_DB = str(_ROOT / "data" / "elenchus.db")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# Addresses that serve nobody but this machine. Anything else is serving other people.
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", ""})


def resolve_runtime(env) -> tuple[str, str, int]:
    """Return (db_path, host, port) from the environment, or raise before the server starts.

    Raises ValueError rather than falling back, because every fallback available here is worse
    than not starting: a defaulted database serves the founder's own 19 sittings to a stranger,
    and a defaulted port silently collides two invitees onto one process.
    """
    host = (env.get("ELENCHUS_HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST
    db = (env.get("ELENCHUS_DB") or "").strip() or DEFAULT_DB

    # Keyed on the VALUE, never on how it arrived. The danger this guard exists for is "an
    # invitee is being served the founder's own file", and that file holds one particular
    # person's decisions whether the path was defaulted or typed out in full. Keying on the
    # variable being EMPTY meant `ELENCHUS_DB=<the default>` -- one copy-paste of the founder's
    # own launch line -- passed in total silence on ANY bind address, while leaving it unset on
    # the same address raised (two-instance isolation audit, 2026-08-31). `resolve()` because
    # the live beta runs a RELATIVE ELENCHUS_DB, so a string compare would miss most spellings
    # of the same file.
    if Path(db).resolve() == Path(DEFAULT_DB).resolve():
        if host not in _LOOPBACK:
            raise ValueError(
                f"refusing to serve {host} out of the default database. Binding a non-loopback "
                f"address means serving other people, and {DEFAULT_DB} holds one particular "
                "person's decisions. Set ELENCHUS_DB to this invitee's own file."
            )
        # Permitted -- the founder's own loopback boot must keep working -- but LOUD (S6 T2
        # review): the refusal above keys on bind address, and a tunnel pointed at loopback
        # presents loopback, so a default boot behind a tunnel serves the founder's own file to
        # a remote invitee while the front door promises "this invite's own private file".
        _log.warning(
            "serving the default database (%s). Do not put a tunnel in front of this instance: "
            "set ELENCHUS_DB to the invitee's own file first.",
            DEFAULT_DB,
        )

    raw_port = (env.get("ELENCHUS_PORT") or "").strip()
    if not raw_port:
        return db, host, DEFAULT_PORT
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(
            f"ELENCHUS_PORT is not a number: {raw_port!r}. Not falling back to {DEFAULT_PORT}, "
            "because a typo that quietly reuses the default port puts two invitees in one process."
        ) from exc
    return db, host, port
