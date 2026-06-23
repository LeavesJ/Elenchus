from retnovation.aim import aim, derive_core, MAX_PROCESS_DIAL


def test_aim_is_founder_ceo_at_max_dial():
    a = aim()
    assert a.posture == "founder_ceo"
    assert a.process_dial == MAX_PROCESS_DIAL
    assert a.content_core is None


def test_derive_core_pulls_frames_from_map():
    core = derive_core(aim())
    assert "protect_the_core_lane" in core.process_frames
    assert "reversible_vs_irreversible" in core.declarative_seed
