"""`ledger_ref` is the identity of one OWNED PROBLEM, and two experiences may not share one.

`continuity_lock_in` and `license_continuity` shipped sharing `veldra:license_fork_risk`. Nothing
broke loudly. Three things broke silently, and these tests lock each of them at the behavioural
level rather than only asserting that a duplicate is rejected:

* the display title of one problem was destroyed by a dict overwrite,
* the two could never both be offered, because the problem menu dedupes by ref,
* one problem was SERVED the other's authored scene while its own rubric did the grading.

Plus the latent one that would have bitten the moment any frame appeared in both rubrics: breadth
and transfer treat a ref as a problem, so a collision under-counts transfer and the strong tier.
The shipped rubrics share no frame, which is exactly why that one had to be tested synthetically.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from elenchus.content_loader import load_library
from elenchus.ledger_ref_migration import MOVED_FRAMES, NEW_REF, OLD_REF, migrate
from elenchus.policy import _transfer
from elenchus.state import _storage_tier
from elenchus.types import FrameStrength, LearnerState, Regime, Strength

NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


def _fs(breadth, unprompted=frozenset(), strength=Strength.forming):
    return FrameStrength(
        strength=strength,
        last_seen=NOW,
        due=NOW + timedelta(days=1),
        last_evidence="x:present_reasoned",
        evidence_count=1,
        breadth=set(breadth),
        unprompted_breadth=set(unprompted),
    )


# --------------------------------------------------------------- the invariant itself ------


def test_no_two_experiences_share_a_ledger_ref_in_the_shipped_library():
    """The collision this whole module exists for. Reads real content."""
    seen: dict[str, str] = {}
    for e in load_library():
        assert e.ledger_ref not in seen, (
            f"{e.experience_id} and {seen[e.ledger_ref]} share {e.ledger_ref}"
        )
        seen[e.ledger_ref] = e.experience_id


def test_load_library_refuses_a_duplicate_ledger_ref():
    """Fails CLOSED at the chokepoint every serving path loads through.

    `admission.py` has a `valid_ledger_refs` check with no caller anywhere in `src/` or `tests/`,
    so it could never have caught this. An invariant that cannot fail is not an invariant."""
    from elenchus.content_loader import _reject_duplicate_ledger_refs

    a, b = load_library()[:2]
    collided = [a, b.model_copy(update={"ledger_ref": a.ledger_ref})]
    with pytest.raises(ValueError, match="duplicate ledger_ref"):
        _reject_duplicate_ledger_refs(collided)


# --------------------------------------------------------- the three behavioural failures ------


def test_both_problems_keep_their_own_display_title():
    """`web/voice.py` builds `out[e.ledger_ref] = title`, so a shared ref silently destroyed one
    title and the surviving one labelled BOTH problems. Measured before the split:
    `display_titles()["veldra:license_fork_risk"]` returned "A contract ambiguity mid-rollout",
    and `continuity_lock_in`'s own title was gone."""
    from elenchus.web.voice import display_titles

    titles = display_titles()
    lib = {e.experience_id: e for e in load_library()}
    for eid in ("continuity_lock_in", "license_continuity"):
        exp = lib[eid]
        assert titles[exp.ledger_ref] == exp.rubric.display_title, (
            f"{eid} is not showing its own title; a ref collision is destroying one of them"
        )
    assert titles["veldra:license_fork_risk"] == lib["continuity_lock_in"].rubric.display_title
    assert len({lib[e].ledger_ref for e in ("continuity_lock_in", "license_continuity")}) == 2


def test_both_problems_are_independently_offerable():
    """`Proposal.problem_menu()` keeps the best-ranked candidate PER OWNED PROBLEM by deduping on
    `ledger_ref`. Correct when a ref is one problem; while the two shared a ref it silently made
    one of them unreachable from the menu whenever the other outranked it."""
    from elenchus.types import NextExperienceSpec, Proposal, SelectionReceipt

    lib = {e.experience_id: e for e in load_library()}

    def _cand(eid, frame):
        exp = lib[eid]
        spec = NextExperienceSpec(
            target_frames=[frame],
            ledger_ref=exp.ledger_ref,
            regime=Regime.open_ended,
            experience_id=eid,
        )
        receipt = SelectionReceipt(
            frame=frame,
            problem=exp.ledger_ref,
            experience_id=eid,
            drive="deploy",
            scores={},
            runner_up_drive=None,
            margin=0.0,
            content_gaps=[],
            created_at=NOW,
        )
        return (spec, receipt)

    menu = Proposal(
        candidates=[
            _cand("continuity_lock_in", "embed_credentials_as_a_list"),
            _cand("license_continuity", "protect_the_core_lane"),
        ]
    ).problem_menu()
    assert [s.experience_id for s, _ in menu] == ["continuity_lock_in", "license_continuity"], (
        "one problem was dropped from the menu: the dedupe key collapsed two owned problems"
    )


