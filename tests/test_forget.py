"""Honoring "please delete what I wrote".

An invitee can ask on 2026-09-06 and there was no mechanism at all: no endpoint, no export, no
script. Honoring it meant the founder `rm -rf`-ing a directory from memory and hoping nothing else
held a copy. That is the shape of promise a beta breaks by accident.

This is NOT in tension with Invariant 4 ("decay demotes, never deletes"). That invariant governs
how the ENGINE treats learner state inside the loop -- forgetting is retrieval failure, not
erasure. A person asking to be forgotten is a different act, performed by an operator, on their
own data, on request.

Destructive by nature, so the shape is: plan first, delete only on an explicit flag, and refuse
outright while anything still holds the database open.
"""

import sqlite3

import pytest

from elenchus import forget


def _tenant(root, slug, turns=3):
    d = root / "tenants" / slug
    d.mkdir(parents=True)
    con = sqlite3.connect(d / "elenchus.db")
    con.execute("create table web_sitting_turn (id integer primary key)")
    con.executemany("insert into web_sitting_turn values (?)", [(i,) for i in range(turns)])
    con.commit()
    con.close()
    (d / "server.log").write_text("INFO: 2601:249:... - POST /api/session/single/say 200 OK\n")
    return d


def test_the_plan_names_every_file_that_holds_this_person(tmp_path):
    d = _tenant(tmp_path, "ada")

    plan = forget.plan(tmp_path, "ada")

    assert set(plan.paths) == {d / "elenchus.db", d / "server.log"}
    assert plan.slug == "ada"


def test_the_plan_counts_what_is_being_destroyed_so_the_operator_sees_it_first(tmp_path):
    _tenant(tmp_path, "ada", turns=27)

    plan = forget.plan(tmp_path, "ada")

    assert plan.turns == 27, "an operator deleting a person's transcript must be shown its size"


def test_backups_that_carry_this_person_are_found_not_left_behind(tmp_path):
    """A tenant database copied into data/backups/ during an operational move still holds the
    person's transcript. A deletion that leaves it there is not a deletion."""
    _tenant(tmp_path, "ada")
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "pre-unsync-move-20260831163706-ada.db").write_bytes(b"")
    (backups / "pre-unsync-move-20260831163706-main.db").write_bytes(b"")  # not hers

    plan = forget.plan(tmp_path, "ada")

    assert backups / "pre-unsync-move-20260831163706-ada.db" in plan.paths
    assert backups / "pre-unsync-move-20260831163706-main.db" not in plan.paths


def test_a_tenant_with_a_LIVE_SERVER_blocks_the_deletion(tmp_path):
    """THE MISS THIS TEST EXISTS FOR (2026-09-02). The first version asked SQLite for an exclusive
    lock and called that "in use". It passed -- because the TEST held a transaction open. Against
    the real running beta it returned False: `sitting_store` opens a connection per call and closes
    it, so between requests nothing holds a lock at all and BEGIN EXCLUSIVE succeeds. The guard
    would have allowed deleting a database out from under a live server, which is the single thing
    it was written to prevent (L-33: a guard the code satisfies by accident has no teeth).

    What actually answers "is this invitee being served" is whether a process exists whose
    ELENCHUS_DB names this file. The process environment is injected here so the interesting case
    is reproducible in a test rather than only on a machine that happens to be serving."""
    d = _tenant(tmp_path, "ada")
    db = d / "elenchus.db"

    serving = [f"ELENCHUS_DB={db} ELENCHUS_PORT=9401"]
    plan = forget.plan(tmp_path, "ada", process_envs=serving)
    assert plan.in_use is True
    with pytest.raises(forget.StillServing):
        forget.execute(plan)

    # a process serving a DIFFERENT tenant must not block this one
    other = [f"ELENCHUS_DB={tmp_path / 'tenants' / 'bo' / 'elenchus.db'} ELENCHUS_PORT=9402"]
    assert forget.plan(tmp_path, "ada", process_envs=other).in_use is False


def test_an_in_flight_transaction_also_blocks_it(tmp_path):
    """Belt on the same seam: even with no matching process env (a launch this scan cannot see),
    a database mid-transaction must not be unlinked."""
    d = _tenant(tmp_path, "ada")
    holder = sqlite3.connect(d / "elenchus.db")
    holder.execute("begin exclusive")
    try:
        assert forget.plan(tmp_path, "ada", process_envs=[]).in_use is True
    finally:
        holder.close()


def test_an_idle_tenant_is_deletable_and_actually_goes(tmp_path):
    d = _tenant(tmp_path, "ada")

    plan = forget.plan(tmp_path, "ada")
    assert plan.in_use is False
    forget.execute(plan)

    assert not (d / "elenchus.db").exists()
    assert not (d / "server.log").exists()
    assert not d.exists(), "the directory itself goes too, or the slug looks live to the launcher"


def test_a_slug_can_never_be_a_path(tmp_path):
    """The slug becomes a directory name under the tenant root, and this function DELETES what it
    resolves to. `../../..` here is not a bug, it is a catastrophe."""
    for bad in ("../evil", "a/b", "", ".", "ADA", "ada ", "/etc"):
        with pytest.raises(ValueError):
            forget.plan(tmp_path, bad)


def test_a_slug_that_was_never_served_says_so_rather_than_reporting_success(tmp_path):
    """A typo'd slug that silently 'deletes nothing' lets an operator tell a person their data is
    gone when it is not."""
    (tmp_path / "tenants").mkdir()

    with pytest.raises(FileNotFoundError):
        forget.plan(tmp_path, "nobody")


def test_the_plan_names_what_it_CANNOT_do(tmp_path):
    """The script owns files. It does not own the Cloudflare Access application carrying the
    person's email address, or the invite itself. Leaving those unsaid is how a deletion gets
    reported as complete while their address is still in an access policy."""
    _tenant(tmp_path, "ada")

    plan = forget.plan(tmp_path, "ada")

    joined = " ".join(plan.by_hand).lower()
    assert "access" in joined and "email" in joined


def _run(args, tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    return subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "forget_invitee.py"), *args],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"},
        timeout=90,
    )


def test_the_script_deletes_NOTHING_without_an_explicit_flag(tmp_path):
    """The default run of a destructive tool must be the safe one. An operator reaching for this
    while upset about an email should have to say twice that they mean it."""
    d = _tenant(tmp_path, "ada", turns=27)

    out = _run(["ada", "--root", str(tmp_path)], tmp_path)

    assert out.returncode == 0, out.stderr
    assert (d / "elenchus.db").exists(), "a dry run deleted real data"
    assert "27" in out.stdout, "the operator must see the size of what they are about to destroy"
    assert "--confirm" in out.stdout, "the dry run must say how to actually do it"


def test_the_script_deletes_when_told_twice(tmp_path):
    d = _tenant(tmp_path, "ada")

    out = _run(["ada", "--root", str(tmp_path), "--confirm"], tmp_path)

    assert out.returncode == 0, out.stderr
    assert not d.exists()


def test_the_script_prints_what_it_cannot_do_even_on_a_dry_run(tmp_path):
    _tenant(tmp_path, "ada")

    out = _run(["ada", "--root", str(tmp_path)], tmp_path)

    assert "access" in out.stdout.lower()


def test_a_bad_slug_fails_loudly_and_deletes_nothing(tmp_path):
    _tenant(tmp_path, "ada")

    out = _run(["../ada", "--root", str(tmp_path), "--confirm"], tmp_path)

    assert out.returncode != 0
    assert (tmp_path / "tenants" / "ada" / "elenchus.db").exists()
