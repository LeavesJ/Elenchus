"""The one-time recovery of web_converged.position for pre-column convergences (Spec-3 §4c).

The words were never lost — they are in web_sitting_turn. `position` is NULL only because the
column postdates those sittings, and log_converged only writes it for NEW rows, so "self-heals
at your next session" was never going to fire for them.

The trap this suite exists to pin: a plateau landing produces a `landing` turn but NO
web_converged row, so a naive Nth-landing mapping slips and writes the wrong words into a
memory. L-3: the migration only ADDS; it never overwrites or deletes."""

import json
import sqlite3

from retnovation.web.sitting_store import SittingStore


def _seed(path, turns, convergences):
    """Build a db the way the app does, then hand-write legacy rows the migration must repair."""
    SittingStore(str(path))  # creates the schema
    c = sqlite3.connect(str(path))
    for sitting_id, seq, kind, payload in turns:
        c.execute(
            "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json) VALUES (?,?,?,?)",
            (sitting_id, seq, kind, json.dumps(payload)),
        )
    for sitting_id, ref, at in convergences:
        c.execute(
            "INSERT INTO web_converged (sitting_id, ref, converged_at, experience_id, position) "
            "VALUES (?,?,?,'',NULL)",
            (sitting_id, ref, at),
        )
    c.commit()
    c.close()


def _positions(path):
    c = sqlite3.connect(str(path))
    rows = c.execute("SELECT ref, position FROM web_converged ORDER BY converged_at").fetchall()
    c.close()
    return dict(rows)


def test_backfill_skips_plateau_landings(tmp_path):
    # THE TRAP. Two landings, but only the SECOND converged. A naive "first landing = first
    # convergence" rule would store "wrong words" — the position from the plateaued arc.
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "wrong words"}),
            ("s1", 2, "landing", {"text": "...", "stop_reason": "plateau"}),
            ("s1", 3, "you", {"text": "right words"}),
            ("s1", 4, "landing", {"text": "...", "stop_reason": "converged"}),
        ],
        convergences=[("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00")],
    )
    SittingStore(str(db))  # re-open: the migration runs in __init__
    assert _positions(db)["gen:s1:1"] == "right words"


def test_backfill_maps_multiple_convergences_in_order(tmp_path):
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "first position"}),
            ("s1", 2, "landing", {"text": "...", "stop_reason": "converged"}),
            ("s1", 3, "you", {"text": "second position"}),
            ("s1", 4, "landing", {"text": "...", "stop_reason": "converged"}),
        ],
        convergences=[
            ("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00"),
            ("s1", "gen:s1:2", "2026-07-05T01:00:00+00:00"),
        ],
    )
    SittingStore(str(db))
    got = _positions(db)
    assert got["gen:s1:1"] == "first position"
    assert got["gen:s1:2"] == "second position"


def test_legacy_sitting_without_stop_reason_uses_count_equality(tmp_path):
    # Pre-column sittings carry no stop_reason. They qualify ONLY when landings == convergences.
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "legacy words"}),
            ("s1", 2, "landing", {"text": "..."}),
        ],
        convergences=[("s1", "veldra:x", "2026-07-02T00:00:00+00:00")],
    )
    SittingStore(str(db))
    assert _positions(db)["veldra:x"] == "legacy words"


def test_ambiguous_legacy_sitting_is_skipped_not_guessed(tmp_path):
    # No stop_reason AND counts disagree: unknowable. An honest NULL beats a wrong memory.
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "a"}),
            ("s1", 2, "landing", {"text": "..."}),
            ("s1", 3, "you", {"text": "b"}),
            ("s1", 4, "landing", {"text": "..."}),
        ],
        convergences=[("s1", "veldra:x", "2026-07-02T00:00:00+00:00")],
    )
    SittingStore(str(db))
    assert _positions(db)["veldra:x"] is None


def test_backfill_never_overwrites_an_existing_position(tmp_path):
    # L-3: the migration only ADDS.
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "new words"}),
            ("s1", 2, "landing", {"text": "...", "stop_reason": "converged"}),
        ],
        convergences=[("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00")],
    )
    c = sqlite3.connect(str(db))
    c.execute("UPDATE web_converged SET position = 'already here'")
    c.commit()
    c.close()
    SittingStore(str(db))
    assert _positions(db)["gen:s1:1"] == "already here"


def test_backfill_is_idempotent(tmp_path):
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "the words"}),
            ("s1", 2, "landing", {"text": "...", "stop_reason": "converged"}),
        ],
        convergences=[("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00")],
    )
    SittingStore(str(db))
    SittingStore(str(db))  # second open must be a no-op, not a re-write
    assert _positions(db)["gen:s1:1"] == "the words"


def test_backfill_treats_empty_stop_reason_as_not_converged(tmp_path):
    # C2 trap: a PRESENT but empty stop_reason ("") must read as "not converged" — not as
    # "no stop_reason column at all". `all(reasons)` tests truthiness, so an empty string used
    # to silently demote the whole sitting to the legacy count-equality heuristic, which does
    # not filter by convergence and would write the plateaued arc's words into a memory.
    db = tmp_path / "t.db"
    _seed(
        db,
        turns=[
            ("s1", 1, "you", {"text": "wrong words"}),
            ("s1", 2, "landing", {"text": "...", "stop_reason": ""}),
            ("s1", 3, "you", {"text": "right words"}),
            ("s1", 4, "landing", {"text": "...", "stop_reason": "converged"}),
        ],
        convergences=[
            ("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00"),
            ("s1", "gen:s1:2", "2026-07-05T01:00:00+00:00"),
        ],
    )
    SittingStore(str(db))
    got = _positions(db)
    # The sitting is genuinely ambiguous now (only one of the two landings truly converged, but
    # there are two convergence rows) — an honest NULL beats a wrong memory. The one thing that
    # must never happen: the plateaued arc's "wrong words" landing in either slot.
    assert got["gen:s1:1"] != "wrong words"
    assert got["gen:s1:2"] != "wrong words"
    assert got["gen:s1:1"] is None
    assert got["gen:s1:2"] is None


def test_backfill_survives_non_object_payload_json(tmp_path):
    # I1: valid JSON that decodes to something other than an object (`null`, a string, a list)
    # must not raise AttributeError out of `.get()` and take down store construction. This
    # directly contradicts "an unopenable path must not crash the registry at construction."
    db = tmp_path / "t.db"
    SittingStore(str(db))  # creates the schema
    c = sqlite3.connect(str(db))
    c.execute(
        "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json) VALUES (?,?,?,?)",
        ("s1", 1, "you", "null"),
    )
    c.execute(
        "INSERT INTO web_sitting_turn (sitting_id, seq, kind, payload_json) VALUES (?,?,?,?)",
        ("s1", 2, "landing", "null"),
    )
    c.execute(
        "INSERT INTO web_converged (sitting_id, ref, converged_at, experience_id, position) "
        "VALUES (?,?,?,'',NULL)",
        ("s1", "gen:s1:1", "2026-07-05T00:00:00+00:00"),
    )
    c.commit()
    c.close()
    store = SittingStore(str(db))  # must not raise, and must not fall back to inert
    assert not store.inert
    assert _positions(db)["gen:s1:1"] is None
