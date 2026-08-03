"""live_corpus reads real learner text from data/elenchus.db for the two live probes
(push_screen_probe, prompt_shift_probe). Every test here builds its own temp sqlite file --
never touches the real data/elenchus.db -- so the absent/empty paths are exercised
deterministically."""

from __future__ import annotations

import json
import sqlite3

from elenchus.live_corpus import read_learner_turns, read_push_response_pairs, read_situations


def _turn_db(path, rows):
    """rows: list of (sitting_id, seq, kind, text_or_None). text=None writes malformed JSON."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE web_sitting_turn (sitting_id TEXT, seq INTEGER, kind TEXT, payload_json TEXT)"
    )
    for sitting_id, seq, kind, text in rows:
        payload = "{not json" if text is None else json.dumps({"text": text})
        conn.execute(
            "INSERT INTO web_sitting_turn VALUES (?, ?, ?, ?)", (sitting_id, seq, kind, payload)
        )
    conn.commit()
    conn.close()


def _world_db(path, rows):
    """rows: list of (sitting_id, situation)."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE web_world (sitting_id TEXT, situation TEXT)")
    conn.executemany("INSERT INTO web_world VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# absent / empty degradation (shared by all three readers)
# ---------------------------------------------------------------------------


def test_read_learner_turns_is_empty_when_db_file_is_absent(tmp_path):
    missing = tmp_path / "nope.db"
    assert not missing.exists()
    assert read_learner_turns(missing) == []
    # Read-only probe: must never create the file it just found absent.
    assert not missing.exists()


def test_read_learner_turns_is_empty_on_a_db_with_no_web_sitting_turn_table(tmp_path):
    path = tmp_path / "pre_web_layer.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE frames (frame_code TEXT)")
    conn.commit()
    conn.close()
    assert read_learner_turns(path) == []


def test_read_push_response_pairs_is_empty_when_db_file_is_absent(tmp_path):
    assert read_push_response_pairs(tmp_path / "nope.db") == []


def test_read_situations_is_empty_when_db_file_is_absent(tmp_path):
    assert read_situations(tmp_path / "nope.db") == []


def test_read_situations_is_empty_on_a_db_with_no_web_world_table(tmp_path):
    path = tmp_path / "pre_web_layer.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE frames (frame_code TEXT)")
    conn.commit()
    conn.close()
    assert read_situations(path) == []


# ---------------------------------------------------------------------------
# read_learner_turns
# ---------------------------------------------------------------------------


def test_read_learner_turns_returns_only_you_turns_in_sitting_seq_order(tmp_path):
    path = tmp_path / "db.sqlite"
    _turn_db(
        path,
        [
            ("s1", 1, "vera", "opening push"),
            ("s1", 2, "you", "first reply"),
            ("s1", 3, "vera", "next push"),
            ("s1", 4, "you", "second reply"),
            ("s0", 1, "you", "earlier sitting reply"),
        ],
    )
    # sitting_id sorts lexicographically ("s0" before "s1"); within a sitting, seq order holds.
    assert read_learner_turns(path) == ["earlier sitting reply", "first reply", "second reply"]


def test_read_learner_turns_skips_whitespace_only_and_malformed_rows(tmp_path):
    path = tmp_path / "db.sqlite"
    _turn_db(
        path,
        [
            ("s1", 1, "you", "   "),
            ("s1", 2, "you", None),  # malformed JSON payload
            ("s1", 3, "you", "a real reply"),
        ],
    )
    assert read_learner_turns(path) == ["a real reply"]


# ---------------------------------------------------------------------------
# read_push_response_pairs
# ---------------------------------------------------------------------------


def test_read_push_response_pairs_pairs_a_you_turn_with_its_immediately_preceding_vera_turn(
    tmp_path,
):
    path = tmp_path / "db.sqlite"
    _turn_db(
        path,
        [
            ("s1", 1, "vera", "push A"),
            ("s1", 2, "you", "reply A"),
            ("s1", 3, "vera", "push B"),
            ("s1", 4, "you", "reply B"),
        ],
    )
    assert read_push_response_pairs(path) == [("push A", "reply A"), ("push B", "reply B")]


def test_read_push_response_pairs_ignores_a_you_turn_not_preceded_by_vera(tmp_path):
    path = tmp_path / "db.sqlite"
    _turn_db(
        path,
        [
            ("s1", 1, "muted", "door chosen"),
            ("s1", 2, "you", "opening say"),  # preceded by 'muted', not 'vera' -- no pair
            ("s1", 3, "vera", "push A"),
            ("s1", 4, "you", "reply A"),
        ],
    )
    assert read_push_response_pairs(path) == [("push A", "reply A")]


def test_read_push_response_pairs_never_pairs_across_a_sitting_boundary(tmp_path):
    path = tmp_path / "db.sqlite"
    _turn_db(
        path,
        [
            ("s1", 9, "vera", "last push of s1"),
            # s2's first turn must not inherit s1's trailing vera as its "previous".
            ("s2", 1, "you", "first turn of s2, a you turn"),
        ],
    )
    assert read_push_response_pairs(path) == []


# ---------------------------------------------------------------------------
# read_situations
# ---------------------------------------------------------------------------


def test_read_situations_returns_nonempty_situations_in_sitting_order(tmp_path):
    path = tmp_path / "db.sqlite"
    _world_db(
        path,
        [
            ("s2", "second situation"),
            ("s1", "first situation"),
            ("s3", "   "),  # whitespace-only, dropped
        ],
    )
    assert read_situations(path) == ["first situation", "second situation"]