def test_each_problem_is_served_its_own_situation():
    """The severest of the three, and the one that decided which ref keeps which problem.

    `experience._attach_scene` REPLACES `exp.prompt` with the corpus scene resolved by
    `ledger_ref`. While the two shared a ref, `license_continuity` was served
    `continuity_lock_in`'s authored scene (a buyer's counsel, pre-signature) while being graded
    against its own rubric (a long-standing customer mid-rollout). The learner read one problem
    and was scored on another.

    A scene may legitimately override a prompt -- that is what the corpus is for -- so this
    asserts the weaker, true property: a scene may only reach the experience that OWNS its ref."""
    from elenchus.experience import _attach_scene
    from elenchus.types import CorpusEntry, Scene

    lib = {e.experience_id: e for e in load_library()}
    owner, other = lib["continuity_lock_in"], lib["license_continuity"]
    corpus = [
        CorpusEntry(
            ledger_ref=owner.ledger_ref,
            domain="founder_ceo",
            why_owned="w",
            unlabeled="u",
            provenance="p",
            corpus_pointers=[],
            scene=Scene(prompt=owner.prompt, situation="s"),
        )
    ]
    assert _attach_scene(other, corpus, None).prompt == other.prompt, (
        "license_continuity was served a scene belonging to another owned problem"
    )


def test_distinct_refs_count_as_distinct_problems_for_transfer_and_the_strong_bar():
    """The latent failure, tested synthetically because the shipped rubrics share no frame code.

    `breadth` is documented as "problems engaged with a mechanism" and is filled with `ledger_ref`.
    Under a collision the two problems collapse to ONE entry, so `_transfer` reports the second
    problem as already-covered and `_storage_tier` never reaches the >= 2 strong bar from them."""
    code = "shared_frame"
    engaged_on_old = LearnerState(frames={code: _fs({OLD_REF})})

    assert _transfer(engaged_on_old, code, NEW_REF) == 1.0, (
        "a genuinely different owned problem must still offer transfer"
    )
    assert _transfer(engaged_on_old, code, OLD_REF) == 0.0  # same problem: no transfer left

    # the strong bar counts PROBLEMS; two distinct refs clear it, one collapsed ref would not
    assert _storage_tier(2, {OLD_REF, NEW_REF}) is Strength.strong
    assert _storage_tier(2, {OLD_REF}) is not Strength.strong


# ----------------------------------------------------------------------- the migration ------

# ----------------------------------------------------------------------- the migration ------
#
# THE PRODUCTION SCHEMA, NEVER A HAND-ROLLED ONE. The first version of these tests built
# `CREATE TABLE selection_log (experience_id TEXT, problem TEXT)` -- two of thirteen columns, a
# shape no production path can emit -- so a migration that rewrote only `problem` and left
# `chosen_problem` on the old ref passed green, and the commit message's row count was measured
# with the same one-sided predicate. The real db then ended up holding an `outcome='accepted'` row
# whose two halves named different owned problems. A fixture narrower than production cannot see
# the columns production has.


def _production_db(path, authored_frames=None):
    """A database with the REAL schema, built by the real writers, in its PRE-split state.

    `authored_frames` is which frames actually HELD OLD_REF in their breadth. It defaults to the
    historical set, but every slot test must set it explicitly: seeding every frame as an author
    made membership and authorship identical in every fixture here, so no test in this file could
    tell them apart -- which is exactly the confusion the migration kept making, encoded into the
    thing meant to catch it."""
    from elenchus.persistence import Store
    from elenchus.web.sitting_store import SittingStore

    Store(path)  # engine tables
    SittingStore(path)  # web tables, same file
    c = sqlite3.connect(path)
    c.execute(
        "INSERT OR REPLACE INTO corpus (ledger_ref, domain, why_owned, unlabeled, provenance,"
        " corpus_pointers_json, scene_json) VALUES (?,?,?,?,?,?,?)",
        (OLD_REF, "founder_ceo", "stakes", "unlabeled", "prov", "[]", None),
    )
    c.execute(
        "INSERT OR REPLACE INTO ledger (id, owned_problem, links_json) VALUES (?,?,?)",
        (OLD_REF, "the license fork problem", "[]"),
    )
    historical = sorted(MOVED_FRAMES) + ["embed_credentials_as_a_list"]
    for code in historical if authored_frames is None else sorted(authored_frames):
        c.execute(
            "INSERT OR REPLACE INTO frames (frame_code, strength, last_seen, due, last_evidence,"
            " evidence_count, breadth_json, unprompted_breadth_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                code,
                "forming",
                NOW.isoformat(),
                NOW.isoformat(),
                "x",
                1,
                f'["{OLD_REF}"]',
                f'["{OLD_REF}"]',
            ),
        )
    # ADVERSARIAL ROW 1: an ACCEPTED selection carrying all four identity columns. The one-sided
    # migration turned this into a row naming two different owned problems.
    c.execute(
        "INSERT INTO selection_log (created_at, frame, problem, experience_id, drive, scores_json,"
        " runner_up_drive, margin, content_gaps_json, outcome, chosen_frame, chosen_problem,"
        " chosen_experience_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            NOW.isoformat(),
            "protect_the_core_lane",
            OLD_REF,
            "license_continuity",
            "deploy",
            "{}",
            None,
            0.0,
            "[]",
            "accepted",
            "protect_the_core_lane",
            OLD_REF,
            "license_continuity",
        ),
    )
    # ADVERSARIAL ROW 2: continuity_lock_in's own row. Must NOT move, either side.
    c.execute(
        "INSERT INTO selection_log (created_at, frame, problem, experience_id, drive, scores_json,"
        " runner_up_drive, margin, content_gaps_json, outcome, chosen_frame, chosen_problem,"
        " chosen_experience_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            NOW.isoformat(),
            "embed_credentials_as_a_list",
            OLD_REF,
            "continuity_lock_in",
            "deploy",
            "{}",
            None,
            0.0,
            "[]",
            "accepted",
            "embed_credentials_as_a_list",
            OLD_REF,
            "continuity_lock_in",
        ),
    )
    # ADVERSARIAL ROW 3: a PRE-EXISTING convergence. The first migration forgot the web tables
    # entirely, and this row is the one whose memory then recalled the other problem's situation.
    c.execute(
        "INSERT INTO web_converged (sitting_id, ref, converged_at, experience_id, position)"
        " VALUES (?,?,?,?,?)",
        ("sit1", OLD_REF, NOW.isoformat(), "license_continuity", "my call"),
    )
    c.commit()
    c.close()
    return path


