from retnovation.model import FakeModel, IntakeClassification, ResponseClassification
from retnovation.types import FrameState, TrapState


def _exp():  # minimal stand-in; FakeModel ignores it
    return None


def test_fake_model_returns_scripted_intake_and_responses():
    intake = IntakeClassification(
        frame_states={"protect_the_core_lane": FrameState.absent},
        trap_states={"erode_core_for_one_customer": TrapState.not_tripped},
    )
    responses = {
        "protect_the_core_lane": [
            ResponseClassification(outcome="closed", mechanism_supplied=True, hard_wrong=False)
        ]
    }
    m = FakeModel(intake=intake, responses=responses)
    assert (
        m.classify_intake(_exp(), "opening").frame_states["protect_the_core_lane"]
        is FrameState.absent
    )
    assert isinstance(m.generate_push(_exp(), "frame", "protect_the_core_lane"), str)
    rc = m.classify_response(_exp(), "frame", "protect_the_core_lane", "push", "reply")
    assert rc.outcome == "closed" and rc.mechanism_supplied is True


def test_fake_model_raises_when_script_exhausted():
    m = FakeModel(IntakeClassification(frame_states={}, trap_states={}), responses={"f": []})
    try:
        m.classify_response(_exp(), "frame", "f", "p", "r")
        raise AssertionError("expected IndexError")
    except IndexError:
        pass
