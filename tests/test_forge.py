"""Living sitting Tasks L1+L2+L3: wire models, the four model methods, territories, the DF
matrix, and the forge (gates, regen, honest fallback, registry seam, two-grain identity).

Live behavior of the AnthropicModel methods is @live-only; here we pin the wire shapes,
the FakeModel constants, the exact signatures later tasks consume verbatim (plan L1), the
territory descriptions' code teeth, the pinned decision_frame matrix (plan L2, spec §2a/§2d),
and the forge's gate order + seam (plan L3, spec §2b).
"""

import inspect
import re

import pytest

from retnovation import forge
from retnovation.content_loader import (
    load_denylist,
    load_experience,
    load_library,
    load_territory_text,
)
from retnovation.generator import select_open_ended, validate_scene
from retnovation.model import AnthropicModel, FakeModel, IntakeClassification, Model
from retnovation.persistence import Store
from retnovation.types import (
    EgressScreen,
    FitCheck,
    NextExperienceSpec,
    Regime,
    Scene,
    TerritoryMap,
)
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


# --- Task L3: the forge — gates, regen, honest fallback, registry seam (spec §2b) ---

SITUATION = "Signing a delivery commitment Thursday; the penalty clause is the fight."
POSITIONS = [
    "I capped the penalty at 2% and told the board why.",
    "I won't move the ship date.",
]

# A realistic forged scenario that clears the code gates against license_continuity's rubric:
# second person, real stakes, ends on the decision ask, no frame/trap code (snake or spaced),
# no framework/scaffold/wrapper word. FakeModel's constant "[forged scenario]" is deliberately
# too degenerate to clear the structural gate, so forge tests subclass (the
# _ConciergeFidelityModel convention the plan names for leak/reject fakes).
_SCENARIO = (
    "You signed the delivery agreement on Thursday, and this morning your second-largest "
    "customer asked for the same penalty terms before Friday's board review. The account team "
    "wants an answer before the standup, and whatever you give one customer the others will "
    "hear about. What do you do?"
)


@pytest.fixture(autouse=True)
def _clean_forge_registry():
    forge.forge_registry.clear()
    yield
    forge.forge_registry.clear()


class _ForgeFake(FakeModel):
    """FakeModel whose forge_scenario returns a gate-clearing scenario and records every
    (brief, steer) call — the spy the brief-purity and steered-regen tests read."""

    def __init__(self):
        super().__init__(IntakeClassification(frame_states={}, trap_states={}), responses={})
        self.briefs: list[tuple[str, str]] = []

    def forge_scenario(self, brief, steer=""):
        self.briefs.append((brief, steer))
        return _SCENARIO


class _LeakScreenModel(_ForgeFake):
    """screen_moves scripted-pop (plan L3: list-pop scripts — the regen path needs different
    behavior across attempts). One `performed` list per call; empty script -> clean."""

    def __init__(self, script):
        super().__init__()
        self._script = script

    def screen_moves(self, moves, text):
        performed = self._script.pop(0) if self._script else []
        return EgressScreen(performed=performed, evidence="(scripted)")


class _FitRejectModel(_ForgeFake):
    """fit_check scripted-pop; empty script -> fits."""

    def __init__(self, script):
        super().__init__()
        self._script = script

    def fit_check(self, scenario, requirements):
        return self._script.pop(0) if self._script else FitCheck(fits=True, reason="")


class _MovesSpyModel(_ForgeFake):
    """Records the move list handed to the union egress screen."""

    def __init__(self):
        super().__init__()
        self.moves = None
        self.screened_text = None

    def screen_moves(self, moves, text):
        self.moves = list(moves)
        self.screened_text = text
        return EgressScreen(performed=[], evidence="(spy)")


def _engine_store(tmp_path):
    return Store(tmp_path / "engine.db")


def _forge(model, store, *, sid="s1", n=1, level="base", engaged=None, base=None):
    base = base or load_experience("license_continuity")
    return forge.forge_experience(
        base, sid, n, SITUATION, POSITIONS, engaged or [], level, model, store
    )


def test_forge_happy_path_world_grain_scene_none_rubric_byte_equal(tmp_path):
    base = load_experience("license_continuity")
    res = _forge(_ForgeFake(), _engine_store(tmp_path))
    assert isinstance(res, forge.ForgeResult)
    assert res.fallback is False
    assert res.instance_ref == "gen:s1:1"  # instance grain — registry key + store identity
    exp = res.experience
    assert exp.ledger_ref == "gen:s1"  # WORLD grain — what the engine grades/banks
    assert exp.scene is None  # a cloned curated scene would feed the wrong situation (D5)
    assert exp.experience_id == base.experience_id
    assert exp.prompt == _SCENARIO and res.scenario == _SCENARIO
    forged_dump, base_dump = exp.model_dump(), base.model_dump()
    for key in ("prompt", "ledger_ref", "scene"):
        forged_dump.pop(key)
        base_dump.pop(key)
    assert forged_dump == base_dump  # rubric (and everything else) byte-equal to the base