def test_migration_moves_every_identity_surface_on_the_production_schema(tmp_path):
    db = _production_db(str(tmp_path / "prod.db"))
    counts = migrate(db)

    assert counts["selection_log_problem"] == 1
    assert counts["selection_log_chosen"] == 1, "the chosen_* pair is a second identity surface"
    assert counts["web_converged"] == 1, "the web tables live in the SAME file"
    assert counts["corpus"] == 1 and counts["ledger"] == 1
    assert counts["frames_breadth"] == 3 and counts["frames_unprompted"] == 3

    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rows = [dict(r) for r in c.execute("SELECT * FROM selection_log")]
    mine = [r for r in rows if r["experience_id"] == "license_continuity"][0]
    theirs = [r for r in rows if r["experience_id"] == "continuity_lock_in"][0]

    # SEMANTIC consistency, not row counts: each identity pair must agree with itself.
    assert mine["problem"] == NEW_REF and mine["chosen_problem"] == NEW_REF
    assert theirs["problem"] == OLD_REF and theirs["chosen_problem"] == OLD_REF
    assert mine["problem"] == mine["chosen_problem"], (
        "an accepted row whose halves name different owned problems is the one-sided migration"
    )
    assert c.execute("SELECT ref FROM web_converged").fetchone()[0] == NEW_REF
    # continuity_lock_in's own frame never moves
    assert (
        OLD_REF
        in c.execute(
            "SELECT breadth_json FROM frames WHERE frame_code='embed_credentials_as_a_list'"
        ).fetchone()[0]
    )
    c.close()


def test_the_repaired_memory_recalls_the_experience_actually_worked(tmp_path):
    """The regression the first migration CAUSED: a pre-existing convergence kept the old ref, and
    because only continuity_lock_in resolves for it now, `_memory_situation`'s experience_id
    disambiguation could no longer match and fell back to the other problem's prompt."""
    db = _production_db(str(tmp_path / "prod.db"))
    migrate(db)

    c = sqlite3.connect(db)
    ref, eid = c.execute("SELECT ref, experience_id FROM web_converged").fetchone()
    c.close()
    lib = {e.experience_id: e for e in load_library()}
    entries = [e for e in load_library() if e.ledger_ref == ref]
    match = [e for e in entries if e.experience_id == eid]
    served = (match or entries)[0]
    assert served.experience_id == "license_continuity"
    assert served.prompt == lib["license_continuity"].prompt


def test_migration_is_idempotent_on_the_production_schema(tmp_path):
    db = _production_db(str(tmp_path / "prod.db"))
    first = migrate(db)
    assert sum(v for k, v in first.items() if not k.startswith("next_pick_ref")) > 0

    c = sqlite3.connect(db)
    before = c.execute("SELECT * FROM selection_log ORDER BY rowid").fetchall()
    c.close()

    second = migrate(db)
    assert all(v == 0 for k, v in second.items() if not k.startswith("next_pick_ref"))
    c = sqlite3.connect(db)
    assert c.execute("SELECT * FROM selection_log ORDER BY rowid").fetchall() == before
    c.close()


def test_migration_upgrades_a_build_store_placeholder_instead_of_no_opping(tmp_path):
    """Booting the app before migrating makes `cli.build_store` author a placeholder corpus/ledger
    row for the new ref. A bare INSERT OR IGNORE would then be a permanent no-op reporting
    `corpus: 0` -- byte-indistinguishable from a clean idempotent re-run, while the fields
    `anti_label_gate` grades on stay machine text forever."""
    from elenchus.cli import build_store

    db = _production_db(str(tmp_path / "prod.db"))
    build_store(db)  # the boot that shipped before the operator ran the migration
    counts = migrate(db)

    assert counts["corpus"] == 1 and counts["ledger"] == 1, "the placeholder must be upgraded"
    c = sqlite3.connect(db)
    why = c.execute("SELECT why_owned FROM corpus WHERE ledger_ref=?", (NEW_REF,)).fetchone()[0]
    owned = c.execute("SELECT owned_problem FROM ledger WHERE id=?", (NEW_REF,)).fetchone()[0]
    c.close()
    assert "seed stakes" not in why and "Abstracted seed" not in owned


