from retnovation.model import FakeModel, InjectionExpressed, IntakeClassification
from retnovation.types import (
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
    """check_injection_expressed flags any text containing 'LEAK' as PERFORMING the move."""

    def echo_push(self, push_text, recent):
        return "LEAK: lead with what you refuse to do"

    def check_injection_expressed(self, injection, framed_output):
        return InjectionExpressed(expressed="LEAK" in framed_output, evidence="x")


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
