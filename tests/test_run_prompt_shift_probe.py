"""The prompt_shift_probe entrypoint: confirmation gate + corpus/db wiring + the two system-text
reconstructions arm C depends on. Never constructs a real AnthropicModel that could issue a
network call -- every test either supplies a scripted `model=` (the `client=` fake-double
convention every other model test uses), fakes `client=` on a REAL AnthropicModel (never network,
proves the reconstructions match the real thing), or declines the confirmation, or drives the
`model=None` gate-accept branch over an empty corpus so no method is ever reached."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from elenchus.model import AnthropicModel, ModelError, ResponseClassification
from elenchus.prompt_shift_probe import (
    ClassifyItem,
    Probe2Result,
    build_classify_corpus,
    build_territory_corpus,
    reconstruct_old_classify_response_user,
    reconstruct_old_map_territories_user,
)
from elenchus.run_prompt_shift_probe import (
    DEFAULT_LIMIT,
    DEFAULT_MARGIN,
    MODEL_ID,
    _MAP_TERRITORIES_SYSTEM,
    _classify_system_for,
    _raw_parse_classify,
    _raw_parse_territory,
    run,
)
from elenchus.types import Experience, Frame, Mode, Regime, Rubric, TerritoryMap, Trap

# ---------------------------------------------------------------------------
# fixtures shared by this file
# ---------------------------------------------------------------------------


def _exp(eid="exp_a", decision_frame="frame_0"):
    rubric = Rubric(
        frames=[Frame(frame_code="frame_0", frame_detail="detail")],
        traps=[Trap(trap_code="trap_0", trap_detail="trap detail")],
        mode=Mode.genuinely_open,
        decision_frame=decision_frame,
    )
    return Experience(
        experience_id=eid,
        prompt="A decision prompt.",
        rubric=rubric,
        ledger_ref=f"veldra:{eid}",
        regime=Regime.open_ended,
    )


def _turn_db(path, rows):
    """rows: list of (sitting_id, seq, kind, text). Same schema as test_live_corpus.py's
    fixture -- copied rather than imported (two call sites; the rule here is extract on the
    third, not the second)."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE web_sitting_turn (sitting_id TEXT, seq INTEGER, kind TEXT, payload_json TEXT)"
    )
    for sitting_id, seq, kind, text in rows:
        conn.execute(
            "INSERT INTO web_sitting_turn VALUES (?, ?, ?, ?)",
            (sitting_id, seq, kind, json.dumps({"text": text})),
        )
    conn.commit()
    conn.close()


