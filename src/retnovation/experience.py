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


def _attach_scene(exp: Experience, corpus: list[CorpusEntry], root: Path | None) -> Experience:
    entry = next((c for c in corpus if c.ledger_ref == exp.ledger_ref), None)
    if entry is None or entry.scene is None or exp.rubric is None:
        return exp  # no scene, or a non-open_ended (no rubric) experience → unchanged
    from .content_loader import load_denylist
    from .generator import validate_scene

    validate_scene(
        entry.scene,
        exp.rubric,
        framework_denylist=load_denylist("framework_denylist", root),
        scaffold_denylist=load_denylist("scaffold_denylist", root),
    )
    return exp.model_copy(update={"prompt": entry.scene.prompt, "scene": entry.scene})


def select_experience(
    core: Core,
    state: LearnerState,
    ledger: list[LedgerEntry],
    corpus: list[CorpusEntry],
    spec: NextExperienceSpec | None = None,
    root: Path | None = None,
) -> Experience:
    regime = spec.regime if spec is not None else Regime.open_ended
    exp = SELECTORS[regime](core, state, ledger, corpus, spec, root)
    return _attach_scene(exp, corpus, root)
