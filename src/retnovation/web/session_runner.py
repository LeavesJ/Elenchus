from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from ..aim import aim, derive_core
from ..assessment.judgment_loop import (
    MAX_PUSHES,
)  # read-only: the arc hint's cap (engine untouched)
from ..cli import build_store
from ..content_loader import load_library, load_progression
from ..orchestration import run_session
from ..scheduler import propose_open_ended
from ..terrain import project_terrain
from ..types import EntryClass, Outcome, Regime, Selection, Work
from . import voice
from .sitting_store import SittingStore

# Liveness bound: after this many consecutive non-substantive door turns, stop re-collecting and
# fall through — treat the latest text as the RAW opening and enter the engine. Without it, a user
# who keeps typing non-substantive input (or a mis-classifying model) pins the session open forever.
_DOOR_MAX_NONSUBSTANTIVE = 3

# Chained sittings: a poison-pill put on an ORPHANED segment's to_worker queue (continue/close over
# a live channel). The worker raises _Abandoned at its next collect, swallows it, and exits through
# finally so its store CLOSES (MF-4 — otherwise the parked worker leaks an open connection forever).
_ABANDON = object()

_STATIC_SITTING_CLOSE = (
    "You stepped away mid-problem — that one stays unbuilt. Here's the village you built."
)

# Durable sittings: the static seam line on a continued segment (signage, not warmth — muted
# register, not a Vera bubble; the sitting-aware AUTHORED seam is founder-gated, spec §1).
_SEAM_TEXT = "Same sitting — next door."


def _serialize_record(rec: dict) -> dict | None:
    """The landed record, reduced to what a future process can rebuild from (spec §2a): the
    experience by id (never the object — the rubric reloads from the L-1 content library),
    dialogue tuples, stop_reason, frozen terrain. None when the exp is missing (degraded)."""
    exp = rec.get("exp")
    if exp is None:
        return None
    return {
        "experience_id": exp.experience_id,
        "posture": rec.get("posture"),
        "recent": [list(t) for t in rec.get("recent", [])],
        "stop_reason": rec.get("stop_reason", "converged"),
        "terrain": rec.get("terrain", []),
    }


class _Abandoned(Exception):
    pass


class _Channel:
    def __init__(self):
        self.to_worker: queue.Queue = queue.Queue()
        self.from_worker: queue.Queue = queue.Queue()
        self.last_menu: list[str] = []
        self.last_menu_refs: list[str] = []  # server-side only (menu_index); never sent to client
        self.terminal: bool = False
        self.thread: threading.Thread | None = None  # the worker (join target for the reap test)
        self.record: dict | None = None  # post-convergence: model+exp+recent+terrain (engine-free)
        self.next_menu: list[
            tuple[str, str]
        ] = []  # (ref, title) ranked next doors; server-side ONLY
        self.inflight_exp: tuple[str, str] | None = None  # (experience_id, ledger_ref) of the
        # segment being presented — worker-set BEFORE the opening emit (happens-before via the
        # queue), registry-persisted as the lost-segment discriminator (spec §2c)


