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
