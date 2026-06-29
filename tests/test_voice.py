from retnovation.model import (
    AnthropicModel,
    FakeModel,
    IntakeClassification,
)
from retnovation.types import (
    EgressScreen,
    EntryClass,
    EntryClassification,
    Experience,
    Frame,
    Mode,
    Regime,
    Rubric,
    Trap,
)
from retnovation.web import voice


def _fake():
    intake = IntakeClassification(frame_states={}, trap_states={})
    return FakeModel(intake, {})


def _intake():
    return IntakeClassification(frame_states={}, trap_states={})


def _exp():
    rubric = Rubric(
        mode=Mode.genuinely_open,
        binding_constraint=None,
        decision_frame=None,
        frames=[
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="State the boundary you will not cross first.",
            )
        ],
        traps=[
            Trap(
                trap_code="scope_creep_to_please", trap_detail="Bend the offer to avoid saying no."
            )
        ],
    )
    return Experience(
        experience_id="e", prompt="p", ledger_ref="r", regime=Regime.open_ended, rubric=rubric
    )


class FakeLeakModel(FakeModel):
    """screen_moves flags any text containing 'LEAK' as PERFORMING every screened move."""

    def echo_push(self, push_text, recent):
        return "LEAK: lead with what you refuse to do"

    def screen_moves(self, moves, text):
        hit = list(range(1, len(moves) + 1)) if "LEAK" in text else []
        return EgressScreen(performed=hit, evidence="x")


def test_entry_classification_type():
    ec = EntryClassification(entry_class=EntryClass.greeting, reply="hi there")
    assert ec.entry_class is EntryClass.greeting and ec.reply == "hi there"


def test_fakemodel_entry_is_substantive_passthrough():
    m = _fake()
    ec = m.classify_entry("problem", "any opening", [])
    assert ec.entry_class is EntryClass.substantive and ec.reply == ""


def test_fakemodel_echo_is_identity():
    m = _fake()
    assert m.echo_push("the push", [("user", "x")]) == "the push"


def test_fakemodel_injection_check_is_safe_by_default():
    m = _fake()
    assert m.check_injection_expressed("a move", "some text").expressed is False


def test_echo_keeps_reskin_when_no_added_leak():
    # identity echo (no 'LEAK') + safe egress -> returned as-is
    m = FakeModel(_intake(), {})
    assert voice.echo(m, _exp(), "the push", [("student", "hi")]) == "the push"


def test_echo_falls_back_when_reskin_adds_a_leak_the_push_lacked():
    # push performs no move (no 'LEAK'); echo NAMES the move ('LEAK') -> added -> verbatim push
    m = FakeLeakModel(_intake(), {})
    assert voice.echo(m, _exp(), "the canonical push", [("student", "hi")]) == "the canonical push"


def test_echo_does_not_flag_a_move_already_performed_by_the_push():
    # both push and echo contain 'LEAK' -> NOT an ADDED revelation -> echo is kept (no false fallback)
    class _BothLeak(FakeLeakModel):
        def echo_push(self, push_text, recent):
            return "LEAK echo variant"

    m = _BothLeak(_intake(), {})
    assert voice.echo(m, _exp(), "LEAK canonical push", [("student", "x")]) == "LEAK echo variant"


def test_egress_safe_reply_flags_a_move_naming_string():
    m = FakeLeakModel(_intake(), {})
    assert voice.egress_safe_reply(m, _exp(), "harmless orientation?") is True
    assert voice.egress_safe_reply(m, _exp(), "LEAK here") is False


def test_egress_also_covers_rubric_traps():
    # a learner-facing reply that PERFORMS a trap move ("never name the move", L-5) must be flagged
    # unsafe — the egress screen covers traps, not only frames. _exp()'s trap is the 2nd move, so
    # flagging ONLY it (not the frame) proves the trap path is screened.
    class _TrapLeak(FakeModel):
        def screen_moves(self, moves, text):
            performed = [
                i for i, m in enumerate(moves, 1) if m == "Bend the offer to avoid saying no."
            ]
            return EgressScreen(performed=performed, evidence="x")

    m = _TrapLeak(_intake(), {})
    assert voice.egress_safe_reply(m, _exp(), "anything") is False


