import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from elenchus.model import FakeModel, IntakeClassification, ResponseClassification  # noqa: E402
from elenchus.types import (  # noqa: E402
    FrameState,
    Outcome,
    Selection,
    TrapState,
)


def _scripted_fake() -> FakeModel:
    """The base scripted FakeModel construction — single-sourced for `make_fake` and
    `make_world_model` (Phase C T4).

    Intake: embed_credentials_as_a_list=present_reasoned, choose_the_failure_default_deliberately=absent.
    Both irreversible_anchor traps not_tripped.
    choose_the_failure_default_deliberately responses: 4x closed+mechanism.
    """
    intake = IntakeClassification(
        frame_states={
            "embed_credentials_as_a_list": FrameState.present_reasoned,
            "choose_the_failure_default_deliberately": FrameState.absent,
        },
        trap_states={
            "deferred_the_one_time_choice": TrapState.not_tripped,
            "assumed_the_happy_path": TrapState.not_tripped,
        },
    )
    closed = [
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        for _ in range(4)
    ]
    return FakeModel(intake, {"choose_the_failure_default_deliberately": closed})


@pytest.fixture
def make_fake():
    """Return a zero-arg factory that produces a scripted FakeModel. See `_scripted_fake`."""

    return _scripted_fake


# The living-sitting scenario text (Phase C T4: moved here from tests/test_web_api.py so
# `make_world_model` and `_world_factory` share one source instead of two copies).
_SCENARIO = (
    "You signed the delivery agreement on Thursday, and this morning your second-largest "
    "customer asked for the same penalty terms before Fridays board review. The account team "
    "wants an answer before the standup, and whatever you give one customer the others will "
    "hear about. What do you do?"
)


def make_world_model() -> FakeModel:
    """Zero-arg factory: the fully configured 'world' FakeModel for the living-sitting/front-door
    flow — `_scripted_fake()` plus the three instance-lambda overrides that used to live only in
    tests/test_web_api.py's `_world_factory` (per-experience classify_intake from
    exp.rubric.frames, an always-closed classify_response, and a structurally-valid
    forge_scenario returning `_SCENARIO`). Single-sourced: tests' `_world_factory` delegates
    here, and so does scripts/smoke_server.py (a zero-token manual smoke harness)."""
    m = _scripted_fake()
    m.classify_intake = lambda exp, opening: IntakeClassification(
        frame_states={f.frame_code: FrameState.absent for f in exp.rubric.frames},
        trap_states={t.trap_code: TrapState.not_tripped for t in exp.rubric.traps},
    )
    m.classify_response = lambda exp, kind, code, push, response, stress=False: (
        ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
    )
    m.forge_scenario = lambda brief, steer="": _SCENARIO
    return m


@pytest.fixture
def steer():
    """Return steer(eid) -> decide_callable that selects the candidate matching experience_id=eid."""

    def steer_fn(eid):
        def decide(proposal):
            for spec, receipt in proposal.candidates:
                if spec.experience_id == eid:
                    top_spec, top_rcpt = proposal.top
                    return Selection(
                        proposed_receipt=top_rcpt,
                        chosen_spec=spec,
                        chosen_receipt=receipt,
                        outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                    )
            raise AssertionError(eid)

        return decide

    return steer_fn
