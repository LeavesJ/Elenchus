"""One-time durable migration: split the `veldra:license_fork_risk` ledger_ref collision.

`continuity_lock_in` and `license_continuity` shipped sharing one `ledger_ref`. Since a
`ledger_ref` IS the owned-problem identity -- `types.FrameState.breadth` is documented as
"problems engaged with a mechanism" and `state.update_state` fills it with exactly this string --
two distinct problems under one ref corrupted three things, two of them live and learner-facing:

* `web/voice.py`'s `display_titles()` builds `out[e.ledger_ref] = title`, so one title silently
  overwrote the other and a problem was labelled with the other problem's name.
* `types.ProblemMenu.problem_menu()` dedupes by `ledger_ref` ("best-ranked candidate per owned
  problem"), so the two could never both be offered.
* `experience._attach_scene` REPLACES `exp.prompt` with the corpus scene found for the ref, so
  `license_continuity` was served `continuity_lock_in`'s authored scene while being graded against
  its own rubric. The learner read one problem and was scored on another.

WHICH REF KEEPS WHICH PROBLEM WAS DECIDED BY THE AUTHORED CORPUS ROW, not by which title happened
to survive the dict overwrite (that ordering is an artifact of the bug, not evidence). The corpus
row for `veldra:license_fork_risk` carries a scene whose prompt is near-verbatim
`continuity_lock_in`'s ("A buyer's counsel has just asked you to make the continuity terms more
concrete before they will sign this quarter"), a `why_owned` about the escrow-as-selling-point
tension, and License Strategy provenance. So `continuity_lock_in` KEEPS the old ref and
`license_continuity` is minted a new one.

`license_continuity` gets a corpus row with NO SCENE. Two separate facts, and an earlier version of
this note conflated them:

* `experience._attach_scene` tolerates a missing entry and returns the experience unchanged, so no
  scene is needed for correct serving. Inventing a replacement scene purely to satisfy a migration
  would fabricate doctrine, which is the one thing the model must never hold. `scene=None` is the
  correct value, and it is what makes `license_continuity` serve its own authored prompt.
* `generator.anti_label_gate` does NOT tolerate a missing entry. It hard-rejects
  `recoverable_label` on an empty `unlabeled` and `cosmetic_engagement` on an empty `why_owned`,
  and `load_gated_library` raises on any hard reject at load. So the new ref needs exactly those
  two fields populated, and nothing more. `provenance` is a quality floor (downgrade, never
  reject), so it records what is true about this row's origin rather than a document pointer that
  would have to be invented.

The `why_owned` and `unlabeled` text below is MIGRATION-AUTHORED, derived from the rubric the
founder already wrote, and is the minimum the invariant requires. It is not EXECLOG-backed the way
`veldra:license_fork_risk`'s is, and it should be replaced with sourced text when convenient.

EXACT ATTRIBUTION, NEVER HEURISTIC. The two rubrics share no frame code and no trap code, so every
affected row can be assigned by identifier rather than by guessing from titles or domains. The
frames below belong to `license_continuity` alone; `embed_credentials_as_a_list` belongs to
`continuity_lock_in` alone and deliberately does NOT move.

The frame list is HARDCODED rather than derived from `content/` at run time. A migration must
describe the world as it was when the rows were written; deriving it from live content would make
a historical rewrite depend on whatever the rubrics say the day it happens to run.

IDEMPOTENT. Re-running finds nothing left to move and reports zeros. Safe to run twice, and the
test suite runs it twice to prove it.
"""

from __future__ import annotations

import json
import sqlite3

OLD_REF = "veldra:license_fork_risk"
NEW_REF = "veldra:midrollout_contract_boundary"

# `license_continuity`'s frames, and only those. `embed_credentials_as_a_list` stays on OLD_REF.
MOVED_FRAMES = frozenset(
    {
        "lead_with_what_you_refuse_to_do",
        "protect_the_core_lane",
        "commit_under_the_deadline",
    }
)
MOVED_EXPERIENCE = "license_continuity"

