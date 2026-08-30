"""The number the beta exists to produce, and the arithmetic under it.

`web_sitting` cannot count returns: `_SITTING_MAX_IDLE = 18h` makes `resume_or_start` RESUME, so
five visits across three days leave ONE row and the bias is inverted -- the better retained the
learner, the fewer rows they generate. The replacement is `web_sitting_turn.at`, gap-clustered
into visits, which is what this module computes.

Written first, watched fail. The plan's Friday 09-05 item.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from elenchus.retention import (
    cluster_visits,
    read_visit_starts,
    retention_by_day,
)

_T0 = datetime(2026, 9, 5, 19, 0, tzinfo=timezone.utc)  # a Friday evening, links out


def test_one_burst_of_turns_is_one_visit():
    stamps = [_T0, _T0 + timedelta(minutes=3), _T0 + timedelta(minutes=11)]
    assert cluster_visits(stamps, timedelta(hours=6)) == [_T0]


def test_a_return_after_the_gap_is_a_second_visit():
    """The whole point. Twelve hours is INSIDE the 18h resume window, so `web_sitting` reports
    one; the turn stamps report two."""
    later = _T0 + timedelta(hours=12)
    stamps = [_T0, _T0 + timedelta(minutes=4), later, later + timedelta(minutes=6)]
    assert cluster_visits(stamps, timedelta(hours=6)) == [_T0, later]


def test_the_threshold_decides_and_that_is_why_it_must_be_named():
    """A single knob turns one visit into two. The plan requires the reported number to name its
    threshold AND say it was chosen post hoc, and this is the test that shows why."""
    stamps = [_T0, _T0 + timedelta(hours=4)]
    assert len(cluster_visits(stamps, timedelta(hours=6))) == 1
    assert len(cluster_visits(stamps, timedelta(hours=2))) == 2


def test_unordered_stamps_still_cluster():
    """Rows come back in whatever order the query gives; visits are a property of the clock."""
    later = _T0 + timedelta(hours=30)
    assert cluster_visits([later, _T0], timedelta(hours=6)) == [_T0, later]


def test_no_stamps_is_no_visits():
    assert cluster_visits([], timedelta(hours=6)) == []


def test_retention_counts_a_learner_present_in_the_day_window():
    """D-N retention: the learner had at least one visit in [N days, N+1 days) after their FIRST
    visit. Day 0 is the visit that starts the clock and is never counted as retention."""
    starts = [_T0, _T0 + timedelta(days=1, hours=2), _T0 + timedelta(days=6, hours=23)]
    by_day = retention_by_day([starts], (1, 7))
    assert by_day[1] == (1, 1), "returned on day 1"
    assert by_day[7] == (0, 1), "day 6 is not day 7"


def test_retention_is_a_fraction_over_the_invitees_who_ever_arrived():
    """An invitee whose database holds no turns at all never started the clock and must not sit in
    the denominator as a retention failure -- they are a delivery failure, a different number."""
    arrived = [_T0, _T0 + timedelta(days=1)]
    never_came = []
    by_day = retention_by_day([arrived, never_came], (1,))
    assert by_day[1] == (1, 1), "the empty database must not enter the denominator"


def test_a_real_store_driven_through_two_visits_reports_two(tmp_path):
    """L-9: the clustering must run on what a PRODUCTION path actually writes, not on a list of
    datetimes this test invented. Drives the real SittingStore and reads the real column back."""
    from elenchus.web.sitting_store import SittingStore

    db = tmp_path / "invitee.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "the decision I am stuck on"}, _T0)
    store.append_turn(sid, "vera", {"text": "a push"}, _T0 + timedelta(minutes=2))
    back = _T0 + timedelta(hours=12)
    store.append_turn(sid, "you", {"text": "coming back to it"}, back)

    starts = read_visit_starts(str(db), timedelta(hours=6))

    assert starts == [_T0, back], (
        "two visits twelve hours apart are not recoverable from a real store"
    )


def test_legacy_turns_with_no_stamp_are_skipped_not_guessed(tmp_path):
    """293 production turns predate the column and are NULL. They must drop out, never be
    attributed to a moment nobody recorded."""
    import sqlite3

    from elenchus.web.sitting_store import SittingStore

    db = tmp_path / "legacy.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "stamped"}, _T0)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json, at) "
        "VALUES (?, 99, 'you', '{\"text\": \"legacy\"}', NULL)",
        (sid,),
    )
    conn.commit()
    conn.close()

    assert read_visit_starts(str(db), timedelta(hours=6)) == [_T0]


def test_a_database_without_the_column_reports_nothing_rather_than_raising(tmp_path):
    """An analyst pointed at a pre-migration file must get an empty answer and a chance to notice,
    not a traceback that looks like a bug in the analysis."""
    import sqlite3

    db = tmp_path / "premigration.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE web_sitting_turn (sitting_id TEXT NOT NULL, seq INTEGER NOT NULL, "
        "kind TEXT NOT NULL, payload_json TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    assert read_visit_starts(str(db), timedelta(hours=6)) == []


def test_a_missing_database_is_an_error_not_a_silent_zero(tmp_path):
    """A typo'd tenant path that reports 'no visits' would read as a real retention result. The
    two must not look alike."""
    with pytest.raises(FileNotFoundError):
        read_visit_starts(str(tmp_path / "nope.db"), timedelta(hours=6))


def test_a_file_that_is_not_an_elenchus_database_says_so(tmp_path):
    """Three failures that must not look alike: a typo'd path, a file that is not ours, and a
    real database written before the column. Only the third is legitimately 'no visits'."""
    import sqlite3

    db = tmp_path / "someone_elses.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="web_sitting_turn"):
        read_visit_starts(str(db), timedelta(hours=6))


def test_a_naive_stamp_does_not_crash_the_comparison(tmp_path):
    """Production writes tz-aware stamps, but the analysis runs over whatever files exist on the
    night, and a single naive row would raise 'can't compare offset-naive and offset-aware' in
    the middle of the only number the beta produces. Naive is read as UTC."""
    import sqlite3

    from elenchus.web.sitting_store import SittingStore

    db = tmp_path / "mixed.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "aware"}, _T0)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json, at) "
        "VALUES (?, 98, 'you', '{\"text\": \"naive\"}', ?)",
        (sid, _T0.replace(tzinfo=None).isoformat()),
    )
    conn.commit()
    conn.close()

    assert read_visit_starts(str(db), timedelta(hours=6)) == [_T0]


def test_the_report_names_the_threshold_it_used(tmp_path):
    """Invariant 7 in the plan's own words: name the threshold and say it was chosen post hoc. A
    retention figure printed without its threshold is not a claim anyone can check."""
    from elenchus.retention import report

    from elenchus.web.sitting_store import SittingStore

    db = tmp_path / "one.db"
    store = SittingStore(str(db))
    sid = store.create_sitting(_T0)
    store.append_turn(sid, "you", {"text": "arrived"}, _T0)
    store.append_turn(sid, "you", {"text": "came back"}, _T0 + timedelta(days=1, hours=1))

    text = report([str(db)], timedelta(hours=6), (1, 7))

    assert "6:00:00" in text or "6h" in text, f"the threshold is not in the output: {text!r}"
    assert "post hoc" in text.lower(), "the output does not disclose that it was chosen post hoc"
    assert "D1" in text and "D7" in text


def test_the_report_script_runs_over_tenant_files(tmp_path):
    """The Friday 09-05 deliverable: point the script at data/tenants and read D1/D7. Driven as a
    real subprocess -- the exact invocation the founders will type -- not an import."""
    import subprocess
    import sys
    from pathlib import Path

    from elenchus.web.sitting_store import SittingStore

    tenants = tmp_path / "tenants"
    for slug, offsets in {"ada": [0, 25], "bo": [0]}.items():
        db = tenants / slug / "elenchus.db"
        db.parent.mkdir(parents=True)
        store = SittingStore(str(db))
        sid = store.create_sitting(_T0)
        for hours in offsets:
            store.append_turn(sid, "you", {"text": "t"}, _T0 + timedelta(hours=hours))

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "retention_report.py"), str(tenants)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src)},
    )

    assert out.returncode == 0, out.stderr
    assert "ada" in out.stdout and "bo" in out.stdout
    assert "D1" in out.stdout and "D7" in out.stdout
    assert "post hoc" in out.stdout.lower()
