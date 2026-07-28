import pytest

from elenchus.model import AnthropicModel, ModelError, ResponseClassification
from elenchus.types import (
    Experience,
    Frame,
    FrameState,
    Mode,
    Regime,
    Rubric,
    Trap,
    TrapState,
)


def _exp():
    rub = Rubric(
        frames=[
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="Keep the promise the core product makes to everyone.",
                paired_trap="erode_core_for_one_customer",
            ),
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="State the boundary you will not cross first.",
                paired_trap="scope_creep_to_please",
            ),
        ],
        traps=[
            Trap(trap_code="erode_core_for_one_customer", trap_detail="Special-case one account."),
            Trap(
                trap_code="scope_creep_to_please", trap_detail="Bend the offer to avoid saying no."
            ),
        ],
        mode=Mode.genuinely_open,
        binding_constraint=None,
    )
    return Experience(
        experience_id="veldra:licensing_continuity",
        prompt="A customer contract ambiguity forces a same-day call.",
        rubric=rub,
        ledger_ref="veldra:licensing_continuity",
        regime=Regime.open_ended,
    )


# --- fake Anthropic client (duck-typed; no SDK, no network) ---


class _Item:
    def __init__(self, code, state):
        self.code = code
        self.state = state


class _Wire:
    def __init__(self, frames, traps):
        self.frames = frames
        self.traps = traps


class _Resp:
    def __init__(self, parsed_output=None, content=None, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.content = content or []
        self.stop_reason = stop_reason


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Messages:
    def __init__(self, parse_result=None, create_result=None):
        self._parse_result = parse_result
        self._create_result = create_result
        self.parse_calls = []
        self.create_calls = []

    def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        if isinstance(self._parse_result, list):  # sequenced: one response per call, in order
            return self._parse_result.pop(0)
        return self._parse_result

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._create_result


class _Client:
    def __init__(self, parse_result=None, create_result=None):
        self.messages = _Messages(parse_result, create_result)


def _system_text(call):
    sys = call["system"]
    return sys if isinstance(sys, str) else " ".join(b["text"] for b in sys)


def _user_text(call):
    return call["messages"][-1]["content"]


def test_classify_intake_classifies_from_rubric_and_opening():
    wire = _Wire(
        frames=[_Item("protect_the_core_lane", FrameState.present_reasoned)],
        traps=[_Item("erode_core_for_one_customer", TrapState.not_tripped)],
    )
    client = _Client(parse_result=_Resp(parsed_output=wire))
    result = AnthropicModel(client=client).classify_intake(
        _exp(), "Here is my reasoning about the core promise."
    )
    # mapping
    assert result.frame_states["protect_the_core_lane"] is FrameState.present_reasoned
    # defaulting: a rubric code absent from the model output falls back to absent / not_tripped
    assert result.frame_states["lead_with_what_you_refuse_to_do"] is FrameState.absent
    assert result.trap_states["scope_creep_to_please"] is TrapState.not_tripped
    # request carries doctrine + rubric detail + the opening
    call = client.messages.parse_calls[0]
    sys = _system_text(call)
    assert "present_reasoned" in sys
    assert "Keep the promise the core product makes" in sys
    assert "Here is my reasoning about the core promise." in _user_text(call)


def test_generate_push_pushes_from_angle_without_naming_it():
    client = _Client(
        create_result=_Resp(content=[_TextBlock("What do you give up by holding that line?")])
    )
    push = AnthropicModel(client=client).generate_push(_exp(), "frame", "protect_the_core_lane")
    assert push == "What do you give up by holding that line?"
    call = client.messages.create_calls[0]
    blob = _system_text(call) + " " + _user_text(call)
    assert "protect_the_core_lane" not in blob  # never feed the label to the model
    assert "Keep the promise the core product makes" in blob  # push from the angle detail


def test_classify_response_classifies_reply():
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    client = _Client(parse_result=_Resp(parsed_output=rc))
    out = AnthropicModel(client=client).classify_response(
        _exp(), "frame", "protect_the_core_lane", "push text", "student reply with a mechanism"
    )
    assert out.outcome == "closed"
    assert out.mechanism_supplied is True
    user = _user_text(client.messages.parse_calls[0])
    assert "push text" in user
    assert "student reply with a mechanism" in user


def test_refusal_raises_model_error():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).classify_intake(_exp(), "opening")


