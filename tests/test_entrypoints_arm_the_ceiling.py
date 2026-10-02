"""Every way of starting the public web surface must reach `create_app` with a ceiling armed.

`spend.from_env` returns None -- meaning UNBOUNDED -- when ELENCHUS_MAX_CALLS is unset, and that
is deliberate: the CLI, the probes and the suite all build models with no budget, and a default
that refused would take the product down rather than bound it (spend.py:54-63). The consequence
is that the ceiling is only real where a LAUNCH PATH puts a value in the environment.
`scripts/serve_invitee.py:163` does. `python -m elenchus.web` did not, and served the same
unauthenticated surface -- where the hostname is the only credential -- with no bound at all.

Written before the fix and watched to fail on both counts, which is the only reason it is
believed: `elenchus.web.__main__` produced a factory whose model held `_budget = None`.

WHY THIS IS BEHAVIOURAL AND NOT A GREP. The bug this replaces has an evil twin: an arming line
placed AFTER `app = create_app(db_path=DB)` satisfies every grep for the variable name and leaves
the process exactly as unbounded, because `model_factory_for_this_process` reads the environment
at create_app time (app.py:90-94) and `__main__` builds the app at IMPORT time, not under the
`__main__` guard. So the measurement is taken at the one instant that decides it: control is
seized inside `create_app` itself, and what is read is the factory the entrypoint was about to
serve under. An arming line in the wrong place fails this file.

The enumeration is read off the tree rather than listed here, so a third entrypoint added later
is covered the day it lands rather than the day somebody remembers this file exists.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

from elenchus.spend import DEFAULT_MAX_CALLS
from elenchus.web import app as web_app

_SRC = Path(__file__).resolve().parents[1] / "src"


def entrypoint_modules() -> list[str]:
    """Package entrypoints, discovered: every `__main__.py` under `src/`.

    `scripts/serve_invitee.py` is a launch path too and is deliberately NOT here: it never calls
    `create_app` at all, it builds an environment and hands it to a CHILD process, so there is no
    factory in THIS process to read. Its arming is pinned by tests/test_serve_invitee.py:345.
    """
    return [
        f"{str(p.relative_to(_SRC).parent).replace(os.sep, '.')}.__main__"
        for p in sorted(_SRC.rglob("__main__.py"))
    ]


class _NotAnApp:
    """Stands in for the FastAPI app so importing an entrypoint neither opens the production
    database nor mounts anything. The factory is what is under test; the app is not."""


def factory_at_create_app_time(module_name: str, monkeypatch) -> object | None:
    """Import an entrypoint for real and return the model factory it reached `create_app` with.

    Nothing is re-implemented about how a path arms the ceiling: the path arms it, and this reads
    what actually arrived, at the moment `create_app` would have read it.
    """
    captured: dict[str, object] = {}

    def recorder(db_path, model_factory=None):
        # Exactly what create_app does when the caller passes nothing (app.py:259). Resolved HERE
        # so the environment sampled is the one the entrypoint had finished building.
        captured["factory"] = model_factory or web_app.model_factory_for_this_process()
        return _NotAnApp()

    monkeypatch.setattr(web_app, "create_app", recorder)

    # The entrypoint loads .env into os.environ with setdefault, which monkeypatch cannot undo
    # because it never saw the write. Leaking a real ANTHROPIC_API_KEY into the session would
    # silently un-skip the @live tests and bill the run.
    before = dict(os.environ)
    sys.modules.pop(module_name, None)
    try:
        importlib.import_module(module_name)
    finally:
        sys.modules.pop(module_name, None)
        os.environ.clear()
        os.environ.update(before)

    return captured.get("factory")


def test_the_enumeration_finds_something():
    """Anti-vacuity. Every assertion below is parametrised over this list, so an empty list would
    turn this whole file into a green report on a tree it never looked at."""
    assert entrypoint_modules(), "discovered no package entrypoints -- the enumeration is broken"


@pytest.mark.parametrize("module_name", entrypoint_modules())
def test_the_entrypoint_arms_the_ceiling_before_it_builds_the_app(module_name, monkeypatch):
    """The obligation, measured through the production wiring: with no ceiling exported, the
    process this entrypoint would serve must still be bounded."""
    monkeypatch.delenv("ELENCHUS_MAX_CALLS", raising=False)

    factory = factory_at_create_app_time(module_name, monkeypatch)
    assert factory is not None, f"{module_name} never reached create_app: nothing was measured"

    budget = factory()._budget
    assert budget is not None, (
        f"{module_name} serves the unauthenticated web surface with NO ceiling on paid model "
        "calls. Arm ELENCHUS_MAX_CALLS before create_app is called, the way "
        "scripts/serve_invitee.py:163 does."
    )
    assert budget.max_calls == DEFAULT_MAX_CALLS, (
        f"{module_name} is bounded at {budget.max_calls}, not the shipped default. If a .env is "
        "supplying its own ceiling, this test is reading the operator's machine and not the code."
    )


@pytest.mark.parametrize("module_name", entrypoint_modules())
def test_a_real_exported_ceiling_still_wins_over_the_entrypoints_default(module_name, monkeypatch):
    """setdefault, not assignment. An operator who has decided this invitee needs a different
    ceiling must not have it silently overwritten by the entrypoint's own floor."""
    monkeypatch.setenv("ELENCHUS_MAX_CALLS", "9")

    factory = factory_at_create_app_time(module_name, monkeypatch)
    assert factory is not None, f"{module_name} never reached create_app: nothing was measured"
    assert factory()._budget.max_calls == 9
