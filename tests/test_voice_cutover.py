from retnovation.content_loader import load_experience
from retnovation.model import AnthropicModel
from retnovation.types import EgressScreen
from retnovation.web import voice


class _Resp:
    def __init__(self, text):
        self.content = [type("B", (), {"type": "text", "text": text})()]
        self.stop_reason = "end_turn"
        self.parsed_output = None


class _EgressResp:
    def __init__(self):
        self.parsed_output = EgressScreen(performed=[], evidence="clean")
        self.stop_reason = "end_turn"
        self.content = []


class _CaptureClient:
    """Captures the authoring (create) request separately from the egress (parse) screen, so the
    composed `voice` system text can be asserted without the egress screen overwriting the capture."""

    def __init__(self, text="ok"):
        self._text = text
        self.last_create = {}
        self.messages = self

    def create(self, **kw):
        self.last_create = kw
        return _Resp(self._text)

    def parse(self, **kw):
        return _EgressResp()  # clean egress so voice.turn keeps the authored text


def test_turn_prepends_the_composed_voice_with_gear_into_the_request():
    exp = load_experience("irreversible_anchor")  # cto
    stub = _CaptureClient("Okay. What breaks first?")
    m = AnthropicModel(client=stub)
    voice.turn(m, exp, "the canonical push", [("student", "ship it raw")], posture="founder_ceo")
    blob = str(stub.last_create)
    assert "You are Vera" in blob  # persona reached the system prompt
    assert "STOP pressing" in blob  # the gear (hard-stop) reached it -> not dropped in the cutover
    assert "embed_credentials_as_a_list" not in blob  # frame-blind: no rubric


def test_converse_also_carries_the_gear():
    exp = load_experience("irreversible_anchor")
    stub = _CaptureClient("Say more.")
    m = AnthropicModel(client=stub)
    voice.converse(m, exp, [("student", "x")], "what about the field?", posture="founder_ceo")
    assert "re-point" in str(stub.last_create).lower()  # re-anchor gear on the converse path too