def _world_db(path, rows):
    """rows: list of (sitting_id, situation)."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE web_world (sitting_id TEXT, situation TEXT)")
    conn.executemany("INSERT INTO web_world VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _seeded_db(path, *, n_pairs, n_situations):
    """A db carrying exactly `n_pairs` (push, response) turn-pairs and `n_situations` world
    rows -- built once here so the exact-call-count test can compute its expectation from the
    same numbers it seeds, independent of run()'s own arithmetic. Two separate connections
    (`_turn_db` then `_world_db`) because each creates its own single table; sqlite is happy to
    reopen the same file."""
    rows = []
    for i in range(n_pairs):
        rows.append((f"s{i}", 1, "vera", f"push {i}"))
        rows.append((f"s{i}", 2, "you", f"reply {i}"))
    _turn_db(path, rows)
    _world_db(path, [(f"w{i}", f"situation {i}") for i in range(n_situations)])


class _ScriptedModel:
    """Supplies both halves of the `Model` protocol this probe needs."""

    def __init__(self, classify_result, territory_result):
        self._classify_result = classify_result
        self._territory_result = territory_result
        self.classify_calls = 0
        self.territory_calls = 0

    def classify_response(self, exp, kind, code, push, response, *, stress=False):
        self.classify_calls += 1
        return self._classify_result

    def map_territories(self, situation, territories):
        self.territory_calls += 1
        return self._territory_result


def _scripted_raw_parse(result):
    calls = []

    def raw_parse(*, system, user, output_format, max_tokens):
        calls.append(
            {
                "system": system,
                "user": user,
                "output_format": output_format,
                "max_tokens": max_tokens,
            }
        )
        return result

    return raw_parse, calls


def _rc():
    return ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)


def _tmap():
    return TerritoryMap(ranked=["exp_a"], confidence="high", reflection="[reflect]")


# ---------------------------------------------------------------------------
# the confirmation gate
# ---------------------------------------------------------------------------


def test_declining_confirmation_makes_no_model_call_and_returns_none(tmp_path):
    outcome = run(
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda probe, n_calls, model_id, max_calls=None: False,
    )
    assert outcome is None
    assert not (tmp_path / "out").exists()


def test_confirm_is_never_consulted_when_a_model_is_already_supplied(tmp_path):
    model = _ScriptedModel(_rc(), _tmap())
    raw_parse_c, _ = _scripted_raw_parse(_rc())
    raw_parse_t, _ = _scripted_raw_parse(_tmap())

    def _explode(probe, n_calls, model_id):
        raise AssertionError("confirm must not be called when model= is supplied")

    outcome = run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=_explode,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert outcome is not None


def test_the_exact_call_count_reported_to_the_gate_matches_the_built_corpus_size(tmp_path):
    """Three arms per item, across both halves -- computed independently here from the same
    (n_pairs, n_situations) the fixture db was seeded with, via the same corpus builders run()
    itself calls, rather than trusting run()'s own arithmetic."""
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=3, n_situations=2)

    from elenchus.content_loader import load_library
    from elenchus.content_loader import load_territory_text as _load_territory_text
    from elenchus.live_corpus import read_push_response_pairs, read_situations

    experiences = [e for e in load_library() if e.regime is Regime.open_ended]
    pairs = read_push_response_pairs(db_path)
    situations = read_situations(db_path)
    classify_items = build_classify_corpus(pairs, experiences, limit=DEFAULT_LIMIT)
    territories = [(e.experience_id, _load_territory_text(e.experience_id)) for e in experiences]
    territory_items = build_territory_corpus(situations, territories, limit=DEFAULT_LIMIT)
    expected = 3 * (len(classify_items) + len(territory_items))
    assert expected > 0  # sanity: the fixture actually produced real items

    captured = {}

    def _capture(probe, n_calls, model_id, max_calls=None):
        captured["n_calls"] = n_calls
        captured["probe"] = probe
        captured["model_id"] = model_id
        captured["max_calls"] = max_calls
        return False

    outcome = run(db_path=db_path, data_dir=tmp_path / "out", confirm=_capture)
    assert outcome is None
    assert captured["n_calls"] == expected
    assert captured["probe"] == "prompt_shift_probe"
    assert captured["model_id"] == MODEL_ID


def test_gate_accepting_proceeds_past_the_confirmation(tmp_path, monkeypatch):
    """confirm() returning True must let run() continue rather than return None -- the mirror of
    the declining test above. Exercised through the REAL `model=None` branch (not bypassed by
    supplying a scripted model), with the db path missing so BOTH corpora are empty: zero items
    means run_classify_probe/run_territory_probe's loops never execute, so neither an
    AnthropicModel method nor `_parse_required` is ever reached regardless of what `AnthropicModel`
    resolves to. The monkeypatch below removes even the possibility: `elenchus.model.AnthropicModel`
    is replaced with a class that raises if any of its methods are ever invoked, so this test
    proves the gate-accept path proceeds without touching the real class at all, let alone the
    network."""
    import elenchus.model as model_module

    constructed = []

    class _NeverCalledAnthropicModel:
        def __init__(self, *, model):
            constructed.append(model)

        def classify_response(self, *a, **kw):
            raise AssertionError("must never be called -- corpus is empty")

        def map_territories(self, *a, **kw):
            raise AssertionError("must never be called -- corpus is empty")

        def _parse_required(self, *a, **kw):
            raise AssertionError("must never be called -- corpus is empty")

    monkeypatch.setattr(model_module, "AnthropicModel", _NeverCalledAnthropicModel)

    outcome = run(
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert outcome is not None
    path, result = outcome
    assert path.exists()
    assert constructed == [MODEL_ID]
    assert result.classify_records == []
    assert result.territory_records == []


# ---------------------------------------------------------------------------
# corpus source / db wiring
# ---------------------------------------------------------------------------


def test_run_records_empty_fallback_on_both_halves_when_the_db_is_absent(tmp_path):
    model = _ScriptedModel(_rc(), _tmap())
    raw_parse_c, calls_c = _scripted_raw_parse(_rc())
    raw_parse_t, calls_t = _scripted_raw_parse(_tmap())
    path, result = run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=tmp_path / "missing.db",
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert result.classify_corpus_source == "empty_fallback"
    assert result.territory_corpus_source == "empty_fallback"
    assert result.classify_records == []
    assert result.territory_records == []
    # empty corpus -> the scripted model/raw_parse are never actually reached
    assert model.classify_calls == 0
    assert model.territory_calls == 0
    assert calls_c == []
    assert calls_t == []


def test_run_records_live_db_on_both_halves_when_the_db_has_rows(tmp_path):
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=2, n_situations=2)
    model = _ScriptedModel(_rc(), _tmap())
    raw_parse_c, _ = _scripted_raw_parse(_rc())
    raw_parse_t, _ = _scripted_raw_parse(_tmap())
    _, result = run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=db_path,
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert result.classify_corpus_source == "live_db"
    assert result.territory_corpus_source == "live_db"
    assert len(result.classify_records) == 2
    assert len(result.territory_records) == 2
    # 2 items each -> 2 arm-A/B model calls each, 1 raw_parse (arm C) call each
    assert model.classify_calls == 4
    assert model.territory_calls == 4


