from __future__ import annotations

from datetime import datetime

from .content_loader import load_library, load_progression
from .policy import select_next
from .types import LearnerState, LedgerEntry, NextExperienceSpec, Regime, SelectionReceipt


def schedule_next(
    state: LearnerState,
    ledger: list[LedgerEntry],
    now: datetime,
    regime: Regime = Regime.open_ended,
    *,
    root=None,
) -> tuple[NextExperienceSpec, SelectionReceipt | None]:
    if regime is Regime.cs_technical:
        ledger_ref = ledger[0].id if ledger else ""
        items = state.declarative_seed
        due = sorted(
            (c for c, si in items.items() if si.due <= now), key=lambda c: (items[c].due, c)
        )
        if due:
            targets = due
        elif items:
            targets = [min(items.items(), key=lambda kv: (kv[1].due, kv[0]))[0]]
        else:
            targets = []
        return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime), None

    experiences = [e for e in load_library(root) if e.regime is Regime.open_ended]
    return select_next(state, experiences, load_progression(root), now)
