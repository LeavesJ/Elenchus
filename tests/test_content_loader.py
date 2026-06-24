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


def test_load_rubric_without_decision_frame_is_none():
    rub = content_loader.load_rubric("license_continuity")
    assert rub.decision_frame is None  # not yet authored on the real rubric until Task 6