def test_limit_truncates_the_corpus_and_therefore_the_call_count(tmp_path):
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=5, n_situations=5)
    captured = {}

    def _capture(probe, n_calls, model_id, max_calls=None):
        captured["n_calls"] = n_calls
        captured["max_calls"] = max_calls
        return False

    run(db_path=db_path, data_dir=tmp_path / "out", confirm=_capture, limit=1)
    assert captured["n_calls"] == 3 * (1 + 1)  # 1 classify item + 1 territory item, 3 arms each
    # Both halves go through `_parse_required`, which spends one retry, so the ceiling is 2x.
    assert captured["max_calls"] == 2 * 3 * (1 + 1)


# ---------------------------------------------------------------------------
# written JSON round-trips
# ---------------------------------------------------------------------------


def test_written_result_round_trips_through_json(tmp_path):
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=1, n_situations=1)
    model = _ScriptedModel(_rc(), _tmap())
    raw_parse_c, _ = _scripted_raw_parse(_rc())
    raw_parse_t, _ = _scripted_raw_parse(_tmap())
    now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
    path, result = run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=db_path,
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=now,
    )
    assert path.name == "20260802T120000Z.json"
    again = Probe2Result.model_validate_json(path.read_text())
    assert again == result
    assert result.model_id == MODEL_ID
    assert result.margin == DEFAULT_MARGIN


# ---------------------------------------------------------------------------
# per-item resilience, checkpointing, and the refusal rate (the founder's incident)
# ---------------------------------------------------------------------------


def test_run_records_a_failed_item_without_aborting_and_reports_the_refusal_rate(tmp_path):
    """End-to-end reproduction of the founder's incident, at the `run()` level: item 1's arm C
    refuses. `run()` must still return a result (not raise, not abort) that carries the failure
    in `classify_failures` (never silently dropped), excludes it from `classify_records`, and
    surfaces it in `classify_rates` -- both the shrunk `comparable_n` and the nonzero
    `refusal_rate`."""
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=2, n_situations=0)
    model = _ScriptedModel(_rc(), _tmap())

    class _RefusesOnceThenOk:
        def __init__(self):
            self.calls = 0

        def __call__(self, *, system, user, output_format, max_tokens):
            self.calls += 1
            if self.calls == 1:
                raise ModelError("model refused or returned no parsed output")
            return _rc()

    raw_parse_c = _RefusesOnceThenOk()
    raw_parse_t, _ = _scripted_raw_parse(_tmap())
    _, result = run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=db_path,
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=datetime(2026, 8, 2, tzinfo=timezone.utc),
    )
    assert len(result.classify_failures) == 1
    assert result.classify_failures[0].arm == "c"
    assert len(result.classify_records) == 1  # the second item still completed
    assert result.classify_rates.comparable_n == 1
    assert result.classify_rates.failed_n == 1
    assert result.classify_rates.attempted_n == 2
    assert result.classify_rates.refused_n == 1
    assert result.classify_rates.refusal_rate == 0.5  # 1 refused / 2 attempted


