from __future__ import annotations

from collections.abc import Callable

from ..types import Regime
from . import checkable_scorer, judgment_loop

ASSESSORS: dict[Regime, Callable] = {
    Regime.open_ended: judgment_loop.assess,
    Regime.cs_technical: checkable_scorer.assess,
}


def get_assessor(regime: Regime) -> Callable:
    return ASSESSORS[regime]
