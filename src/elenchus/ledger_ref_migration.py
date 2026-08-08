"""One-time durable migration: split the `veldra:license_fork_risk` ledger_ref collision.

`continuity_lock_in` and `license_continuity` shipped sharing one `ledger_ref`. A `ledger_ref` IS
the identity of an owned problem (`types.FrameStrength.breadth` is documented as "problems engaged
with a mechanism" and `state.update_state` fills it with exactly this string), so two problems under
one ref corrupted the display title, the problem menu, the served scene, and transfer breadth.

`continuity_lock_in` KEEPS the old ref: the corpus row's scene prompt is near-verbatim its authored
prompt, its `why_owned` is the escrow-clause tension, and the `ledger` row's `owned_problem` is the
Source-Available-vs-BSL decision. `license_continuity` is minted `veldra:midrollout_contract_boundary`.
Which title survived the pre-split dict overwrite is NOT evidence: that ordering is the bug.

THE FIRST VERSION OF THIS MIGRATION MOVED FOUR COLUMNS AND THERE ARE ELEVEN. It rewrote
`corpus`, `frames.breadth_json`, `frames.unprompted_breadth_json`, `selection_log.problem` and
`queue.ledger_ref`, and silently left `ledger.id`, `selection_log.chosen_problem`,
`web_converged.ref`, `web_domain_slot.member_refs_json`, `web_sitting_state.record_json`,
`web_sitting_state.inflight_json` and `web_sitting_state.next_pick_ref` behind -- the web tables live
in the SAME sqlite file. The result was worse than no migration on two surfaces:

* a real `web_converged` row (`experience_id='license_continuity'`) kept the old ref, and because
  only `continuity_lock_in` now resolves for it, `session_runner._memory_situation`'s experience_id
  disambiguation can no longer match and falls back to `entries[0].prompt`. The learner's memory of
  that sitting showed the OTHER problem's situation. It had been correct before the split.
* `selection_log` carries FOUR identity columns; rewriting only the proposed side produced an
  `outcome='accepted'` row whose `chosen_problem` and `chosen_experience_id` named different owned
  problems.

The lesson, and the rule this module now follows: **enumerate every column that can hold the
identifier before writing a single UPDATE, and key each one on the strongest discriminator that
column actually has.** Never on the old ref alone, which by definition cannot tell the two apart.

DISCRIMINATOR PER SURFACE, all verified against the real database before this was written:

| surface                              | discriminator                                    |
|--------------------------------------|--------------------------------------------------|
| corpus / ledger                       | neither moves; a NEW row is minted for NEW_REF   |
| frames.*_breadth_json                 | frame_code (the two rubrics share none)          |
| selection_log.problem                 | experience_id                                    |
| selection_log.chosen_problem          | chosen_experience_id                             |
| queue.ledger_ref                      | experience_id                                    |
| web_converged.ref                     | experience_id                                    |
| web_sitting_state.inflight_json       | experience_id INSIDE the json                    |
| web_sitting_state.record_json         | experience_id INSIDE the json                    |
| web_domain_slot.member_refs_json      | derived: only if web_converged proves the old ref|
|                                       | was converged solely by MOVED_EXPERIENCE         |
| web_sitting_state.next_pick_ref       | NONE AVAILABLE -- deliberately left alone, below |

`next_pick_ref` is a bare ref with no companion experience_id, on sittings that are closed. There is
no discriminator, so rewriting it would be guessing which problem a dead sitting intended to serve
next. Left as-is and reported in the counts as `next_pick_ref_left`, because a silent skip is how
the first version of this file went wrong.

`license_continuity` gets a corpus row with NO SCENE. `experience._attach_scene` returns the
experience unchanged when no entry resolves, so it serves its own authored prompt, which is the
behaviour the split exists to restore. Inventing a scene to satisfy a migration would fabricate
doctrine. But `generator.anti_label_gate` DOES hard-reject an empty `why_owned` (cosmetic_engagement)
or `unlabeled` (recoverable_label), so those two fields are populated and nothing more. That text is
migration-authored from the rubric and is not EXECLOG-sourced; replace it when convenient.

IDEMPOTENT, and it upgrades `cli.build_store`'s placeholder. If the app booted before this ran,
`build_store` will have authored a placeholder corpus/ledger row for the new ref, and a bare
`INSERT OR IGNORE` would then be a permanent no-op reporting `corpus: 0` -- byte-indistinguishable
from a clean re-run. Placeholder rows are machine text, so this replaces them; anything else is left
untouched.
"""

from __future__ import annotations

import json
import sqlite3

OLD_REF = "veldra:license_fork_risk"
NEW_REF = "veldra:midrollout_contract_boundary"

