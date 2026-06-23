from __future__ import annotations

from pathlib import Path

from .content_loader import load_experience_meta, load_rubric
from .types import Core, Experience, LearnerState, LedgerEntry, NextExperienceSpec, Regime

FIXED_EXPERIENCE = "veldra_licensing_continuity"


def select_experience(
    core: Core,
    state: LearnerState,
    ledger: list[LedgerEntry],
    spec: NextExperienceSpec | None = None,
    root: Path | None = None,
) -> Experience:
    rubric = load_rubric(FIXED_EXPERIENCE, root=root)
    meta = load_experience_meta(FIXED_EXPERIENCE, root=root)
    ledger_ref = spec.ledger_ref if spec is not None else meta["ledger_ref"]
    return Experience(
        prompt=meta["prompt"], rubric=rubric, ledger_ref=ledger_ref, regime=Regime(meta["regime"])
    )
