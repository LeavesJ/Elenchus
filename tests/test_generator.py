import pytest

from retnovation.types import (
    CorpusEntry,
    Experience,
    Frame,
    Trap,
    Rubric,
    Mode,
    Regime,
    GateCode,
)


def _corpus(ref="veldra:x", unlabeled="x is unlabeled", why="real stakes", prov="docs/X"):
    return CorpusEntry(
        ledger_ref=ref,
        domain="founder_ceo",
        why_owned=why,
        unlabeled=unlabeled,
        provenance=prov,
        corpus_pointers=[],
    )


def _exp(
    prompt="Decide what you do and account for what you are trading.",
    frames=None,
    traps=None,
    mode=Mode.genuinely_open,
    binding=None,
    ref="veldra:x",
):
    frames = (
        frames
        if frames is not None
        else [
            Frame(
                frame_code="lead_with_what_you_refuse_to_do",
                frame_detail="State the boundary first.",
                paired_trap="scope_creep_to_please",
            ),
            Frame(
                frame_code="protect_the_core_lane",
                frame_detail="Keep the core promise intact.",
                paired_trap="erode_core_for_one_customer",
            ),
        ]
    )
    traps = (
        traps
        if traps is not None
        else [
            Trap(trap_code="scope_creep_to_please", trap_detail="Bending to avoid saying no."),
            Trap(
                trap_code="erode_core_for_one_customer",
                trap_detail="Weakening the core for one account.",
            ),
        ]
    )
    return Experience(
        experience_id="t",
        prompt=prompt,
        rubric=Rubric(frames=frames, traps=traps, mode=mode, binding_constraint=binding),
        ledger_ref=ref,
        regime=Regime.open_ended,
    )


GATE_KW = dict(
    min_angle_count=8,
    framework_denylist=["swot", "five forces"],
    scaffold_denylist=["this is a", "apply the"],
)


def test_angle_count_counts_frames_traps_binding_and_four_dims():
    from retnovation.generator import angle_count

    assert angle_count(_exp().rubric) == 2 + 2 + 0 + 4  # 8
    assert angle_count(_exp(mode=Mode.bounded_error, binding="hard line").rubric) == 9


def test_good_experience_passes():
    from retnovation.generator import anti_label_gate

    res = anti_label_gate(_exp(), _corpus(), **GATE_KW)
    assert res.passed and res.rejects == [] and res.angle_count == 8


def test_recoverable_label_trips_when_corpus_missing_or_unlabeled_empty():
    from retnovation.generator import anti_label_gate

    assert GateCode.recoverable_label in anti_label_gate(_exp(), None, **GATE_KW).rejects
    assert (
        GateCode.recoverable_label
        in anti_label_gate(_exp(), _corpus(unlabeled="   "), **GATE_KW).rejects
    )


def test_pre_named_framework_trips_on_method_name_and_frame_leak():
    from retnovation.generator import anti_label_gate

    assert (
        GateCode.pre_named_framework
        in anti_label_gate(_exp(prompt="Run a SWOT and decide."), _corpus(), **GATE_KW).rejects
    )
    assert (
        GateCode.pre_named_framework
        in anti_label_gate(
            _exp(prompt="Lead with what you refuse to do, then decide."), _corpus(), **GATE_KW
        ).rejects
    )


def test_type_hint_scaffold_trips_on_category_cue():
    from retnovation.generator import anti_label_gate

    assert (
        GateCode.type_hint_scaffold
        in anti_label_gate(
            _exp(prompt="This is a tradeoff problem; decide."), _corpus(), **GATE_KW
        ).rejects
    )


def test_softened_ambiguity_trips_on_mode_dishonesty():
    from retnovation.generator import anti_label_gate

    assert (
        GateCode.softened_ambiguity
        in anti_label_gate(
            _exp(mode=Mode.genuinely_open, binding="a hard line"), _corpus(), **GATE_KW
        ).rejects
    )
    assert (
        GateCode.softened_ambiguity
        in anti_label_gate(
            _exp(mode=Mode.bounded_error, binding=None), _corpus(), **GATE_KW
        ).rejects
    )


def test_cosmetic_engagement_trips_on_wrapper_or_missing_stakes():
    from retnovation.generator import anti_label_gate

    assert (
        GateCode.cosmetic_engagement
        in anti_label_gate(
            _exp(prompt="Keep your streak alive and decide."), _corpus(), **GATE_KW
        ).rejects
    )
    assert (
        GateCode.cosmetic_engagement
        in anti_label_gate(_exp(), _corpus(why="   "), **GATE_KW).rejects
    )


def test_depth_floor_trips_below_min_angle_count():
    from retnovation.generator import anti_label_gate

    thin = _exp(
        frames=[Frame(frame_code="protect_the_core_lane", frame_detail="d", paired_trap=None)],
        traps=[],
    )
    res = anti_label_gate(thin, _corpus(), **GATE_KW)  # 1 + 0 + 0 + 4 = 5 < 8
    assert GateCode.insufficient_interrogation_depth in res.rejects
    assert res.passed is False


def test_quality_floors_downgrade_not_reject():
    from retnovation.generator import anti_label_gate

    res = anti_label_gate(_exp(), _corpus(prov="   "), **GATE_KW)  # empty provenance
    assert GateCode.owned_or_real in res.downgrades
    assert res.passed is True  # floors downgrade, never reject


def _write_gate_files(root):
    (root / "gate").mkdir()
    (root / "gate" / "depth.yaml").write_text("min_angle_count: 8\n")
    (root / "gate" / "framework_denylist.yaml").write_text("- swot\n")
    (root / "gate" / "scaffold_denylist.yaml").write_text("- this is a\n")
    (root / "rubrics").mkdir()