MOVED_EXPERIENCE = "license_continuity"
# `license_continuity`'s frames, and only those. `embed_credentials_as_a_list` belongs to
# `continuity_lock_in` (and to `irreversible_anchor`) and must NOT move. Hardcoded rather than
# derived from live content: a migration describes the world as it was when the rows were written.
MOVED_FRAMES = frozenset(
    {"lead_with_what_you_refuse_to_do", "protect_the_core_lane", "commit_under_the_deadline"}
)

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
NEW_LEDGER_OWNED_PROBLEM = (
    "A contract ambiguity surfaces mid-rollout with a long-standing customer: honouring their "
    "reading costs a guarantee made to every other customer, refusing risks the rollout and the "
    "relationship, and they want an answer today. Migration-authored from the rubric."
)
# `cli.build_store` authors these on any boot where a ref has no row. Machine text, safe to replace.
_PLACEHOLDER_WHY = "seed stakes (abstracted)"
_PLACEHOLDER_OWNED = f"Abstracted seed for {MOVED_EXPERIENCE}."


def _has_table(conn, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    )


def _swap_list(raw: str | None) -> tuple[str | None, bool]:
    """Rewrite OLD_REF to NEW_REF inside a JSON array, preserving order and DE-DUPLICATING.

    Dedup matters: between the content change shipping and this running, a live sitting writes
    NEW_REF into breadth, so a row can already hold both. Mapping without dedup stores the same ref
    twice. Nothing miscounts today (`persistence.load_state` wraps it in a set) but a durable row
    that literally repeats an identifier is a lie about what happened."""
    if not raw:
        return raw, False
    refs = json.loads(raw)
    if OLD_REF not in refs:
        return raw, False
    out: list[str] = []
    for r in refs:
        r = NEW_REF if r == OLD_REF else r
        if r not in out:
            out.append(r)
    return json.dumps(out), True