def test_forge_registry_pop_via_select_open_ended(tmp_path):
    res = _forge(_ForgeFake(), _engine_store(tmp_path))
    spec = NextExperienceSpec(
        target_frames=[],
        ledger_ref=res.instance_ref,
        regime=Regime.open_ended,
        experience_id="license_continuity",  # forged specs carry the base id — the gen: branch
    )  # must fire FIRST or the curated bypass would load the curated prompt from disk
    exp = select_open_ended(None, None, [], [], spec)
    assert exp is res.experience and exp.prompt == _SCENARIO
    assert res.instance_ref not in forge.forge_registry  # pop, not read — consumed once


def test_leak_flagged_once_regens_with_steer_then_serves(tmp_path):
    m = _LeakScreenModel([[1], []])
    res = _forge(m, _engine_store(tmp_path))
    assert res.fallback is False and res.experience.prompt == _SCENARIO
    assert len(m.briefs) == 2  # one generation + ONE steered regen
    assert m.briefs[0][1] == ""
    assert m.briefs[1][1] != ""  # steer = the failing gate's reason
    assert m.briefs[1][0] == m.briefs[0][0]  # same brief; the steer rides separately


def test_leak_flagged_twice_falls_back_to_the_curated_base(tmp_path):
    base = load_experience("license_continuity")
    m = _LeakScreenModel([[1], [2]])
    res = _forge(m, _engine_store(tmp_path))
    assert res.fallback is True
    assert res.experience.prompt == base.prompt  # the CURATED base, untouched
    assert res.experience.ledger_ref == base.ledger_ref
    assert res.scenario == base.prompt
    assert len(m.briefs) == 2  # exactly one regen, then the honest fallback — never a loop


def test_fit_reject_steers_with_the_reason_then_serves(tmp_path):
    m = _FitRejectModel([FitCheck(fits=False, reason="the scenario establishes no deadline")])
    res = _forge(m, _engine_store(tmp_path))
    assert res.fallback is False
    assert m.briefs[1][1] == "the scenario establishes no deadline"  # the reason IS the steer


def test_fit_reject_twice_falls_back(tmp_path):
    base = load_experience("license_continuity")
    m = _FitRejectModel(
        [
            FitCheck(fits=False, reason="no deadline"),
            FitCheck(fits=False, reason="still no deadline"),
        ]
    )
    res = _forge(m, _engine_store(tmp_path))
    assert res.fallback is True and res.experience.prompt == base.prompt


def test_hallucinated_screen_index_does_not_gate(tmp_path):
    # Parity with voice._performed: out-of-range indices from the judge are dropped.
    m = _LeakScreenModel([[99]])
    res = _forge(m, _engine_store(tmp_path))
    assert res.fallback is False and len(m.briefs) == 1


def test_degenerate_generation_fails_structural_gate_then_falls_back(tmp_path):
    # The plain FakeModel constant "[forged scenario]" is not a scenario: no second person, no
    # decision ask, too short. Both attempts fail the CODE gate -> honest fallback.
    base = load_experience("license_continuity")
    res = _forge(_fake(), _engine_store(tmp_path))
    assert res.fallback is True and res.experience.prompt == base.prompt


def test_fallback_bridge_is_the_pinned_line():
    assert forge._FALLBACK_BRIDGE == (
        "I'll hold your situation — first, work this one; "
        "it's the same pressure you're standing in."
    )


def test_build_brief_purity_and_level_line():
    territory = load_territory_text("license_continuity")
    brief = forge.build_brief(territory, SITUATION, POSITIONS, "ceo", "base")
    assert SITUATION in brief
    for p in POSITIONS:
        assert p in brief
    assert territory.strip() in brief
    assert "Level: base" in brief.splitlines()  # the 3-value enum line, exact — never prose
    assert "Vera" not in brief  # Vera-free (D3): no persona, no landing text
    exp = load_experience("license_continuity")
    for detail in [f.frame_detail for f in exp.rubric.frames] + [
        t.trap_detail for t in exp.rubric.traps
    ]:
        assert detail not in brief  # frame-blind: never frame/trap details or rubric text
    with pytest.raises(ValueError):
        forge.build_brief(territory, SITUATION, POSITIONS, "ceo", "one notch past")


