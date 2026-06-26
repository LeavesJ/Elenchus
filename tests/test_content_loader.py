from retnovation import content_loader
from retnovation.types import Mode


def test_load_founder_ceo_map():
    frames, seed = content_loader.load_map("founder_ceo")
    assert "protect_the_core_lane" in frames
    assert "reversible_vs_irreversible" in seed


def test_load_rubric_parses_frames_traps_mode():
    rub = content_loader.load_rubric("license_continuity")
    assert rub.mode is Mode.genuinely_open
    assert any(f.frame_code == "protect_the_core_lane" for f in rub.frames)
    assert any(t.trap_code == "erode_core_for_one_customer" for t in rub.traps)


def test_load_experience_meta():
    meta = content_loader.load_experience_meta("license_continuity")
    assert meta["ledger_ref"] == "veldra:license_fork_risk"
    assert meta["regime"] == "open_ended"
    assert meta["prompt"].strip()


def test_load_min_angle_count_and_denylists():
    from retnovation.content_loader import load_min_angle_count, load_denylist

    assert load_min_angle_count() == 8
    fw = load_denylist("framework_denylist")
    assert "swot" in fw and all(isinstance(t, str) for t in fw)
    sc = load_denylist("scaffold_denylist")
    assert "this is a" in sc


def test_load_experience_and_library_build_full_experiences():
    from retnovation.content_loader import load_experience, load_library
    from retnovation.types import Experience, Regime

    lib = load_library()
    assert lib, "content/rubrics should hold at least one experience"
    assert all(isinstance(e, Experience) for e in lib)
    one = lib[0]
    again = load_experience(one.experience_id)
    assert again.experience_id == one.experience_id
    assert again.regime in (Regime.open_ended, Regime.cs_technical)
    assert again.rubric.frames or again.rubric.traps


def test_load_path_type_and_content_map():
    from retnovation.content_loader import load_path_type, load_content_map

    assert load_path_type("founder_ceo") == "posture"
    assert load_path_type("cs_systems") == "domain"
    core = load_content_map("cs_systems")
    assert "safety_vs_liveness" in core and "quorum_intersection" in core


def test_load_spacing_returns_policy():
    from retnovation.content_loader import load_spacing

    sp = load_spacing()
    assert sp["initial_interval_days"] == 1
    assert sp["ease_factor"] == 2.0
    assert sp["min_interval_days"] == 1


def test_load_checkable_library_builds_cs_experiences():
    from retnovation.content_loader import load_checkable_experience, load_checkable_library
    from retnovation.types import Experience, Regime, CheckType

    lib = load_checkable_library()
    assert lib, "content/checkables should hold at least one cs experience"
    assert all(isinstance(e, Experience) and e.regime is Regime.cs_technical for e in lib)
    one = load_checkable_experience("consensus_safety_liveness")
    assert one.checkable.questions[0].concept == "safety_vs_liveness"
    assert one.rubric is None and one.ledger_ref == "veldra:consensus_correctness"
    # both check types are represented across the library
    kinds = {q.check_type for e in lib for q in e.checkable.questions}
    assert CheckType.deterministic in kinds and CheckType.model_graded in kinds


def _write_decision_rubric(tmp_path):
    import textwrap

    rdir = tmp_path / "rubrics"
    rdir.mkdir()
    (rdir / "x.yaml").write_text(
        textwrap.dedent(
            """
            experience_id: x
            ledger_ref: "veldra:x"
            regime: open_ended
            mode: genuinely_open
            binding_constraint: null
            prompt: "A same-day call forces a real trade-off."
            decision_frame: f1
            frames:
              - frame_code: f1
                frame_detail: commit and name the reversal
            traps: []
            """
        )
    )
    return tmp_path


def test_load_rubric_threads_decision_frame(tmp_path):
    root = _write_decision_rubric(tmp_path)
    rub = content_loader.load_rubric("x", root=root)
    assert rub.decision_frame == "f1"


def test_load_experience_threads_decision_frame(tmp_path):
    root = _write_decision_rubric(tmp_path)
    exp = content_loader.load_experience("x", root=root)
    assert exp.rubric.decision_frame == "f1"


def test_a_rubric_without_a_decision_frame_loads_with_none(tmp_path):
    import textwrap

    rdir = tmp_path / "rubrics"
    rdir.mkdir()
    (rdir / "y.yaml").write_text(
        textwrap.dedent(
            """
            experience_id: y
            ledger_ref: "veldra:y"
            regime: open_ended
            mode: genuinely_open
            binding_constraint: null
            prompt: "p"
            frames:
              - frame_code: f1
                frame_detail: d
            traps: []
            """
        )
    )
    assert content_loader.load_rubric("y", root=tmp_path).decision_frame is None


def test_license_continuity_declares_the_commitment_decision_frame():
    rub = content_loader.load_rubric("license_continuity")
    assert rub.decision_frame == "commit_under_the_deadline"
    assert any(f.frame_code == "commit_under_the_deadline" for f in rub.frames)
    assert any(t.trap_code == "commit_without_a_tripwire" for t in rub.traps)


def test_load_progression_returns_weights_and_threshold():
    from retnovation.content_loader import load_progression

    p = load_progression()
    assert p["wU"] == 1.0 and p["wR"] == 1.0 and p["wT"] == 1.5 and p["wL"] == 0.5
    assert p["theta_located"] == 0.5


def test_load_progression_has_theta_ledger_refs():
    from retnovation.content_loader import load_progression

    cfg = load_progression()
    assert cfg["theta_ledger_refs"] == 2
    assert isinstance(cfg["theta_ledger_refs"], int)


def test_load_lift_config_and_scenarios():
    from retnovation.content_loader import load_lift_config, load_lift_scenarios
    from retnovation.types import LiftScenario

    cfg = load_lift_config()
    assert cfg["theta_dist"] == 1 and cfg["min_scenarios"] == 3
    assert isinstance(cfg["theta_dist"], int) and isinstance(cfg["min_scenarios"], int)

    scenarios = load_lift_scenarios("scenarios.example")
    assert scenarios and all(isinstance(s, LiftScenario) for s in scenarios)
    assert all(s.scenario_id and s.prompt and s.posture for s in scenarios)


def test_lift_scenario_accepts_optional_candidate():
    from retnovation.types import LiftScenario

    s = LiftScenario(scenario_id="s1", prompt="p", posture="founder_ceo", candidate="frame_x")
    assert s.candidate == "frame_x"
    s2 = LiftScenario(scenario_id="s2", prompt="p", posture="founder_ceo")  # back-compat
    assert s2.candidate is None


def test_load_lift_candidates_parses_example(tmp_path):
    import textwrap
    from retnovation.content_loader import load_lift_candidates

    root = tmp_path / "content"
    (root / "lift").mkdir(parents=True)
    (root / "lift" / "candidates.yaml").write_text(
        textwrap.dedent("""
        candidates:
          - frame_code: build_more_to_own_less
            frame_detail: A larger build can be the net-simpler system.
            injection: Account for net component count, not effort.
            posture: founder_ceo
            hypothesis: the model conflates more-build with more-complexity
            nearest_sibling: protect_the_core_lane
            separating_artifact: a net-component-count ledger
            provenance:
              source_type: owned
              pointer: EXECLOG EX-028
    """)
    )
    cands = load_lift_candidates(root=root)
    assert len(cands) == 1
    assert cands[0].frame_code == "build_more_to_own_less"
    assert cands[0].provenance.pointer == "EXECLOG EX-028"
