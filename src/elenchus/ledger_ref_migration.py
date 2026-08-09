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
| record_json.ledger_ref                | experience_id INSIDE the json (its own identity) |
| record_json.house_refs                | PER INDEX: (house_refs[i], house_at[i]) ->       |
|                                       | web_converged.experience_id                      |
| web_domain_slot.member_refs_json      | member_frames_json: MOVED_FRAMES decides the new |
|                                       | ref, KEPT_FRAMES decides whether the old survives|
| web_sitting_state.next_pick_ref       | none; cleared on LIVE, left+counted on closed    |

A SECOND ADVERSARIAL PASS FOUND THREE MORE, ALL THE SAME ROOT ERROR ONE LEVEL DOWN: a discriminator
at the wrong GRAIN, or read from the wrong TABLE.

* `record_json.house_refs` was guarded by the RECORD's experience_id. It is not the record's own
  list: it is `convergence_order(converged_log())`, the cumulative cross-experience order of every
  convergence ever logged, and each element belongs to a different convergence. Rewriting all of
  them moved houses owned by `continuity_lock_in`, and `session_runner.memory` -- which compares the
  live `web_converged.ref` against this frozen list -- then returned `unavailable` for a memory that
  had opened correctly moments before, with `record_outcome` at that index refused by the same
  guard. Now discriminated per index against `house_at`.
* `web_domain_slot` was gated on who CONVERGED the ref. `member_refs` comes from
  `state.frames[c].breadth`, written on ENGAGEMENT, so a plateaued or CLI sitting puts the ref in a
  slot with no `web_converged` row at all and the gate passed on the wrong evidence. The
  discriminator is `member_frames_json`, and the rewrite ADDS rather than replaces: a slot whose
  members include frames from both problems legitimately draws on both after the split.