def test_forge_passes_build_brief_output_verbatim(tmp_path):
    m = _ForgeFake()
    _forge(m, _engine_store(tmp_path), level="firm")
    expected = forge.build_brief(
        load_territory_text("license_continuity"), SITUATION, POSITIONS, "ceo", "firm"
    )
    assert m.briefs[0][0] == expected  # brief inputs are EXACTLY build_brief's — no extras


def test_union_screen_covers_base_moves_and_engaged_frames(tmp_path):
    base = load_experience("license_continuity")
    m = _MovesSpyModel()
    engaged = "choose_the_failure_default_deliberately"  # engaged this sitting; not on the base
    _forge(m, _engine_store(tmp_path), engaged=[engaged])
    assert m.screened_text == _SCENARIO
    base_moves = [f.frame_detail for f in base.rubric.frames] + [
        t.trap_detail for t in base.rubric.traps
    ]
    for move in base_moves:
        assert m.moves.count(move) == 1  # base moves present, never duplicated
    lib_details = {
        f.frame_detail
        for e in load_library()
        if e.rubric
        for f in e.rubric.frames
        if f.frame_code == engaged
    }
    assert lib_details and lib_details <= set(m.moves)  # D1: the cross-segment echo is screened


def test_forge_and_voice_moves_share_one_source_of_truth():
    """Triage fold 2026-07-03: forge._moves was an untested byte-copy of voice._moves — silent
    drift would have screened generated scenarios against a stale L-5 move list (the scenario
    then enters the registry with no other screen against the missing category). Both now
    delegate to types.hidden_move_details; this pins the delegation AND behavioral equality
    (order included — the live echo-gate's move indices map onto it)."""
    from retnovation.types import hidden_move_details

    for e in load_library():
        assert forge._moves(e) == voice._moves(e) == hidden_move_details(e)
    no_rubric = load_experience("license_continuity").model_copy(update={"rubric": None})
    assert forge._moves(no_rubric) == voice._moves(no_rubric) == []
    # the delegation itself, so a re-fork can't reintroduce the drift silently
    assert "hidden_move_details" in inspect.getsource(forge._moves)
    assert "hidden_move_details" in inspect.getsource(voice._moves)


def test_ledger_seeded_once_per_world(tmp_path):
    store = _engine_store(tmp_path)
    _forge(_ForgeFake(), store, n=1)
    _forge(_ForgeFake(), store, n=2)  # two forges, ONE world
    gen_rows = [e for e in store.load_ledger() if e.id == "gen:s1"]
    assert len(gen_rows) == 1  # add_ledger_entry upserts on id — idempotent per world
    assert gen_rows[0].owned_problem == SITUATION  # her real situation IS the owned problem


def test_fallback_does_not_seed_the_ledger(tmp_path):
    store = _engine_store(tmp_path)
    _forge(_LeakScreenModel([[1], [1]]), store)
    assert [e for e in store.load_ledger() if e.id.startswith("gen:")] == []


def test_parse_required_retries_once_on_truncation_then_fails_loud():
    """Founder live dogfood 2026-07-02: one adaptive-thinking excursion past the base budget must
    cost a RETRY at 2x, never the segment; a second truncation still fails LOUD (L-17)."""
    import pytest

    from retnovation.model import AnthropicModel, ModelError

    class _Resp:
        def __init__(self, stop, parsed):
            self.stop_reason = stop
            self.parsed_output = parsed

    class _Msgs:
        def __init__(self, script):
            self.script = script
            self.budgets = []

        def parse(self, **kw):
            self.budgets.append(kw["max_tokens"])
            return self.script.pop(0)

    class _Client:
        def __init__(self, script):
            self.messages = _Msgs(script)

    m = AnthropicModel.__new__(AnthropicModel)  # no key, no network
    m._model = "test-model"
    m._client = _Client([_Resp("max_tokens", None), _Resp("end_turn", {"ok": True})])
    out = m._parse_required(max_tokens=100, system="s", messages=[])
    assert out == {"ok": True}
    assert m._client.messages.budgets == [100, 200]  # exactly one doubled retry

    m2 = AnthropicModel.__new__(AnthropicModel)
    m2._model = "test-model"
    m2._client = _Client([_Resp("max_tokens", None), _Resp("max_tokens", None)])
    with pytest.raises(ModelError, match="truncated"):
        m2._parse_required(max_tokens=100, system="s", messages=[])
    assert m2._client.messages.budgets == [100, 200]  # retry spent; loud, not looping
