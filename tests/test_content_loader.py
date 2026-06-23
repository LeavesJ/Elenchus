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
