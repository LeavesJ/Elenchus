from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from ..aim import aim, derive_core
from ..cli import build_store
from ..orchestration import run_session
from ..types import EntryClass, Outcome, Regime, Selection, Work
from . import voice

# Liveness bound: after this many consecutive non-substantive door turns, stop re-collecting and
# fall through — treat the latest text as the RAW opening and enter the engine. Without it, a user
# who keeps typing non-substantive input (or a mis-classifying model) pins the session open forever.
_DOOR_MAX_NONSUBSTANTIVE = 3


class _Channel:
    def __init__(self):
        self.to_worker: queue.Queue = queue.Queue()
        self.from_worker: queue.Queue = queue.Queue()
        self.last_menu: list[str] = []
        self.last_menu_refs: list[str] = []  # server-side only (menu_index); never sent to client
        self.terminal: bool = False


class SessionRegistry:
    def __init__(self, db_path: str, model_factory: Callable[[], object]):
        self._db_path = db_path
        self._model_factory = model_factory
        self._ch: dict[str, _Channel] = {}
        self._lock = threading.Lock()

    def start(self, session_id: str, now: datetime | None = None) -> tuple[str, dict]:
        now = now or datetime.now(timezone.utc)
        ch = _Channel()
        with self._lock:
            self._ch[session_id] = ch

        def worker():
            store = None
            try:
                store = build_store(self._db_path)
                core = derive_core(aim())
                model = self._model_factory()

                def decide(proposal):
                    menu = proposal.problem_menu()
                    titles = voice.display_titles()
                    # Clean human labels; never the ledger_ref (veldra: slug). titles covers every
                    # open-ended experience, so the generic fallback is belt-and-suspenders only.
                    labels = [titles.get(s.ledger_ref, "Untitled problem") for s, _ in menu]
                    refs = [s.ledger_ref for s, _ in menu]  # server-side only; never sent to client
                    ch.from_worker.put(("menu", {"problems": labels, "refs": refs}))
                    idx = ch.to_worker.get()
                    spec, receipt = menu[idx]
                    top_spec, top_rcpt = proposal.top
                    return Selection(
                        proposed_receipt=top_rcpt,
                        chosen_spec=spec,
                        chosen_receipt=receipt,
                        outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                    )

                captured: dict = {}

                def present(exp):
                    # The Concierge authors every visible turn. Opening = scenario verbatim + the
                    # static invite (turn 0 has no dialogue to ground on); the gate only decides
                    # when a real position has arrived so the engine can start grading.
                    ch.from_worker.put(("say", {"text": voice.opening(model, exp)}))
                    recent: list[tuple[str, str]] = []
                    nonsubstantive = 0
                    while True:
                        text = ch.to_worker.get()
                        ec = voice.gate(model, exp, text, recent)
                        recent.append(("student", text))
                        if ec is EntryClass.substantive:
                            opening = text  # RAW opening to the engine — bridge stays transparent
                            break
                        nonsubstantive += 1
                        if nonsubstantive >= _DOOR_MAX_NONSUBSTANTIVE:
                            # cap reached: stop re-collecting, treat the latest text as the opening
                            opening = text
                            break
                        reinvite = voice.turn(model, exp, "", recent)  # push="" -> re-invite
                        ch.from_worker.put(("say", {"text": reinvite}))
                        recent.append(("Vera", reinvite))
                    captured["exp"], captured["recent"] = exp, recent

                    def respond(push):
                        # Display the engaged, dialogue-grounded turn; the engine still grades the
                        # CANONICAL push vs the RAW reply (bridge transparency preserved).
                        shown = voice.turn(model, exp, push, recent)
                        ch.from_worker.put(("say", {"text": shown}))
                        recent.append(("Vera", shown))
                        student = ch.to_worker.get()
                        recent.append(("student", student))
                        return student  # RAW reply to the engine — canonical push is what it grades

                    return Work(opening=opening, respond=respond)

                state, assessment = run_session(
                    store,
                    core,
                    model,
                    now,
                    regime=Regime.open_ended,
                    present=present,
                    decide=decide,
                    decide_core=lambda c: [],
                )
                close_text = (
                    voice.close(model, captured["exp"], captured["recent"]) if captured else ""
                )
                ch.from_worker.put(
                    ("done", {"state": state, "assessment": assessment, "close": close_text})
                )
            except Exception as e:  # surface, never hang the client
                ch.from_worker.put(("error", {"message": repr(e)}))
            finally:
                if store is not None:
                    store.close()

        threading.Thread(target=worker, daemon=True).start()
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
            ch.last_menu_refs = data.get("refs", [])
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def step(self, session_id: str, value) -> tuple[str, dict]:
        ch = self._ch[session_id]
        if ch.terminal:
            return ("error", {"message": "session already ended"})
        ch.to_worker.put(value)
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
            ch.last_menu_refs = data.get("refs", [])
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def menu_index(self, session_id: str, ledger_ref: str) -> int:
        return self._ch[session_id].last_menu_refs.index(ledger_ref)
