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


def test_aim_domain_path_is_low_dial():
    from retnovation.aim import aim, MIN_PROCESS_DIAL

    a = aim("cs_systems")
    assert a.posture == "cs_systems"
    assert a.process_dial == MIN_PROCESS_DIAL


def test_derive_core_domain_path_loads_content_core():
    from retnovation.aim import aim, derive_core

    core = derive_core(aim("cs_systems"))
    assert "safety_vs_liveness" in core.content_core
    assert core.declarative_seed == core.content_core
    assert core.process_frames == []