class _PerMoveModel(FakeModel):
    """screen_moves flags moves per-text (content-addressed) so a test can represent PARTIAL added
    revelation — candidate performs move A, push performs a DIFFERENT move B — which the
    all-or-nothing LEAK fake cannot. These pin the set-difference heart of the echo gate offline
    (was @live-only): a candidate that adds a move the push lacked must fall back; a candidate whose
    moves are a SUBSET of the push's must be kept."""

    def __init__(self, intake, flags):
        super().__init__(intake, {})
        self._flags = flags

    def echo_push(self, push_text, recent):
        return "CANDIDATE"

    def screen_moves(self, moves, text):
        return EgressScreen(performed=self._flags.get(text, []), evidence="x")


def test_echo_keeps_candidate_when_its_moves_are_a_subset_of_the_push():
    # candidate performs only move {2}, which the push ALSO performs -> no ADDED revelation -> keep
    m = _PerMoveModel(_intake(), {"CANDIDATE": [2], "PUSH": [1, 2]})
    assert voice.echo(m, _exp(), "PUSH", [("student", "x")]) == "CANDIDATE"


def test_echo_falls_back_on_partial_added_revelation():
    # candidate performs move {1}; push performs a DIFFERENT move {2} -> {1}-{2}={1} added -> push
    m = _PerMoveModel(_intake(), {"CANDIDATE": [1], "PUSH": [2]})
    assert voice.echo(m, _exp(), "PUSH", [("student", "x")]) == "PUSH"


class FakeDoorModel(FakeModel):
    def __init__(self, intake, entry_class, reply):
        super().__init__(intake, {})
        self._entry = EntryClassification(entry_class=entry_class, reply=reply)

    def classify_entry(self, prompt, opening, recent):
        return self._entry


def test_door_substantive_enters_engine():
    m = FakeDoorModel(_intake(), EntryClass.substantive, "")
    cls, reply = voice.door(m, _exp(), "I'd hold the line because...", [])
    assert cls is EntryClass.substantive and reply is None


def test_door_greeting_returns_authored_reply():
    m = FakeDoorModel(_intake(), EntryClass.greeting, "Welcome — take a position to begin.")
    cls, reply = voice.door(m, _exp(), "hi", [])
    assert cls is EntryClass.greeting and reply == "Welcome — take a position to begin."


def test_door_replaces_leaking_reply_with_safe_contract():
    m = FakeDoorModel(_intake(), EntryClass.confusion, "lead with what you refuse to do")
    m.screen_moves = lambda moves, text: EgressScreen(
        performed=([1] if "refuse" in text else []), evidence="x"
    )
    cls, reply = voice.door(m, _exp(), "I don't get it", [])
    assert cls is EntryClass.confusion and reply == voice.SAFE_CONTRACT


class _Resp:
    def __init__(self, parsed=None, content=None, stop_reason="end_turn"):
        self.parsed_output = parsed
        self.content = content or []
        self.stop_reason = stop_reason


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _StubClient:
    """Captures the last request kwargs and returns canned responses."""

    def __init__(self, parsed=None, text=None):
        self._parsed, self._text = parsed, text
        self.last = {}
        self.messages = self

    def parse(self, **kw):
        self.last = kw
        return _Resp(parsed=self._parsed)

    def create(self, **kw):
        self.last = kw
        return _Resp(content=[_Block(self._text)])


def test_classify_entry_is_frame_blind_and_parses():
    parsed = EntryClassification(entry_class=EntryClass.greeting, reply="Welcome.")
    stub = _StubClient(parsed=parsed)
    m = AnthropicModel(client=stub)
    out = m.classify_entry("The pricing problem text.", "hi", [("student", "hi")])
    assert out.entry_class is EntryClass.greeting
    # frame-blind: neither rubric codes nor details may appear anywhere in the request
    blob = str(stub.last)
    assert "lead_with_what_you_refuse_to_do" not in blob
    assert "frame_detail" not in blob and "Rubric" not in blob
    # the problem prompt IS available to the classifier
    assert "The pricing problem text." in blob


def test_echo_push_is_frame_blind_and_returns_text():
    stub = _StubClient(
        text="Given you'd hold firm — what makes you sure that's the reversible side?"
    )
    m = AnthropicModel(client=stub)
    out = m.echo_push("Which mistake can you walk back?", [("student", "I'd hold firm.")])
    assert out.startswith("Given you'd hold firm")
    blob = str(stub.last)
    assert "lead_with_what_you_refuse_to_do" not in blob and "Rubric" not in blob
    # the canonical push IS the input to re-voice
    assert "Which mistake can you walk back?" in blob
