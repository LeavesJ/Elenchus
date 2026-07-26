"""The confirm-before-commit door (Spec-3 §4).

The 2026-07-24 dogfood: the mapper read a go-to-market question as a commitment decision and
forged a scenario; the founder's correction ("no no like how to get my first client") was
absorbed as evasion because voice.gate only asks *is this substantive?*. The sitting then
converged, writing a permanent memory of a decision he never made.

The fix is a gate BEFORE the forge, not an exit inside the loop (L-5: the loop stays sealed —
the gate fires while no scenario exists, so there is no effort to evade yet)."""

from retnovation.web.session_runner import _is_affirmative


def test_plain_agreement_is_affirmative():
    for t in ["yes", "Yes", "yep", "yeah", "correct", "that's it", "right", "ok", "go", "sure"]:
        assert _is_affirmative(t), t


def test_a_correction_is_not_affirmative():
    for t in [
        "no no like how to get my first client",  # the founder's actual words
        "not quite, it's about pricing",
        "no",
        "that's not it",
        "actually I meant the hiring decision",
    ]:
        assert not _is_affirmative(t), t


def test_a_substantive_reply_is_not_affirmative():
    # Anything with real content is a correction or a position, never a bare yes. Erring here
    # costs one re-map; erring the other way forges an unagreed scenario.
    assert not _is_affirmative("yes but the real problem is the co-founder equity split")
    assert not _is_affirmative("I need to decide whether to sign by Friday")


def test_empty_and_whitespace_are_not_affirmative():
    for t in ["", "   ", "\n"]:
        assert not _is_affirmative(t)