def _write_seed(root, eid, ref, frames):
    lines = [
        f"experience_id: {eid}",
        f'ledger_ref: "{ref}"',
        "regime: open_ended",
        "mode: genuinely_open",
        "binding_constraint: null",
        "prompt: Decide and account for the trade today.",
        "frames:",
    ]
    traps = []
    for code, trap in frames:
        lines.append(f"  - {{frame_code: {code}, frame_detail: angle, paired_trap: {trap}}}")
        traps.append(trap)
    lines.append("traps:")
    for trap in traps:
        lines.append(f"  - {{trap_code: {trap}, trap_detail: shortcut}}")
    (root / "rubrics" / f"{eid}.yaml").write_text("\n".join(lines) + "\n")


def test_load_gated_library_raises_on_a_bad_rubric(tmp_path):
    from retnovation.generator import load_gated_library, GateError

    _write_gate_files(tmp_path)
    # one thin (sub-8-angle) rubric: 1 frame + 1 trap + 4 = 6 < 8
    _write_seed(
        tmp_path, "thin", "veldra:x", [("protect_the_core_lane", "erode_core_for_one_customer")]
    )
    with pytest.raises(GateError):
        load_gated_library([_corpus(ref="veldra:x")], root=tmp_path)


def test_select_open_ended_ranks_by_frame_coverage(tmp_path):
    from retnovation.generator import select_open_ended
    from retnovation.types import LearnerState, NextExperienceSpec

    _write_gate_files(tmp_path)
    _write_seed(
        tmp_path,
        "seed_a",
        "veldra:a",
        [
            ("lead_with_what_you_refuse_to_do", "scope_creep_to_please"),
            ("protect_the_core_lane", "erode_core_for_one_customer"),
        ],
    )
    _write_seed(
        tmp_path,
        "seed_b",
        "veldra:b",
        [
            ("choose_the_failure_default_deliberately", "assumed_the_happy_path"),
            ("lead_with_what_you_refuse_to_do", "scope_creep_to_please"),
        ],
    )
    corpus = [_corpus(ref="veldra:a"), _corpus(ref="veldra:b")]
    spec = NextExperienceSpec(
        target_frames=["protect_the_core_lane"], ledger_ref="", regime=Regime.open_ended
    )
    exp = select_open_ended(
        core=None, state=LearnerState(), ledger=[], corpus=corpus, spec=spec, root=tmp_path
    )
    assert exp.experience_id == "seed_a"  # only A carries protect_the_core_lane


def test_select_cs_technical_ranks_by_concept_coverage():
    from retnovation.generator import select_cs_technical
    from retnovation.types import LearnerState, NextExperienceSpec, Regime

    spec = NextExperienceSpec(
        target_frames=["safety_vs_liveness", "quorum_intersection"],
        ledger_ref="",
        regime=Regime.cs_technical,
    )
    exp = select_cs_technical(core=None, state=LearnerState(), ledger=[], corpus=[], spec=spec)
    # consensus_safety_liveness covers both target concepts; replication_models covers neither
    assert exp.experience_id == "consensus_safety_liveness"
    assert exp.regime is Regime.cs_technical and exp.ledger_ref == "veldra:consensus_correctness"


def test_select_cs_technical_cold_start_falls_back_to_content_core():
    from retnovation.generator import select_cs_technical
    from retnovation.types import Core, LearnerState

    core = Core(
        process_frames=[],
        declarative_seed=["linearizability_vs_eventual"],
        content_core=["linearizability_vs_eventual"],
    )
    exp = select_cs_technical(core=core, state=LearnerState(), ledger=[], corpus=[], spec=None)
    assert exp.experience_id == "replication_models"  # the one covering that concept


def test_every_authored_rubric_passes_the_gate_and_clears_eight_angles():
    """The moat: the gate holds the unlabeled test over everything the generator produces."""
    from retnovation.content_loader import load_library, load_min_angle_count, load_denylist
    from retnovation.generator import anti_label_gate, angle_count

    min_angle = load_min_angle_count()
    fw, sc = load_denylist("framework_denylist"), load_denylist("scaffold_denylist")
    lib = load_library()
    assert len(lib) >= 3, "the founder thin seed must hold the three authored experiences"
    for exp in lib:
        corpus = _corpus(ref=exp.ledger_ref)  # synthetic, hermetic — no confidential db
        res = anti_label_gate(
            exp, corpus, min_angle_count=min_angle, framework_denylist=fw, scaffold_denylist=sc
        )
        assert res.passed, f"{exp.experience_id} tripped {[c.value for c in res.rejects]}"
        assert angle_count(exp.rubric) >= min_angle, exp.experience_id


def test_seed_frame_subsets_differ_so_the_selector_discriminates():
    from retnovation.content_loader import load_library

    subsets = {frozenset(f.frame_code for f in e.rubric.frames) for e in load_library()}
    assert len(subsets) >= 2


@pytest.mark.skipif(
    not __import__("pathlib").Path("data/retnovation.db").exists(),
    reason="real seeded corpus (gitignored data/) not present",
)
def test_seed_ledger_refs_resolve_in_the_real_corpus():
    """Catch the orphan class of bug: every seed must bind to a real seeded founder entry."""
    from retnovation.content_loader import load_library
    from retnovation.persistence import Store

    store = Store("data/retnovation.db")
    try:
        for exp in load_library():
            entry = store.get_corpus(exp.ledger_ref)
            assert entry is not None, f"{exp.experience_id} -> orphan {exp.ledger_ref}"
            assert entry.unlabeled.strip(), f"{exp.ledger_ref} has empty unlabeled rationale"
    finally:
        store.close()