def test_run_checkpoints_every_item_as_it_completes(tmp_path):
    """Every item (classify AND territory) lands in the `.checkpoint.jsonl` file exactly once,
    tagged by which half it came from -- the file this founder would have needed to see the 33
    already-paid-for items survive the crash."""
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=2, n_situations=2)
    model = _ScriptedModel(_rc(), _tmap())
    raw_parse_c, _ = _scripted_raw_parse(_rc())
    raw_parse_t, _ = _scripted_raw_parse(_tmap())
    now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)
    run(
        model=model,
        raw_parse_classify=raw_parse_c,
        raw_parse_territory=raw_parse_t,
        db_path=db_path,
        data_dir=tmp_path / "out",
        confirm=lambda *a, **k: True,
        now=now,
    )
    checkpoint_path = tmp_path / "out" / "20260802T120000Z.checkpoint.jsonl"
    assert checkpoint_path.exists()
    lines = [json.loads(line) for line in checkpoint_path.read_text().splitlines()]
    assert len(lines) == 4  # 2 classify items + 2 territory items
    assert [line["probe"] for line in lines] == ["classify", "classify", "territory", "territory"]
    assert all(line["outcome"] == "record" for line in lines)


def test_a_crash_partway_leaves_a_readable_checkpoint_of_the_completed_items(tmp_path):
    """The exact failure mode this change fixes: an UNANTICIPATED error (deliberately not a
    `ModelError`, so `run_classify_probe` does not catch it and it propagates out of `run()`
    too) hits on the second classify item's first call. The first item's three arms already
    completed and must be on disk in the checkpoint -- readable, without needing `run()` to have
    returned -- and the run's final consolidated JSON file must NOT exist, since `run()` never
    reached that line."""
    db_path = tmp_path / "db.sqlite"
    _seeded_db(db_path, n_pairs=2, n_situations=0)  # empty territory corpus: crash never reaches it

    class _CrashesOnThirdCall:
        def __init__(self):
            self.calls = 0

        def classify_response(self, exp, kind, code, push, response, *, stress=False):
            self.calls += 1
            if self.calls == 3:  # item 2's arm A
                raise RuntimeError("simulated unanticipated crash")
            return _rc()

        def map_territories(self, situation, territories):
            raise AssertionError("territory phase must never be reached")

    model = _CrashesOnThirdCall()
    raw_parse_c, _ = _scripted_raw_parse(_rc())
    raw_parse_t, _ = _scripted_raw_parse(_tmap())
    now = datetime(2026, 8, 2, 12, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(RuntimeError, match="simulated unanticipated crash"):
        run(
            model=model,
            raw_parse_classify=raw_parse_c,
            raw_parse_territory=raw_parse_t,
            db_path=db_path,
            data_dir=tmp_path / "out",
            confirm=lambda *a, **k: True,
            now=now,
        )

    checkpoint_path = tmp_path / "out" / "20260802T120000Z.checkpoint.jsonl"
    assert checkpoint_path.exists()
    lines = [json.loads(line) for line in checkpoint_path.read_text().splitlines()]
    assert len(lines) == 1  # only item 1 (2 model calls) landed before the crash on call 3
    assert lines[0]["probe"] == "classify"
    assert lines[0]["outcome"] == "record"
    assert lines[0]["data"]["push"] == "push 0"
    result_path = tmp_path / "out" / "20260802T120000Z.json"
    assert not result_path.exists()  # run() never reached its own path.write_text


# ---------------------------------------------------------------------------
# _raw_parse_classify / _raw_parse_territory
# ---------------------------------------------------------------------------


class _FakeParseRequiredModel:
    def __init__(self):
        self.calls = []

    def _parse_required(self, **kwargs):
        self.calls.append(kwargs)
        return "PARSED"


def test_raw_parse_classify_composes_a_single_user_message_and_forwards_high_effort_params():
    model = _FakeParseRequiredModel()
    result = _raw_parse_classify(
        model, system="SYS", user="USR", output_format=ResponseClassification, max_tokens=123
    )
    assert result == "PARSED"
    call = model.calls[0]
    assert call["system"] == "SYS"
    assert call["messages"] == [{"role": "user", "content": "USR"}]
    assert call["output_format"] is ResponseClassification
    assert call["max_tokens"] == 123
    assert call["output_config"] == {"effort": "high"}


def test_raw_parse_territory_forwards_medium_effort_not_high():
    model = _FakeParseRequiredModel()
    _raw_parse_territory(
        model, system="SYS", user="USR", output_format=TerritoryMap, max_tokens=123
    )
    assert model.calls[0]["output_config"] == {"effort": "medium"}


# ---------------------------------------------------------------------------
# system-text reconstructions, pinned against the REAL AnthropicModel (client=, never network)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output
        self.stop_reason = "end_turn"


class _Messages:
    def __init__(self, result):
        self._result = result
        self.parse_calls = []

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return _Resp(self._result)


class _Client:
    def __init__(self, result):
        self.messages = _Messages(result)


def test_classify_system_for_matches_the_real_system_and_only_the_user_differs_from_arm_c():
    """Drives arm A (`classify_response` itself) and arm C (`_raw_parse_classify`, the private
    `_parse_required` helper) through the SAME real `AnthropicModel` over a scripted client
    (never network) and proves `_classify_system_for` reproduces the exact system text
    `classify_response` composes, while the two arms' user messages differ -- the validity
    condition the whole probe rests on."""
    exp = _exp()
    client = _Client(_rc())
    model = AnthropicModel(client=client)
    push, response = "What do you give up?", "I would hold the line."
    item = ClassifyItem(exp, "frame", "frame_0", False, push, response)

    model.classify_response(exp, "frame", "frame_0", push, response, stress=False)  # arm A
    _raw_parse_classify(
        model,
        system=_classify_system_for(item),
        user=reconstruct_old_classify_response_user(push, response),
        output_format=ResponseClassification,
        max_tokens=4096,
    )  # arm C

    arm_a_call, arm_c_call = client.messages.parse_calls
    assert arm_c_call["system"] == arm_a_call["system"]
    assert arm_c_call["messages"][-1]["content"] != arm_a_call["messages"][-1]["content"]
    assert arm_c_call["output_config"] == arm_a_call["output_config"]  # same effort (_PARAMS)


def test_classify_system_for_carries_the_stress_addendum_when_stress_is_true():
    """A stress push adds `response_stress`'s text to the system prompt (model.py,
    `classify_response`) -- if `_classify_system_for` dropped the `item.stress` branch, this
    would still pass every OTHER test in this file (none of them sets stress=True), so it is
    pinned on its own against the real call."""
    exp = _exp()
    client = _Client(_rc())
    model = AnthropicModel(client=client)
    push, response = "What do you give up?", "I would hold the line."
    item = ClassifyItem(exp, "frame", "frame_0", True, push, response)

    model.classify_response(exp, "frame", "frame_0", push, response, stress=True)
    call = client.messages.parse_calls[0]
    assert call["system"] == _classify_system_for(item)


def test_map_territories_system_matches_the_real_system_and_only_the_user_differs_from_arm_c():
    client = _Client(_tmap())
    model = AnthropicModel(client=client)
    situation = "Committing to an industry at a young age"
    territories = [("exp_a", "desc a")]

    model.map_territories(situation, territories)  # arm A
    _raw_parse_territory(
        model,
        system=_MAP_TERRITORIES_SYSTEM,
        user=reconstruct_old_map_territories_user(situation, territories),
        output_format=TerritoryMap,
        max_tokens=4096,
    )  # arm C

    arm_a_call, arm_c_call = client.messages.parse_calls
    assert arm_c_call["system"] == arm_a_call["system"]
    assert arm_c_call["messages"][-1]["content"] != arm_a_call["messages"][-1]["content"]
    assert arm_c_call["output_config"] == arm_a_call["output_config"]  # same effort (_MED_PARAMS)
