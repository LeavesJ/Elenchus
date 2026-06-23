from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .aim import aim, derive_core
from .model import AnthropicModel
from .orchestration import run_session
from .persistence import Store
from .types import LedgerEntry, NextExperienceSpec, Regime

DEFAULT_DB = Path("data/retnovation.db")
_SEED_PROBLEM = "A customer contract ambiguity forces a same-day call (sanitized seed)."


def build_store(db_path: str | Path = DEFAULT_DB) -> Store:
    store = Store(db_path)
    if not store.load_ledger():
        store.add_ledger_entry(
            LedgerEntry(id="veldra:licensing_continuity", owned_problem=_SEED_PROBLEM)
        )
    if store.queue_len() == 0:
        store.queue_push(
            NextExperienceSpec(
                target_frames=["lead_with_what_you_refuse_to_do", "protect_the_core_lane"],
                ledger_ref="veldra:licensing_continuity",
                regime=Regime.open_ended,
            )
        )
    return store


def main(argv: list[str] | None = None) -> int:
    store = build_store()
    core = derive_core(aim())
    model = AnthropicModel()
    state, assessment = run_session(store, core, model, datetime.now(timezone.utc))
    print(f"stop_reason={assessment.stop_reason.value} frames_moved={len(state.frames)}")
    return 0
