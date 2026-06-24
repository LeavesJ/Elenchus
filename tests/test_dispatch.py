from retnovation.assessment import get_assessor, ASSESSORS
from retnovation.assessment import judgment_loop
from retnovation.types import Regime


def test_open_ended_dispatches_to_judgment_loop():
    assert get_assessor(Regime.open_ended) is judgment_loop.assess
    assert Regime.open_ended in ASSESSORS


def test_cs_technical_is_registered():
    from retnovation.assessment import checkable_scorer

    assert get_assessor(Regime.cs_technical) is checkable_scorer.assess
    assert Regime.cs_technical in ASSESSORS
