"""The four states of crash reporting, as tests rather than as a claim.

These were checked by hand when the wiring landed — no DSN, DSN without the
extra, valid DSN with it, malformed DSN — and a manual check leaves no trace
that anybody can re-run. Elenchus's evidence policy asks for a web test when a
web surface changes, and it is right to: `create_app` now calls out to a third
party at startup, and the failure that matters is the app not starting at all.

The one that would actually hurt is the last: a reporter that raises on a bad
DSN takes the whole app down at boot, which inverts its own purpose. It is
tested with a genuinely malformed value rather than a mocked exception, so the
test exercises sentry_sdk's real parsing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from elenchus.web.app import create_app  # noqa: E402


def _app(tmp_path, monkeypatch, **env):
    for k in ("SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_TRACES_SAMPLE_RATE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return create_app(db_path=str(tmp_path / "obs.db"))


def test_no_dsn_leaves_reporting_off(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    assert app.state.observability == "off: no SENTRY_DSN"


def test_a_blank_dsn_is_the_same_as_none(tmp_path, monkeypatch):
    """An unset secret in CI arrives as an empty string, not as absence."""
    app = _app(tmp_path, monkeypatch, SENTRY_DSN="   ")
    assert app.state.observability == "off: no SENTRY_DSN"


def test_a_malformed_dsn_does_not_take_the_app_down(tmp_path, monkeypatch):
    pytest.importorskip("sentry_sdk", reason="needs the observability extra")
    app = _app(tmp_path, monkeypatch, SENTRY_DSN="not-a-dsn")
    assert app.state.observability.startswith("off: sentry init failed")
    # The point of the test: the app still exists and still serves.
    assert app.state.observability != "on"
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/" in routes and "/api/health" in routes


def test_a_valid_dsn_turns_it_on(tmp_path, monkeypatch):
    pytest.importorskip("sentry_sdk", reason="needs the observability extra")
    app = _app(
        tmp_path,
        monkeypatch,
        SENTRY_DSN="https://abc123@o0.ingest.sentry.io/0",
        SENTRY_ENVIRONMENT="test",
    )
    assert app.state.observability == "on"


def test_reporting_is_off_by_default_for_every_other_test(tmp_path, monkeypatch):
    """No test in this suite should be initialising a reporter as a side effect,
    and a default sample rate is a bill nobody chose."""
    app = _app(tmp_path, monkeypatch)
    assert app.state.observability.startswith("off:")
