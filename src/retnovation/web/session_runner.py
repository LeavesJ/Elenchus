from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from ..aim import aim, derive_core
from ..cli import build_store
from ..orchestration import run_session
from ..types import Outcome, Regime, Selection, Work


class _Channel:
    def __init__(self):
        self.to_worker: queue.Queue = queue.Queue()
        self.from_worker: queue.Queue = queue.Queue()
        self.last_menu: list[str] = []
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
                    ch.from_worker.put(("menu", {"problems": [s.ledger_ref for s, _ in menu]}))
                    idx = ch.to_worker.get()
                    spec, receipt = menu[idx]
                    top_spec, top_rcpt = proposal.top
                    return Selection(
                        proposed_receipt=top_rcpt,
                        chosen_spec=spec,
                        chosen_receipt=receipt,
                        outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                    )

                def present(exp):
                    ch.from_worker.put(
                        ("problem", {"prompt": exp.prompt, "ledger_ref": exp.ledger_ref})
                    )
                    opening = ch.to_worker.get()

                    def respond(push):
                        ch.from_worker.put(("push", {"text": push}))
                        return ch.to_worker.get()

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
                ch.from_worker.put(("done", {"state": state, "assessment": assessment}))
            except Exception as e:  # surface, never hang the client
                ch.from_worker.put(("error", {"message": repr(e)}))
            finally:
                if store is not None:
                    store.close()

        threading.Thread(target=worker, daemon=True).start()
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
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
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def menu_index(self, session_id: str, ledger_ref: str) -> int:
        return self._ch[session_id].last_menu.index(ledger_ref)