def test_migration_survives_degenerate_databases(tmp_path):
    """Empty, schema-only, and already-migrated. A migration nobody dares re-run is a migration
    that will be run twice by accident anyway."""
    empty = str(tmp_path / "empty.db")
    sqlite3.connect(empty).close()
    assert all(v == 0 for v in migrate(empty).values())

    db = _production_db(str(tmp_path / "p2.db"))
    migrate(db)
    assert all(v == 0 for k, v in migrate(db).items() if not k.startswith("next_pick_ref"))


def test_breadth_never_stores_the_same_problem_twice(tmp_path):
    """Between the content change shipping and the operator migrating, a live sitting writes the
    NEW ref into breadth, so a row can hold both. Mapping without de-duplication stores the same
    identifier twice -- a durable row lying about what happened, even though `load_state`'s set()
    hides it from every reader."""
    db = _production_db(str(tmp_path / "prod.db"))
    c = sqlite3.connect(db)
    c.execute(
        "UPDATE frames SET breadth_json=? WHERE frame_code='protect_the_core_lane'",
        (json.dumps([OLD_REF, NEW_REF]),),
    )
    c.commit()
    c.close()

    migrate(db)
    c = sqlite3.connect(db)
    stored = json.loads(
        c.execute(
            "SELECT breadth_json FROM frames WHERE frame_code='protect_the_core_lane'"
        ).fetchone()[0]
    )
    c.close()
    assert stored == [NEW_REF], f"duplicate identifier persisted: {stored}"


def test_next_pick_residuals_cannot_reach_a_learner(tmp_path):
    """`next_pick_ref` is the one identity surface with NO discriminator (a bare ref, no companion
    experience_id), so the migration reports it as `next_pick_ref_left` rather than guessing. That
    is only acceptable if such a row cannot be consumed, and this proves it can't.

    `SessionRegistry` restores a persisted pick into `_next_pick` and can drive a selection from
    it -- but only for the LIVE sitting. `SittingStore.live_sitting` selects `WHERE status='live'`,
    `web_sitting.status` has exactly two writers (INSERT 'live' for a NEW id, UPDATE to 'closed'),
    nothing reopens a closed sitting, and a unique index allows at most one live row. So a stale
    pick on a closed sitting is dead transient state."""
    from elenchus.web.sitting_store import SittingStore

    db = str(tmp_path / "pick.db")
    st = SittingStore(db)
    sid = st.create_sitting(NOW)
    st.write_state(sid, next_pick=(OLD_REF, "a stale door"), now=NOW)
    assert st.read_state(sid)["next_pick"] == (OLD_REF, "a stale door")

    st.close_sitting(sid)
    assert st.live_sitting() is None, "a closed sitting must not resume"

    # a new sitting is a NEW id and carries none of the closed one's pick
    sid2 = st.create_sitting(NOW + timedelta(hours=1))
    assert sid2 != sid
    assert st.read_state(sid2)["next_pick"] is None
    assert st.live_sitting()["id"] == sid2

    c = sqlite3.connect(db)
    stale = c.execute(
        "SELECT COUNT(*) FROM web_sitting_state s JOIN web_sitting w ON w.id=s.sitting_id "
        "WHERE s.next_pick_ref=? AND w.status='live'",
        (OLD_REF,),
    ).fetchone()[0]
    c.close()
    assert stale == 0, "a stale pick survives on a LIVE sitting; reporting it is not enough"


