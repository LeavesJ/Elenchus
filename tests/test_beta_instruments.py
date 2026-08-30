"""The beta's measurement instruments, tested before they exist (2026-09-12 beta).

These tests are RED on purpose at the commit that introduces them. Each one pins a defect the
2026-08-29 readiness audit reproduced by execution, and each one is the guard for a spine item in
the two-week plan. Written first, watched fail, per the project's TDD rule.

The defect they share: **retention is the product claim and the schema cannot measure it.**
`web_sitting` is (id, status, updated_at) and `web_sitting_turn` is
(sitting_id, seq, kind, payload_json) -- no per-turn time anywhere. Combined with
`_SITTING_MAX_IDLE = 18h`, which RESUMES rather than creating, the bias is inverted: the better
retained a learner is, the fewer rows they leave behind.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")

from elenchus.web.session_runner import SessionRegistry  # noqa: E402
from elenchus.web.sitting_store import SittingStore  # noqa: E402

_T0 = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)  # a Tuesday, 09:00 UTC


def _rows(db_path, sql: str, *params) -> list[sqlite3.Row]:
    """Read the database the way an analyst would: our own connection, named columns.

    Deliberately not `SittingStore._conn`, which is private and hands back plain tuples.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ---- spine item 2: web_sitting_turn.at ---------------------------------------------------------


def test_append_turn_records_when_the_turn_happened(tmp_path):
    """`append_turn` is already handed `now` and spends it only on `web_sitting.updated_at`
    (sitting_store.py:334-337). The turn itself keeps no time, so a transcript cannot be placed on
    a clock. This is the column the founder signed off as T3 on 2026-08-29.

    Fails today with: no such column: at
    """
    db = tmp_path / "at.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "a decision I am stuck on"}, _T0)

    rows = _rows(db, "SELECT at FROM web_sitting_turn WHERE sitting_id=? ORDER BY seq", sid)

    assert rows, "the turn was not stored at all"
    assert rows[0]["at"] == _T0.isoformat(), "the turn does not carry the time it was handed"


def test_turn_times_survive_a_second_turn_in_the_same_sitting(tmp_path):
    """Two turns an hour apart must be distinguishable in time, not merely in `seq`. Sequence
    ordering already works; it is elapsed time that the retention curve needs and cannot get.
    """
    db = tmp_path / "at2.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "first"}, _T0)
    store.append_turn(sid, "you", {"text": "second"}, _T0 + timedelta(hours=1))

    stamps = [
        r["at"]
        for r in _rows(db, "SELECT at FROM web_sitting_turn WHERE sitting_id=? ORDER BY seq", sid)
    ]

    assert stamps == [_T0.isoformat(), (_T0 + timedelta(hours=1)).isoformat()]


# ---- the finding itself: web_sitting cannot count returns --------------------------------------


def _visits_from_turn_times(db_path, gap: timedelta) -> int:
    """Gap-cluster every turn in the database into visits. This is the analysis the beta's
    retention number depends on, written here as the test's own oracle so the assertion below
    describes the instrument the plan actually calls for."""
    try:
        rows = _rows(db_path, "SELECT at FROM web_sitting_turn WHERE at IS NOT NULL")
    except sqlite3.OperationalError:
        return 0  # no time column: zero visits are recoverable, which is the point
    stamps = sorted(datetime.fromisoformat(r["at"]) for r in rows)
    if not stamps:
        return 0
    visits = 1
    for prev, cur in zip(stamps, stamps[1:]):
        if cur - prev >= gap:
            visits += 1
    return visits


