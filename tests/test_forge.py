"""Living sitting Tasks L1+L2: wire models, the four model methods, territories, the DF matrix.

Live behavior of the AnthropicModel methods is @live-only; here we pin the wire shapes,
the FakeModel constants, the exact signatures later tasks consume verbatim (plan L1), the
territory descriptions' code teeth, and the pinned decision_frame matrix (plan L2, spec §2a/§2d).
"""

import inspect
import re

import pytest

from retnovation.content_loader import (
    load_denylist,
    load_experience,
    load_library,
    load_territory_text,
)
from retnovation.generator import validate_scene
from retnovation.model import AnthropicModel, FakeModel, IntakeClassification, Model
from retnovation.types import FitCheck, Scene, TerritoryMap
from retnovation.web import voice


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


# --- Task L2: territory descriptions (spec §2a) + the DF matrix (spec §2d) ---

TERRITORY_IDS = (
    "license_continuity",
    "decision_under_stakes",
    "irreversible_anchor",
    "continuity_lock_in",
    "proof_before_promise",
)

# The pinned DF matrix (spec §2d). license_continuity's is pre-existing; the other four are the
# arc floor, with the signal costs named in the spec (a DF frame loses reasoned_unprompted THERE;
# irreversible_anchor's DF is therefore NOT embed — the spine frame keeps its unprompted channel).
PINNED_DECISION_FRAMES = {
    "license_continuity": "commit_under_the_deadline",
    "decision_under_stakes": "choose_the_failure_default_deliberately",
    "irreversible_anchor": "choose_the_failure_default_deliberately",
    "continuity_lock_in": "embed_credentials_as_a_list",
    "proof_before_promise": "protect_the_core_lane",
}


@pytest.mark.parametrize("eid", TERRITORY_IDS)
def test_territory_description_loads_non_empty(eid):
    assert load_territory_text(eid).strip(), f"territory description for {eid} is empty"


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _four_grams(text: str) -> set[str]:
    w = _norm_words(text)
    return {" ".join(w[i : i + 4]) for i in range(len(w) - 3)}


@pytest.mark.parametrize("eid", TERRITORY_IDS)
def test_territory_description_clears_the_code_teeth(eid):
    """§2a teeth 1+2 (structure): each description must clear validate_scene's own bar against its
    OWN rubric (frame/trap codes snake+spaced, framework + scaffold denylists, wrapper words),
    share no 4+-word verbatim run with any hidden move's detail text, and screen clean through the
    egress shape (FakeModel — structural; tooth 3, the behavioral intake-shift probe, is @live via
    the elicitation harness kept alive by the §2d DF-free variants)."""
    desc = load_territory_text(eid)
    exp = load_experience(eid)
    # tooth 1a: the production scene gate, reused verbatim (no raise)
    validate_scene(
        Scene(prompt=desc, situation=""),
        exp.rubric,
        framework_denylist=load_denylist("framework_denylist"),
        scaffold_denylist=load_denylist("scaffold_denylist"),
    )
    # tooth 1b: no 4+-word verbatim substring of any frame_detail/trap_detail (the move text)
    desc_grams = _four_grams(desc)
    details = [f.frame_detail for f in exp.rubric.frames] + [
        t.trap_detail for t in exp.rubric.traps
    ]
    for detail in details:
        shared = _four_grams(detail) & desc_grams
        assert not shared, f"{eid}: description shares {sorted(shared)} with a hidden move"
    # tooth 2 (structure only): the description performs none of the rubric's moves
    assert voice._performed(_fake(), exp, desc) == set()


def test_df_matrix_is_pinned_and_the_rule_holds():
    """§2d: every rubric carries the PINNED decision_frame, the DF names a frame that exists in
    that rubric, and the rule holds — computed from content: no frame that lives on 2+ territories
    is DF on all of them (a multi-home frame keeps an unprompted channel somewhere). A single-home
    DF is forced by construction (commit_under_the_deadline has only one home) and is pinned above."""
    library = {e.experience_id: e for e in load_library()}
    assert set(PINNED_DECISION_FRAMES) == set(library)
    homes: dict[str, set[str]] = {}
    df_of: dict[str, str] = {}
    for eid, pinned in PINNED_DECISION_FRAMES.items():
        rubric = library[eid].rubric
        assert rubric.decision_frame == pinned, f"{eid}: decision_frame != the pinned matrix"
        codes = {f.frame_code for f in rubric.frames}
        assert pinned in codes, f"{eid}: decision_frame {pinned!r} is not a frame of the rubric"
        df_of[eid] = pinned
        for c in codes:
            homes.setdefault(c, set()).add(eid)
    for code, ids in homes.items():
        if len(ids) < 2:
            continue
        assert any(df_of[eid] != code for eid in ids), (
            f"{code} is decision_frame on every territory where it appears — "
            "it would lose its unprompted channel entirely (§2d rule)"
        )
