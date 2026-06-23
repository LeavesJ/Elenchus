from __future__ import annotations

from datetime import datetime
from collections.abc import Callable

from .assessment import get_assessor
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import schedule_next
from .state import update_state
from .types import Assessment, Core, Experience, LearnerState, Work


def present_and_collect(exp: Experience) -> Work:
    print(exp.prompt)
    opening = input("> ")

    def respond(push: str) -> str:
        print(push)
        return input("> ")

    return Work(opening=opening, respond=respond)


def run_session(
    store: Store,
    core: Core,
    model: Model,
    now: datetime,
    present: Callable[[Experience], Work] = present_and_collect,
) -> tuple[LearnerState, Assessment]:
    state = store.load_state()
    ledger = store.load_ledger()
    corpus = store.load_corpus()
    spec = store.queue_pop()
    exp = select_experience(core, state, ledger, corpus, spec)
    work = present(exp)
    assessor = get_assessor(exp.regime)
    assessment = assessor(exp, work, model)
    state = update_state(state, assessment, now, exp.experience_id)
    store.save_state(state)
    store.queue_push(schedule_next(state, ledger, now, exp.regime))
    return state, assessment