# The two fields `anti_label_gate` hard-rejects on when absent, and nothing else. Deliberately no
# scene: `_attach_scene` then leaves `license_continuity`'s authored prompt in place, which is the
# behaviour the split exists to restore.
NEW_CORPUS = {
    "domain": "founder_ceo",
    "why_owned": (
        "A live customer commitment collides with a guarantee made to everyone else, and the "
        "cost of honouring either is real and already incurred. Migration-authored from the "
        "rubric; not yet sourced to an EXECLOG entry the way license_fork_risk is."
    ),
    "unlabeled": (
        "Nothing in the situation says whether the binding constraint is the relationship, the "
        "core promise, or the deadline, and the three point at different decisions."
    ),
    "provenance": (
        "split from veldra:license_fork_risk by src/elenchus/ledger_ref_migration.py; "
        "content/rubrics/license_continuity.yaml"
    ),
}


def _swap(raw: str | None) -> tuple[str | None, bool]:
    """Rewrite OLD_REF to NEW_REF inside one breadth JSON array, preserving order and the rest of
    the set. Returns the new value and whether anything changed."""
    if not raw:
        return raw, False
    refs = json.loads(raw)
    if OLD_REF not in refs:
        return raw, False
    swapped = [NEW_REF if r == OLD_REF else r for r in refs]
    return json.dumps(swapped), True


def migrate(db_path: str) -> dict[str, int]:
    """Move `license_continuity`'s durable rows from OLD_REF to NEW_REF, in one transaction.

    Returns per-table counts of rows actually changed, so a caller can tell a real migration from
    a no-op re-run."""
    counts = {
        "frames_breadth": 0,
        "frames_unprompted": 0,
        "selection_log": 0,
        "queue": 0,
        "corpus": 0,
    }
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # one transaction: commits on success, rolls back on any exception
            # The ownership row the load gate requires. Inserted first: if it fails, nothing else
            # moves, and a half-migrated db whose new ref has no corpus entry cannot load content
            # at all. INSERT OR IGNORE keeps the re-run a no-op and never overwrites founder text.
            if conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='corpus'"
            ).fetchone():
                cur = conn.execute(
                    "INSERT OR IGNORE INTO corpus (ledger_ref, domain, why_owned, unlabeled, "
                    "provenance, corpus_pointers_json, scene_json) VALUES (?,?,?,?,?,?,?)",
                    (
                        NEW_REF,
                        NEW_CORPUS["domain"],
                        NEW_CORPUS["why_owned"],
                        NEW_CORPUS["unlabeled"],
                        NEW_CORPUS["provenance"],
                        "[]",
                        None,  # no scene: the authored prompt stands
                    ),
                )
                counts["corpus"] = cur.rowcount

            for row in conn.execute(
                "SELECT frame_code, breadth_json, unprompted_breadth_json FROM frames"
            ).fetchall():
                if row["frame_code"] not in MOVED_FRAMES:
                    continue
                breadth, b_changed = _swap(row["breadth_json"])
                unprompted, u_changed = _swap(row["unprompted_breadth_json"])
                if not (b_changed or u_changed):
                    continue
                conn.execute(
                    "UPDATE frames SET breadth_json=?, unprompted_breadth_json=? "
                    "WHERE frame_code=?",
                    (breadth, unprompted, row["frame_code"]),
                )
                counts["frames_breadth"] += int(b_changed)
                counts["frames_unprompted"] += int(u_changed)

            cur = conn.execute(
                "UPDATE selection_log SET problem=? WHERE experience_id=? AND problem=?",
                (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
            )
            counts["selection_log"] = cur.rowcount

            # Empty at migration time; done anyway so a queued row written between the backup and
            # this run is not stranded on a ref no experience claims any more.
            cur = conn.execute(
                "UPDATE queue SET ledger_ref=? WHERE experience_id=? AND ledger_ref=?",
                (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
            )
            counts["queue"] = cur.rowcount
    finally:
        conn.close()
    return counts


if __name__ == "__main__":  # pragma: no cover - operational entrypoint
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/elenchus.db"
    print(f"migrating {path}: {migrate(path)}")
