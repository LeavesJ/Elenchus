from __future__ import annotations

from datetime import datetime

from .policy import select_next
from .types import Experience, LearnerState, LedgerEntry, NextExperienceSpec, Proposal, Regime


def schedule_cs(
    state: LearnerState, ledger: list[LedgerEntry], now: datetime
) -> NextExperienceSpec:
    ledger_ref = ledger[0].id if ledger else ""
    items = state.declarative_seed
    due = sorted((c for c, si in items.items() if si.due <= now), key=lambda c: (items[c].due, c))
    if due:
        targets = due
    elif items:
        targets = [min(items.items(), key=lambda kv: (kv[1].due, kv[0]))[0]]
    else:
        targets = []
    return NextExperienceSpec(
        target_frames=targets, ledger_ref=ledger_ref, regime=Regime.cs_technical
    )


def propose_open_ended(
    state: LearnerState, experiences: list[Experience], config: dict, now: datetime
) -> Proposal:
    return Proposal(candidates=select_next(state, experiences, config, now))
