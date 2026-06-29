import sys
from pathlib import Path

import pytest

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from retnovation.model import FakeModel, IntakeClassification, ResponseClassification  # noqa: E402
from retnovation.types import (  # noqa: E402
    FrameState,
    Outcome,
    Selection,
    TrapState,
)


@pytest.fixture
def make_fake():
    """Return a zero-arg factory that produces a scripted FakeModel.

    Intake: embed_credentials_as_a_list=present_reasoned, choose_the_failure_default_deliberately=absent.
    Both irreversible_anchor traps not_tripped.
    choose_the_failure_default_deliberately responses: 4x closed+mechanism.
    """

    def factory() -> FakeModel:
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

    return factory


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
