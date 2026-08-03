"""The push_screen_probe entrypoint: confirmation gate + corpus/db wiring. Never constructs a
real AnthropicModel or touches the network -- every test either supplies a scripted `model=` (the
`client=` fake-double convention every other model test uses) or declines the confirmation, which
must return before the lazy `AnthropicModel` import ever runs."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from elenchus.push_screen_probe import build_cases
from elenchus.run_push_screen_probe import _confirm, run
from elenchus.types import Positions


class _ScriptedModel:
    def __init__(self, text="an ordinary push"):
        self._text = text
        self.calls = 0

    def generate_push(self, exp, kind, code, *, stress=False, positions=Positions(), steer=""):
        self.calls += 1
        return self._text


def test_declining_confirmation_makes_no_model_call_and_returns_none(tmp_path):
    """model=None is the real, money-spending path -- confirming False must return before the
    lazy `from .model import AnthropicModel` import, which would fail loud here anyway if the
    `anthropic` package were absent, proving the import was never reached."""
    outcome = run(
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda probe, n_calls, model_id: False,
    )
    assert outcome is None
    assert not (tmp_path / "out").exists()


def test_confirm_is_never_consulted_when_a_model_is_already_supplied(tmp_path):
    """Tests inject a scripted model and must run non-interactively -- confirm must be skipped
    entirely on that path, not just answered automatically."""
    model = _ScriptedModel()

    def _explode(probe, n_calls, model_id):
        raise AssertionError("confirm must not be called when model= is supplied")

    path, result = run(
        model=model,
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=_explode,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert path.exists()
    assert result.model_id == "claude-opus-5"


def test_run_falls_back_to_empty_positions_and_reports_the_mode_when_the_db_is_absent(tmp_path):
    model = _ScriptedModel()
    _, result = run(
        model=model,
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda *a: True,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert result.corpus_source == "empty_fallback"
    assert result.positions_pool_size == 0


def test_run_writes_one_record_per_generate_push_call_and_a_timestamped_file(tmp_path):
    model = _ScriptedModel()
    now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
    path, result = run(
        model=model,
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda *a: True,
        now=now,
    )
    assert path.name == "20260802T120000Z.json"
    assert len(result.records) == model.calls
    assert model.calls > 0


def test_confirm_reports_the_probe_name_call_count_and_model_before_asking(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "no")
    answered = _confirm("push_screen_probe", 64, "claude-opus-5")
    out = capsys.readouterr().out
    assert "push_screen_probe" in out
    assert "64" in out
    assert "claude-opus-5" in out
    assert answered is False


@pytest.mark.parametrize(
    "typed,expected",
    [("yes", True), ("Yes", True), (" YES ", True), ("no", False), ("", False), ("y", False)],
)
def test_confirm_requires_the_exact_word_yes(monkeypatch, typed, expected):
    monkeypatch.setattr("builtins.input", lambda _prompt="": typed)
    assert _confirm("push_screen_probe", 1, "claude-opus-5") is expected


def test_the_real_number_of_generate_push_calls_matches_build_cases_over_the_real_library():
    """Guards the count `main()` prints against `build_cases` drifting from the real content
    library without anyone noticing -- this is the exact `n_calls` the gate shows before the
    founder ever types 'yes'."""
    from elenchus.content_loader import load_library
    from elenchus.types import Regime

    experiences = [e for e in load_library() if e.regime is Regime.open_ended]
    assert len(build_cases(experiences)) > 0  # sanity: the real library isn't accidentally empty
