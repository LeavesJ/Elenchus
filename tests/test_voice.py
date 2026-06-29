from retnovation.model import FakeModel, IntakeClassification
from retnovation.types import EntryClass, EntryClassification


def _fake():
    intake = IntakeClassification(frame_states={}, trap_states={})
    return FakeModel(intake, {})


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
