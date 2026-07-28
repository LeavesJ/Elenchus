import os

import pytest

from elenchus.elicitation import DEFAULT_TARGET, run_elicitation_probe
from elenchus.run_elicitation import load_probe_experience
from elenchus.types import FrameState, ProbeResult

_HAS_KEY = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


@pytest.mark.live
@pytest.mark.skipif(not _HAS_KEY, reason="no Anthropic credential")
def test_live_elicitation_smoke():
    """One real Opus run on the isolate: the pipeline returns a valid ProbeResult with the target
    classified. NO assertion on the substantive verdict — that is the human's (SP1/L-15)."""
    from elenchus.model import AnthropicModel

    exp = load_probe_experience("continuity_lock_in")  # DF-free variant (§2d)
    result = run_elicitation_probe([exp], AnthropicModel(), runs_by_id={"continuity_lock_in": 1})
    assert isinstance(result, ProbeResult) and len(result.runs) == 1
    run = result.runs[0]
    if not run.refused:
        assert DEFAULT_TARGET in run.frame_states
        assert all(isinstance(v, FrameState) for v in run.frame_states.values())
