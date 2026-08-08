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


def _seed(path):
    c = sqlite3.connect(path)
    c.executescript(
        "CREATE TABLE frames (frame_code TEXT PRIMARY KEY, breadth_json TEXT, "
        "unprompted_breadth_json TEXT);"
        "CREATE TABLE selection_log (experience_id TEXT, problem TEXT);"
        "CREATE TABLE queue (experience_id TEXT, ledger_ref TEXT);"
        "CREATE TABLE corpus (ledger_ref TEXT PRIMARY KEY, domain TEXT, why_owned TEXT, "
        "unlabeled TEXT, provenance TEXT, corpus_pointers_json TEXT, scene_json TEXT);"
    )
    c.executemany(
        "INSERT INTO frames VALUES (?,?,?)",
        [
            ("protect_the_core_lane", f'["gen:x", "{OLD_REF}"]', f'["{OLD_REF}"]'),
            ("lead_with_what_you_refuse_to_do", f'["{OLD_REF}"]', "[]"),
            ("commit_under_the_deadline", f'["{OLD_REF}"]', "[]"),
            # continuity_lock_in's own frame: must NOT move
            ("embed_credentials_as_a_list", f'["veldra:other", "{OLD_REF}"]', "[]"),
        ],
    )
    c.executemany(
        "INSERT INTO selection_log VALUES (?,?)",
        [
            ("license_continuity", OLD_REF),
            ("license_continuity", OLD_REF),
            ("continuity_lock_in", OLD_REF),
        ],
    )
    c.execute("INSERT INTO queue VALUES (?,?)", ("license_continuity", OLD_REF))
    c.commit()
    c.close()


def test_migration_moves_exactly_the_rows_that_belong_to_the_new_problem(tmp_path):
    """Exact attribution by identifier, never heuristics by title or domain. The two rubrics share
    no frame code, so every row is assignable without guessing."""
    db = str(tmp_path / "m.db")
    _seed(db)
    counts = migrate(db)
    assert counts == {
        "frames_breadth": 3,
        "frames_unprompted": 1,
        "selection_log": 2,
        "queue": 1,
        "corpus": 1,
    }

    # the new ref gets ownership metadata the load gate requires, and NO scene: `_attach_scene`
    # must leave license_continuity's own authored prompt in place
    row = (
        sqlite3.connect(db)
        .execute(
            "SELECT why_owned, unlabeled, scene_json FROM corpus WHERE ledger_ref=?", (NEW_REF,)
        )
        .fetchone()
    )
    assert row[0].strip() and row[1].strip(), "the gate hard-rejects on either being empty"
    assert row[2] is None, "a migration must not fabricate a scene"

    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    rows = {r["frame_code"]: dict(r) for r in c.execute("SELECT * FROM frames")}
    for code in MOVED_FRAMES:
        assert OLD_REF not in rows[code]["breadth_json"]
        assert NEW_REF in rows[code]["breadth_json"]
    # continuity_lock_in's frame is untouched, and unrelated refs in a moved row survive
    assert rows["embed_credentials_as_a_list"]["breadth_json"] == f'["veldra:other", "{OLD_REF}"]'
    assert "gen:x" in rows["protect_the_core_lane"]["breadth_json"]
    # the other experience's selection_log rows keep the old ref
    kept = c.execute(
        "SELECT COUNT(*) FROM selection_log WHERE experience_id='continuity_lock_in' AND problem=?",
        (OLD_REF,),
    ).fetchone()[0]
    assert kept == 1
    c.close()


def test_migration_is_idempotent(tmp_path):
    """A migration that cannot be re-run safely is a migration nobody dares re-run. The second
    pass must find nothing and change nothing."""
    db = str(tmp_path / "m.db")
    _seed(db)
    first = migrate(db)
    assert sum(first.values()) > 0

    c = sqlite3.connect(db)
    before = c.execute("SELECT * FROM frames ORDER BY frame_code").fetchall()
    c.close()

    second = migrate(db)
    assert second == {
        "frames_breadth": 0,
        "frames_unprompted": 0,
        "selection_log": 0,
        "queue": 0,
        "corpus": 0,
    }

    c = sqlite3.connect(db)
    assert c.execute("SELECT * FROM frames ORDER BY frame_code").fetchall() == before
    c.close()
