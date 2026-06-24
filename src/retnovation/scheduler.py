from __future__ import annotations

from datetime import datetime

from .types import LearnerState, LedgerEntry, NextExperienceSpec, Regime, Strength


def schedule_next(
    state: LearnerState,
    ledger: list[LedgerEntry],
    now: datetime,
    regime: Regime = Regime.open_ended,
) -> NextExperienceSpec:
    ledger_ref = ledger[0].id if ledger else ""

    if regime is Regime.cs_technical:
        items = state.declarative_seed
        due = sorted((c for c, si in items.items() if si.due <= now), key=lambda c: items[c].due)
        if due:
            targets = due
        elif items:
            targets = [min(items.items(), key=lambda kv: kv[1].due)[0]]
        else:
            targets = []
        return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime)

    weak = [c for c, fs in state.frames.items() if fs.strength is Strength.weak]
    forming = [c for c, fs in state.frames.items() if fs.strength is Strength.forming]
    if weak:
        targets = sorted(weak)
    elif forming:
        targets = sorted(forming)
    else:
        strong = sorted(state.frames.items(), key=lambda kv: kv[1].due)
        targets = [strong[0][0]] if strong else []
    return NextExperienceSpec(target_frames=targets, ledger_ref=ledger_ref, regime=regime)
