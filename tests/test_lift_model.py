import pytest

from retnovation.model import AnthropicModel, ModelError
from retnovation.types import GeneratedOutput, InjectionExpressed, PreferenceRating


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

    def parse(self, **kw):
        self.parse_calls.append(kw)
        return self._parse_result

    def create(self, **kw):
        self.create_calls.append(kw)
        return self._create_result


class _Client:
    def __init__(self, parse_result=None, create_result=None):
        self.messages = _Messages(parse_result, create_result)


def _sys(call):
    s = call["system"]
    return s if isinstance(s, str) else " ".join(b["text"] for b in s)


def test_generate_output_control_has_no_system_frame():
    client = _Client(create_result=_Resp(content=[_TextBlock("control text")]))
    out = AnthropicModel(client=client).generate_output("Write a pitch.", None)
    assert isinstance(out, GeneratedOutput) and out.text == "control text" and out.refused is False
    assert "system" not in client.messages.create_calls[0]  # control is frame-naive


def test_generate_output_framed_injects_the_frame_as_system():
    client = _Client(create_result=_Resp(content=[_TextBlock("framed text")]))
    AnthropicModel(client=client).generate_output(
        "Write a pitch.", "lead with what you refuse to do"
    )
    assert "lead with what you refuse to do" in _sys(client.messages.create_calls[0])


def test_generate_output_captures_refusal_instead_of_raising():
    # EXP-002 B2: a control refusal is SIGNAL — must be captured, not raised (unlike generate_push).
    client = _Client(
        create_result=_Resp(content=[_TextBlock("I can't help with that.")], stop_reason="refusal")
    )
    out = AnthropicModel(client=client).generate_output("Announce a data feature.", None)
    assert out.refused is True and out.text == "I can't help with that."


def test_rate_preference_is_unprimed_and_parses():
    pr = PreferenceRating(
        distinguishability=2, preferred="A", magnitude=1, key_difference="A is concrete"
    )
    client = _Client(parse_result=_Resp(parsed_output=pr))
    out = AnthropicModel(client=client).rate_preference("task", "out A", "out B")
    assert out.preferred == "A" and out.magnitude == 1
    blob = (
        _sys(client.messages.parse_calls[0])
        + " "
        + client.messages.parse_calls[0]["messages"][-1]["content"]
    )
    assert "out A" in blob and "out B" in blob
    assert "refuse" not in blob.lower()  # unprimed: no frame text leaks to the rater


def test_check_injection_expressed_is_primed_and_parses():
    ie = InjectionExpressed(expressed=True, evidence="'we never take custody'")
    client = _Client(parse_result=_Resp(parsed_output=ie))
    out = AnthropicModel(client=client).check_injection_expressed(
        "lead with what you refuse to do", "We never take custody of your funds."
    )
    assert out.expressed is True and out.evidence
    # primed: the injection (the move to check for) reaches the checker
    assert "lead with what you refuse to do" in _sys(client.messages.parse_calls[0])


def test_rate_preference_refusal_raises():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).rate_preference("t", "a", "b")


def test_check_injection_expressed_refusal_raises():
    client = _Client(parse_result=_Resp(parsed_output=None, stop_reason="refusal"))
    with pytest.raises(ModelError):
        AnthropicModel(client=client).check_injection_expressed("some injection", "some output")


def test_fake_lift_model_scripts_the_three_methods():
    from retnovation.model import FakeLiftModel

    fake = FakeLiftModel(
        outputs={("p", False): GeneratedOutput(text="C"), ("p", True): GeneratedOutput(text="F")},
        ratings={
            "p": PreferenceRating(
                distinguishability=2, preferred="B", magnitude=2, key_difference="k"
            )
        },
        expressed={"F": InjectionExpressed(expressed=True, evidence="e")},
    )
    assert fake.generate_output("p", None).text == "C"
    assert fake.generate_output("p", "inj").text == "F"
    assert fake.rate_preference("p", "x", "y").preferred == "B"
    assert fake.check_injection_expressed("inj", "F").expressed is True
