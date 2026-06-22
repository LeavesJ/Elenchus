from retnovation.aim import aim, derive_core
from retnovation.experience import select_experience, FIXED_EXPERIENCE
from retnovation.types import LearnerState, Regime


def test_select_returns_the_fixed_experience():
    core = derive_core(aim())
    exp = select_experience(core, LearnerState(), ledger=[], spec=None)
    assert exp.regime is Regime.open_ended
    assert exp.ledger_ref == "veldra:licensing_continuity"
    assert exp.prompt.strip()
    assert any(f.frame_code == "protect_the_core_lane" for f in exp.rubric.frames)
    assert FIXED_EXPERIENCE == "veldra_licensing_continuity"
