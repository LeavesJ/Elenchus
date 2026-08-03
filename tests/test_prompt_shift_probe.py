"""Pure logic for probe 2 (does the reformatted graded prompt shift a decision). No model call
anywhere in this file: `classify_response`/`map_territories` and the arm-C raw parse are always
scripted doubles, so every assertion here is provable offline."""

from __future__ import annotations

from elenchus.model import ResponseClassification
from elenchus.prompt_shift_probe import (
    ClassifyItem,
    ClassifyRecord,
    Probe2Result,
    TerritoryItem,
    build_classify_corpus,
    build_territory_corpus,
    classify_response_disagree,
    reconstruct_old_classify_response_user,
    reconstruct_old_map_territories_user,
    run_classify_probe,
    run_territory_probe,
    summarize_disagreement,
    territories_disagree,
    territory_head,
    verdict,
)
from elenchus.types import Experience, Frame, Mode, Regime, Rubric, TerritoryMap, Trap


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


def _rc(outcome="unchanged", mechanism_supplied=False, hard_wrong=False):
    return ResponseClassification(
        outcome=outcome, mechanism_supplied=mechanism_supplied, hard_wrong=hard_wrong
    )


def _tmap(ranked, confidence="high", reflection="[reflect]"):
    return TerritoryMap(ranked=ranked, confidence=confidence, reflection=reflection)


# ---------------------------------------------------------------------------
# Reconstructing the pre-indent (5d05267) prompt shape
# ---------------------------------------------------------------------------


def test_reconstructed_old_classify_response_user_matches_5d05267_single_line():
    # Pinned against `git show 5d05267:src/elenchus/model.py` (classify_response,
    # `user = f"Push:\n{push}\n\nStudent reply:\n{response}"` verbatim -- no `labelled`, no
    # indent, no cap existed yet).
    push, response = "What do you give up?", "I would hold the line."
    assert reconstruct_old_classify_response_user(push, response) == (
        f"Push:\n{push}\n\nStudent reply:\n{response}"
    )


def test_reconstructed_old_classify_response_user_matches_5d05267_multiline():
    push = "What do you give up?"
    response = "I would hold the line.\nEven under pressure."
    assert reconstruct_old_classify_response_user(push, response) == (
        f"Push:\n{push}\n\nStudent reply:\n{response}"
    )


def test_reconstructed_old_classify_response_user_differs_from_the_new_indented_form():
    """Proves the reconstruction is genuinely the OLD (unindented) shape and not accidentally
    byte-identical to what `prompt_text.labelled` produces today -- a single-line response gets
    no leading indent in the reconstruction, but `labelled` always indents even the first line."""
    from elenchus.prompt_text import labelled

    push, response = "What do you give up?", "I would hold the line."
    old_user = reconstruct_old_classify_response_user(push, response)
    new_user = f"Push:\n{push}\n\n{labelled('Student reply:', response)}"
    assert old_user != new_user


def test_reconstructed_old_map_territories_user_matches_5d05267():
    # Pinned against `git show 5d05267:src/elenchus/model.py` (map_territories,
    # `user = f"Her situation:\n{situation}\n\nTerritories:\n{numbered}"` verbatim).
    situation = "Committing to an industry at a young age"
    territories = [("exp_a", "desc a"), ("exp_b", "desc b")]
    numbered = "1. [exp_a] desc a\n2. [exp_b] desc b"
    assert reconstruct_old_map_territories_user(situation, territories) == (
        f"Her situation:\n{situation}\n\nTerritories:\n{numbered}"
    )


def test_reconstructed_old_map_territories_user_differs_from_the_new_indented_form():
    from elenchus.prompt_text import labelled

    situation = "Committing to an industry at a young age"
    territories = [("exp_a", "desc a")]
    old_user = reconstruct_old_map_territories_user(situation, territories)
    new_user = f"{labelled('Her situation:', situation)}\n\nTerritories:\n1. [exp_a] desc a"
    assert old_user != new_user


