import os

import pytest

from retnovation.aim import aim, derive_core
from retnovation.experience import select_experience
from retnovation.model import AnthropicModel, IntakeClassification
from retnovation.types import FrameState, LearnerState, TrapState

_HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential in env")
def test_live_intake_on_fixed_experience():
    """Smoke: a real Opus 4.8 call classifies every rubric code on the fixed experience."""
    core = derive_core(aim())
    exp = select_experience(core, LearnerState(), ledger=[], spec=None)
    result = AnthropicModel().classify_intake(
        exp, "I would honor the customer's reading because the relationship matters most."
    )
    assert isinstance(result, IntakeClassification)
    assert set(result.frame_states) == {f.frame_code for f in exp.rubric.frames}
    assert set(result.trap_states) == {t.trap_code for t in exp.rubric.traps}
    assert all(isinstance(v, FrameState) for v in result.frame_states.values())
    assert all(isinstance(v, TrapState) for v in result.trap_states.values())