def test_house_refs_are_discriminated_per_index_not_per_record(tmp_path):
    """`house_refs` is the cumulative CROSS-EXPERIENCE convergence order, not the record's own
    refs. Guarding it by the record's experience_id and then rewriting every element moves houses
    owned by `continuity_lock_in`; `session_runner.memory` compares the live `web_converged.ref`
    against this frozen list and returns `unavailable` for a memory that opened a moment earlier."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "h.db"))
    st = SittingStore(db)
    sid = st.create_sitting(NOW)
    later = NOW + timedelta(minutes=5)
    # two convergences on the OLD ref, one per problem -- the case the record grain cannot see
    st.log_converged(sid, OLD_REF, NOW, experience_id="continuity_lock_in", position="a")
    st.log_converged(sid, OLD_REF, later, experience_id="license_continuity", position="b")
    st.write_state(
        sid,
        record={
            "experience_id": "license_continuity",
            "ledger_ref": OLD_REF,
            "house_refs": [OLD_REF, OLD_REF],
            "house_at": [NOW.isoformat(), later.isoformat()],
        },
        now=later,
    )

    migrate(db)
    c = sqlite3.connect(db)
    rec = json.loads(
        c.execute(
            "SELECT record_json FROM web_sitting_state WHERE sitting_id=?", (sid,)
        ).fetchone()[0]
    )
    c.close()
    assert rec["house_refs"] == [OLD_REF, NEW_REF], (
        "continuity_lock_in's house was rewritten; the discriminator is per INDEX, not per record"
    )
    assert rec["ledger_ref"] == NEW_REF  # the record's OWN identity still moves


def test_domain_slot_keeps_the_old_ref_when_a_non_moved_frame_owns_it(tmp_path):
    """`member_refs` is built from breadth (ENGAGEMENT), not from convergence, so gating on
    `web_converged` read the wrong table. The discriminator is `member_frames_json`, and a slot
    whose members include frames from BOTH problems legitimately draws on both after the split."""
    db = _production_db(str(tmp_path / "s.db"))
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO web_domain_slot (slot, first_touch_at, member_refs_json, member_frames_json,"
        " status) VALUES (?,?,?,?,?)",
        (
            0,
            NOW.isoformat(),
            json.dumps([OLD_REF]),
            json.dumps(sorted(MOVED_FRAMES) + ["embed_credentials_as_a_list"]),
            "live",
        ),
    )
    # a slot owned ONLY by moved frames: the old ref should not survive there
    c.execute(
        "INSERT INTO web_domain_slot (slot, first_touch_at, member_refs_json, member_frames_json,"
        " status) VALUES (?,?,?,?,?)",
        (1, NOW.isoformat(), json.dumps([OLD_REF]), json.dumps(sorted(MOVED_FRAMES)), "live"),
    )
    c.commit()
    c.close()

    migrate(db)
    c = sqlite3.connect(db)
    mixed = json.loads(
        c.execute("SELECT member_refs_json FROM web_domain_slot WHERE slot=0").fetchone()[0]
    )
    pure = json.loads(
        c.execute("SELECT member_refs_json FROM web_domain_slot WHERE slot=1").fetchone()[0]
    )
    c.close()
    assert mixed == [OLD_REF, NEW_REF], f"a mixed slot must draw on both problems, got {mixed}"
    assert pure == [NEW_REF], f"a slot owned only by moved frames must move, got {pure}"


def test_a_stale_pick_on_a_LIVE_sitting_is_cleared_not_left(tmp_path):
    """The earlier claim that these rows are always on closed sittings was true of one database and
    false in general. On a live sitting the pick is restored into `_next_pick` and can be offered
    to the learner under an identity that now means the other problem."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "p.db"))
    st = SittingStore(db)
    live = st.create_sitting(NOW)
    st.write_state(live, next_pick=(OLD_REF, "a stale door"), now=NOW)

    counts = migrate(db)
    assert counts["next_pick_ref_cleared_live"] == 1
    assert st.read_state(live)["next_pick"] is None, "a live sitting still serves the stale pick"


def test_a_slot_does_not_keep_the_old_ref_for_a_frame_that_could_not_have_written_it(tmp_path):
    """The third wrong-grain defect, and the fixture that could not see it.

    `member_frames_json` is a connected-COMPONENT union across experiences, so frames belonging to
    `decision_under_stakes` / `proof_before_promise` / `irreversible_anchor` sit in essentially
    every real slot. Those write their OWN ref and can never have contributed OLD_REF. Asking
    `frames - MOVED_FRAMES` therefore kept OLD_REF almost always, on evidence of a frame that could
    not have produced it -- and the earlier test only exercised a slot whose extra frame WAS
    `embed_credentials_as_a_list`, the single case where the wrong predicate gives the right
    answer."""
    db = _production_db(str(tmp_path / "slotgrain.db"))
    c = sqlite3.connect(db)
    # a real component shape: license_continuity's frames unioned with decision_under_stakes'.
    # continuity_lock_in was never engaged, so nothing here can have written OLD_REF but the
    # moved frames.
    c.execute(
        "INSERT INTO web_domain_slot (slot, first_touch_at, member_refs_json, member_frames_json,"
        " status) VALUES (?,?,?,?,?)",
        (
            0,
            NOW.isoformat(),
            json.dumps([OLD_REF, "veldra:concentrated_market_pricing_power"]),
            json.dumps(sorted(MOVED_FRAMES) + ["choose_the_failure_default_deliberately"]),
            "live",
        ),
    )
    c.commit()
    c.close()

    migrate(db)
    c = sqlite3.connect(db)
    refs = json.loads(
        c.execute("SELECT member_refs_json FROM web_domain_slot WHERE slot=0").fetchone()[0]
    )
    c.close()
    assert OLD_REF not in refs, (
        "the slot kept an owned problem no member frame could have engaged; a later "
        "continuity_lock_in component then matches this slot by ref and never earns its own bearing"
    )
    assert NEW_REF in refs and "veldra:concentrated_market_pricing_power" in refs