# ---------------------------------------------------------------------------
# classify_response_disagree
# ---------------------------------------------------------------------------


def test_classify_response_disagree_false_when_all_three_fields_match():
    a = _rc("closed", True, False)
    b = _rc("closed", True, False)
    assert classify_response_disagree(a, b) is False


def test_classify_response_disagree_true_on_outcome_alone():
    a = _rc("closed", True, False)
    b = _rc("unchanged", True, False)
    assert classify_response_disagree(a, b) is True


def test_classify_response_disagree_true_on_mechanism_supplied_alone():
    a = _rc("closed", True, False)
    b = _rc("closed", False, False)
    assert classify_response_disagree(a, b) is True


def test_classify_response_disagree_true_on_hard_wrong_alone():
    a = _rc("regressed", False, True)
    b = _rc("regressed", False, False)
    assert classify_response_disagree(a, b) is True


# ---------------------------------------------------------------------------
# territory_head / territories_disagree
# ---------------------------------------------------------------------------


def test_territory_head_takes_the_first_known_id_in_ranked_order():
    assert territory_head(["exp_b", "exp_a"], ["exp_a", "exp_b"]) == "exp_b"


def test_territory_head_filters_out_hallucinated_ids():
    # 'exp_z' is not a real territory -- the real selector (web/session_runner.py:889-890)
    # filters to known ids before taking ranked[0].
    assert territory_head(["exp_z", "exp_b"], ["exp_a", "exp_b"]) == "exp_b"


def test_territory_head_falls_back_to_known_order_when_ranked_names_nothing_real():
    assert territory_head(["exp_z"], ["exp_a", "exp_b"]) == "exp_a"


def test_territories_disagree_false_when_heads_match_even_if_full_rank_order_differs():
    a = _tmap(["exp_a", "exp_b"])
    b = _tmap(["exp_a", "exp_c"])  # differs after the head -- must not count as disagreement
    assert territories_disagree(a, b, ["exp_a", "exp_b", "exp_c"]) is False


def test_territories_disagree_true_when_heads_differ():
    a = _tmap(["exp_a", "exp_b"])
    b = _tmap(["exp_b", "exp_a"])
    assert territories_disagree(a, b, ["exp_a", "exp_b"]) is True


# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------


def test_verdict_false_when_rates_are_exactly_equal():
    assert verdict(same_prompt_disagreement=0.2, new_vs_old_disagreement=0.2, margin=0.1) is False


def test_verdict_false_when_the_gap_is_smaller_than_the_margin():
    assert verdict(same_prompt_disagreement=0.1, new_vs_old_disagreement=0.15, margin=0.1) is False


def test_verdict_false_when_the_gap_exactly_equals_the_margin():
    # Strict inequality: a gap that only MEETS the margin is not a claimed shift.
    assert verdict(same_prompt_disagreement=0.1, new_vs_old_disagreement=0.2, margin=0.1) is False


def test_verdict_true_when_the_gap_exceeds_the_margin():
    assert verdict(same_prompt_disagreement=0.1, new_vs_old_disagreement=0.25, margin=0.1) is True


def test_verdict_false_when_new_vs_old_is_lower_than_same_prompt():
    assert verdict(same_prompt_disagreement=0.3, new_vs_old_disagreement=0.1, margin=0.1) is False


# ---------------------------------------------------------------------------
# corpus builders
# ---------------------------------------------------------------------------


def test_build_classify_corpus_round_robins_experiences_and_carries_the_pair_through():
    pairs = [("push1", "resp1"), ("push2", "resp2"), ("push3", "resp3")]
    exps = [_exp("exp_a"), _exp("exp_b")]
    items = build_classify_corpus(pairs, exps)
    assert [it.exp.experience_id for it in items] == ["exp_a", "exp_b", "exp_a"]
    assert items[0].push == "push1"
    assert items[0].response == "resp1"
    assert items[0].kind == "frame"
    assert items[0].code == "frame_0"


