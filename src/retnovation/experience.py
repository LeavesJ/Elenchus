from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import generator
from .types import (
    Core,
    CorpusEntry,
    Experience,
    LearnerState,
    LedgerEntry,
    NextExperienceSpec,
    Regime,
)

# Experience selection is pluggable by regime, mirroring assessment.ASSESSORS, so the CS
# domain-path selector (content-concept coverage) is a clean Step-4 seam and is never
# collapsed into the founder posture-path's process-frame coverage (Complete Picture §10).
SELECTORS: dict[Regime, Callable] = {
    Regime.open_ended: generator.select_open_ended,
    Regime.cs_technical: generator.select_cs_technical,
}


def select_experience(
    core: Core,
    state: LearnerState,
    ledger: list[LedgerEntry],
    corpus: list[CorpusEntry],
    spec: NextExperienceSpec | None = None,
    root: Path | None = None,
) -> Experience:
    regime = spec.regime if spec is not None else Regime.open_ended
    return SELECTORS[regime](core, state, ledger, corpus, spec, root)