def test_house_refs_without_house_at_falls_back_to_the_aggregate_when_unambiguous(tmp_path):
    """A record written before `house_at` existed has no per-index key. "Leave it" is not the safe
    default it looks like: `web_converged.ref` moves, so a left-behind OLD_REF makes `memory`
    compare a moved live ref against a frozen stale one and return `unavailable` -- the exact drift
    the per-index discriminator exists to prevent."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "noat.db"))
    st = SittingStore(db)
    sid = st.create_sitting(NOW)
    st.log_converged(sid, OLD_REF, NOW, experience_id="license_continuity", position="p")
    st.write_state(
        sid,
        record={
            "experience_id": "license_continuity",
            "ledger_ref": OLD_REF,
            "house_refs": [OLD_REF],
        },  # no house_at at all
        now=NOW,
    )
    counts = migrate(db)
    c = sqlite3.connect(db)
    rec = json.loads(
        c.execute(
            "SELECT record_json FROM web_sitting_state WHERE sitting_id=?", (sid,)
        ).fetchone()[0]
    )
    c.close()
    assert rec["house_refs"] == [NEW_REF]
    assert counts["house_refs_undiscriminated"] == 0


def test_an_ambiguous_house_entry_is_left_and_counted_never_guessed(tmp_path):
    """`(ref, converged_at)` has no unique constraint -- this module says so itself about the
    forecast write. Two rows sharing it with DIFFERENT owners make the per-index lookup undecidable,
    and a plain dict would silently keep the last writer."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "amb.db"))
    st = SittingStore(db)
    sid = st.create_sitting(NOW)
    st.log_converged(sid, OLD_REF, NOW, experience_id="license_continuity", position="a")
    st.log_converged(sid, OLD_REF, NOW, experience_id="continuity_lock_in", position="b")
    st.write_state(
        sid,
        record={
            "experience_id": "license_continuity",
            "ledger_ref": OLD_REF,
            "house_refs": [OLD_REF],
            "house_at": [NOW.isoformat()],
        },
        now=NOW,
    )
    counts = migrate(db)
    c = sqlite3.connect(db)
    rec = json.loads(
        c.execute(
            "SELECT record_json FROM web_sitting_state WHERE sitting_id=?", (sid,)
        ).fetchone()[0]
    )
    c.close()
    assert rec["house_refs"] == [OLD_REF], "an undecidable entry was guessed"
    assert counts["house_refs_undiscriminated"] == 1, "and it must be reported, never silent"


# ------------------------------------------------------------- the migration doctrine ------
#
# NEVER INFER OWNERSHIP FROM MEMBERSHIP IN AN AGGREGATE UNLESS EVERY MEMBER OF THAT AGGREGATE IS
# CAPABLE OF PRODUCING THE VALUE BEING MIGRATED.
#
# That single sentence is the conceptual error behind three consecutive adversarial rounds:
#   round 1: four of eleven identity columns migrated, keyed on the old ref alone.
#   round 2: `house_refs` guarded at the RECORD grain when it is a cumulative cross-experience
#            array; `web_domain_slot` gated on convergence when its data comes from engagement.
#   round 3: `keeps_old = frames - MOVED_FRAMES` -- membership in a component union treated as
#            evidence of authorship, when most members cannot author the value at all.
#
# The example-based tests above each pinned one instance. This section pins the PROPERTY, which is
# what would have caught round three on the day it shipped.

_UNRELATED_FRAME = "choose_the_failure_default_deliberately"  # decision_under_stakes / proof


def _slot_refs_after_migration(tmp_path, name, frames, authored, refs=(OLD_REF,)):
    """Build a slot whose member_frames are `frames`, where only `authored` actually held OLD_REF.

    THE `authored` AXIS IS THE WHOLE POINT and it is required, not optional. `member_frames_json`
    is a connected-COMPONENT union -- `terrain._components` links frames by ANY shared breadth ref
    and `slots._union_into` only ever grows it -- so a frame reaches a slot through refs that have
    nothing to do with the split. A helper that let membership imply authorship is how the previous
    property test looked thorough while encoding the exact bug it was written to catch."""
    db = _production_db(str(tmp_path / f"{name}.db"), authored_frames=authored)
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO web_domain_slot (slot, first_touch_at, member_refs_json, member_frames_json,"
        " status) VALUES (?,?,?,?,?)",
        (0, NOW.isoformat(), json.dumps(list(refs)), json.dumps(sorted(frames)), "live"),
    )
    c.commit()
    c.close()
    migrate(db)
    c = sqlite3.connect(db)
    out = json.loads(
        c.execute("SELECT member_refs_json FROM web_domain_slot WHERE slot=0").fetchone()[0]
    )
    c.close()
    return out


def test_a_non_authoring_frame_cannot_change_how_the_old_ref_is_treated(tmp_path):
    """THE PROPERTY, on the axis that actually decides.

    A frame that never held OLD_REF must not change its treatment -- not whether it moves, not
    whether it is retained -- no matter which side of the split that frame's rubric sits on. Four
    adversarial rounds died on this one invariant: `frames - MOVED_FRAMES`, then
    `frames & KEPT_FRAMES`, then `frames & MOVED_FRAMES` one line above it, all read component
    membership as evidence of authorship."""
    from elenchus.ledger_ref_migration import KEPT_FRAMES

    kept, moved = sorted(KEPT_FRAMES)[0], sorted(MOVED_FRAMES)[0]
    for label, authors in (
        ("moved_author", {moved}),
        ("kept_author", {kept}),
        ("both_authors", {kept, moved}),
    ):
        alone = _slot_refs_after_migration(tmp_path, f"{label}_a", authors, authors)
        for i, passenger in enumerate([kept, moved, _UNRELATED_FRAME]):
            if passenger in authors:
                continue
            widened = _slot_refs_after_migration(
                tmp_path, f"{label}_{i}", authors | {passenger}, authors
            )
            assert widened == alone, (
                f"a non-authoring {passenger!r} in a {label} slot changed the treatment of the "
                f"old ref: {alone} -> {widened}. Membership is being read as authorship."
            )