* `next_pick_ref` was left everywhere on the argument that such rows sit on CLOSED sittings. That
  was true of one particular database and false as a general claim. On a live sitting the pick is
  restored into `_next_pick` and can be offered to the learner under an identity that now means the
  other problem, so it is CLEARED there (transient state the next selection recomputes) and left,
  counted, on closed sittings where it is genuinely dead.

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
# The frames whose OLD_REF breadth entry can only have come from a `license_continuity` sitting.
#
# NOT "license_continuity's frames, and only those", which an earlier version of this comment said
# and which is FALSE: `lead_with_what_you_refuse_to_do` is also in `decision_under_stakes` and
# `protect_the_core_lane` is also in `proof_before_promise`. The migration is still correct, but for
# a different reason than that sentence gave, and the reason is what a future maintainer needs:
# `state.update_state` adds only the SERVED experience's OWN ledger_ref to a frame's breadth, so a
# sitting on `decision_under_stakes` writes ITS ref, never OLD_REF. Of the experiences carrying these
# three codes, only `license_continuity` ever carried OLD_REF, so an OLD_REF entry on any of them is
# necessarily its own. `embed_credentials_as_a_list` is excluded because it belongs to
# `continuity_lock_in`, which KEEPS the old ref.
#
# The distinction matters if this file is ever reused as a template: swapping by frame_code is safe
# only after re-deriving that no OTHER experience sharing the code also carried the ref being split.
# Hardcoded rather than derived from live content: a migration describes the world as it was when
# the rows were written, not whatever the rubrics say the day it happens to run.
MOVED_FRAMES = frozenset(
    {"lead_with_what_you_refuse_to_do", "protect_the_core_lane", "commit_under_the_deadline"}
)
# `continuity_lock_in`'s OWN rubric frames -- the only frames that can have put OLD_REF into a
# domain slot on the kept side. Its rubric is exactly one frame.
#
# THE MIRROR OF MOVED_FRAMES, and its absence was the third wrong-grain defect in a row. The slot
# rewrite asked `frames - MOVED_FRAMES` -- "is any other frame present?" -- but `member_frames_json`
# is a connected-COMPONENT union across experiences (`terrain._components` links frames by a shared
# breadth ref), so frames of `decision_under_stakes`, `proof_before_promise` and
# `irreversible_anchor` are present in essentially every real slot. Those write THEIR OWN ref and
# can never have contributed OLD_REF, so the predicate was almost always true and kept OLD_REF on
# evidence of a frame that could not have produced it. The same reasoning the module already spells
# out for the moved side (`update_state` adds only the SERVED experience's own ref) applies in
# mirror here, and was not applied.
KEPT_FRAMES = frozenset({"embed_credentials_as_a_list"})

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
        "house_refs_undiscriminated": 0,
        "next_pick_ref_cleared_live": 0,
        "next_pick_ref_left_closed": 0,
    }
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:  # commits on success, rolls back on any exception
            # Derived BEFORE any UPDATE runs. `web_domain_slot`'s discriminator is "who converged
            # the old ref", read out of `web_converged` -- and `web_converged` is rewritten below,
            # after which the query returns the empty set and the slot rewrite would silently skip.
            # Reading it here is the difference between migrating that surface and quietly not.
            # (ref, converged_at) -> experience_id, for EVERY convergence on the old ref. This is
            # the discriminator `record_json.house_refs` needs, and it must be read before
            # `web_converged` is rewritten below.
            # A value of None means AMBIGUOUS: two rows share the key with different owners.
            # `(sitting_id, ref, converged_at)` has no unique constraint -- this module says so
            # itself about the forecast write -- so `(ref, converged_at)` certainly does not, and a
            # plain dict would silently keep the last writer. Ambiguity must be detectable.
            converged_owner: dict[tuple[str, str], str | None] = {}
            old_ref_owners: set[str] = set()
            if _has_table(conn, "web_converged"):
                for r in conn.execute(
                    "SELECT ref, converged_at, experience_id FROM web_converged WHERE ref=?",
                    (OLD_REF,),
                ):
                    key = (r[0], r[1])
                    if key in converged_owner and converged_owner[key] != r[2]:
                        converged_owner[key] = None  # two owners, one key: undecidable
                    else:
                        converged_owner.setdefault(key, r[2])
                    old_ref_owners.add(r[2])

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
                        changed = False
                        # `ledger_ref` IS this record's own identity, so the record's own
                        # experience_id is the right discriminator for it.
                        if (
                            d.get("experience_id") == MOVED_EXPERIENCE
                            and d.get("ledger_ref") == OLD_REF
                        ):
                            d["ledger_ref"] = NEW_REF
                            changed = True
                        # `house_refs` IS NOT. It is `convergence_order(converged_log())`, the
                        # cumulative CROSS-EXPERIENCE list of every convergence ever logged, and
                        # `house_at` is its index-parallel timestamp list. Each element belongs to a
                        # DIFFERENT convergence with its own experience_id, so the record-grain
                        # discriminator is wrong by a whole grain here: an earlier version guarded
                        # the record and then rewrote every element, which moved houses belonging to
                        # `continuity_lock_in`. `session_runner.memory` then compares the live
                        # `web_converged.ref` against this frozen list and returns `unavailable` for
                        # a memory that opened correctly a moment earlier -- and `record_outcome` at
                        # that index is refused by the same guard. Discriminate PER INDEX, via
                        # (house_refs[i], house_at[i]) -> web_converged.experience_id.
                        houses = d.get("house_refs")
                        ats = d.get("house_at")
                        if isinstance(houses, list) and OLD_REF in houses:
                            # `house_at` is the per-index key. Present and unambiguous, it
                            # decides. MISSING (a record predating the column) or SHORT, there is
                            # no per-index key -- and "leave it" is not the safe default it looks
                            # like: `web_converged.ref` moves below, so a left-behind OLD_REF makes
                            # `memory` compare a moved live ref against a frozen stale one and
                            # return `unavailable`, the exact drift this discriminator exists to
                            # prevent. Fall back to the AGGREGATE, but only when it is unambiguous.
                            # Otherwise leave it and COUNT it: a silent skip reported as zero is how
                            # the first version of this file went wrong.
                            aggregate_safe = old_ref_owners == {MOVED_EXPERIENCE}
                            out = []
                            for i, h in enumerate(houses):
                                if h != OLD_REF:
                                    out.append(h)
                                    continue
                                at = ats[i] if isinstance(ats, list) and i < len(ats) else None
                                if at is not None and (h, at) in converged_owner:
                                    owner = converged_owner[(h, at)]
                                    if owner is None:  # two owners share the key
                                        c["house_refs_undiscriminated"] += 1
                                        out.append(h)
                                    else:
                                        out.append(NEW_REF if owner == MOVED_EXPERIENCE else h)
                                elif aggregate_safe:
                                    out.append(NEW_REF)
                                else:
                                    c["house_refs_undiscriminated"] += 1
                                    out.append(h)
                            if out != houses:
                                d["house_refs"] = out
                                changed = True
                        if changed:
                            conn.execute(
                                "UPDATE web_sitting_state SET record_json=? WHERE sitting_id=?",
                                (json.dumps(d), row["sitting_id"]),
                            )
                            c["web_sitting_record"] += 1
                # `next_pick_ref` is a bare ref with no companion experience_id, so it cannot be
                # discriminated. On a CLOSED sitting that is dead transient state: a persisted pick
                # is restored only for the live sitting, and closed is terminal. On a LIVE sitting
                # it is not -- it is restored into `_next_pick` and can be offered to the learner,
                # now naming the OTHER owned problem. An earlier version counted both together and
                # called the whole thing harmless, which was true of one particular database and
                # false as a general claim.
                #
                # The live one is CLEARED rather than guessed at. A next pick is transient
                # scheduling state that the next selection recomputes, so dropping it loses nothing
                # durable, whereas leaving it serves a door under an identity that no longer means
                # what it meant when it was written.
                if _has_table(conn, "web_sitting"):
                    c["next_pick_ref_cleared_live"] = conn.execute(
                        "UPDATE web_sitting_state SET next_pick_ref=NULL, next_pick_title='' "
                        "WHERE next_pick_ref=? AND sitting_id IN "
                        "(SELECT id FROM web_sitting WHERE status='live')",
                        (OLD_REF,),
                    ).rowcount
                c["next_pick_ref_left_closed"] = conn.execute(
                    "SELECT COUNT(*) FROM web_sitting_state WHERE next_pick_ref=?", (OLD_REF,)
                ).fetchone()[0]

            # -- domain slots: derived discriminator, and it refuses to guess --------------
            if _has_table(conn, "web_domain_slot"):
                # THE DISCRIMINATOR IS `member_frames_json`, NOT `web_converged`. An earlier version
                # gated this on who CONVERGED the old ref, but `member_refs` is built from
                # `state.frames[c].breadth`, which is written on ENGAGEMENT -- `breadth.add(ref)`
                # runs for any frame closed under pressure or reasoned unprompted, while
                # `log_converged` fires only on a genuine convergence. A plateaued sitting, or any
                # CLI run, puts the ref in a slot with no `web_converged` row at all, so the
                # convergence-derived gate passed while the slot's ref actually came from the frame
                # that does NOT move. The row then named a problem its own frames contradict, and a
                # RETIRED slot can never self-heal (`slots.resolve_slots` re-unions live rows only).
                #
                # ADD, never replace: a slot whose members include frames from BOTH problems
                # legitimately draws on both owned problems after the split.
                for row in conn.execute(
                    "SELECT slot, member_refs_json, member_frames_json FROM web_domain_slot"
                ).fetchall():
                    refs = json.loads(row["member_refs_json"] or "[]")
                    if OLD_REF not in refs:
                        continue
                    frames = set(json.loads(row["member_frames_json"] or "[]"))
                    if not (frames & MOVED_FRAMES):
                        continue  # no moved frame contributed this ref
                    # Not `frames - MOVED_FRAMES`: see KEPT_FRAMES. The question is whether a
                    # frame that could have WRITTEN the old ref is in this slot, not whether any
                    # other frame is.
                    keeps_old = bool(frames & KEPT_FRAMES)
                    out: list[str] = []
                    for r in refs:
                        if r == OLD_REF:
                            if keeps_old and OLD_REF not in out:
                                out.append(OLD_REF)
                            if NEW_REF not in out:
                                out.append(NEW_REF)
                        elif r not in out:
                            out.append(r)
                    if out != refs:
                        swapped, changed = json.dumps(out), True
                    else:
                        swapped, changed = row["member_refs_json"], False
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
