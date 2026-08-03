"""Pure logic for probe 2 (does the reformatted graded prompt shift a decision). No model call
anywhere in this file: `classify_response`/`map_territories` and the arm-C raw parse are always
scripted doubles, so every assertion here is provable offline."""

from __future__ import annotations

import pytest

from elenchus.model import ModelError, ResponseClassification
from elenchus.prompt_shift_probe import (
    ClassifyFailure,
    ClassifyItem,
    ClassifyRecord,
    Probe2Result,
    TerritoryFailure,
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
    records, failures = run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "SYSTEM", max_tokens=999
    )
    assert len(model.calls) == 2
    assert len(raw_calls) == 1
    assert len(records) == 1
    assert failures == []


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
    records, _ = run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "S", max_tokens=1
    )
    assert records[0].same_prompt_disagree is True
    assert records[0].new_vs_old_disagree is False


def test_run_classify_probe_flags_new_vs_old_disagreement_when_a_and_c_differ():
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _ScriptedClassifyModel([_rc("closed", True, False), _rc("closed", True, False)])
    raw_parse, _ = _raw_parse_scripted([_rc("regressed", False, False)])  # differs from arm A
    records, _ = run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "S", max_tokens=1
    )
    assert records[0].same_prompt_disagree is False
    assert records[0].new_vs_old_disagree is True


# ---------------------------------------------------------------------------
# run_classify_probe -- per-item ModelError resilience
# ---------------------------------------------------------------------------


class _RaisingClassifyModel:
    """Arm A/B calls: pops a scripted result OR raises the scripted exception."""

    def __init__(self, arm_a_b):
        self._queue = list(arm_a_b)

    def classify_response(self, exp, kind, code, push, response, *, stress=False):
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _raw_parse_raising(outcomes):
    """Pops a scripted result OR raises the scripted exception, per call."""

    def raw_parse(*, system, user, output_format, max_tokens):
        item = outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return raw_parse


def test_run_classify_probe_records_an_arm_c_refusal_as_a_failure_and_keeps_going():
    """The founder's exact incident: arm C (`_parse_required` on the reconstructed pre-indent
    prompt) raises `ModelError` on one item. That item must be recorded as a `ClassifyFailure`
    naming arm "c" and the run must still process the SECOND item rather than aborting -- the
    defect this whole change fixes."""
    exp = _exp()
    items = [
        ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1"),
        ClassifyItem(exp, "frame", "frame_0", False, "push2", "resp2"),
    ]
    model = _RaisingClassifyModel(
        [_rc(), _rc(), _rc(), _rc()]  # 2 items * arm A/B each
    )
    raw_parse = _raw_parse_raising(
        [ModelError("model refused or returned no parsed output"), _rc()]
    )
    records, failures = run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "S", max_tokens=1
    )
    assert len(failures) == 1
    assert len(records) == 1  # the SECOND item still completed
    failure = failures[0]
    assert isinstance(failure, ClassifyFailure)
    assert failure.arm == "c"
    assert failure.push == "push1"
    assert "refused" in failure.error
    assert records[0].push == "push2"


def test_run_classify_probe_records_which_arm_failed_for_arm_a_and_arm_b_too():
    """Arm attribution must be correct for ALL three positions, not just arm C -- a reader needs
    to distinguish a refusal on the FIRST call (arm A) from one on the retry-control call (arm B)
    from the reconstructed-prompt call (arm C), since only arm C sends prompt text no shipped
    method composes today."""
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model_a_fails = _RaisingClassifyModel(
        [ModelError("model refused or returned no parsed output")]
    )
    _, failures_a = run_classify_probe(
        items, model_a_fails, _raw_parse_raising([]), system_for=lambda it: "S", max_tokens=1
    )
    assert failures_a[0].arm == "a"

    model_b_fails = _RaisingClassifyModel(
        [_rc(), ModelError("model refused or returned no parsed output")]
    )
    _, failures_b = run_classify_probe(
        items, model_b_fails, _raw_parse_raising([]), system_for=lambda it: "S", max_tokens=1
    )
    assert failures_b[0].arm == "b"


