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


def test_two_overlapping_says_never_stack_two_learner_turns(tmp_path, make_fake):
    """The splice, reproduced with ONE person, ONE process, ONE database: two overlapping `/say`
    calls produce two consecutive `you` rows with no push between, and the sitting then CONVERGES
    on the splice -- writing web_converged, frames and ledger rows off corrupted input.

    Was `xfail(strict=True)` from 2026-08-29 until the guard landed 2026-08-30; the transcript
    really did come back `['vera', 'you', 'you', 'vera', 'vera']`, deterministically. The marker
    came off in the same commit as the fix, which is what strict=True is for.

    `_stepping` (session_runner.py:717) is a COUNTER by design, for the drain/reap guard; its own
    comment says overlapping requests must not unmark each other, and two readers do pure
    membership tests on it. So single-flight is NEW work over its own structure, not a repair of
    that one, and the fix is additive.

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


def test_the_refused_say_says_so_and_leaves_no_trace(tmp_path, make_fake):
    """Rejecting is only half of it. The learner's second message must NOT reach the transcript,
    and she must be TOLD it did not, or she watches her own words vanish and assumes they landed.

    The guard therefore sits ABOVE `append_turn` (session_runner.py:2049), not around the
    put/get pair. A guard around the channel alone still writes the doubled `you` row, which is
    the row the measurement is made of.
    """
    import threading

    db = tmp_path / "refused.db"
    reg = SessionRegistry(str(db), model_factory=_slow_factory(make_fake, 0.25))
    reg.resume_or_start("single")

    first, second = "the first thing I typed", "the second, sent far too fast"
    out: dict[str, tuple] = {}

    def say(name: str, text: str) -> None:
        out[name] = reg.step("single", text)

    a = threading.Thread(target=say, args=("a", first))
    a.start()
    deadline = time.monotonic() + 15
    while reg._stepping.get("single", 0) < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert reg._stepping.get("single", 0) >= 1, "thread A never registered as in flight"
    b = threading.Thread(target=say, args=("b", second))
    b.start()
    a.join(timeout=60)
    b.join(timeout=60)

    assert out["b"][0] == "nudge", f"the overlapping request was not refused: {out['b']}"
    assert out["b"][1]["message"], "refused with an empty message"

    store = SittingStore(str(db))
    live = store.live_sitting()
    assert live is not None
    said = [t["payload"].get("text") for t in store.turns(live["id"]) if t["kind"] == "you"]
    assert first in said, "the request that DID get the turn lost its text"
    assert second not in said, (
        f"the refused text reached the transcript anyway: {said}; the guard is below append_turn"
    )


def test_a_second_thread_is_refused_but_the_same_thread_may_re_enter(tmp_path, make_fake):
    """The scope question, unit-level. `choose()` calls `step()` (session_runner.py:2124) and
    both write learner turns, so a guard that refuses on identity alone would make every door
    click refuse ITSELF. Re-entrancy is per THREAD, and it has to nest, because the outer claim
    must survive the inner release."""
    import threading

    reg = SessionRegistry(str(tmp_path / "claim.db"), model_factory=make_fake)

    assert reg._claim_turn("single") is True
    assert reg._claim_turn("single") is True, "the owning thread must be able to re-enter"

    refused: list[bool] = []
    other = threading.Thread(target=lambda: refused.append(reg._claim_turn("single")))
    other.start()
    other.join(timeout=10)
    assert refused == [False], "a second thread got in while the first held the turn"

    reg._release_turn("single")  # inner
    still_held: list[bool] = []
    t2 = threading.Thread(target=lambda: still_held.append(reg._claim_turn("single")))
    t2.start()
    t2.join(timeout=10)
    assert still_held == [False], "the inner release dropped the OUTER claim"

    reg._release_turn("single")  # outer
    freed: list[bool] = []
    t3 = threading.Thread(target=lambda: freed.append(reg._claim_turn("single")))
    t3.start()
    t3.join(timeout=10)
    assert freed == [True], "the turn was never released"


def test_a_refresh_during_an_in_flight_turn_still_resumes(tmp_path, make_fake):
    """The guard must NOT cover the page load. `resume_or_start` is what a refresh calls, and the
    stale-tab rule (spec 2c) makes refresh the documented way out of every wedged state -- the
    two other nudges in this file both say "refresh to pick up where you left off". A guard that
    refused a refresh while a slow turn was in flight would break the product's own escape hatch
    at exactly the moment a learner reaches for it."""
    import threading

    db = tmp_path / "refresh.db"
    reg = SessionRegistry(str(db), model_factory=_slow_factory(make_fake, 0.25))
    reg.resume_or_start("single")

    def say() -> None:
        reg.step("single", "something slow")

    a = threading.Thread(target=say)
    a.start()
    deadline = time.monotonic() + 15
    while reg._stepping.get("single", 0) < 1 and time.monotonic() < deadline:
        time.sleep(0.001)
    assert reg._stepping.get("single", 0) >= 1

    tag, _ = reg.resume_or_start("single")
    a.join(timeout=60)

    assert tag != "nudge", "a refresh mid-turn was refused; the guard is scoped too wide"


def test_every_learner_turn_write_is_behind_the_guard():
    """The claim is "two overlapping requests never stack two learner turns", so the guard has to
    cover EVERY method that writes one, not the one a concurrency test happened to reach (L-33).

    Three sites write kind `you`: `step`, `choose` and `converse`. `converse` never touches the
    worker channel, which is exactly why a guard reasoned about as "protect the channel" would
    miss it and leave the claim false.

    `continue_session` is deliberately NOT here. It writes only `muted` turns and already holds
    its own atomic check-and-set on `rec["continued"]` (session_runner.py:2163-2169); a second
    guard over it would replace a tested error message with a nudge and buy no new safety.
    """
    import pathlib
    import re

    from elenchus.web import session_runner as sr

    lines = pathlib.Path(sr.__file__).read_text().splitlines()
    # Anchored at each call's OWN opening paren: a `muted` write on the line above a `you` write
    # (session_runner.py:2110/2111) must not be counted, and a multi-line call must still be.
    writes = []
    for i, line in enumerate(lines):
        if "append_turn(" not in line:
            continue
        chunk = "\n".join(lines[i : i + 4])
        call = chunk[chunk.index("append_turn(") :]
        if re.match(r'append_turn\(\s*[^,]+,\s*"you"', call, re.S):
            writes.append(i)
    assert len(writes) == 3, (
        f"expected three learner-turn writes, found {len(writes)} at {[i + 1 for i in writes]}; "
        "a new one was added and the guard's scope needs rechecking"
    )

    unguarded = []
    for i in writes:
        start = max(j for j, line in enumerate(lines[: i + 1]) if line.startswith("    def "))
        if "_claim_turn(" not in "\n".join(lines[start:i]):
            unguarded.append((lines[start].strip().split("(")[0], i + 1))
    assert not unguarded, (
        f"these learner-turn writes are not behind the single-flight guard: {unguarded}"
    )


# ---- safety floor S3: a working exit (2026-08-30) ----------------------------------------------


def _leave_kit(tmp_path, make_fake, name):
    from conftest import make_world_model

    db = str(tmp_path / name)
    reg = SessionRegistry(db, model_factory=make_world_model)
    return db, reg


def test_close_at_the_front_door_is_an_exit_not_an_error(tmp_path, make_fake):
    """Verified over HTTP on 2026-08-29: /close returned {'kind':'error','message':'session has
    not converged'} at the front door, after choosing a door, and after a real turn. The only
    working exit was closing the tab, and the End control did not render until a convergence
    existed -- so 100% of first sittings had no visible stop control. The exit is the honest
    substitute for the care lane the product must not claim: full recall for anyone who wants
    out, no distribution required.
    """
    db, reg = _leave_kit(tmp_path, make_fake, "leave-frontdoor.db")
    reg.resume_or_start("single")

    tag, data = reg.close("single")

    assert tag == "close", f"the front-door exit still errors: {(tag, data)}"
    assert data["close"], "the leave serves no text"
    live = SittingStore(db).live_sitting()
    assert live is None, "the sitting is still live after she left"


def test_leaving_writes_left_not_closed_and_keeps_every_turn(tmp_path, make_fake):
    """Invariant 4 half: nothing demoted, nothing deleted -- her rows survive the exit. And the
    status is 'left', not 'closed', because a walked-out sitting and a converged one must be
    distinguishable in the data the beta reads: a cohort that leaves at the front door and a
    cohort that converges are opposite findings."""
    db, reg = _leave_kit(tmp_path, make_fake, "leave-status.db")
    reg.resume_or_start("single")
    reg.step("single", "the decision I am actually facing")  # a real turn, mid-press

    tag, _ = reg.close("single")
    assert tag == "close"

    rows = _rows(db, "SELECT status FROM web_sitting")
    assert [r["status"] for r in rows] == ["left"], (
        f"expected the walked-out status, got {[r['status'] for r in rows]}"
    )
    turns = _rows(db, "SELECT kind FROM web_sitting_turn")
    assert any(t["kind"] == "you" for t in turns), "her turns were not retained through the exit"


def test_a_converged_close_still_writes_closed(tmp_path, make_fake):
    """The two exits stay distinguishable from the other side too."""
    from conftest import make_world_model

    reg2 = SessionRegistry(str(tmp_path / "leave-converged2.db"), model_factory=make_world_model)
    reg2.start("s2", now=_T0)
    idx = reg2.menu_index("s2", "veldra:embedded_anchor_lock_in")  # the anchor ref other tests use
    reg2.step("s2", idx)
    for _ in range(8):
        tag, data = reg2.step("s2", "I'd hold the launch and say why, in writing.")
        if tag == "done":
            break
    assert tag == "done", f"the scripted door never landed: {(tag, data)}"
    tag, _ = reg2.close("s2")
    assert tag == "close"
    rows = _rows(str(tmp_path / "leave-converged2.db"), "SELECT status FROM web_sitting")
    assert [r["status"] for r in rows] == ["closed"]


def test_after_leaving_the_next_visit_is_a_fresh_front_door(tmp_path, make_fake):
    """'left' must not resume: she ended it. The next visit starts clean, and her old rows stay
    in the file untouched."""
    db, reg = _leave_kit(tmp_path, make_fake, "leave-return.db")
    reg.resume_or_start("single")
    reg.step("single", "something I was working through")
    reg.close("single")

    reg2 = SessionRegistry(db, model_factory=reg._model_factory)
    tag, data = reg2.resume_or_start("single")

    assert tag == "say" and data.get("frontdoor"), (
        f"a left sitting resumed instead of starting fresh: {(tag, sorted(data))}"
    )
    sittings = _rows(db, "SELECT status FROM web_sitting ORDER BY id")
    assert [r["status"] for r in sittings] == ["left", "live"]


def test_a_stale_tab_close_is_still_a_nudge(tmp_path, make_fake):
    """The refresh escape hatch stays intact: a previous process's tab gets the nudge, never a
    leave it did not ask this process for."""
    db, reg = _leave_kit(tmp_path, make_fake, "leave-stale.db")
    tag, data = reg.close("single")
    assert tag == "nudge", (tag, data)


def test_the_end_control_renders_from_the_first_screen():
    """The audit's finding: end_visible lived only in the resume payload and the button did not
    render until a convergence existed. The exit works everywhere now, so it shows everywhere:
    the front door renders it, and the resume flag rides as a constant the client still reads."""
    import pathlib

    html = pathlib.Path("src/elenchus/web/static/index.html").read_text()
    frontdoor = html[html.index("function renderFrontdoor") : html.index("function renderReserve")]
    assert "showEnd(true)" in frontdoor, "the front door never shows the End control"


# ---- T2 review findings on the guard (F1/F2/F3) and on the exit (seed line) --------------------


def _converge(reg, sid):
    """Drive the scripted anchor door to a landing so a rec exists."""
    reg.resume_or_start(sid)
    idx = reg.menu_index(sid, "veldra:embedded_anchor_lock_in")
    reg.step(sid, idx)
    for _ in range(10):
        tag, data = reg.step(sid, "a position with its mechanism")
        if tag == "done":
            return
    raise AssertionError(f"the scripted door never landed: {(tag, data)}")


def test_a_close_racing_the_claim_window_hangs_nothing_and_leaks_no_claim(tmp_path, make_fake):
    """T2 review F1, reproduced before fixing: close() reaps the worker in the window between
    _claim_turn and _step_begin (the slow `you` append holds it open), the step's get() then
    blocks forever on a pilled worker, and the claim leaks -- surviving the product's own escape
    hatch, because resume_or_start rebuilds the channel but not _in_flight. An eternal-nudge
    brick, reachable with two tabs: one clicks End while the other submits a position.
    """
    import threading

    db = tmp_path / "f1.db"
    reg = SessionRegistry(str(db), model_factory=make_fake)
    _converge(reg, "single")
    reg.continue_session("single")  # segment 2: a live, non-terminal, mid-probe worker

    real_append = reg._store.append_turn
    in_window = threading.Event()

    def slow_append(sit, kind, payload, now):
        if kind == "you":
            in_window.set()
            time.sleep(0.6)
        return real_append(sit, kind, payload, now)

    reg._store.append_turn = slow_append
    out: dict[str, tuple] = {}

    # daemon: on the RED side of this test the step blocks forever, and a non-daemon thread
    # would then hang the pytest process at exit -- failing loud beats failing hung.
    stepper = threading.Thread(
        target=lambda: out.update(step=reg.step("single", "my position")), daemon=True
    )
    stepper.start()
    assert in_window.wait(5), "the stepper never reached the widened window"
    time.sleep(0.05)  # inside the window, before _step_begin
    out["close"] = reg.close("single")
    stepper.join(timeout=10)

    assert not stepper.is_alive(), "the racing step never returned: the F1 deadlock is back"
    assert out["step"][0] in ("nudge", "say", "error"), out["step"]
    assert reg._in_flight == {}, f"the turn claim leaked: {reg._in_flight}"
    # and the session is not bricked: after a refresh, a fresh step is accepted
    reg._store.append_turn = real_append
    tag, data = reg.resume_or_start("single")
    tag2, data2 = reg.step("single", "a fresh situation after the refresh")
    assert (tag2, data2.get("message")) != (
        "nudge",
        "Still working on the one before this — nothing was sent.",
    ), "the eternal in-flight nudge survived the refresh"


def test_a_continue_refused_by_the_guard_does_not_brick_continue(tmp_path, make_fake):
    """T2 review F2: continue_session set rec['continued'] and only then ran its inner guarded
    step; a converse holding the claim nudged that inner step, the flag stayed True, and every
    later Continue answered 'continuation already in flight' until a restart. The whole
    continue_session is a turn: it claims up front and refuses cleanly before touching state.
    """
    import threading

    db = tmp_path / "f2.db"
    reg = SessionRegistry(str(db), model_factory=_slow_factory(make_fake, 0.4))
    _converge(reg, "single")

    out: dict[str, tuple] = {}
    talker = threading.Thread(
        target=lambda: out.update(converse=reg.converse("single", "so what about the long run?")),
        daemon=True,
    )
    talker.start()
    deadline = time.monotonic() + 15
    while "single" not in reg._in_flight and time.monotonic() < deadline:
        time.sleep(0.001)
    assert "single" in reg._in_flight, "the converse never claimed the turn"

    out["continue"] = reg.continue_session("single")
    talker.join(timeout=60)

    assert out["continue"][0] == "nudge", f"the raced continue was not refused: {out['continue']}"
    tag, data = reg.continue_session("single")
    assert (tag, data.get("message")) != ("error", "continuation already in flight"), (
        "the refused continue left rec['continued'] set and bricked the button"
    )


def test_the_client_unwinds_the_optimistic_bubble_on_a_nudge():
    """T2 review F3: the client renders the typed text as a `you` bubble and clears the input
    BEFORE the reply arrives; on a nudge the phantom bubble stood above 'nothing was sent' and
    the text was gone. The unwind must remove the bubble and put her words back in the box."""
    import pathlib

    html = pathlib.Path("src/elenchus/web/static/index.html").read_text()
    assert "unwindSay" in html, "no unwind path for the optimistic say render"
    # anchor inside advance(), where the say/converse reply lands -- the memory panel has its own
    # earlier nudge handler that never renders an optimistic bubble
    advance_at = html.index("if(r.kind==='nudge'){")
    assert "unwindSay(" in html[advance_at : advance_at + 120], (
        "advance()'s nudge branch does not unwind the optimistic bubble and restore the text"
    )
    submit_at = html.index("composer.addEventListener('submit'")
    assert "pendingSay=" in html[submit_at : submit_at + 700], (
        "the submit handler no longer records the optimistic render for the unwind"
    )


def test_the_leave_screen_does_not_plant_a_seed(tmp_path, make_fake):
    """S3 review finding 1, executed by the reviewer: every leave rendered a world panel with
    'A seed was planted — your world begins' -- false on a first visit and reading as data loss
    on a return visit, right under leave copy promising the room keeps what she wrote. The
    client skips the terrain render when the close payload carries no world at all."""
    import pathlib

    html = pathlib.Path("src/elenchus/web/static/index.html").read_text()
    close_fn = html[html.index("function renderClose") : html.index("const homebaseEl")]
    assert "renderTerrain" in close_fn
    guarded = "((r.terrain||[]).length || (r.houses||[]).length)" in close_fn
    assert guarded, "renderClose still renders an empty world (the seed line) on a bare leave"


def test_serving_the_default_database_warns(caplog):
    """S6 review finding 2: with ELENCHUS_DB unset on a loopback bind, the default boot serves
    the founder's own file -- and a tunnel pointed at loopback then serves it to a remote
    invitee while the front door promises 'this invite's own private file'. The configuration
    is permitted (the founder's own boot must keep working), so the honest floor is a loud
    warning on the record."""
    import logging

    from elenchus.web.runtime import DEFAULT_DB, resolve_runtime

    with caplog.at_level(logging.WARNING, logger="elenchus.web.runtime"):
        db, host, port = resolve_runtime({})
    assert db == DEFAULT_DB
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "default database" in logged and "tunnel" in logged, (
        f"no warning on the default-db boot: {logged!r}"
    )

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="elenchus.web.runtime"):
        resolve_runtime({"ELENCHUS_DB": str(tmp := "/tmp/x/elenchus.db")})
    assert not caplog.records, "an isolated boot must not warn"
    assert tmp  # keep ruff quiet about the walrus


def test_the_leave_copy_promises_only_what_a_left_room_delivers():
    """Found by the founder reading the real screen (2026-08-30, from a phone): the leave said
    "it's here when you come back", but a left sitting deliberately never resumes -- the next
    visit is a fresh front door and the retained words are not re-shown. Rows kept: true.
    Room re-served: false. The copy may promise the first, never the second."""
    from elenchus.web.session_runner import _STATIC_LEAVE

    low = _STATIC_LEAVE.lower()
    assert "stays saved" in low or "keeps what you wrote" in low, (
        "the true half -- the words are retained -- should still be said"
    )
    for false_promise in ("when you come back", "pick up where", "resume"):
        assert false_promise not in low, (
            f"the leave promises {false_promise!r}, but a left room is never re-entered"
        )