def test_a_slot_no_member_of_which_authored_the_old_ref_is_left_alone(tmp_path):
    """The ref arrived through some other member of the component and is none of this migration's
    business. Touching it would assert an ownership the database does not record."""
    from elenchus.ledger_ref_migration import KEPT_FRAMES

    out = _slot_refs_after_migration(
        tmp_path, "noauthor", set(KEPT_FRAMES) | set(MOVED_FRAMES), authored=set()
    )
    assert out == [OLD_REF], f"a slot with no author of the old ref was rewritten anyway: {out}"


def test_each_authorship_case_gets_the_right_treatment(tmp_path):
    """What the ANSWER is for each case, so "an unrelated frame changes nothing" cannot be
    satisfied by a migration that does nothing at all."""
    from elenchus.ledger_ref_migration import KEPT_FRAMES

    kept, moved = sorted(KEPT_FRAMES)[0], sorted(MOVED_FRAMES)[0]

    assert _slot_refs_after_migration(tmp_path, "k", {kept}, {kept}) == [OLD_REF], (
        "only continuity_lock_in's frame authored it: the old ref stays, alone"
    )
    assert _slot_refs_after_migration(tmp_path, "m", {moved}, {moved}) == [NEW_REF], (
        "only a moved frame authored it: the old ref cannot have come from anywhere else here"
    )
    assert _slot_refs_after_migration(tmp_path, "b", {kept, moved}, {kept, moved}) == [
        OLD_REF,
        NEW_REF,
    ], "both authored it: the slot genuinely draws on both owned problems"


def test_an_unauthored_slot_is_left_alone_AND_COUNTED(tmp_path):
    """Leaving the row alone is right. Reporting nothing about it is not.

    One block up, `house_refs_undiscriminated` exists because "a silent skip reported as zero is
    how the first version of this file went wrong". The slot branch added in round four skipped
    silently, so an operator reading `web_domain_slot: 0` could not tell "no slot needed migrating"
    from "a slot holds the old ref and I declined to touch it". Same policy, same file, one block
    apart.

    TWO SLOTS, AND THAT IS THE POINT. The first version of this test built ONE slot and made it
    unauthored, so the counter could be hoisted above the authorship predicate -- counting every
    slot holding the old ref rather than only the refused ones -- and the whole file still passed.
    That is this file's oldest failure repeating itself for a fifth time: a fixture in which the
    wrong predicate cannot give a different answer. A counter that discriminates must be shown a
    case on each side of the line."""
    from elenchus.ledger_ref_migration import KEPT_FRAMES

    moved = sorted(MOVED_FRAMES)[0]
    kept = sorted(KEPT_FRAMES)[0]
    db = _production_db(str(tmp_path / "unauthored.db"), authored_frames={moved})
    c = sqlite3.connect(db)
    for slot, members in ((0, [moved]), (1, [kept, _UNRELATED_FRAME])):
        c.execute(
            "INSERT INTO web_domain_slot (slot, first_touch_at, member_refs_json,"
            " member_frames_json, status) VALUES (?,?,?,?,?)",
            (slot, NOW.isoformat(), json.dumps([OLD_REF]), json.dumps(sorted(members)), "live"),
        )
    c.commit()
    c.close()

    counts = migrate(db)

    assert counts["web_domain_slot"] == 1, "slot 0's member authored the ref and must move"
    assert counts["web_domain_slot_unauthored"] == 1, (
        "exactly ONE slot was refused. Counting 2 means the counter is keyed on holding the old "
        "ref rather than on the refusal, which is the discrimination it exists to report"
    )
    c = sqlite3.connect(db)
    rows = dict(c.execute("SELECT slot, member_refs_json FROM web_domain_slot").fetchall())
    c.close()
    assert json.loads(rows[0]) == [NEW_REF], "the authored slot moves"
    assert json.loads(rows[1]) == [OLD_REF], "the unauthored slot is untouched"


