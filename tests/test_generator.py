import pytest

from elenchus.types import (
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
    from elenchus.generator import angle_count

    assert angle_count(_exp().rubric) == 2 + 2 + 0 + 4  # 8
    assert angle_count(_exp(mode=Mode.bounded_error, binding="hard line").rubric) == 9


def test_good_experience_passes():
    from elenchus.generator import anti_label_gate

    res = anti_label_gate(_exp(), _corpus(), **GATE_KW)
    assert res.passed and res.rejects == [] and res.angle_count == 8


def test_recoverable_label_trips_when_corpus_missing_or_unlabeled_empty():
    from elenchus.generator import anti_label_gate

    assert GateCode.recoverable_label in anti_label_gate(_exp(), None, **GATE_KW).rejects
    assert (
        GateCode.recoverable_label
        in anti_label_gate(_exp(), _corpus(unlabeled="   "), **GATE_KW).rejects
    )


def test_pre_named_framework_trips_on_method_name_and_frame_leak():
    from elenchus.generator import anti_label_gate

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
    from elenchus.generator import anti_label_gate

    assert (
        GateCode.type_hint_scaffold
        in anti_label_gate(
            _exp(prompt="This is a tradeoff problem; decide."), _corpus(), **GATE_KW
        ).rejects
    )


def test_softened_ambiguity_trips_on_mode_dishonesty():
    from elenchus.generator import anti_label_gate

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
    from elenchus.generator import anti_label_gate

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
    from elenchus.generator import anti_label_gate

    thin = _exp(
        frames=[Frame(frame_code="protect_the_core_lane", frame_detail="d", paired_trap=None)],
        traps=[],
    )
    res = anti_label_gate(thin, _corpus(), **GATE_KW)  # 1 + 0 + 0 + 4 = 5 < 8
    assert GateCode.insufficient_interrogation_depth in res.rejects
    assert res.passed is False


def test_quality_floors_downgrade_not_reject():
    from elenchus.generator import anti_label_gate

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
    from elenchus.generator import load_gated_library, GateError

    _write_gate_files(tmp_path)
    # one thin (sub-8-angle) rubric: 1 frame + 1 trap + 4 = 6 < 8
    _write_seed(
        tmp_path, "thin", "veldra:x", [("protect_the_core_lane", "erode_core_for_one_customer")]
    )
    with pytest.raises(GateError):
        load_gated_library([_corpus(ref="veldra:x")], root=tmp_path)


def test_select_open_ended_ranks_by_frame_coverage(tmp_path):
    from elenchus.generator import select_open_ended
    from elenchus.types import LearnerState, NextExperienceSpec

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
    from elenchus.generator import select_cs_technical
    from elenchus.types import LearnerState, NextExperienceSpec, Regime

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
    from elenchus.generator import select_cs_technical
    from elenchus.types import Core, LearnerState

    core = Core(
        process_frames=[],
        declarative_seed=["linearizability_vs_eventual"],
        content_core=["linearizability_vs_eventual"],
    )
    exp = select_cs_technical(core=core, state=LearnerState(), ledger=[], corpus=[], spec=None)
    assert exp.experience_id == "replication_models"  # the one covering that concept


def test_select_cs_technical_raises_on_empty_library(tmp_path):
    (tmp_path / "checkables").mkdir()
    from elenchus.generator import select_cs_technical, GateError
    from elenchus.types import LearnerState

    with pytest.raises(GateError):
        select_cs_technical(
            core=None, state=LearnerState(), ledger=[], corpus=[], spec=None, root=tmp_path
        )


def test_every_authored_rubric_passes_the_gate_and_clears_eight_angles():
    """The moat: the gate holds the unlabeled test over everything the generator produces."""
    from elenchus.content_loader import load_library, load_min_angle_count, load_denylist
    from elenchus.generator import anti_label_gate, angle_count

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
    from elenchus.content_loader import load_library

    subsets = {frozenset(f.frame_code for f in e.rubric.frames) for e in load_library()}
    assert len(subsets) >= 2


def test_frame_trap_phrases_rejects_a_leading_underscore_frame_code():
    """Mutation-discriminating regression pinning the actual hazard the T2 review found: a
    frame_code with a leading underscore mechanically derives a spaced form with a LEADING SPACE
    (`_protect_the_core_lane`.replace('_', ' ') == ' protect_the_core_lane', lowercased). A phrase
    that doesn't begin with an alphanumeric is exactly the shape that makes _contains_phrase's
    lookaround-based boundary stricter than the old \\b it replaced, so the spaced-form check can
    silently go dark on real leaked text while the snake form keeps matching -- invisible because
    half the check still works. frame_trap_phrases must now reject this at derivation instead of
    returning a live phrase list containing it."""
    from elenchus.generator import frame_trap_phrases

    rubric = Rubric(
        frames=[Frame(frame_code="_protect_the_core_lane", frame_detail="d")],
        traps=[],
        mode=Mode.genuinely_open,
    )
    with pytest.raises(ValueError) as exc:
        frame_trap_phrases(rubric)
    assert "_protect_the_core_lane" in str(exc.value)


def test_frame_trap_phrases_rejects_a_trailing_underscore_trap_code():
    """Same hazard, trailing form and the trap_code path (not just frame_code)."""
    from elenchus.generator import frame_trap_phrases

    rubric = Rubric(
        frames=[],
        traps=[Trap(trap_code="erode_core_for_one_customer_", trap_detail="d")],
        mode=Mode.genuinely_open,
    )
    with pytest.raises(ValueError) as exc:
        frame_trap_phrases(rubric)
    assert "erode_core_for_one_customer_" in str(exc.value)


def test_frame_trap_phrases_accepts_every_real_rubric_in_content():
    """Loading every curated rubric under content/rubrics/ and deriving its frame/trap phrases
    must not raise, and the combined phrase count across the real library is the reproducible
    figure any report citing 'how many real phrases validate clean' should point at -- computed
    here, not assumed."""
    from pathlib import Path

    from elenchus.content_loader import load_rubric
    from elenchus.generator import frame_trap_phrases

    names = sorted(p.stem for p in Path("content/rubrics").glob("*.yaml"))
    assert names  # the glob itself found real files, not an empty directory
    total = 0
    for name in names:
        phrases = frame_trap_phrases(load_rubric(name))
        assert phrases  # every curated rubric carries at least one frame or trap
        total += len(phrases)
    assert total > 0
    print(f"content/rubrics/*.yaml real frame/trap phrases, validated clean: {total}")


def test_label_leak_returns_the_matched_phrase_or_none():
    from elenchus.generator import label_leak

    rubric = _exp().rubric  # frames lead_with_what_you_refuse_to_do, protect_the_core_lane
    fw = ["swot", "five forces"]

    # named framework hit
    assert label_leak("Run a SWOT and decide.", rubric, fw) == "swot"
    # leaked frame code, snake form
    assert (
        label_leak("lead_with_what_you_refuse_to_do is the frame", rubric, fw)
        == "lead_with_what_you_refuse_to_do"
    )
    # leaked frame code, spaced form
    assert (
        label_leak("Lead with what you refuse to do, then decide.", rubric, fw)
        == "lead with what you refuse to do"
    )
    # clean text: no match
    assert label_leak("A same-day call forces a real trade-off.", rubric, fw) is None


def test_contains_phrase_boundary_excludes_only_alphanumerics():
    """The fix: rejecting only alphanumerics (not `\\b`, which treats `_` as a word char) still
    matches the snake form (interior underscores untouched), the plain spaced form, and the
    post-`_strip_emphasis` bold form -- and still correctly rejects a word-internal near-miss and
    an occurrence immediately adjacent to a digit, since the lookarounds exclude digits too, not
    just letters."""
    from elenchus.generator import _contains_phrase

    phrase = "protect the core lane"

    # regression: snake form, spaced form, and the (already emphasis-stripped) bold form match
    assert _contains_phrase("protect_the_core_lane", "protect_the_core_lane") is True
    assert _contains_phrase("you must protect the core lane always", phrase) is True
    assert _contains_phrase("protect the core lane", phrase) is True  # ** stripped upstream

    # still correctly rejected: word-internal near-misses
    assert _contains_phrase("protecting the core lanes", phrase) is False
    assert _contains_phrase("xprotect the core lanex", phrase) is False
    # still correctly rejected: adjacent to a digit on either side
    assert _contains_phrase("protect the core lane2", phrase) is False
    assert _contains_phrase("3protect the core lane", phrase) is False


def test_contains_phrase_catches_underscore_italics():
    """Mutation-discriminating: of every case in this file, only these two differ between the
    fixed alphanumeric-exclusion boundary and the old `\\b` boundary it replaces -- `\\b` treats
    `_` as a word character, so a leading/trailing `_` (markdown's other italic marker,
    deliberately left alone by `_strip_emphasis` because snake_case codes need it) destroyed the
    boundary and let the phrase through uncaught. See
    test_label_leak_catches_underscore_italic_frame_code for the same case through the real
    label_leak entry point, not just this private helper."""
    from elenchus.generator import _contains_phrase

    phrase = "protect the core lane"
    assert _contains_phrase("_protect the core lane_", phrase) is True
    assert _contains_phrase("__protect the core lane__", phrase) is True


def test_label_leak_catches_underscore_italic_frame_code():
    """The other markdown italic marker: `_protect the core lane_` must be caught the same as
    `**protect the core lane**` is (see test_validate_scene_sees_through_markdown_emphasis).
    `_strip_emphasis` deliberately leaves `_` alone since snake_case frame codes need their
    interior underscores, so the boundary in `_contains_phrase` must treat a leading or trailing
    `_` as a boundary on its own -- confirmed here through the real label_leak path a model output
    would actually go through, single and double underscore, asserted against the literal matched
    phrase."""
    from elenchus.generator import label_leak

    rubric = _exp().rubric  # frames lead_with_what_you_refuse_to_do, protect_the_core_lane
    fw = ["swot", "five forces"]

    assert (
        label_leak("_protect the core lane_ is the answer.", rubric, fw) == "protect the core lane"
    )
    assert (
        label_leak("__protect the core lane__ is the answer.", rubric, fw)
        == "protect the core lane"
    )


def test_phrase_leak_returns_the_first_match_in_LIST_order_not_text_order():
    """W1. `phrase_leak` is the extracted strip-lower-scan `label_leak` now delegates to, and
    `_push_label_leak` also scans the push category denylist through it. Both phrases below are
    present in the text, and 'use the framework' appears EARLIER in the text than 'classic case
    of' -- so if this returned by text position it would pick 'use the framework' regardless of
    list order. Flipping the list order and getting the flipped answer proves the scan follows
    the list, not the text."""
    from elenchus.generator import phrase_leak

    text = "Go ahead and use the framework here -- this is a classic case of scope creep."
    assert phrase_leak(text, ["classic case of", "use the framework"]) == "classic case of"
    assert phrase_leak(text, ["use the framework", "classic case of"]) == "use the framework"


def test_validate_scene_passes_clean_and_rejects_leaks():
    from elenchus.generator import GateError, validate_scene
    from elenchus.types import Scene

    rubric = _exp().rubric  # frames lead_with_what_you_refuse_to_do, protect_the_core_lane
    kw = dict(
        framework_denylist=["swot", "five forces"], scaffold_denylist=["this is a", "apply the"]
    )

    # clean concrete prompt: no framework, no frame leak, no scaffold, no wrapper
    validate_scene(
        Scene(prompt="A same-day call forces a real trade-off.", situation="w"), rubric, **kw
    )  # no raise

    import pytest

    with pytest.raises(GateError):  # named framework
        validate_scene(Scene(prompt="Run a SWOT and decide.", situation="w"), rubric, **kw)
    with pytest.raises(GateError):  # leaked frame code (spaced)
        validate_scene(
            Scene(prompt="Lead with what you refuse to do.", situation="w"), rubric, **kw
        )
    with pytest.raises(GateError):  # type-hint scaffold
        validate_scene(Scene(prompt="This is a tradeoff problem.", situation="w"), rubric, **kw)
    with pytest.raises(GateError):  # cosmetic wrapper
        validate_scene(Scene(prompt="Keep your streak and decide.", situation="w"), rubric, **kw)

    # a clean prompt but a SITUATION that leaks a frame code / framework must also raise
    with pytest.raises(GateError):
        validate_scene(
            Scene(
                prompt="A same-day call forces a real trade-off.",
                situation="Lead with what you refuse to do, then run a SWOT.",
            ),
            rubric,
            **kw,
        )
    # a fully-clean scene (clean prompt AND clean situation) passes
    validate_scene(
        Scene(
            prompt="A same-day call forces a real trade-off.",
            situation="A long client is mid-rollout; a guarantee is under pressure.",
        ),
        rubric,
        **kw,
    )  # no raise


@pytest.mark.skipif(
    not __import__("pathlib").Path("data/elenchus.db").exists(),
    reason="real seeded corpus (gitignored data/) not present",
)
def test_seed_ledger_refs_resolve_in_the_real_corpus():
    """Catch the orphan class of bug: every seed must bind to a real seeded founder entry."""
    from elenchus.content_loader import load_library
    from elenchus.persistence import Store

    store = Store("data/elenchus.db")
    try:
        for exp in load_library():
            entry = store.get_corpus(exp.ledger_ref)
            assert entry is not None, f"{exp.experience_id} -> orphan {exp.ledger_ref}"
            assert entry.unlabeled.strip(), f"{exp.ledger_ref} has empty unlabeled rationale"
    finally:
        store.close()


@pytest.mark.skipif(
    not __import__("pathlib").Path("data/elenchus.db").exists(),
    reason="real seeded corpus (gitignored data/) not present",
)
def test_both_split_problems_resolve_scene_and_rubric_through_their_own_ref():
    """BOTH sides, named explicitly. Filename ordering must not decide what this covers.

    The earlier version read `veldra:license_fork_risk`'s scene and validated it against
    `license_continuity`'s rubric. Those were one problem when it was written; after the ledger_ref
    split the ref belongs to `continuity_lock_in`, so it paired one problem's scene with another's
    rubric and green meant nothing. The rewrite after that took `next(...)` over the library, which
    sorts by rubric filename, so it silently settled on `continuity_lock_in` and covered one of the
    two. This drives `_attach_scene` itself for each side.

      continuity_lock_in  -> veldra:license_fork_risk            -> receives the continuity scene
      license_continuity  -> veldra:midrollout_contract_boundary -> keeps its authored prompt
    """
    from elenchus.content_loader import load_denylist, load_library
    from elenchus.experience import _attach_scene
    from elenchus.generator import validate_scene
    from elenchus.persistence import Store

    lib = {e.experience_id: e for e in load_library()}
    assert lib["continuity_lock_in"].ledger_ref == "veldra:license_fork_risk"
    assert lib["license_continuity"].ledger_ref == "veldra:midrollout_contract_boundary"

    store = Store("data/elenchus.db")
    try:
        corpus = store.load_corpus()
        by_ref = {c.ledger_ref: c for c in corpus}
        for eid in ("continuity_lock_in", "license_continuity"):
            exp = lib[eid]
            entry = by_ref.get(exp.ledger_ref)
            if entry is None:
                pytest.skip(f"{exp.ledger_ref} absent from this data/")
            served = _attach_scene(exp, corpus, None)
            if entry.scene is None:
                # no scene for this owned problem: the authored prompt must stand, untouched
                assert served.prompt == exp.prompt, f"{eid} was served a scene it does not own"
                continue
            # a scene exists for THIS ref: it is the one served, and it must clear the moat
            # against THIS problem's own rubric — the only pairing _attach_scene can produce
            assert served.prompt == entry.scene.prompt
            validate_scene(
                entry.scene,
                exp.rubric,
                framework_denylist=load_denylist("framework_denylist"),
                scaffold_denylist=load_denylist("scaffold_denylist"),
            )
    finally:
        store.close()


def test_validate_scene_sees_through_markdown_emphasis():
    """Legibility lets scenes carry **bold**; the moat must strip emphasis before checking so a
    frame phrase split by markdown (e.g. `**Lead** with what you refuse to do`) cannot slip past."""
    import pytest

    from elenchus.generator import GateError, validate_scene
    from elenchus.types import Scene

    rubric = _exp().rubric  # frames lead_with_what_you_refuse_to_do, protect_the_core_lane
    kw = dict(
        framework_denylist=["swot", "five forces"], scaffold_denylist=["this is a", "apply the"]
    )

    # bold across a frame phrase would split it for a raw-text check — must still raise
    with pytest.raises(GateError):
        validate_scene(
            Scene(prompt="A clean decision.", situation="**Lead** with what you refuse to do."),
            rubric,
            **kw,
        )
    # legitimate bold on safe terms (and a code span) passes
    validate_scene(
        Scene(
            prompt="Decide the **escrow** terms today.",
            situation="A client mid-rollout; a `guarantee` is under pressure.",
        ),
        rubric,
        **kw,
    )  # no raise


def test_anti_label_gate_sees_through_markdown_emphasis():
    """The same emphasis strip applies to the open_ended prompt gate, so a bold-split frame leak in
    exp.prompt is caught — the two gates stay consistent if abstract prompts also become legible."""
    from elenchus.generator import anti_label_gate

    res = anti_label_gate(
        _exp(prompt="**Lead** with what you refuse to do, then decide."), _corpus(), **GATE_KW
    )
    assert GateCode.pre_named_framework in res.rejects


def test_select_open_ended_honors_experience_id():
    from elenchus.generator import select_open_ended
    from elenchus.types import NextExperienceSpec, Regime

    spec = NextExperienceSpec(
        target_frames=["commit_under_the_deadline"],
        ledger_ref="veldra:license_fork_risk",
        regime=Regime.open_ended,
        experience_id="license_continuity",
    )
    exp = select_open_ended(None, None, [], [], spec)
    assert exp.experience_id == "license_continuity"
