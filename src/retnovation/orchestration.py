from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .assessment import get_assessor
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import schedule_next
from .state import STATE_UPDATERS
from .types import Assessment, CheckableAssessment, Core, Experience, LearnerState, Regime, Work


def present_and_collect(exp: Experience) -> Work:
    def respond(push: str) -> str:
        print(push)
        return input("> ")

    if exp.regime is Regime.cs_technical:
        return Work(opening="", respond=respond)
    print(exp.prompt)
    opening = input("> ")
    return Work(opening=opening, respond=respond)


def run_session(
    store: Store,
    core: Core,
    model: Model,
    now: datetime,
    present: Callable[[Experience], Work] = present_and_collect,
) -> tuple[LearnerState, Assessment | CheckableAssessment]:
    state = store.load_state(now)
    ledger = store.load_ledger()
    corpus = store.load_corpus()
    spec = store.queue_pop()
    exp = select_experience(core, state, ledger, corpus, spec)
    work = present(exp)
    assessment = get_assessor(exp.regime)(exp, work, model)
    state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id, exp.ledger_ref)
    store.save_state(state)
    next_spec, receipt = schedule_next(state, ledger, now, exp.regime)
    if receipt is not None:
        store.log_selection(receipt)
    store.queue_push(next_spec)
    return state, assessment