def test_build_classify_corpus_respects_a_limit():
    pairs = [("p1", "r1"), ("p2", "r2"), ("p3", "r3")]
    items = build_classify_corpus(pairs, [_exp()], limit=2)
    assert len(items) == 2


def test_build_classify_corpus_is_empty_with_no_experiences():
    assert build_classify_corpus([("p", "r")], []) == []


def test_build_territory_corpus_carries_the_same_territory_list_into_every_item():
    territories = [("exp_a", "desc a"), ("exp_b", "desc b")]
    items = build_territory_corpus(["sit1", "sit2"], territories)
    assert [it.situation for it in items] == ["sit1", "sit2"]
    assert all(it.territories == tuple(territories) for it in items)


def test_build_territory_corpus_respects_a_limit():
    items = build_territory_corpus(["s1", "s2", "s3"], [("e", "d")], limit=1)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# run_classify_probe / run_territory_probe -- pure orchestration
# ---------------------------------------------------------------------------


class _ScriptedClassifyModel:
    def __init__(self, arm_a_b):
        self._queue = list(arm_a_b)  # popped for arm A then arm B, in order
        self.calls = []

    def classify_response(self, exp, kind, code, push, response, *, stress=False):
        self.calls.append((exp.experience_id, kind, code, push, response, stress))
        return self._queue.pop(0)


def _raw_parse_scripted(results):
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
        return results.pop(0)

    return raw_parse, calls


def test_run_classify_probe_makes_exactly_two_model_calls_and_one_raw_parse_call_per_item():
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _ScriptedClassifyModel([_rc("closed", True, False), _rc("closed", True, False)])
    raw_parse, raw_calls = _raw_parse_scripted([_rc("closed", True, False)])
    records = run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "SYSTEM", max_tokens=999
    )
    assert len(model.calls) == 2
    assert len(raw_calls) == 1
    assert len(records) == 1


def test_run_classify_probe_arm_c_sends_the_reconstructed_old_user_and_the_given_system():
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _ScriptedClassifyModel([_rc(), _rc()])
    raw_parse, raw_calls = _raw_parse_scripted([_rc()])
    run_classify_probe(items, model, raw_parse, system_for=lambda it: "MY SYSTEM", max_tokens=999)
    assert raw_calls[0]["system"] == "MY SYSTEM"
    assert raw_calls[0]["user"] == reconstruct_old_classify_response_user("push1", "resp1")
    assert raw_calls[0]["max_tokens"] == 999


def test_run_classify_probe_flags_same_prompt_disagreement_when_a_and_b_differ():
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _ScriptedClassifyModel([_rc("closed", True, False), _rc("unchanged", True, False)])
    raw_parse, _ = _raw_parse_scripted([_rc("closed", True, False)])  # matches arm A
    records = run_classify_probe(items, model, raw_parse, system_for=lambda it: "S", max_tokens=1)
    assert records[0].same_prompt_disagree is True
    assert records[0].new_vs_old_disagree is False


def test_run_classify_probe_flags_new_vs_old_disagreement_when_a_and_c_differ():
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _ScriptedClassifyModel([_rc("closed", True, False), _rc("closed", True, False)])
    raw_parse, _ = _raw_parse_scripted([_rc("regressed", False, False)])  # differs from arm A
    records = run_classify_probe(items, model, raw_parse, system_for=lambda it: "S", max_tokens=1)
    assert records[0].same_prompt_disagree is False
    assert records[0].new_vs_old_disagree is True


class _ScriptedTerritoryModel:
    def __init__(self, arm_a_b):
        self._queue = list(arm_a_b)
        self.calls = []

    def map_territories(self, situation, territories):
        self.calls.append((situation, territories))
        return self._queue.pop(0)