def test_a_pick_whose_sitting_status_is_unknown_is_not_reported_as_closed(tmp_path):
    """`next_pick_ref_left_closed` counts every row the live clear did not take and calls it dead.

    The live clear matches `sitting_id IN (SELECT id FROM web_sitting WHERE status='live')`, so a
    state row whose sitting has no `web_sitting` row at all is not cleared, is counted, and is
    reported under a name asserting it is closed. Nothing in the file establishes that. The whole
    point of leaving these rows was that a bare ref cannot be discriminated, so the count must not
    quietly claim otherwise."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "orphan.db"))
    st = SittingStore(db)

    # TWO closed and ONE orphan, and the asymmetry is deliberate. With one of each, the correct
    # predicate and its exact INVERSION both return 1, so the test was satisfied by the negation
    # of the thing it protects. Counts on the two sides must differ for the assertion to mean
    # anything: 1 unverified against 2 verifiable.
    for i, label in enumerate(("a genuinely dead door", "another dead door")):
        dead = st.create_sitting(NOW + timedelta(minutes=i))
        st.write_state(dead, next_pick=(OLD_REF, label), now=NOW)
        st.close_sitting(dead)

    orphan = st.create_sitting(NOW + timedelta(minutes=5))
    st.write_state(orphan, next_pick=(OLD_REF, "a door of unknown status"), now=NOW)
    c = sqlite3.connect(db)
    c.execute("DELETE FROM web_sitting WHERE id=?", (orphan,))  # state outlives its sitting row
    c.commit()
    c.close()

    counts = migrate(db)

    assert counts["next_pick_ref_cleared_live"] == 0, "nothing is live"
    assert counts["next_pick_ref_left_closed"] == 3, "all three rows were left in place"
    assert counts["next_pick_ref_left_unverified"] == 1, (
        "exactly ONE of the three cannot be shown to sit on a closed sitting. Reading 2 means the "
        "predicate is inverted; reading 3 means it is not discriminating at all"
    )


def test_one_null_id_cannot_drive_the_unverified_count_to_zero(tmp_path):
    """The counter must fail CLOSED. `NOT IN` fails open, and that is how it was first written.

    SQLite permits NULL in a `TEXT PRIMARY KEY` (`web_sitting.id` is exactly that), and its
    three-valued `NOT IN` yields UNKNOWN, never TRUE, once a NULL appears in the subquery. So a
    single `web_sitting` row with a NULL id drove this counter to 0 no matter how many rows were
    genuinely unverifiable, reporting "nothing here was guessed" precisely when the data is at its
    most ambiguous.

    The fixture holds one row on each side of the line, because a fixture where every row is
    unverifiable cannot tell an undercount from a correct answer. `NOT IN` returns 0 here and the
    truth is 1.

    Same shape as everything else this file has been wrong about: a check that answers zero when it
    cannot decide, instead of answering that it cannot decide."""
    from elenchus.web.sitting_store import SittingStore

    db = _production_db(str(tmp_path / "nullid.db"))
    st = SittingStore(db)

    # Only ONE sitting may be live at a time: a partial unique index makes the second
    # `create_sitting` ADOPT the first rather than mint a second id. Close before creating.
    dead = st.create_sitting(NOW)
    st.write_state(dead, next_pick=(OLD_REF, "provably dead"), now=NOW)
    st.close_sitting(dead)

    orphan = st.create_sitting(NOW + timedelta(minutes=1))
    st.write_state(orphan, next_pick=(OLD_REF, "unknowable"), now=NOW)

    c = sqlite3.connect(db)
    c.execute("DELETE FROM web_sitting WHERE id=?", (orphan,))  # state outlives its sitting row
    c.execute(
        "INSERT INTO web_sitting (id, status, updated_at) VALUES (NULL,'closed',?)",
        (NOW.isoformat(),),
    )
    c.commit()
    assert c.execute("SELECT COUNT(*) FROM web_sitting WHERE id IS NULL").fetchone()[0] == 1, (
        "the whole point of this fixture is a NULL id; if sqlite ever rejects it, this test is void"
    )
    c.close()

    counts = migrate(db)

    assert counts["next_pick_ref_cleared_live"] == 0, "nothing is live"
    assert counts["next_pick_ref_left_closed"] == 2, "both rows were left in place"
    assert counts["next_pick_ref_left_unverified"] == 1, (
        "the orphan cannot be shown to sit on a closed sitting and must be reported; a NULL id "
        "elsewhere in the table must not silently answer the question for every row at once"
    )


def test_without_web_sitting_every_left_row_is_unverified(tmp_path):
    """The branch the counter exists for, and it had no test.

    `next_pick_ref_left_closed` is computed unconditionally, but the live clear that gives the word
    "closed" its meaning runs only `if _has_table(conn, "web_sitting")`. Without that table nothing
    establishes any row's status, so every left row is a guess and the fallback must say so.
    Deleting the `else` branch entirely left the whole file green before this existed."""
    db = _production_db(str(tmp_path / "nositting.db"))
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO web_sitting_state (sitting_id, next_pick_ref, next_pick_title) VALUES (?,?,?)",
        ("orphaned-state-row", OLD_REF, "a door with no sitting table at all"),
    )
    c.execute("DROP TABLE web_sitting")
    c.commit()
    c.close()

    counts = migrate(db)

    assert counts["next_pick_ref_cleared_live"] == 0, "there is no table to read status from"
    assert counts["next_pick_ref_left_closed"] == 1
    assert counts["next_pick_ref_left_unverified"] == 1, (
        "with no web_sitting table NOTHING is provably closed, so the whole left count is guessed"
    )