class SessionRegistry:
    def __init__(self, db_path: str, model_factory: Callable[[], object]):
        self._db_path = db_path
        self._model_factory = model_factory
        self._ch: dict[str, _Channel] = {}
        self._lock = threading.Lock()
        # Chained sittings (spec 2026-07-01): the LAST CONVERGED record (close/converse anytime),
        # the refs CONVERGED this sitting (MF-1 repeat guard), and the guarded next pick (a ref;
        # server-side only — L-13).
        self._last_record: dict[str, dict] = {}
        self._sitting_done: dict[str, set[str]] = {}
        self._next_pick: dict[str, str | None] = {}
        # Durable sittings (spec 2026-07-01 late): the write-through store and its bookkeeping.
        # The `continued` idempotency flag stays IN-MEMORY only (rec dict) — it guards "in flight
        # in this process"; persisting it would brick Continue after a restart (spec §2a).
        self._store = SittingStore(db_path)
        self._sitting_id: dict[str, str] = {}  # sid -> live sitting id
        self._next_pick_title: dict[str, str] = {}
        self._seam_pending: dict[str, str] = {}  # consumed by the next opening say
        self._inflight_synced: dict[str, tuple | None] = {}
        self._stepping: set[str] = set()  # sids with a step blocked on from_worker (drain guard)

    def start(self, session_id: str, now: datetime | None = None) -> tuple[str, dict]:
        now = now or datetime.now(timezone.utc)
        self._ensure_sitting(session_id, now)
        ch = _Channel()
        with self._lock:
            self._ch[session_id] = ch

        # Queue-handshake invariant (load-bearing for write-through, spec §2b): the worker emits
        # exactly one from_worker.put per consumed to_worker.get (plus the initial menu put), and
        # `done` is put while the final step() is still blocked on from_worker.get — so EVERY
        # emission is dequeued inside the HTTP request that triggered it, and persistence lives
        # entirely at the dequeue/endpoint layer. A future PROACTIVE emission breaks this.
        def worker():
            store = None
            try:
                store = build_store(self._db_path)
                a = aim()
                core = derive_core(a)
                posture = a.posture  # resolves the presentation profile (voice + visual theme)
                model = self._model_factory()

                def decide(proposal):
                    menu = proposal.problem_menu()
                    titles = voice.display_titles()
                    # Clean human labels; never the ledger_ref (veldra: slug). titles covers every
                    # open-ended experience, so the generic fallback is belt-and-suspenders only.
                    labels = [titles.get(s.ledger_ref, "Untitled problem") for s, _ in menu]
                    refs = [s.ledger_ref for s, _ in menu]  # server-side only; never sent to client
                    # Phase 1 of the visual theme: persona + subject (posture), no role yet (no exp).
                    theme = voice.resolve_presentation(posture, None)["visual"]
                    ch.from_worker.put(("menu", {"problems": labels, "refs": refs, "theme": theme}))
                    idx = ch.to_worker.get()
                    if idx is _ABANDON:
                        raise _Abandoned()
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
                    # Phase 2: the role atmosphere is known now (exp.role) — rides the opening say.
                    # Durable sittings: mark the in-flight segment BEFORE the opening emit (the
                    # queue put orders this write before the registry's read — spec §2c).
                    ch.inflight_exp = (exp.experience_id, exp.ledger_ref)
                    role_theme = voice.resolve_presentation(posture, exp)["visual"]
                    ch.from_worker.put(
                        ("say", {"text": voice.opening(model, exp, posture), "theme": role_theme})
                    )
                    recent: list[tuple[str, str]] = []
                    nonsubstantive = 0
                    while True:
                        text = ch.to_worker.get()
                        if text is _ABANDON:
                            raise _Abandoned()
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
                        reinvite = voice.turn(
                            model, exp, "", recent, posture
                        )  # push="" -> re-invite
                        ch.from_worker.put(("say", {"text": reinvite}))
                        recent.append(("Vera", reinvite))
                    captured["exp"], captured["recent"] = exp, recent

                    pushes = 0

                    def respond(push):
                        # Display the engaged, dialogue-grounded turn; the engine still grades the
                        # CANONICAL push vs the RAW reply (bridge transparency preserved). The arc
                        # hint (pre-incremented: first probe = push 1) rides the DISPLAY path only.
                        nonlocal pushes
                        pushes += 1
                        shown = voice.turn(model, exp, push, recent, posture, (pushes, MAX_PUSHES))
                        ch.from_worker.put(("say", {"text": shown}))
                        recent.append(("Vera", shown))
                        student = ch.to_worker.get()
                        if student is _ABANDON:
                            raise _Abandoned()
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
                landing = ""
                if captured:
                    # Author the felt landing STRICTLY downstream of the frozen assessment — the
                    # session is terminal, so this never re-enters a graded call. voice.land applies
                    # the egress screen HERE before the text reaches the payload (mirrors voice.close).
                    # It rewards arrival/rigor, never correctness (L-4). captured is always set when
                    # done fires (present() sets it before run_session returns).
                    landing = voice.land(
                        model,
                        captured["exp"],
                        captured["recent"],
                        assessment.stop_reason.value,
                        posture,
                    )
                    # Persist the record BEFORE queuing done (and before store.close in finally) so
                    # it is live the instant the client can request converse/close. Holds the rubric
                    # (in exp) server-side for the egress screen; never serialized to the client. The
                    # close is no longer authored here — it moves to the user-owned /close path.
                    # stop_reason keeps the wind-down (converse) convergence-aware.
                    ch.record = {
                        "model": model,
                        "posture": posture,
                        "exp": captured["exp"],
                        "recent": captured["recent"],
                        "stop_reason": assessment.stop_reason.value,
                        "terrain": project_terrain(state, now).learner_view(),
                    }
                # The engine converged — but the SESSION does not end here. 'done' is an internal
                # signal; the user owns closure (converse/close serve the rest from the record). The
                # landing rides the done payload as a felt arrival; the End affordance follows it.
                # The next door (chained sittings): the PURE policy over the post-session state.
                # "Empty menu" is an EXCEPTION path here (select_next raises ValueError on no
                # candidates; Proposal.top raises IndexError) — any failure means "no door offered",
                # never an error emission (MF-2). Runs pre-finally; needs no store. Refs stay
                # server-side (L-13).
                try:
                    exps = [e for e in load_library() if e.regime is Regime.open_ended]
                    menu2 = propose_open_ended(state, exps, load_progression(), now).problem_menu()
                    titles2 = voice.display_titles()
                    ch.next_menu = [
                        (sp.ledger_ref, titles2.get(sp.ledger_ref, "Untitled problem"))
                        for sp, _ in menu2
                    ]
                except Exception:
                    ch.next_menu = []
                ch.from_worker.put(
                    ("done", {"state": state, "assessment": assessment, "landing": landing})
                )
            except _Abandoned:
                pass  # orphaned segment (user continued/closed past it); store closes in finally
            except Exception as e:  # surface, never hang the client
                ch.from_worker.put(("error", {"message": repr(e)}))
            finally:
                if store is not None:
                    store.close()

        t = threading.Thread(target=worker, daemon=True)
        ch.thread = t
        t.start()
        tag, data = ch.from_worker.get()
        if tag == "menu":
            ch.last_menu = data["problems"]
            ch.last_menu_refs = data.get("refs", [])
        self._persist_emit(session_id, ch, tag, data)
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag == "error":
            self._unstick_continue(session_id)
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def _ensure_sitting(self, session_id: str, now: datetime) -> str | None:
        """Adopt the live sitting or open a new one (atomic under the registry lock + the store's
        partial unique live index — a racing double cold-start resolves to one sitting)."""
        with self._lock:
            sit = self._sitting_id.get(session_id)
            if sit is not None:
                return sit
            row = self._store.live_sitting()
            sit = row["id"] if row is not None else self._store.create_sitting(now)
            if self._store.inert:
                return None
            self._sitting_id[session_id] = sit
            return sit

    def _persist_emit(self, session_id: str, ch: _Channel, tag: str, data: dict) -> None:
        """Write-through at the PROJECTION layer (spec §2b): only what the client renders is
        persisted — vera text for says (menus, errors, and raw registry data never land; error
        text can carry frame codes, L-14). The pending seam is consumed by the next say (the
        opening of a continued segment) and rides the response for the shell to render."""
        sit = self._sitting_id.get(session_id)
        if sit is None:
            return
        now = datetime.now(timezone.utc)
        if tag == "say":
            seam = self._seam_pending.pop(session_id, None)
            if seam:
                self._store.append_turn(sit, "seam", {"text": seam}, now)
                data["seam"] = seam
            if (
                ch.inflight_exp is not None
                and self._inflight_synced.get(session_id) != ch.inflight_exp
            ):
                eid, ref = ch.inflight_exp
                self._store.write_state(sit, inflight={"experience_id": eid, "ledger_ref": ref})
                self._inflight_synced[session_id] = ch.inflight_exp
            self._store.append_turn(sit, "vera", {"text": data["text"]}, now)
        if data.get("theme"):
            self._store.write_state(sit, theme=data["theme"])

    def _unstick_continue(self, session_id: str) -> None:
        # F2: a segment that ERRORS never reaches _on_done, so the prior record's idempotency flag
        # would stick forever and dead-end every future continue. A failed segment re-enables it.
        rec = self._last_record.get(session_id)
        if rec is not None:
            rec.pop("continued", None)

    def _on_done(self, session_id: str, ch: _Channel, data: dict) -> None:
        # Sitting bookkeeping (MF-1): bank the converged ref; the offered next door is the
        # highest-ranked proposal NOT already converged this sitting; if all repeat -> no door
        # (the within-sitting clock is frozen — same-day retention/staleness are zero — so the
        # policy alone cannot rotate a just-worked item away; the guard lives HERE, engine untouched).
        now = datetime.now(timezone.utc)
        sit = self._sitting_id.get(session_id)
        if ch.record is not None:
            self._last_record[session_id] = ch.record
            # F1: the dedupe banks CONVERGED refs ONLY — a plateaued/budget/errored problem was not
            # built into a house and may legitimately be re-offered (spec §6).
            if ch.record.get("stop_reason") == "converged":
                self._sitting_done.setdefault(session_id, set()).add(ch.record["exp"].ledger_ref)
                if sit is not None:
                    self._store.log_converged(sit, ch.record["exp"].ledger_ref, now)
            if sit is not None:
                # The landed record + cleared inflight marker, one honest boundary (spec §2b).
                self._store.write_state(sit, record=_serialize_record(ch.record), inflight=None)
                self._inflight_synced[session_id] = None
        done_refs = self._sitting_done.get(session_id, set())
        pick = next(((r, t) for r, t in ch.next_menu if r not in done_refs), None)
        self._next_pick[session_id] = pick[0] if pick else None
        self._next_pick_title[session_id] = pick[1] if pick else ""
        data["next_title"] = pick[1] if pick else ""
        if sit is not None:
            self._store.write_state(sit, next_pick=pick if pick else None)
            if data.get("landing"):
                self._store.append_turn(sit, "landing", {"text": data["landing"]}, now)

    def step(self, session_id: str, value) -> tuple[str, dict]:
        ch = self._ch[session_id]
        if ch.terminal:
            return ("error", {"message": "session already ended"})
        sit = self._sitting_id.get(session_id)
        if sit is not None and isinstance(value, str):
            # The user's words persist even if the segment later errors — she DID say them and the
            # client rendered them (menu indexes are not user text; choose() persists the title).
            self._store.append_turn(sit, "you", {"text": value}, datetime.now(timezone.utc))
        with self._lock:
            self._stepping.add(session_id)
        try:
            ch.to_worker.put(value)
            tag, data = ch.from_worker.get()
        finally:
            with self._lock:
                self._stepping.discard(session_id)
        if tag == "menu":
            ch.last_menu = data["problems"]
            ch.last_menu_refs = data.get("refs", [])
        self._persist_emit(session_id, ch, tag, data)
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag == "error":
            self._unstick_continue(session_id)
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def choose(self, session_id: str, idx: int) -> tuple[str, dict]:
        """A CLIENT-initiated menu choice: persist what the user did (marker + chosen title —
        titles only, never refs), then step. continue_session's internal auto-step bypasses this
        deliberately — the user never saw that menu (spec §2b: no fabricated turns)."""
        sit = self._sitting_id.get(session_id)
        ch = self._ch.get(session_id)
        if sit is not None and ch is not None and 0 <= idx < len(ch.last_menu):
            now = datetime.now(timezone.utc)
            self._store.append_turn(sit, "muted", {"text": "door chosen"}, now)
            self._store.append_turn(sit, "you", {"text": ch.last_menu[idx]}, now)
        return self.step(session_id, idx)

    def _drain(self, session_id: str) -> None:
        """Defensive: consume a queued-but-undequeued emission before close/continue branch on
        stale state. Under the handshake invariant this is a no-op (every emission is dequeued by
        the request that triggered it) — it catches drift, e.g. a future proactive emission. It
        NEVER drains while a step is in flight for this sid: get_nowait would STEAL the emission
        from the blocked request and hang it forever."""
        with self._lock:
            if session_id in self._stepping:
                return
        ch = self._ch.get(session_id)
        if ch is None or ch.terminal:
            return
        try:
            tag, data = ch.from_worker.get_nowait()
        except queue.Empty:
            return
        if tag == "menu":
            ch.last_menu = data["problems"]
            ch.last_menu_refs = data.get("refs", [])
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag == "error":
            self._unstick_continue(session_id)
        if tag in ("done", "error"):
            ch.terminal = True

    def continue_session(self, session_id: str, menu: bool = False) -> tuple[str, dict]:
        """Chained sittings: start the NEXT bounded session in the same thread. One-click path
        auto-picks the door the button NAMED (the guarded next pick); menu=True returns the inline
        picker instead. Idempotent per converged segment (MF-6); reaps a live prior worker (MF-4);
        an absent pick returns the MENU, never a silent door-0 (MF-3)."""
        self._drain(session_id)
        with self._lock:  # M1: atomic check-and-set (FastAPI threadpool can race two POSTs)
            rec = self._last_record.get(session_id)
            if rec is None:
                return ("error", {"message": "nothing to continue from"})
            if rec.get("continued"):
                return ("error", {"message": "continuation already in flight"})
            rec["continued"] = True
        old_ch = self._ch.get(session_id)
        if old_ch is not None and not old_ch.terminal:
            old_ch.to_worker.put(_ABANDON)  # reap the parked mid-segment worker
        pick = self._next_pick.get(session_id)
        # Durable sittings: the seam line rides the NEXT opening say (one-click or via the
        # inline picker); the one-click marker mirrors the button the user pressed (spec §2b).
        self._seam_pending[session_id] = _SEAM_TEXT
        sit = self._sitting_id.get(session_id)
        if sit is not None and not menu and pick is not None:
            title = self._next_pick_title.get(session_id, "")
            self._store.append_turn(
                sit,
                "muted",
                {"text": f"Continue → {title}" if title else "Continue"},
                datetime.now(timezone.utc),
            )
        tag, data = self.start(session_id)
        if tag != "menu" or menu or pick is None:
            return (tag, data)
        try:
            idx = self.menu_index(session_id, pick)
        except ValueError:
            return (tag, data)  # the offered door vanished: show the doors honestly (MF-3)
        return self.step(session_id, idx)

    def menu_index(self, session_id: str, ledger_ref: str) -> int:
        return self._ch[session_id].last_menu_refs.index(ledger_ref)

    def converse(self, session_id: str, value) -> tuple[str, dict]:
        """Post-convergence engaged turn — engine-free, served from the SITTING's last converged
        record (survives chained segments); never touches the terminal-guarded worker queue."""
        rec = self._last_record.get(session_id)
        if rec is None:
            return ("error", {"message": "session has not converged"})
        reply = voice.converse(
            rec["model"],
            rec["exp"],
            rec["recent"],
            value,
            rec["posture"],
            rec.get("stop_reason", "converged"),
        )
        rec["recent"].append(("student", value))
        rec["recent"].append(("Vera", reply))
        sit = self._sitting_id.get(session_id)
        if sit is not None:
            # Persist the pair AND rewrite the record in the same short transaction window —
            # otherwise a second restart makes Vera forget conversation visible on screen (§2b).
            now = datetime.now(timezone.utc)
            self._store.append_turn(sit, "you", {"text": value}, now)
            self._store.append_turn(sit, "vera", {"text": reply}, now)
            self._store.write_state(sit, record=_serialize_record(rec))
        return ("say", {"text": reply})

    def close(self, session_id: str) -> tuple[str, dict]:
        """User-owned close: author the honest close from the SITTING's last converged record and
        return it with that record's terrain (the village, cumulative). Engine-free; no step().
        MF-5: an in-flight segment past the last convergence gets an honest STATIC sign-off — a
        mirrored close would reflect the PREVIOUS problem while the current turns vanish — and the
        parked worker is reaped (MF-4)."""
        self._drain(session_id)
        rec = self._last_record.get(session_id)
        if rec is None:
            return ("error", {"message": "session has not converged"})
        ch = self._ch.get(session_id)
        if ch is not None and not ch.terminal and ch.record is None:
            ch.to_worker.put(_ABANDON)
            result = ("close", {"close": _STATIC_SITTING_CLOSE, "terrain": rec["terrain"]})
        else:
            close_text = voice.close(rec["model"], rec["exp"], rec["recent"], rec["posture"])
            result = ("close", {"close": close_text, "terrain": rec["terrain"]})
        self._end_sitting(session_id)
        return result

    def _end_sitting(self, session_id: str) -> None:
        """The sitting is over: mark it closed (rows retained, L-3) and clear the per-sid state so
        a stale converse/close says so honestly instead of re-serving a finished sitting."""
        sit = self._sitting_id.pop(session_id, None)
        if sit is not None:
            self._store.close_sitting(sit)
        self._last_record.pop(session_id, None)
        self._sitting_done.pop(session_id, None)
        self._next_pick.pop(session_id, None)
        self._next_pick_title.pop(session_id, None)
        self._seam_pending.pop(session_id, None)
        self._inflight_synced.pop(session_id, None)