def test_stochastic_refusal_costs_one_plain_retry_not_the_segment():
    """Founder live dogfood 2026-07-03: classify_response refused mid-press on an ethically
    pointed reply and killed the door; the instrumented replay proved the class stochastic
    (same dialogue: 2 clean runs, 1 refusal). One plain retry recovers it."""
    wire = _Wire(
        frames=[_Item("protect_the_core_lane", FrameState.present_reasoned)],
        traps=[_Item("erode_core_for_one_customer", TrapState.not_tripped)],
    )
    client = _Client(
        parse_result=[
            _Resp(parsed_output=None, stop_reason="refusal"),
            _Resp(parsed_output=wire),
        ]
    )
    out = AnthropicModel(client=client).classify_intake(_exp(), "opening")
    # the retry's output is the call's output
    assert out.frame_states["protect_the_core_lane"] is FrameState.present_reasoned
    calls = client.messages.parse_calls
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == calls[1]["max_tokens"]  # plain retry — not budget-doubled


def test_persistent_refusal_fails_loud_after_exactly_one_retry():
    client = _Client(
        parse_result=[
            _Resp(parsed_output=None, stop_reason="refusal"),
            _Resp(parsed_output=None, stop_reason="refusal"),
        ]
    )
    with pytest.raises(ModelError):
        AnthropicModel(client=client).classify_intake(_exp(), "opening")
    assert len(client.messages.parse_calls) == 2  # bounded: the single retry, then loud


def test_truncation_then_refusal_stays_bounded_at_two_calls():
    """The retry budget is ONE, whichever class strikes first — a truncated call whose doubled
    retry then refuses must fail loud, never spend a third call."""
    wire_unused = _Resp(parsed_output=None, stop_reason="refusal")
    client = _Client(
        parse_result=[_Resp(parsed_output=None, stop_reason="max_tokens"), wire_unused]
    )
    with pytest.raises(ModelError):
        AnthropicModel(client=client).classify_intake(_exp(), "opening")
    calls = client.messages.parse_calls
    assert len(calls) == 2
    assert calls[1]["max_tokens"] == calls[0]["max_tokens"] * 2  # the one retry was the doubled one


def test_grade_answer_parses_correctness_against_criteria():
    from elenchus.types import CheckableGrade, CheckableQuestion, CheckType

    q = CheckableQuestion(
        question_id="q1",
        concept="at_least_once_vs_exactly_once",
        prompt="Explain effectively-once.",
        check_type=CheckType.model_graded,
        answer_key=["idempotent handler makes a duplicate a no-op"],
        criteria="must mention duplicates and idempotency",
    )
    client = _Client(parse_result=_Resp(parsed_output=CheckableGrade(correct=True)))
    out = AnthropicModel(client=client).grade_answer(
        _exp(), q, "duplicates are no-ops if idempotent"
    )
    assert out.correct is True
    call = client.messages.parse_calls[0]
    sys = _system_text(call)
    assert "must mention duplicates and idempotency" in sys  # criteria reach the grader
    assert "duplicates are no-ops if idempotent" in _user_text(call)


def test_grade_answer_refusal_raises():
    from elenchus.types import CheckableQuestion, CheckType

    q = CheckableQuestion(
        question_id="q1", concept="c", prompt="p", check_type=CheckType.model_graded, criteria="x"
    )
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).grade_answer(_exp(), q, "answer")


def test_grade_sharper_is_blind_and_parses_verdict():
    from elenchus.types import SharperVerdict

    client = _Client(
        parse_result=_Resp(parsed_output=SharperVerdict(sharper=True, reason="cited a mechanism"))
    )
    out = AnthropicModel(client=client).grade_sharper(
        _exp(),
        "frame",
        "protect_the_core_lane",
        "What do you give up by holding that line?",
        "I hold it because unverified work destroys revenue exactly when outages cluster.",
    )
    assert out.sharper is True
    call = client.messages.parse_calls[0]
    # the target angle detail reaches the grader's system prompt
    assert "Keep the promise the core product makes" in _system_text(call)
    # the raw student reply reaches the grader's user turn
    assert "unverified work destroys revenue" in _user_text(call)
    # blindness is structural: grade_sharper's signature has no instructor-outcome parameter


def test_grade_sharper_refusal_raises():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).grade_sharper(
            _exp(), "frame", "protect_the_core_lane", "push", "reply"
        )


def test_classify_intake_ignores_hallucinated_codes():
    # The model returns a frame/trap code that is not in the rubric — it must be dropped,
    # or it would corrupt the judgment loop's convergence/target logic.
    wire = _Wire(
        frames=[
            _Item("protect_the_core_lane", FrameState.present_reasoned),
            _Item("totally_made_up_frame", FrameState.present_reasoned),
        ],
        traps=[_Item("not_a_real_trap", TrapState.tripped)],
    )
    client = _Client(parse_result=_Resp(parsed_output=wire))
    result = AnthropicModel(client=client).classify_intake(_exp(), "opening")
    assert set(result.frame_states) == {"protect_the_core_lane", "lead_with_what_you_refuse_to_do"}
    assert set(result.trap_states) == {"erode_core_for_one_customer", "scope_creep_to_please"}


