"""Real learner text from the live sitting database (data/elenchus.db), for the two live probes
(push_screen_probe.py, prompt_shift_probe.py). Both need the exact same absent/empty
degradation -- say so and fall back to an empty corpus, rather than measuring against an
invented fixture, the mistake both prior push corpora (neither real generate_push output) made.

Read-only: a missing path must never become an empty file just because sqlite3.connect() would
happily create one, so every read opens `mode=ro` and treats "the file is not there" as "no
corpus" rather than letting the driver silently start one.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _rows(db_path: str | Path, query: str) -> list[tuple] | None:
    """Every row `query` returns, or None if the db file is absent or the query fails (no such
    table on a pre-web-layer db, a locked file, a non-sqlite file at that path, ...). Never
    raises -- the callers below turn None into an empty corpus and let their own caller report
    which mode ran."""
    path = Path(db_path)
    if not path.exists():
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            return conn.execute(query).fetchall()
    except sqlite3.Error:
        return None


def _text(payload_json: str) -> str | None:
    try:
        decoded = json.loads(payload_json)
    except (ValueError, TypeError):
        return None
    text = decoded.get("text") if isinstance(decoded, dict) else None  # shape-safe, not raise
    return text.strip() if isinstance(text, str) and text.strip() else None


def read_learner_turns(db_path: str | Path) -> list[str]:
    """Every non-empty learner ('you') turn, sitting/seq order. [] when the db is absent, holds
    no web_sitting_turn table, or has no 'you' rows."""
    rows = _rows(
        db_path,
        "SELECT payload_json FROM web_sitting_turn WHERE kind='you' ORDER BY sitting_id, seq",
    )
    if rows is None:
        return []
    texts = (_text(payload) for (payload,) in rows)
    return [t for t in texts if t is not None]


def read_push_response_pairs(db_path: str | Path) -> list[tuple[str, str]]:
    """(the Vera turn, the learner's very next reply) for every learner turn immediately
    preceded by a Vera turn in the same sitting -- the closest real stand-in this db holds for
    (push, response): the raw engine push text (assessment/judgment_loop.py's
    `model.generate_push` output) is never persisted, only the Vera-voiced turn
    `web/session_runner.py` appends right before the learner's reply. [] under the same
    absent/empty rule as read_learner_turns."""
    rows = _rows(
        db_path,
        "SELECT sitting_id, seq, kind, payload_json FROM web_sitting_turn ORDER BY sitting_id, seq",
    )
    if rows is None:
        return []
    pairs: list[tuple[str, str]] = []
    prev_sitting = object()  # sentinel: never equals a real sitting_id
    prev_kind: str | None = None
    prev_text: str | None = None
    for sitting_id, _seq, kind, payload in rows:
        if sitting_id != prev_sitting:
            prev_kind, prev_text = None, None
        text = _text(payload)
        if kind == "you" and prev_kind == "vera" and prev_text and text:
            pairs.append((prev_text, text))
        prev_sitting, prev_kind, prev_text = sitting_id, kind, text
    return pairs


def read_situations(db_path: str | Path) -> list[str]:
    """Every non-empty web_world.situation -- her own words at the front door, sitting order.
    [] under the same absent/empty rule."""
    rows = _rows(db_path, "SELECT situation FROM web_world ORDER BY sitting_id")
    if rows is None:
        return []
    return [s.strip() for (s,) in rows if isinstance(s, str) and s.strip()]