def test_run_classify_probe_lets_a_non_model_error_propagate_uncaught():
    """`ModelError` is caught narrowly, not `Exception` -- an unanticipated error class (a
    transport failure, a programming bug) must still crash the run rather than being silently
    absorbed as an ordinary failed item, so a reader who sees the run finish cleanly can trust
    every non-empty `error` field really is a `ModelError`."""
    exp = _exp()
    items = [ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1")]
    model = _RaisingClassifyModel([RuntimeError("boom, not a ModelError")])
    with pytest.raises(RuntimeError, match="boom"):
        run_classify_probe(
            items, model, _raw_parse_raising([]), system_for=lambda it: "S", max_tokens=1
        )


def test_run_classify_probe_calls_on_item_once_per_item_with_the_record_or_failure():
    """`on_item` is the checkpoint hook: it must fire exactly once per item, in order, carrying
    whichever outcome that item actually produced -- a dropped or misordered call would silently
    lose or misattribute a checkpointed item."""
    exp = _exp()
    items = [
        ClassifyItem(exp, "frame", "frame_0", False, "push1", "resp1"),
        ClassifyItem(exp, "frame", "frame_0", False, "push2", "resp2"),
    ]
    model = _RaisingClassifyModel([_rc(), _rc(), _rc(), _rc()])
    raw_parse = _raw_parse_raising(
        [ModelError("model refused or returned no parsed output"), _rc()]
    )
    seen = []
    run_classify_probe(
        items, model, raw_parse, system_for=lambda it: "S", max_tokens=1, on_item=seen.append
    )
    assert len(seen) == 2
    assert isinstance(seen[0], ClassifyFailure) and seen[0].push == "push1"
    assert isinstance(seen[1], ClassifyRecord) and seen[1].push == "push2"


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
    records, failures = run_territory_probe(
        items, model, raw_parse, system_text="SYSTEM", max_tokens=999
    )
    assert len(model.calls) == 2
    assert len(raw_calls) == 1
    assert len(records) == 1
    assert failures == []


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
    records, _ = run_territory_probe(items, model, raw_parse, system_text="S", max_tokens=1)
    assert records[0].same_prompt_disagree is True  # arm A head exp_a, arm B head exp_b
    assert records[0].new_vs_old_disagree is False  # arm A head exp_a, arm C head exp_a


# ---------------------------------------------------------------------------
# run_territory_probe -- per-item ModelError resilience
# ---------------------------------------------------------------------------


class _RaisingTerritoryModel:
    def __init__(self, arm_a_b):
        self._queue = list(arm_a_b)

    def map_territories(self, situation, territories):
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_run_territory_probe_records_an_arm_c_refusal_as_a_failure_and_keeps_going():
    items = [
        TerritoryItem("situation1", (("exp_a", "desc a"),)),
        TerritoryItem("situation2", (("exp_a", "desc a"),)),
    ]
    model = _RaisingTerritoryModel(
        [_tmap(["exp_a"]), _tmap(["exp_a"]), _tmap(["exp_a"]), _tmap(["exp_a"])]
    )
    raw_parse = _raw_parse_raising(
        [ModelError("model refused or returned no parsed output"), _tmap(["exp_a"])]
    )
    records, failures = run_territory_probe(items, model, raw_parse, system_text="S", max_tokens=1)
    assert len(failures) == 1
    assert len(records) == 1
    assert isinstance(failures[0], TerritoryFailure)
    assert failures[0].arm == "c"
    assert failures[0].situation == "situation1"
    assert records[0].situation == "situation2"


def test_run_territory_probe_lets_a_non_model_error_propagate_uncaught():
    items = [TerritoryItem("situation1", (("exp_a", "desc a"),))]
    model = _RaisingTerritoryModel([RuntimeError("boom, not a ModelError")])
    with pytest.raises(RuntimeError, match="boom"):
        run_territory_probe(items, model, _raw_parse_raising([]), system_text="S", max_tokens=1)


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
    rates = summarize_disagreement(records, [], margin=0.1)
    assert rates.comparable_n == 4
    assert rates.same_prompt_disagreement == 0.25
    assert rates.new_vs_old_disagreement == 0.5
    assert rates.margin == 0.1
    assert rates.shift_claimed is True  # 0.5 - 0.25 = 0.25 > 0.1


def test_summarize_disagreement_is_zero_and_unclaimed_on_an_empty_corpus():
    rates = summarize_disagreement([], [], margin=0.1)
    assert rates.comparable_n == 0
    assert rates.same_prompt_disagreement == 0.0
    assert rates.new_vs_old_disagreement == 0.0
    assert rates.shift_claimed is False


def test_summarize_disagreement_excludes_failed_items_from_both_rates_and_reports_denominators():
    """The core anti-bias property: a failed item must shrink neither the disagreement COUNT
    without shrinking the denominator (which would read as "agreement") nor vanish from the
    output entirely. 1 comparable item that DISAGREES on both axes, plus 3 failed items, must
    report disagreement rates of 1/1 = 1.0 (not 1/4 = 0.25, which is what counting failures as
    non-disagreeing "comparable" items would produce), while still surfacing that 3 items were
    attempted and excluded."""
    disagreeing = ClassifyRecord(
        experience_id="e",
        kind="frame",
        code="c",
        push="p",
        response="r",
        arm_a=_rc("closed", True, False),
        arm_b=_rc("unchanged", True, False),
        arm_c=_rc("regressed", False, False),
        same_prompt_disagree=True,
        new_vs_old_disagree=True,
    )
    failures = [
        ClassifyFailure(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm="a",
            error="model refused or returned no parsed output",
        ),
        ClassifyFailure(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm="b",
            error="model refused or returned no parsed output",
        ),
        ClassifyFailure(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm="c",
            error="structured output truncated at max_tokens -- raise this call's budget (L-17)",
        ),
    ]
    rates = summarize_disagreement([disagreeing], failures, margin=0.1)
    assert rates.comparable_n == 1
    assert rates.failed_n == 3
    assert rates.attempted_n == 4
    assert rates.same_prompt_disagreement == 1.0  # 1/1, NOT 1/4
    assert rates.new_vs_old_disagreement == 1.0  # 1/1, NOT 1/4


def test_summarize_disagreement_reports_the_refusal_rate_distinct_from_other_failures():
    """Only failures whose error text says "refused" count toward `refused_n`/`refusal_rate` --
    a truncation or an oversized-input guard is a real `ModelError` too, but not the specific
    stochastic-refusal property L-17 documents and this probe measures."""
    failures = [
        ClassifyFailure(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm="c",
            error="model refused or returned no parsed output",
        ),
        ClassifyFailure(
            experience_id="e",
            kind="frame",
            code="c",
            push="p",
            response="r",
            arm="a",
            error="structured output truncated at max_tokens -- raise this call's budget (L-17)",
        ),
    ]
    rates = summarize_disagreement([], failures, margin=0.1)
    assert rates.attempted_n == 2
    assert rates.refused_n == 1
    assert rates.refusal_rate == 0.5


def test_probe2_result_round_trips_through_json():
    classify_rates = summarize_disagreement([], [], margin=0.1)
    territory_rates = summarize_disagreement([], [], margin=0.1)
    result = Probe2Result(
        model_id="claude-opus-5",
        margin=0.1,
        classify_corpus_source="live_db",
        classify_records=[],
        classify_failures=[],
        classify_rates=classify_rates,
        territory_corpus_source="empty_fallback",
        territory_records=[],
        territory_failures=[],
        territory_rates=territory_rates,
    )
    again = Probe2Result.model_validate_json(result.model_dump_json())
    assert again == result