def _age_everything(db_path, by: timedelta) -> None:
    """Push everything that has already happened back by `by` -- sitting AND its turns.

    This is what real elapsed time does. Ageing only `web_sitting.updated_at` is not enough: the
    turns would stay at wall clock and two visits would cluster as one, which is a bug in the
    simulation rather than in the product.

    Injecting `now` into `resume_or_start` does NOT work for this at all. `now` reaches
    `create_sitting`, which stamps it correctly, but is dropped before the internal `append_turn`,
    which re-stamps `updated_at` from the wall clock. So an injected-time test silently compares a
    2026-09 `now` against a wall-clock `updated_at`, always exceeds the idle bound, and always
    creates a fresh sitting -- measuring nothing. One field written by two writers under different
    preconditions (project lesson L-32), and the reason no existing test covers the 18h window.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT id, updated_at FROM web_sitting").fetchall()
        for sid, updated_at in rows:
            aged = (datetime.fromisoformat(updated_at) - by).isoformat()
            conn.execute("UPDATE web_sitting SET updated_at=? WHERE id=?", (aged, sid))
        for rowid, at in conn.execute(
            "SELECT rowid, at FROM web_sitting_turn WHERE at IS NOT NULL"
        ).fetchall():
            aged = (datetime.fromisoformat(at) - by).isoformat()
            conn.execute("UPDATE web_sitting_turn SET at=? WHERE rowid=?", (aged, rowid))
        conn.commit()
    finally:
        conn.close()


def test_a_return_inside_the_idle_window_is_not_a_new_sitting_row(tmp_path, make_fake):
    """THE headline defect, driven at the boundary rather than asserted.

    `_SITTING_MAX_IDLE = timedelta(hours=18)` (session_runner.py:533) makes `resume_or_start`
    RESUME rather than create. Swept: gaps of 1h, 12h and 17h all collapse into ONE `web_sitting`
    row; 19h and 30h create a second. So a learner who comes back the same evening, or the next
    morning, leaves no new row -- and a daily-practice learner leaves the fewest rows of anyone.
    That is the wrong way round for a retention engine.

    The fix is not a person column on `web_sitting`. It is a time on each TURN, gap-clustered into
    visits, which is what this test asserts and what the founder signed off on 2026-08-29.

    KNOWN LIMIT of that fix, found while writing this test: a resume appends NO turn -- it shows
    the learner the room they were already in. So a visit where somebody opens the app, reads their
    transcript and leaves is invisible even WITH `at`. Turn times count visits where the learner
    SPOKE, which is a defensible definition of a retained visit but is not the same as "opened the
    app", and the beta's reported number must say which one it is. Stamping the resume itself is a
    separate decision, deliberately not taken here.
    """
    db = tmp_path / "ret.db"
    reg = SessionRegistry(str(db), model_factory=make_fake)

    reg.resume_or_start("single")  # visit one
    reg.step("single", "the thing I am actually stuck on")
    _age_everything(db, timedelta(hours=12))
    reg.resume_or_start("single")  # visit two, twelve hours later
    reg.step("single", "coming back to it the same evening")

    sittings = _rows(db, "SELECT COUNT(*) AS n FROM web_sitting")[0]["n"]
    assert sittings == 1, (
        f"expected the collapse this test documents, got {sittings} sittings; the idle-window "
        "behaviour changed and this test's premise needs rechecking"
    )

    assert _visits_from_turn_times(db, timedelta(hours=6)) == 2, (
        "two visits twelve hours apart are not recoverable from the store: web_sitting holds "
        "1 row for both, and the turns do not separate them"
    )


# ---- spine item 4: the single-flight guard ------------------------------------------------------


class _Slow:
    """A model whose every call takes real time, so two requests genuinely overlap.

    The scripted fake answers in microseconds, which is the one condition under which this class
    of bug hides: thread A finishes before thread B starts and nothing races. Production is never
    that fast (39.9 calls and ~$0.89 a sitting against Opus 5), so the delay restores the real
    shape rather than inventing one.
    """

    def __init__(self, inner: object, delay: float) -> None:
        self._inner = inner
        self._delay = delay

    def __getattr__(self, name: str):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def slowed(*args, **kwargs):
            time.sleep(self._delay)
            return attr(*args, **kwargs)

        return slowed


def _slow_factory(inner_factory, delay: float):
    return lambda: _Slow(inner_factory(), delay)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN, UNFIXED: no single-flight guard. Recorded rather than fixed because the fix is "
        "T2 (it adds learner-facing rejection copy) and wants an independent reviewer, and "
        "because nothing can hit it yet -- zero sittings since 2026-07-30, beta no earlier than "
        "2026-09-05. Scheduled Mon 2026-09-01, reviewed Tue. strict=True: the day someone lands "
        "the guard this test FAILS as an unexpected pass and forces this marker off."
    ),
)
def test_two_overlapping_says_never_stack_two_learner_turns(tmp_path, make_fake):
    """The splice, reproduced with ONE person, ONE process, ONE database: two overlapping `/say`
    calls produce two consecutive `you` rows with no push between, and the sitting then CONVERGES
    on the splice -- writing web_converged, frames and ledger rows off corrupted input.

    XFAIL, NOT SKIP, NOT FIXED. The transcript really does come back
    `['vera', 'you', 'you', 'vera', 'vera']`, deterministically. This marker records a live defect
    in the suite's own vocabulary; it does not repair it, and the gate going green does not mean
    the product is safe to put a second concurrent request in front of.

    `_stepping` (session_runner.py:717) is a COUNTER by design, for the drain/reap guard; its own
    comment says overlapping requests must not unmark each other. So single-flight is NEW work,
    not a broken guard, and the fix is additive.

    Per-invitee isolation does not reach this. It is per-device: a double-click on a slow response
    is enough. The guard must span `append_turn` (:2048) as well as the put/get pair, or the
    doubled `you` row survives the fix.

    Overlap is forced rather than hoped for. The scripted fake answers instantly, so a plain
    "start two threads" version passes roughly half the time by luck -- A finishes before B begins.
    `_Slow` gives every model call a real duration, which is the production condition anyway: the
    audit reproduced this against a 1.2s model, and a human double-clicking a slow answer is the
    whole scenario.
    """
    import threading

    db = tmp_path / "splice.db"
    reg = SessionRegistry(str(db), model_factory=_slow_factory(make_fake, 0.25))
    reg.resume_or_start("single")

    crashes: list[BaseException] = []

    def say(text: str) -> None:
        try:
            reg.step("single", text)
        except Exception as exc:  # a REJECTION is the pass condition; only a crash fails
            crashes.append(exc)

    a = threading.Thread(target=say, args=("the first thing I typed",))
    a.start()
    # Wait until the registry itself reports A in flight, then overlap it.
    deadline = time.monotonic() + 15
    while reg._stepping.get("single", 0) < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert reg._stepping.get("single", 0) >= 1, "thread A never registered as in flight"
    b = threading.Thread(target=say, args=("the second thing, sent too fast",))
    b.start()
    a.join(timeout=60)
    b.join(timeout=60)

    store = SittingStore(str(db))
    live = store.live_sitting()
    assert live is not None, "the sitting vanished under concurrent steps"
    kinds = [t["kind"] for t in store.turns(live["id"])]

    doubled = [i for i in range(len(kinds) - 1) if kinds[i] == kinds[i + 1] == "you"]
    assert not doubled, (
        f"two learner turns were spliced together with no push between them at {doubled}; "
        f"transcript kinds were {kinds}"
    )


# ---- spine item 3: web_content_gap.sitting_id --------------------------------------------------


def _gap_shape_a461fd(reg, sid: str) -> None:
    """Drive the front door the way the founder's 2026-07-29 sitting actually went: an opening,
    ONE substantive correction, then two bare rejections that hit `_MAX_BARE_REJECTIONS`.

    The words are synthetic. The real ones are 188 characters of the founder's own equity split
    and live only in the gitignored `data/` (Invariant 9); the SHAPE is what this replays, and it
    was read off `web_sitting_turn` for sitting `...-a461fd` seqs 2/6/8/10.

    That shape reaches the cap through the `bare` counter while `corrections == 1`, which is a
    DIFFERENT branch from the two-substantive-corrections case the existing gap tests drive
    (test_session_runner.py). Verified by execution 2026-08-29 against a scratch copy of the real
    turns: the row lands and holds the CORRECTED words, not the untouched opening.
    """
    reg.step(sid, "Founder equity split")
    reg.step(sid, "no. Again it is about settling the split with my cofounder before we file")
    reg.step(sid, "no")
    reg.step(sid, "no")


def test_a_content_gap_records_which_sitting_produced_it(tmp_path):
    """Twelve gap rows with no sitting cannot distinguish twelve people each missing a territory
    from one frustrated person correcting twelve times, and those two readings prescribe opposite
    content. It is the only genuinely NOT-BACKFILLABLE column in the plan: a row written without
    it can never be attributed afterwards, so it has to land before the first invitee.

    Fails today with: no such column: sitting_id
    """
    from conftest import make_world_model

    db = tmp_path / "gap-sitting.db"
    reg = SessionRegistry(str(db), model_factory=make_world_model)
    reg.start("s1", now=_T0)
    _gap_shape_a461fd(reg, "s1")

    live = SittingStore(str(db)).live_sitting()
    assert live is not None, "the sitting vanished before the gap was logged"
    rows = _rows(db, "SELECT sitting_id, corrected FROM web_content_gap")

    assert len(rows) == 1, f"the cap did not record a content gap at all: {rows}"
    assert rows[0]["corrected"] == 1
    assert rows[0]["sitting_id"] == live["id"], (
        "the gap row cannot be attributed to the sitting that produced it"
    )


def test_gap_rows_written_before_the_column_keep_their_place(tmp_path):
    """The defensive-migration half, and the reason this is T1 rather than T3: production holds
    ZERO `web_content_gap` rows (verified 2026-08-29), so the ALTER migrates nothing. Any OTHER
    database that already has rows must still open, keep them, and read NULL for the sitting they
    came from -- the same stance `outcome` and legacy `at` take, because the information exists
    nowhere to backfill from.
    """
    db = tmp_path / "gap-legacy.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE web_content_gap ("
        "situation TEXT NOT NULL, mapped_eid TEXT NOT NULL, confidence TEXT NOT NULL, "
        "verdict TEXT NOT NULL, corrected INTEGER NOT NULL, at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO web_content_gap VALUES (?,?,?,?,?,?)",
        ("a situation nobody could serve", "some_eid", "high", "decision", 1, _T0.isoformat()),
    )
    conn.commit()
    conn.close()

    SittingStore(str(db))  # opening it is the migration

    rows = _rows(db, "SELECT situation, sitting_id FROM web_content_gap")
    assert len(rows) == 1, "the pre-existing gap row did not survive the migration"
    assert rows[0]["situation"] == "a situation nobody could serve"
    assert rows[0]["sitting_id"] is None, "a legacy row must not be attributed to a guess"
