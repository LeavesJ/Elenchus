"""Living sitting Task L1: wire models + the four model methods (fake/protocol layer).

Live behavior of the AnthropicModel methods is @live-only; here we pin the wire shapes,
the FakeModel constants, and the exact signatures later tasks consume verbatim (plan L1).
"""

import inspect

from retnovation.model import AnthropicModel, FakeModel, IntakeClassification, Model
from retnovation.types import FitCheck, TerritoryMap


def _fake():
    return FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={})


def test_wire_models_validate():
    tm = TerritoryMap(ranked=["a"], confidence="high", reflection="r")
    assert tm.ranked == ["a"] and tm.confidence == "high" and tm.reflection == "r"
    fc = FitCheck(fits=False, reason="the scenario establishes no deadline")
    assert fc.fits is False and fc.reason == "the scenario establishes no deadline"


def test_fake_model_map_territories_ranks_all_ids():
    out = _fake().map_territories(
        "signing a delivery commitment Thursday",
        [("license_continuity", "desc a"), ("irreversible_anchor", "desc b")],
    )
    assert isinstance(out, TerritoryMap)
    assert out.ranked == ["license_continuity", "irreversible_anchor"]  # all ids, given order
    assert out.confidence == "high"
    assert out.reflection == "[reflect]"


def test_fake_model_forge_fit_and_sitting_close_constants():
    m = _fake()
    assert m.forge_scenario("the brief") == "[forged scenario]"
    assert m.forge_scenario("the brief", steer="establish the deadline") == "[forged scenario]"
    fc = m.fit_check("[forged scenario]", "requires a deadline")
    assert isinstance(fc, FitCheck) and fc.fits is True and fc.reason == ""
    assert m.concierge_sitting_close("her situation", [[("you", "turn")]]) == "[sitting close]"


def test_protocol_and_anthropic_carry_the_four_methods():
    for name in ("map_territories", "forge_scenario", "fit_check", "concierge_sitting_close"):
        assert hasattr(Model, name), f"Model protocol missing {name}"
        assert hasattr(AnthropicModel, name), f"AnthropicModel missing {name}"
        assert hasattr(FakeModel, name), f"FakeModel missing {name}"


def test_anthropic_signatures_match_the_plan():
    # Later tasks consume these signatures verbatim (plan L1) — pin names and defaults on the
    # CLASS, never instantiating (live behavior is @live-only).
    sig = inspect.signature(AnthropicModel.map_territories)
    assert list(sig.parameters) == ["self", "situation", "territories"]
    sig = inspect.signature(AnthropicModel.forge_scenario)
    assert list(sig.parameters) == ["self", "brief", "steer"]
    assert sig.parameters["steer"].default == ""
    sig = inspect.signature(AnthropicModel.fit_check)
    assert list(sig.parameters) == ["self", "scenario", "requirements"]
    sig = inspect.signature(AnthropicModel.concierge_sitting_close)
    assert list(sig.parameters) == ["self", "situation", "segments", "voice"]
    assert sig.parameters["voice"].default == ""