def migrate(db_path: str) -> dict[str, int]:
    """Move every durable row that belongs to `license_continuity` onto NEW_REF, in ONE
    transaction. Returns per-surface counts so a real migration is distinguishable from a no-op."""
    c: dict[str, int] = {
        "corpus": 0,
        "ledger": 0,
        "frames_breadth": 0,
        "frames_unprompted": 0,
        "selection_log_problem": 0,
        "selection_log_chosen": 0,
        "queue": 0,
        "web_converged": 0,
        "web_sitting_inflight": 0,
        "web_sitting_record": 0,
        "web_domain_slot": 0,
        "next_pick_ref_left": 0,
    }
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commits on success, rolls back on any exception
            # Derived BEFORE any UPDATE runs. `web_domain_slot`'s discriminator is "who converged
            # the old ref", read out of `web_converged` -- and `web_converged` is rewritten below,
            # after which the query returns the empty set and the slot rewrite would silently skip.
            # Reading it here is the difference between migrating that surface and quietly not.
            slot_owners: set[str] = set()
            if _has_table(conn, "web_converged"):
                slot_owners = {
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT experience_id FROM web_converged WHERE ref=?", (OLD_REF,)
                    )
                }

            # -- the owned-problem rows the load gate and the vessel count require ----------
            if _has_table(conn, "corpus"):
                row = conn.execute(
                    "SELECT why_owned FROM corpus WHERE ledger_ref=?", (NEW_REF,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO corpus (ledger_ref, domain, why_owned, unlabeled, "
                        "provenance, corpus_pointers_json, scene_json) VALUES (?,?,?,?,?,?,?)",
                        (
                            NEW_REF,
                            NEW_CORPUS["domain"],
                            NEW_CORPUS["why_owned"],
                            NEW_CORPUS["unlabeled"],
                            NEW_CORPUS["provenance"],
                            "[]",
                            None,
                        ),
                    )
                    c["corpus"] = 1
                elif row["why_owned"] == _PLACEHOLDER_WHY:
                    conn.execute(
                        "UPDATE corpus SET why_owned=?, unlabeled=?, provenance=? "
                        "WHERE ledger_ref=?",
                        (
                            NEW_CORPUS["why_owned"],
                            NEW_CORPUS["unlabeled"],
                            NEW_CORPUS["provenance"],
                            NEW_REF,
                        ),
                    )
                    c["corpus"] = 1
            if _has_table(conn, "ledger"):
                row = conn.execute(
                    "SELECT owned_problem FROM ledger WHERE id=?", (NEW_REF,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO ledger (id, owned_problem, links_json) VALUES (?,?,?)",
                        (NEW_REF, NEW_LEDGER_OWNED_PROBLEM, "[]"),
                    )
                    c["ledger"] = 1
                elif row["owned_problem"] == _PLACEHOLDER_OWNED:
                    conn.execute(
                        "UPDATE ledger SET owned_problem=? WHERE id=?",
                        (NEW_LEDGER_OWNED_PROBLEM, NEW_REF),
                    )
                    c["ledger"] = 1

            # -- learner state: discriminated by frame_code -------------------------------
            if _has_table(conn, "frames"):
                for row in conn.execute(
                    "SELECT frame_code, breadth_json, unprompted_breadth_json FROM frames"
                ).fetchall():
                    if row["frame_code"] not in MOVED_FRAMES:
                        continue
                    breadth, b = _swap_list(row["breadth_json"])
                    unprompted, u = _swap_list(row["unprompted_breadth_json"])
                    if not (b or u):
                        continue
                    conn.execute(
                        "UPDATE frames SET breadth_json=?, unprompted_breadth_json=? "
                        "WHERE frame_code=?",
                        (breadth, unprompted, row["frame_code"]),
                    )
                    c["frames_breadth"] += int(b)
                    c["frames_unprompted"] += int(u)

            # -- the decision log: BOTH identity pairs, each on its own discriminator ------
            if _has_table(conn, "selection_log"):
                c["selection_log_problem"] = conn.execute(
                    "UPDATE selection_log SET problem=? WHERE experience_id=? AND problem=?",
                    (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
                ).rowcount
                c["selection_log_chosen"] = conn.execute(
                    "UPDATE selection_log SET chosen_problem=? "
                    "WHERE chosen_experience_id=? AND chosen_problem=?",
                    (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
                ).rowcount

            if _has_table(conn, "queue"):
                c["queue"] = conn.execute(
                    "UPDATE queue SET ledger_ref=? WHERE experience_id=? AND ledger_ref=?",
                    (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
                ).rowcount

            # -- the web half of the SAME file, which the first version forgot entirely ----
            if _has_table(conn, "web_converged"):
                c["web_converged"] = conn.execute(
                    "UPDATE web_converged SET ref=? WHERE experience_id=? AND ref=?",
                    (NEW_REF, MOVED_EXPERIENCE, OLD_REF),
                ).rowcount

            if _has_table(conn, "web_sitting_state"):
                for row in conn.execute(
                    "SELECT sitting_id, record_json, inflight_json FROM web_sitting_state"
                ).fetchall():
                    # inflight carries its own experience_id: the strongest discriminator there is
                    inflight = row["inflight_json"]
                    if inflight and OLD_REF in inflight:
                        d = json.loads(inflight)
                        if (
                            d.get("experience_id") == MOVED_EXPERIENCE
                            and d.get("ledger_ref") == OLD_REF
                        ):
                            d["ledger_ref"] = NEW_REF
                            conn.execute(
                                "UPDATE web_sitting_state SET inflight_json=? WHERE sitting_id=?",
                                (json.dumps(d), row["sitting_id"]),
                            )
                            c["web_sitting_inflight"] += 1
                    record = row["record_json"]
                    if record and OLD_REF in record:
                        d = json.loads(record)
                        if d.get("experience_id") != MOVED_EXPERIENCE:
                            continue  # not this problem's record; never guess from the ref alone
                        changed = False
                        if d.get("ledger_ref") == OLD_REF:
                            d["ledger_ref"] = NEW_REF
                            changed = True
                        houses = d.get("house_refs")
                        if isinstance(houses, list) and OLD_REF in houses:
                            d["house_refs"] = [NEW_REF if h == OLD_REF else h for h in houses]
                            changed = True
                        if changed:
                            conn.execute(
                                "UPDATE web_sitting_state SET record_json=? WHERE sitting_id=?",
                                (json.dumps(d), row["sitting_id"]),
                            )
                            c["web_sitting_record"] += 1
                # No discriminator exists for next_pick_ref (a bare ref, no companion
                # experience_id). Counted, never guessed.
                c["next_pick_ref_left"] = conn.execute(
                    "SELECT COUNT(*) FROM web_sitting_state WHERE next_pick_ref=?", (OLD_REF,)
                ).fetchone()[0]

            # -- domain slots: derived discriminator, and it refuses to guess --------------
            if _has_table(conn, "web_domain_slot"):
                # Only safe when the old ref's convergences are ALL this experience's; otherwise a
                # slot entry could belong to either problem and there is nothing to tell them apart.
                if slot_owners == {MOVED_EXPERIENCE}:
                    for row in conn.execute(
                        "SELECT slot, member_refs_json FROM web_domain_slot"
                    ).fetchall():
                        swapped, changed = _swap_list(row["member_refs_json"])
                        if changed:
                            conn.execute(
                                "UPDATE web_domain_slot SET member_refs_json=? WHERE slot=?",
                                (swapped, row["slot"]),
                            )
                            c["web_domain_slot"] += 1
    finally:
        conn.close()
    return c


if __name__ == "__main__":  # pragma: no cover - operational entrypoint
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/elenchus.db"
    counts = migrate(path)
    print(f"migrating {path}:")
    for k, v in counts.items():
        print(f"  {k:24s} {v}")
