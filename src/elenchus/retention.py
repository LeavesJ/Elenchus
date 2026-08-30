"""Visits, and the retention curve over them.

`web_sitting` cannot count returns. `_SITTING_MAX_IDLE = timedelta(hours=18)`
(`web/session_runner.py`) makes `resume_or_start` RESUME rather than create, so a learner who
came back five times across three days leaves exactly ONE `web_sitting` row. The bias is
inverted: the better retained the learner, the fewer rows they generate, and retention is the
whole product claim. Never derive a curve from `web_sitting` -- it reports 1 where the truth is 5
and it undercounts the most engaged learners hardest.

The instrument is `web_sitting_turn.at`, gap-clustered into visits, which is what this module
does. Two real callers: `scripts/retention_report.py` and `tests/test_retention.py`.

TWO LIMITS, both structural, both of which the reported number has to carry.

1. **The threshold decides the answer.** Four hours apart is one visit at a six-hour gap and two
   at a two-hour gap. There is no principled value; it is chosen by looking at the data. Say so,
   and say it was chosen post hoc -- `report()` prints both.
2. **A silent visit is invisible.** A resume appends no turn: it shows the learner the room they
   were already in. Someone who opens the app, reads their transcript and leaves produces no row
   even WITH `at`. This counts visits where the learner SPOKE, which is a defensible definition
   of a retained visit and is not the same as "opened the app".
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def cluster_visits(stamps: list[datetime], gap: timedelta) -> list[datetime]:
    """Cluster turn times into visits and return the START of each.

    A visit ends when the next turn is at least `gap` away. Sorts first: rows arrive in whatever
    order the query gave them, and a visit is a property of the clock, not of the table.
    """
    ordered = sorted(stamps)
    if not ordered:
        return []
    starts = [ordered[0]]
    for prev, cur in zip(ordered, ordered[1:]):
        if cur - prev >= gap:
            starts.append(cur)
    return starts


def read_visit_starts(db_path: str, gap: timedelta) -> list[datetime]:
    """One invitee's visit starts, read out of their own database file.

    Three failures that must not look alike, because two of them are operator error and only the
    third is a real reading of zero:

    * the path does not exist -> `FileNotFoundError`. A typo'd tenant slug reporting "no visits"
      would be indistinguishable from an invitee who never showed up.
    * the file has no `web_sitting_turn` -> `ValueError`. Pointed at the wrong file entirely.
    * the table has no `at` -> `[]`. A real pre-migration database, honestly empty of the signal.

    Legacy rows with `at IS NULL` are skipped rather than guessed at: the information exists
    nowhere to backfill from, and 293 production turns are in that state.
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(web_sitting_turn)")}
        if not columns:
            raise ValueError(f"{db_path}: no web_sitting_turn table -- not an Elenchus database")
        if "at" not in columns:
            return []
        rows = conn.execute("SELECT at FROM web_sitting_turn WHERE at IS NOT NULL").fetchall()
    finally:
        conn.close()
    return cluster_visits([_parse(row[0]) for row in rows], gap)


def _parse(stamp: str) -> datetime:
    """Read a stored stamp, treating a naive one as UTC.

    Production writes `datetime.now(timezone.utc).isoformat()`, so every row it makes is aware.
    The analysis runs over whatever files exist on the night, though, and ONE naive row among
    aware ones raises "can't compare offset-naive and offset-aware" out of `sorted` -- in the
    middle of the only number the beta produces.
    """
    parsed = datetime.fromisoformat(stamp)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def retention_by_day(
    per_invitee: list[list[datetime]], days: tuple[int, ...]
) -> dict[int, tuple[int, int]]:
    """D-N retention as (returned, denominator) per day.

    An invitee is retained on day N if they have a visit in `[N days, N+1 days)` after their OWN
    first visit. Each invitee's clock starts when they arrive, not when the links went out, so a
    late starter is not scored as a day-one failure.

    An invitee with no visits at all is dropped from the DENOMINATOR, not counted as a failure.
    A database with nothing in it is a delivery failure -- the link never got opened -- and
    folding that into retention makes a distribution problem look like a product problem.
    """
    arrived = [starts for starts in per_invitee if starts]
    out: dict[int, tuple[int, int]] = {}
    for day in days:
        returned = 0
        for starts in arrived:
            low = starts[0] + timedelta(days=day)
            high = starts[0] + timedelta(days=day + 1)
            if any(low <= visit < high for visit in starts):
                returned += 1
        out[day] = (returned, len(arrived))
    return out


def report(db_paths: list[str], gap: timedelta, days: tuple[int, ...]) -> str:
    """The readout, with the caveats attached to the numbers rather than filed beside them.

    The threshold and its post-hoc provenance are printed with the figures on purpose. A
    retention number without its clustering threshold is not a claim anyone can check, and the
    threshold here is chosen by looking at the data it is about to summarise.
    """
    per_invitee = []
    lines = ["Elenchus retention", ""]
    for path in db_paths:
        starts = read_visit_starts(path, gap)
        per_invitee.append(starts)
        first = starts[0].isoformat() if starts else "never arrived"
        lines.append(f"  {Path(path).parent.name or path}: {len(starts)} visits, first {first}")

    lines += ["", f"  gap threshold: {gap}  (CHOSEN POST HOC, after the data existed)", ""]
    by_day = retention_by_day(per_invitee, days)
    for day in days:
        returned, total = by_day[day]
        pct = f"{100 * returned / total:.0f}%" if total else "n/a"
        lines.append(f"  D{day}: {returned}/{total}  {pct}")

    lines += [
        "",
        "  Denominator is invitees who ever spoke; an empty database is a delivery failure,",
        "  not a retention failure. A visit is a burst in which the learner SPOKE -- a resume",
        "  appends no turn, so opening the app and only reading is invisible here.",
        "  Never quote a web_sitting-derived curve: it reports 1 where the truth is 5.",
    ]
    return "\n".join(lines)
