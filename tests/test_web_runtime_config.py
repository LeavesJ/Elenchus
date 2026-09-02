"""Per-invitee isolation, spine item 1 of the 2026-09-12 beta plan.

The beta's entire safety argument is one process and one database file per invitee. Co-tenancy is
only dangerous when there are co-tenants, and `_SID = "single"` (app.py:14) plus a schema with no
learner column means two people on one database ARE one learner. Three independent adversarial
reviews promoted this item from T1/0.5h to T2, calling it the only failure in the plan that is
unrecoverable after the fact.

Today `src/elenchus/web/__main__.py` hardcodes all three values it needs -- database at :9, host
and port at :34 -- and computes the app at import time, so none of it is reachable from a test
without reloading the module, which would open the REAL production database. Hence a pure
resolver: the module calls it, tests call it, and nothing has to import a live app to check the
rules.

The load-bearing rule is the last test in this file. Serving a non-loopback address means serving
OTHER PEOPLE, and doing that out of the founder's own database is the disaster the isolation
strategy exists to prevent. A forgotten environment variable must fail loudly at startup rather
than quietly pooling two humans into one learner.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from elenchus.web.runtime import DEFAULT_DB, resolve_runtime  # noqa: E402


def test_the_default_is_unchanged_when_nothing_is_set():
    """The founder's own instance must not move. `data/elenchus.db` stays the literal default and
    the environment variables are override-only, which is what keeps this a T1-shaped change to
    existing behaviour rather than an unlabelled migration of durable state."""
    db, host, port = resolve_runtime({})

    assert db == DEFAULT_DB
    assert host == "127.0.0.1"
    assert port == 8000


def test_elenchus_db_overrides_the_database(tmp_path):
    """One database file per invitee is the whole isolation mechanism."""
    target = str(tmp_path / "tenants" / "ada" / "elenchus.db")
    db, _, _ = resolve_runtime({"ELENCHUS_DB": target})

    assert db == target


def test_elenchus_port_overrides_the_port():
    """One process per invitee means one port per invitee."""
    _, _, port = resolve_runtime({"ELENCHUS_DB": "/tmp/x.db", "ELENCHUS_PORT": "9401"})

    assert port == 9401


def test_a_non_numeric_port_is_rejected_at_startup(tmp_path):
    """A typo in a launch script must not fall back to 8000 and silently collide with another
    invitee's instance."""
    with pytest.raises(ValueError, match="ELENCHUS_PORT"):
        resolve_runtime({"ELENCHUS_DB": str(tmp_path / "a.db"), "ELENCHUS_PORT": "94o1"})


def test_serving_a_non_loopback_address_requires_an_explicit_database(tmp_path):
    """THE GUARD. Binding anything but loopback means serving other people.

    Doing that against the default database puts every invitee in the founder's own room, with 19
    sittings, 293 turns and 8 convergences of his private decisions already in it. The failure is
    silent today and unrecoverable afterwards, so it has to be loud and it has to be at startup.

    Note the shape: the rule is not "the path must never be the default". That would break the
    founder's own dogfood instance, which SHOULD use the default. It is a rule every caller can
    satisfy -- serve yourself on loopback, or name a database -- rather than a guard relocated to
    suit one awkward caller (project lesson L-31).
    """
    with pytest.raises(ValueError, match="ELENCHUS_DB"):
        resolve_runtime({"ELENCHUS_HOST": "0.0.0.0"})

    # ...and the same binding WITH an explicit database is exactly the supported deployment.
    db, host, _ = resolve_runtime(
        {"ELENCHUS_HOST": "0.0.0.0", "ELENCHUS_DB": str(tmp_path / "ada.db")}
    )
    assert host == "0.0.0.0"
    assert db.endswith("ada.db")


def test_loopback_without_an_explicit_database_stays_allowed():
    """The founder running `python -m elenchus.web` on his laptop is the unchanged path."""
    db, host, _ = resolve_runtime({"ELENCHUS_HOST": "127.0.0.1"})

    assert db == DEFAULT_DB
    assert host == "127.0.0.1"


def test_the_entrypoint_makes_info_logs_reach_stderr(tmp_path):
    """The model_call timing lines log at INFO, and logging's last-resort handler drops below
    WARNING -- so the production process silently discarded the exact data Monday's measurement
    needs, while the suite's caplog (which captures at any level) stayed green: L-9's logging
    variant, found live on 2026-08-30. The entrypoint must configure logging so INFO from the
    elenchus loggers lands on stderr."""
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import logging, elenchus.web.__main__; "
            "logging.getLogger('elenchus.model').info('model_call probe 0.42s')",
        ],
        env={
            "PYTHONPATH": str(src),
            "PATH": "/usr/bin:/bin",
            "ELENCHUS_DB": str(tmp_path / "probe.db"),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert "model_call probe" in out.stderr, (
        f"an INFO log from the model logger never reached stderr: {out.stderr!r}"
    )


def test_the_production_path_set_EXPLICITLY_is_refused_exactly_like_a_defaulted_one():
    """The guard keyed on the ELENCHUS_DB string being EMPTY, but the danger is its VALUE: the
    founder's own file holds one particular person's decisions however that path arrived. So
    `ELENCHUS_DB=<the default>` — one copy-paste of the founder's own launch line into an
    invitee's — sailed through in total silence, on ANY bind address, while leaving the variable
    unset on the same address raised. Found by the two-instance isolation audit, 2026-08-31.
    """
    from elenchus.web.runtime import DEFAULT_DB, resolve_runtime

    with pytest.raises(ValueError, match="default database"):
        resolve_runtime({"ELENCHUS_HOST": "0.0.0.0", "ELENCHUS_DB": DEFAULT_DB})


def test_the_production_path_set_explicitly_on_loopback_warns_like_a_defaulted_one(caplog):
    """Same equivalence on the permitted side: loopback keeps working (the founder's own boot
    must not move) but must be just as LOUD, because a named tunnel presents loopback and that is
    the topology the live beta actually runs."""
    from elenchus.web.runtime import DEFAULT_DB, resolve_runtime

    with caplog.at_level("WARNING", logger="elenchus.web.runtime"):
        db, host, _ = resolve_runtime({"ELENCHUS_HOST": "127.0.0.1", "ELENCHUS_DB": DEFAULT_DB})

    assert db == DEFAULT_DB and host == "127.0.0.1"
    assert any("default database" in r.getMessage() for r in caplog.records), (
        "an explicit production path on loopback passed silently"
    )


def test_a_relative_spelling_of_the_production_path_is_still_the_production_path():
    """The live beta runs with a RELATIVE ELENCHUS_DB (verified: `ps eww` shows
    `ELENCHUS_DB=data/tenants/rehearsal/elenchus.db`), so a value-based guard that compared
    strings would miss `./data/elenchus.db` and every other spelling of the same file."""
    import os
    from pathlib import Path

    from elenchus.web.runtime import DEFAULT_DB, resolve_runtime

    root = Path(DEFAULT_DB).parent.parent
    relative = os.path.relpath(DEFAULT_DB, root)
    cwd = os.getcwd()
    os.chdir(root)
    try:
        with pytest.raises(ValueError, match="default database"):
            resolve_runtime({"ELENCHUS_HOST": "0.0.0.0", "ELENCHUS_DB": relative})
    finally:
        os.chdir(cwd)