def _exp_with_scene():
    from elenchus.types import Scene

    return _exp().model_copy(
        update={
            "prompt": "A same-day call forces a real trade-off.",
            "scene": Scene(
                prompt="A same-day call forces a real trade-off.",
                situation="A long client is mid-rollout; a guarantee is under pressure.",
            ),
        }
    )


def test_situation_is_woven_in_when_a_scene_is_present():
    # generate_push includes the situation (user/system blob)
    client = _Client(create_result=_Resp(content=[_TextBlock("What do you give up?")]))
    AnthropicModel(client=client).generate_push(_exp_with_scene(), "frame", "protect_the_core_lane")
    call = client.messages.create_calls[0]
    assert "mid-rollout" in _system_text(call) + " " + _user_text(call)

    # classify_intake includes the situation (system context)
    wire = _Wire(frames=[_Item("protect_the_core_lane", FrameState.present_reasoned)], traps=[])
    c2 = _Client(parse_result=_Resp(parsed_output=wire))
    AnthropicModel(client=c2).classify_intake(_exp_with_scene(), "opening")
    assert "mid-rollout" in _system_text(c2.messages.parse_calls[0])

    # classify_response includes the situation (system context)
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    c3 = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=c3).classify_response(
        _exp_with_scene(), "frame", "protect_the_core_lane", "push text", "student reply"
    )
    assert "mid-rollout" in _system_text(c3.messages.parse_calls[0])


def test_no_scene_calls_omit_the_situation():
    client = _Client(create_result=_Resp(content=[_TextBlock("push")]))
    AnthropicModel(client=client).generate_push(_exp(), "frame", "protect_the_core_lane")
    call = client.messages.create_calls[0]
    assert "Situation:" not in _system_text(call) + " " + _user_text(
        call
    )  # byte-identical to today

    # classify_intake and classify_response also omit the situation with no scene
    wire = _Wire(frames=[_Item("protect_the_core_lane", FrameState.present_reasoned)], traps=[])
    ci = _Client(parse_result=_Resp(parsed_output=wire))
    AnthropicModel(client=ci).classify_intake(_exp(), "opening")
    assert "Situation:" not in _system_text(ci.messages.parse_calls[0])
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    cr = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=cr).classify_response(_exp(), "frame", "protect_the_core_lane", "p", "r")
    assert "Situation:" not in _system_text(cr.messages.parse_calls[0])


def test_generate_push_stress_mode_adds_the_stress_doctrine():
    client = _Client(create_result=_Resp(content=[_TextBlock("What would reverse this?")]))
    AnthropicModel(client=client).generate_push(
        _exp(), "frame", "protect_the_core_lane", stress=True
    )
    blob = _system_text(client.messages.create_calls[0])
    assert "already engaged this angle" in blob  # marker from push_stress.md


def test_generate_push_without_stress_is_byte_stable():
    client = _Client(create_result=_Resp(content=[_TextBlock("push")]))
    AnthropicModel(client=client).generate_push(_exp(), "frame", "protect_the_core_lane")
    blob = _system_text(client.messages.create_calls[0])
    assert "already engaged this angle" not in blob  # no stress doctrine when stress=False
    assert "case instructor" in blob  # the base push doctrine is still present (no drop)


def test_classify_response_stress_mode_adds_the_stress_doctrine():
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    client = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=client).classify_response(
        _exp(), "frame", "protect_the_core_lane", "push", "reply", stress=True
    )
    sys = _system_text(client.messages.parse_calls[0])
    assert "deepening mechanism" in sys  # marker from response_stress.md


def test_classify_response_without_stress_is_byte_stable():
    rc = ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    client = _Client(parse_result=_Resp(parsed_output=rc))
    AnthropicModel(client=client).classify_response(
        _exp(), "frame", "protect_the_core_lane", "push", "reply"
    )
    sys = _system_text(client.messages.parse_calls[0])
    assert "deepening mechanism" not in sys  # no stress doctrine when stress=False
    assert "case instructor" in sys  # the base response doctrine is still present (no drop)


def test_map_territories_instruction_carries_the_conversion_doctrine():
    """Spec §2a: the mapper authors the conversion — the instruction must define the topic
    verdict and the conversion craft (engage her subject, one question, never answer, never
    name a territory, never out-of-scope)."""
    from elenchus.types import TerritoryMap

    wire = TerritoryMap(ranked=["e1"], confidence="high", reflection="r")
    client = _Client(parse_result=_Resp(parsed_output=wire))
    AnthropicModel(client=client).map_territories("her situation", [("e1", "desc one")])
    sys = _system_text(client.messages.parse_calls[0])
    assert "`verdict`" in sys and '"topic"' in sys
    assert "`conversion`" in sys
    assert "never answers her question" in sys
    assert "out of scope" in sys  # the instruction FORBIDS it by naming it