def test_run_territory_probe_makes_exactly_two_model_calls_and_one_raw_parse_call_per_item():
    items = [TerritoryItem("situation", (("exp_a", "desc a"),))]
    model = _ScriptedTerritoryModel([_tmap(["exp_a"]), _tmap(["exp_a"])])
    raw_parse, raw_calls = _raw_parse_scripted([_tmap(["exp_a"])])
    records = run_territory_probe(items, model, raw_parse, system_text="SYSTEM", max_tokens=999)
    assert len(model.calls) == 2
    assert len(raw_calls) == 1
    assert len(records) == 1


def test_run_territory_probe_arm_c_sends_the_reconstructed_old_user_and_the_given_system():
    items = [TerritoryItem("situation", (("exp_a", "desc a"),))]
    model = _ScriptedTerritoryModel([_tmap(["exp_a"]), _tmap(["exp_a"])])
    raw_parse, raw_calls = _raw_parse_scripted([_tmap(["exp_a"])])
    run_territory_probe(items, model, raw_parse, system_text="MY SYSTEM", max_tokens=999)
    assert raw_calls[0]["system"] == "MY SYSTEM"
    assert raw_calls[0]["user"] == reconstruct_old_map_territories_user(
        "situation", [("exp_a", "desc a")]
    )


def test_run_territory_probe_flags_disagreement_by_head_not_full_rank_equality():
    items = [TerritoryItem("situation", (("exp_a", "desc a"), ("exp_b", "desc b")))]
    model = _ScriptedTerritoryModel([_tmap(["exp_a", "exp_b"]), _tmap(["exp_b", "exp_a"])])
    raw_parse, _ = _raw_parse_scripted([_tmap(["exp_a", "exp_b"])])  # same head as arm A
    records = run_territory_probe(items, model, raw_parse, system_text="S", max_tokens=1)
    assert records[0].same_prompt_disagree is True  # arm A head exp_a, arm B head exp_b
    assert records[0].new_vs_old_disagree is False  # arm A head exp_a, arm C head exp_a


# ---------------------------------------------------------------------------
# summarize_disagreement
# ---------------------------------------------------------------------------


def test_summarize_disagreement_computes_both_rates_and_the_verdict():
    records = [
        ClassifyRecord(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm_a=_rc(),
            arm_b=_rc(),
            arm_c=_rc(),
            same_prompt_disagree=True,
            new_vs_old_disagree=False,
        ),
        ClassifyRecord(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm_a=_rc(),
            arm_b=_rc(),
            arm_c=_rc(),
            same_prompt_disagree=False,
            new_vs_old_disagree=True,
        ),
        ClassifyRecord(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm_a=_rc(),
            arm_b=_rc(),
            arm_c=_rc(),
            same_prompt_disagree=False,
            new_vs_old_disagree=True,
        ),
        ClassifyRecord(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm_a=_rc(),
            arm_b=_rc(),
            arm_c=_rc(),
            same_prompt_disagree=False,
            new_vs_old_disagree=False,
        ),
    ]
    rates = summarize_disagreement(records, margin=0.1)
    assert rates.sample_size == 4
    assert rates.same_prompt_disagreement == 0.25
    assert rates.new_vs_old_disagreement == 0.5
    assert rates.margin == 0.1
    assert rates.shift_claimed is True  # 0.5 - 0.25 = 0.25 > 0.1


def test_summarize_disagreement_is_zero_and_unclaimed_on_an_empty_corpus():
    rates = summarize_disagreement([], margin=0.1)
    assert rates.sample_size == 0
    assert rates.same_prompt_disagreement == 0.0
    assert rates.new_vs_old_disagreement == 0.0
    assert rates.shift_claimed is False


def test_probe2_result_round_trips_through_json():
    classify_rates = summarize_disagreement([], margin=0.1)
    territory_rates = summarize_disagreement([], margin=0.1)
    result = Probe2Result(
        model_id="claude-opus-5",
        margin=0.1,
        classify_corpus_source="live_db",
        classify_records=[],
        classify_rates=classify_rates,
        territory_corpus_source="empty_fallback",
        territory_records=[],
        territory_rates=territory_rates,
    )
    again = Probe2Result.model_validate_json(result.model_dump_json())
    assert again == result
