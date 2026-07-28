from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from .assessment import get_assessor
from .content_loader import load_library, load_progression
from .crystallization import crystallization_candidates
from .experience import select_experience
from .model import Model
from .persistence import Store
from .scheduler import propose_open_ended, schedule_cs
from .state import STATE_UPDATERS
from .surface import format_problem_menu
from .types import (
    Assessment,
    CheckableAssessment,
    Core,
    CoreCandidate,
    CoreVerdict,
    Experience,
    LearnerState,
    Outcome,
    Proposal,
    Regime,
    Selection,
    Work,
)


def present_and_collect(exp: Experience) -> Work:
    def respond(push: str) -> str:
        print(push)
        return input("> ")

    if exp.regime is Regime.cs_technical:
        return Work(opening="", respond=respond)
    print(exp.prompt)
    opening = input("> ")
    return Work(opening=opening, respond=respond)


def decide_cli(proposal: Proposal) -> Selection:
    menu = proposal.problem_menu()
    print(format_problem_menu(proposal))
    while True:
        raw = input("> ").strip()
        if raw == "" or raw == "1":
            spec, receipt = proposal.top
            return Selection(
                proposed_receipt=proposal.top[1],
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=Outcome.accepted,
            )
        if raw.isdigit() and 1 <= int(raw) <= len(menu):
            spec, receipt = menu[int(raw) - 1]
            return Selection(
                proposed_receipt=proposal.top[1],
                chosen_spec=spec,
                chosen_receipt=receipt,
                outcome=Outcome.redirected,
            )
        print(f"Enter 1-{len(menu)} or just Enter.")


def decide_core_cli(candidates: list[CoreCandidate]) -> list[CoreVerdict]:
    verdicts: list[CoreVerdict] = []
    for c in candidates:
        print(f"[{c.kind.value}] {c.target}: {c.rationale}")
        ans = input("accept? [y/N] > ").strip().lower()
        verdicts.append(CoreVerdict(candidate=c, outcome="accepted" if ans == "y" else "rejected"))
    return verdicts


def run_session(
    store: Store,
    core: Core,
    model: Model,
    now: datetime,
    *,
    regime: Regime = Regime.open_ended,
    present: Callable[[Experience], Work] = present_and_collect,
    decide: Callable[[Proposal], Selection] = decide_cli,
    decide_core: Callable[[list[CoreCandidate]], list[CoreVerdict]] = decide_core_cli,
) -> tuple[LearnerState, Assessment | CheckableAssessment]:
    state = store.load_state(now)
    ledger = store.load_ledger()
    corpus = store.load_corpus()

    if regime is Regime.cs_technical:
        spec = store.queue_pop()
        if spec is None:  # guard the latent open_ended crossover on an empty cs queue
            raise ValueError("cs_technical run requires a queued spec")
        exp = select_experience(core, state, ledger, corpus, spec)
        work = present(exp)
        assessment = get_assessor(exp.regime)(exp, work, model)
        state = STATE_UPDATERS[exp.regime](
            state, assessment, now, exp.experience_id, exp.ledger_ref
        )
        store.save_state(state)
        store.queue_push(schedule_cs(state, ledger, now))  # cs stays queue-driven (byte-stable)
        return state, assessment

    # open_ended: propose from LIVE state, ignore the queue (§17.2)
    experiences = [e for e in load_library() if e.regime is Regime.open_ended]
    proposal = propose_open_ended(state, experiences, load_progression(), now)
    selection = decide(proposal)
    exp = select_experience(core, state, ledger, corpus, selection.chosen_spec)
    work = present(exp)
    assessment = get_assessor(exp.regime)(exp, work, model)
    state = STATE_UPDATERS[exp.regime](state, assessment, now, exp.experience_id, exp.ledger_ref)
    store.save_state(state)
    store.log_decision(selection)

    candidates = crystallization_candidates(
        state, core, ledger, experiences, now, load_progression()
    )
    if candidates:
        for verdict in decide_core(candidates):
            store.log_core_decision(verdict, now)
    return state, assessment
