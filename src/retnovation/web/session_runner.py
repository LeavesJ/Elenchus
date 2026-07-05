from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from ..aim import aim, derive_core
from ..assessment.judgment_loop import (
    MAX_PUSHES,
)  # read-only: the arc hint's cap (engine untouched)
from ..cli import build_store
from ..content_loader import load_library, load_progression, load_territory_text
from ..forge import _FALLBACK_BRIDGE, LEVELS, forge_experience, forge_registry
from ..orchestration import run_session
from ..scheduler import propose_open_ended
from ..terrain import compose_houses, project_terrain
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

# Branch-accurate honesty copy for a lost in-flight segment (spec §2c states 4/6): the engine is
# not checkpointable (byte-untouched), so a restart loses the segment's grading — never the words.
_HONESTY_RESTART_LANDED = (
    "The server restarted mid-problem; that door closed unfinished. Your conversation is saved — "
    "continue to a next door, or end to see what you've built."
)
_HONESTY_RESTART_FIRST = (
    "The server restarted mid-problem. Your words are saved above — pick a door to keep going."
)
_HONESTY_DOOR_FAILED = "That door failed — it reopens fresh."

# The static reopen variant when a later segment re-enters the interrupted door: mechanical
# honesty (the user can SEE their prior words above; pretending otherwise is the amnesia bug).
_REOPEN_SEAM = "Starting this one over — restate your position, or build on what you wrote above."

# The MF-5 static close over an interrupted tail (never a mirrored close of the previous problem
# beneath the interrupted problem's visible turns). Cause-NEUTRAL (batch-review C7/C16): the tail
# may have died with a restart OR errored in this process — the resume honesty line already told
# the cause-specific story; the close must not invent a restart that never happened.
_STATIC_RESTART_CLOSE = "That last door closed unfinished — here's the village you built."

# Stale-tab soft fail (a request against a channel this process never had).
_STALE_NUDGE = "This room went stale — refresh to pick up where you left off."

# An errored segment's dead channel: every reply must point at the honest way forward (refresh →
# durable-sitting resume: transcript + honesty line + working doors), never a bare dead end.
_DOOR_FAILED_NUDGE = "That door hit an error — refresh to pick up where you left off."

# Worker failures log the traceback SERVER-side (the only durable copy — founder dogfood
# 2026-07-03: the wire's repr(e) rendered as one transient muted line and the refresh the
# recovery path itself recommends destroyed it; the failure's class was unrecoverable). The
# wire carries only the generic nudge: exception text can name frames/refs (the L-14 class).
_log = logging.getLogger(__name__)

# A live sitting idle past this is abandoned: an evening, not an undying thread (spec §2c).
_SITTING_MAX_IDLE = timedelta(hours=18)

# ---- The living sitting (spec 2026-07-02): the front door, the forge path, the close ---------

# The STATIC front-door ask (§2a): the coldest beat pays zero model calls.
_FRONTDOOR_ASK = "What are you facing right now? Describe the decision."

# Honest fit, user-centric (§2a, copy pinned): low mapper confidence never silently stretches.
_HONEST_FIT = (
    "There's more in that than one sitting can press. The sharpest pressure I can put on it: "
    "{desc}. Start there — or look at the other doors first?"
)

# Variant rotation (front-door conversion spec §2d): the same contract three ways — honest
# about the stretch, the territory description inlined, the doors escape. Variant 0 is the
# original so a session's FIRST serve stays byte-identical (existing pins). Rotation is
# per-session in-memory; a restart resets it (cosmetic).
_HONEST_FIT_VARIANTS = (
    _HONEST_FIT,
    "I can't press all of that at once — but this edge of it takes real weight: {desc}. "
    "Stand there — or look at the other doors first?",
    "One piece of that is pressable today: {desc}. Want to start there — or scan the other "
    "doors first?",
)

# The static heard-you bridge when the mapper's reflection fails its egress screen (D9).
_STATIC_BRIDGE = "Understood — stand in it:"

# The conversion beat's static fallback (front-door conversion spec §2a): served only when
# the authored conversion is empty/refused/leaky. It must CONVERT, never deflect — the words
# "out of scope" are forbidden output (founder constraint, 2026-07-04).
_STATIC_CONVERSION = (
    "I don't hand out answers on a topic — I press decisions. Somewhere in what you just "
    "described there's a call you have to make. What is it?"
)

# The informed re-serve (§2c review P3, copy pinned): all territories windowed is a DEFINED
# state — a question, never a refusal, never a false fresh-situation door.
_RESERVE_COPY = (
    "You worked this pressure this morning — pressing it again now will echo more than it "
    "reveals. Work it anyway, or come back tomorrow?"
)
_RESERVE_CHOICES = ["Work it anyway", "Come back tomorrow"]


def _territory_subtitle(experience_id: str) -> str:
    """The Continue button's subtitle (§2c review P4): the target territory's curated
    description, whitespace-collapsed, capped at 80 chars — zero latency, zero new leak class
    (the description already carries §2a's three teeth)."""
    desc = " ".join(load_territory_text(experience_id).split())
    return desc if len(desc) <= 80 else desc[:79].rstrip() + "…"


def _clip80(text: str) -> str:
    """Her raw steer words for the muted label line (user-steered chapters §2c): whitespace-
    collapsed, ~80 chars — echoed so she SEES the pressure was absorbed (F2: her words, never the
    server-side distillation)."""
    t = " ".join(text.split())
    return t if len(t) <= 80 else t[:79].rstrip() + "…"


def _serialize_record(rec: dict) -> dict | None:
    """The landed record, reduced to what a future process can rebuild from (spec §2a): the
    experience by id (never the object — the rubric reloads from the L-1 content library),
    dialogue tuples, stop_reason, frozen terrain. None when the exp is missing (degraded).
    `ledger_ref` is the INSTANCE-grain identity (living sitting §2f/M2): for a forged segment it
    is `gen:{sitting}:{n}` — the key the rebuild uses to reload the GENERATED scenario; for a
    curated segment it equals the curated ref."""
    exp = rec.get("exp")
    if exp is None:
        return None
    return {
        "experience_id": exp.experience_id,
        "ledger_ref": rec.get("ledger_ref") or exp.ledger_ref,
        "posture": rec.get("posture"),
        "recent": [list(t) for t in rec.get("recent", [])],
        "stop_reason": rec.get("stop_reason", "converged"),
        "terrain": rec.get("terrain", []),
        "houses": rec.get("houses", []),
    }


class _Abandoned(Exception):
    pass


class _Channel:
    def __init__(self):
        self.to_worker: queue.Queue = queue.Queue()
        self.from_worker: queue.Queue = queue.Queue()
        self.sit: str | None = None  # the sitting this channel was BORN into (stamped in
        # start(), immutable): every dequeue-layer write for this channel's emissions keys on
        # it — a late emission after a mid-flight close + fresh sitting must land on ITS OWN
        # sitting, never the current one (the deferred cross-write class, fixed 2026-07-04)
        self.last_menu: list[str] = []
        self.last_menu_refs: list[str] = []  # server-side only (menu_index); never sent to client
        self.last_menu_eids: list[str] = []  # server-side only — territory grain (reopen seam)
        self.terminal: bool = False
        self.thread: threading.Thread | None = None  # the worker (join target for the reap test)
        self.record: dict | None = None  # post-convergence: model+exp+recent+terrain (engine-free)
        self.next_menu: list[
            tuple[str, str]
        ] = []  # (ref, title) ranked next doors; server-side ONLY
        self.inflight_exp: tuple[str, str] | None = None  # (experience_id, ledger_ref) of the
        # segment being presented — worker-set BEFORE the opening emit (happens-before via the
        # queue), registry-persisted as the lost-segment discriminator (spec §2c)
        # Living sitting (§2b/§2g) — all three mirror the inflight_exp pattern: worker-set
        # BEFORE the opening emit, consumed by _persist_emit at the dequeue layer (the queue
        # put orders the write before the registry's read).
        self.forged: tuple[str, str, str] | None = None  # (instance_ref, experience_id,
        # scenario) — the instance row the registry persists (the worker never touches the
        # SittingStore's write path for rows the write-through layer owns)
        self.pending_bridge: str | None = None  # the heard-you / fallback bridge line: rides
        # the NEXT opening say as data["bridge"] and persists as its own turn (the seam pattern
        # — a second proactive emission would break the one-put-per-get handshake)
        self.mapped_rank: list[str] | None = None  # the mapper's territory ranking, banked
        # registry-side for Continue targeting (§2c)
        self.frontdoor_pending: str | None = None  # the exact front-door question the worker
        # is parked on (plain ask vs honest-fit — worker-set BEFORE the put, cleared on
        # consume): a state-3 resume must re-serve the question actually pending, or the
        # user's answer to "what are you facing?" is consumed as consent to the OLD mapping
        # (triage fold, 2026-07-03)


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
        # sids with a request blocked on from_worker (drain/reap guard) — a COUNTER, not a set:
        # overlapping requests for one sid must not unmark each other (batch-review C4).
        self._stepping: dict[str, int] = {}
        self._menu_nonce: dict[str, int] = {}  # stale-menu guard: choose echoes, mismatch re-serves
        # A restart-lost segment's identity (server-side only): drives the reopen seam and the
        # interrupted-adjacent converse union screen (spec §2c); cleared at the next landing.
        self._lost_ref: dict[str, str] = {}
        self._lost_exp_id: dict[str, str] = {}
        # The living sitting (spec 2026-07-02): the mapper's territory ranking (in-memory; the
        # fallback order is the policy's next_menu, then the library — §2c), the queued
        # continue-target territory (set by continue_session, popped by the worker's decide),
        # the bounded difficulty index into LEVELS (derived from durable history on a miss,
        # §2e), the per-sitting forge instance counter (seeded past the store's max n so a
        # restart can never overwrite a prior instance row), and the sids whose continue-boot
        # front-door emission is INTERNAL (auto-picked past; never persisted).
        self._territory_rank: dict[str, list[str]] = {}
        self._continue_target: dict[str, str] = {}
        self._level_idx: dict[str, int] = {}
        self._forge_n: dict[str, int] = {}
        self._fit_variant_idx: dict[str, int] = {}  # honest-fit rotation (spec §2d)
        self._frontdoor_swallow: set[str] = set()
        # User-steered chapters (spec 2026-07-05): the pending steer captured in converse (raw
        # words + distilled pressure + pre-mapped territory eid) and, at Continue, the distilled
        # pressure queued for decide()'s forge focus. In-memory ONLY — a steer lost to a restart is
        # re-typed (no L-14 surface); cleared on consume / any non-steer continue / _end_sitting.
        self._steer_pending: dict[str, tuple[str, str, str]] = {}
        self._steer_consume: dict[str, str] = {}

    def start(self, session_id: str, now: datetime | None = None) -> tuple[str, dict]:
        now = now or datetime.now(timezone.utc)
        self._ensure_sitting(session_id, now)
        ch = _Channel()
        ch.sit = self._sitting_id.get(session_id)  # stamped at birth; None on inert stores
        with self._lock:
            # Reap a replaced non-terminal channel (MF-4 class; batch-review C2/C8/C15): the
            # 18h-abandonment path and racing cold-starts otherwise orphan a parked worker
            # holding an open engine store connection forever.
            old = self._ch.get(session_id)
            if old is not None and not old.terminal:
                old.to_worker.put(_ABANDON)
            self._ch[session_id] = ch

        # Queue-handshake invariant (load-bearing for write-through, spec §2b): the worker emits
        # exactly one from_worker.put per consumed to_worker.get (plus the INITIAL put — the
        # front-door say, or the forged opening say when a continue-target skips the front
        # door), and `done` is put while the final step() is still blocked on from_worker.get —
        # so EVERY emission is dequeued inside the HTTP request that triggered it, and
        # persistence lives entirely at the dequeue/endpoint layer. A future PROACTIVE emission
        # breaks this. The front-door loop preserves it: each of its puts answers exactly one
        # consumed get, and the heard-you/fallback bridge RIDES the opening say (a standalone
        # bridge put would be a second put for one get).
        def worker():
            store = None
            try:
                store = build_store(self._db_path)
                a = aim()
                core = derive_core(a)
                posture = a.posture  # resolves the presentation profile (voice + visual theme)
                model = self._model_factory()
                captured: dict = {}
                # The sitting id was stamped on the channel before this thread started; None on
                # an inert (:memory:) store. The SittingStore opens a connection per operation,
                # so the worker thread may READ it (world, positions, history) and write the
                # world row (which must precede the forge — a dequeue-layer write would only
                # land at the next emission, after the very failure it guards against).
                sit = ch.sit

                def decide(proposal):
                    menu = proposal.problem_menu()
                    titles = voice.display_titles()
                    # Clean human labels; never the ledger_ref (veldra: slug). titles covers every
                    # open-ended experience, so the generic fallback is belt-and-suspenders only.
                    labels = [titles.get(s.ledger_ref, "Untitled problem") for s, _ in menu]
                    refs = [s.ledger_ref for s, _ in menu]  # server-side only; never sent to client
                    # Territory keys for the just-worked marker (L4 review F1): a forged
                    # convergence logs a gen: ref that never matches a curated door ref, so the
                    # marker must also key on experience_id. Server-side only — _emit projects
                    # menus as problems+nonce; the no-eids wire tests pin it.
                    eids = [s.experience_id for s, _ in menu]
                    # Phase 1 of the visual theme: persona + subject (posture), no role yet (no exp).
                    theme = voice.resolve_presentation(posture, None)["visual"]
                    top_spec, top_rcpt = proposal.top
                    open_exps = [e for e in load_library() if e.regime is Regime.open_ended]

                    def menu_selection(idx):
                        spec, receipt = menu[idx]
                        return Selection(
                            proposed_receipt=top_rcpt,
                            chosen_spec=spec,
                            chosen_receipt=receipt,
                            outcome=Outcome.accepted if spec is top_spec else Outcome.redirected,
                        )

                    def forge_selection(eid, situation, clicked=False, focus=None):
                        # Forge a generated problem over the curated base (spec §2b). Brief
                        # inputs come from the DURABLE sitting: her final substantive `you`
                        # turns per landed segment, the frames engaged this sitting, the
                        # bounded level — empty by construction at a sitting's first door.
                        base = next(e for e in open_exps if e.experience_id == eid)
                        res = forge_experience(
                            base,
                            sit or session_id,  # inert stores have no sitting id; the ref only
                            self._next_instance_n(session_id, sit),  # needs process uniqueness
                            situation,
                            self._positions(sit),
                            self._engaged_frames(sit),
                            self._level(session_id),
                            model,
                            store,  # the worker's ENGINE store: ledger seeding, M9
                            # A sequel (spec §2b): the prior chapter's scenario when the last
                            # landed record is forged+converged (the ONE _story predicate — None
                            # on the first door and after a plateau/curated segment: a fresh forge).
                            story=self._story(sit),
                            # A user-steered chapter (§2d): her distilled next pressure, posed IN
                            # this world under the mapped rubric. None on a rotation continue.
                            focus=focus,
                        )
                        if res.fallback:
                            # Honest fallback (P1): the curated base serves untouched; the
                            # bridge line rides the opening payload; no instance row persists
                            # (the record rebuilds through the curated path).
                            ch.pending_bridge = _FALLBACK_BRIDGE
                        else:
                            captured["instance_ref"] = res.instance_ref
                            ch.forged = (res.instance_ref, base.experience_id, res.scenario)
                        # Honest selection_log: the chosen spec carries the instance ref (the
                        # gen: seam key) + the base id; the receipt is the base's scored
                        # candidate when the policy ranked it (candidates, not the deduped
                        # menu — two territories can share a curated ledger_ref), else the top.
                        spec_src, receipt = next(
                            ((s, r) for s, r in proposal.candidates if s.experience_id == eid),
                            (top_spec, top_rcpt),
                        )
                        spec = spec_src.model_copy(
                            update={"ledger_ref": res.instance_ref, "experience_id": eid}
                        )
                        return Selection(
                            proposed_receipt=top_rcpt,
                            chosen_spec=spec,
                            chosen_receipt=receipt,
                            outcome=(
                                # Free text: she authored the ask. A CLICK keeps menu
                                # semantics — accepted only when it is the policy top
                                # (spec §2b: selection telemetry stays honest).
                                Outcome.accepted
                                if not clicked or spec_src is top_spec
                                else Outcome.redirected
                            ),
                        )

                    # Same-world Continue (§2c): a queued target territory + a persisted world
                    # skip the front door — straight to the forge; the opening say is the boot's
                    # first emission. A steered continue also popped a queued focus (§2d): her
                    # distilled pressure threads into the forge; None on a rotation continue.
                    with self._lock:
                        target = self._continue_target.pop(session_id, None)
                        focus = self._steer_consume.pop(session_id, None)
                    world = self._store.read_world(sit) if sit is not None else None
                    if target is not None and world is not None:
                        return forge_selection(target, world, focus=focus)

                    # THE FRONT DOOR (§2a/§2g): the static ask + the small doors, one say.
                    ch.frontdoor_pending = _FRONTDOOR_ASK  # set BEFORE the put (queue orders it)
                    ch.from_worker.put(
                        (
                            "say",
                            {
                                "text": _FRONTDOOR_ASK,
                                "frontdoor": True,
                                "menu": {"problems": labels, "refs": refs, "eids": eids},
                                "theme": theme,
                            },
                        )
                    )
                    value = ch.to_worker.get()
                    ch.frontdoor_pending = None  # consumed — the worker is no longer parked here
                    if value is _ABANDON:
                        raise _Abandoned()
                    if isinstance(value, int):
                        return menu_selection(value)  # today's curated path, unchanged
                    situation = value
                    if sit is not None:
                        # BEFORE forging (P1/§2g): the world persists even if the forge falls
                        # back or the process dies mid-map — mid-front-door is a durable state.
                        # A topic-world is accepted (spec §2a): the forge instantiates
                        # territories ON her material; topics forge well (dogfood-proven).
                        self._store.write_world(sit, situation, now)
                    territories = [
                        (e.experience_id, load_territory_text(e.experience_id)) for e in open_exps
                    ]
                    known = {eid for eid, _ in territories}
                    force_fit = False
                    converted = False
                    while True:
                        tmap = model.map_territories(situation, territories)
                        ranked = [eid for eid in tmap.ranked if eid in known]
                        if not ranked:  # a hallucinated ranking cannot pick the door
                            ranked = [eid for eid, _ in territories]
                        eid = ranked[0]
                        ch.mapped_rank = ranked  # banked registry-side at the next dequeue
                        if tmap.verdict != "topic":
                            break
                        if converted:
                            # ONE conversion per pass (spec §2a): a second topic falls through
                            # to the honest-fit beat on THIS map's best stretch — pressing the
                            # conversion twice is an interrogation, and the fit beat carries
                            # the doors escape. The composer never dead-ends.
                            force_fit = True
                            break
                        converted = True
                        # The conversion beat: engage THEIR subject, ask for the decision
                        # inside it — authored by the mapper, screened like the reflection
                        # (§2a gated precedent); the static fallback converts too. Never
                        # "out of scope" (founder constraint, 2026-07-04). Verdict trumps
                        # confidence: a topic is not a decision however cleanly it maps.
                        base0 = next(e for e in open_exps if e.experience_id == eid)
                        text = tmap.conversion.strip()
                        served = (
                            text
                            if text
                            # The founder's forbidden phrase is unservable STRUCTURALLY
                            # (review fold 2026-07-04): the move screen is blind to
                            # deflection language, and instruction compliance alone is
                            # not trusted anywhere else on this path either.
                            and "out of scope" not in text.lower()
                            and voice.egress_safe_reply(model, base0, text)
                            else _STATIC_CONVERSION
                        )
                        ch.frontdoor_pending = served  # before the put (resume re-serves it)
                        ch.from_worker.put(("say", {"text": served}))
                        value = ch.to_worker.get()
                        ch.frontdoor_pending = None  # consumed
                        if value is _ABANDON:
                            raise _Abandoned()
                        if isinstance(value, int):
                            # A click with fed material this pass forges the CLICKED
                            # territory around it (spec §2b); cold clicks at the initial
                            # ask stay curated.
                            return forge_selection(eids[value], situation, clicked=True)
                        situation = value  # a fresh intake, NOT consent — re-map it
                        if sit is not None:
                            self._store.write_world(sit, situation, now)
                    # Conservative read (batch-review fold): anything a live model returns that
                    # is not clearly "high" takes the honest-fit beat — silent stretching costs
                    # signal; the extra beat costs one collect. force_fit (a second topic)
                    # takes it regardless of confidence.
                    if force_fit or tmap.confidence.strip().lower() != "high":
                        # Honest fit (§2a): her situation stays the world; no silent stretching.
                        desc = " ".join(load_territory_text(eid).split()).rstrip(".")
                        with self._lock:
                            n = self._fit_variant_idx.get(session_id, 0)
                            self._fit_variant_idx[session_id] = n + 1
                        fit_copy = _HONEST_FIT_VARIANTS[n % len(_HONEST_FIT_VARIANTS)]
                        ch.frontdoor_pending = fit_copy.format(desc=desc)  # before the put
                        ch.from_worker.put(("say", {"text": ch.frontdoor_pending}))
                        value = ch.to_worker.get()
                        ch.frontdoor_pending = None  # consumed
                        if value is _ABANDON:
                            raise _Abandoned()
                        if isinstance(value, int):
                            return forge_selection(eids[value], situation, clicked=True)
                        # any text proceeds with the MAPPED territory (branch kept simple)
                    base = next(e for e in open_exps if e.experience_id == eid)
                    sel = forge_selection(eid, situation)
                    try:
                        if ch.pending_bridge is None:
                            # The heard-you beat (§2a, gated per D9): the mapper's reflection is
                            # learner-facing text from a frame-aware call — screened before it
                            # rides; the static bridge on refusal/empty/leak.
                            reflection = tmap.reflection.strip()
                            ch.pending_bridge = (
                                reflection
                                if reflection and voice.egress_safe_reply(model, base, reflection)
                                else _STATIC_BRIDGE
                            )
                    except Exception:
                        # A post-forge failure (the heard-you screen is a live model call) must
                        # not leak the registered entry for the process lifetime (triage fold,
                        # 2026-07-03). decide()-local pop, NOT a worker-finally: on the
                        # reseed-collision key a dying worker's finally could pop a FRESH entry
                        # another worker just registered under the same ref.
                        forge_registry.pop(captured.get("instance_ref") or "", None)
                        raise
                    return sel

                def present(exp):
                    # The Concierge authors every visible turn. Opening = scenario verbatim + the
                    # static invite (turn 0 has no dialogue to ground on); the gate only decides
                    # when a real position has arrived so the engine can start grading.
                    # Phase 2: the role atmosphere is known now (exp.role) — rides the opening say.
                    # Durable sittings: mark the in-flight segment BEFORE the opening emit (the
                    # queue put orders this write before the registry's read — spec §2c).
                    ch.inflight_exp = (exp.experience_id, exp.ledger_ref)
                    role_theme = voice.resolve_presentation(posture, exp)["visual"]
                    if exp.ledger_ref.startswith("gen:"):
                        # A forged experience's scenario IS the opening (spec §2b/M6): authored
                        # in opening voice and already gated by the forge — a second
                        # concierge_open pass would re-author screened content. Verbatim; the
                        # bridge/seam ride per _persist_emit.
                        opening_text = exp.prompt
                    else:
                        opening_text = voice.opening(model, exp, posture)
                    ch.from_worker.put(("say", {"text": opening_text, "theme": role_theme}))
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
                        # Instance-grain identity (§2f/M2): the forged instance ref when this
                        # segment was forged (decide set it; fallback/menu segments carry the
                        # curated ref) — what _serialize_record persists for rebuild fidelity.
                        "ledger_ref": captured.get("instance_ref") or captured["exp"].ledger_ref,
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
            except Exception:  # surface, never hang the client
                _log.exception("segment worker died (session %s)", session_id)
                ch.from_worker.put(("error", {"message": _DOOR_FAILED_NUDGE}))
            finally:
                if store is not None:
                    store.close()

        t = threading.Thread(target=worker, daemon=True)
        ch.thread = t
        t.start()
        # The initial dequeue counts as an in-flight step (batch-review C4): _drain's get_nowait
        # must never steal this emission from under us (a stolen menu hangs /continue forever).
        self._step_begin(session_id)
        try:
            tag, data = ch.from_worker.get()
        finally:
            self._step_end(session_id)
        if tag == "menu":
            self._cache_menu(session_id, ch, data)
        elif tag == "say" and isinstance(data.get("menu"), dict):
            # The front door embeds the small doors (§2a): cache + nonce-stamp them exactly
            # like a bare menu so choose()/menu_index answer the same protocol.
            self._cache_menu(session_id, ch, data["menu"])
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

    def _step_begin(self, session_id: str) -> None:
        with self._lock:
            self._stepping[session_id] = self._stepping.get(session_id, 0) + 1

    def _step_end(self, session_id: str) -> None:
        with self._lock:
            n = self._stepping.get(session_id, 0) - 1
            if n <= 0:
                self._stepping.pop(session_id, None)
            else:
                self._stepping[session_id] = n

    def _cache_menu(self, session_id: str, ch: _Channel, data: dict) -> None:
        """Cache the menu server-side and stamp it with a nonce the client must echo on choose —
        a stale tab's click then re-serves the menu instead of opening a door nobody picked.
        Doors converged within the rolling window gain ' · just worked' (spec §2e): a repeat
        becomes a visible, informed choice, never a silent re-serve. Title-layer only — the menu's
        content and ORDER are untouched (reordering would corrupt proposed-vs-chosen selection
        semantics), and refs stay server-side."""
        refs = data.get("refs", [])
        eids = data.get("eids", [])
        if len(eids) != len(refs):
            eids = [""] * len(refs)
        now = datetime.now(timezone.utc)
        ref_window = self._store.converged_within(now) if refs else set()
        # Territory-keyed too (L4 review F1): forged convergences log gen: refs that never match
        # a curated door ref — without this, a forge-converged territory re-serves silently.
        terr_window = self._store.territories_within(now) if refs else set()
        if ref_window or terr_window:
            data["problems"] = [
                p + " · just worked" if (r in ref_window or (e and e in terr_window)) else p
                for p, r, e in zip(data["problems"], refs, eids)
            ]
        ch.last_menu = data["problems"]
        ch.last_menu_refs = refs
        ch.last_menu_eids = eids
        nonce = self._menu_nonce.get(session_id, 0) + 1
        self._menu_nonce[session_id] = nonce
        data["nonce"] = nonce

    def resume_or_start(self, session_id: str, now: datetime | None = None) -> tuple[str, dict]:
        """The front door (spec §2c): a live sitting resumes — same room, whole conversation —
        instead of the unconditional cold start that reproduced the founder's amnesia incident.
        No live sitting (or one idle past the abandonment bound) cold-starts as today."""
        now = now or datetime.now(timezone.utc)
        row = None if self._store.inert else self._store.live_sitting()
        if row is not None:
            try:
                idle = now - datetime.fromisoformat(row["updated_at"])
            except ValueError:
                idle = _SITTING_MAX_IDLE  # unreadable timestamp: treat as abandoned, keep rows
            if idle >= _SITTING_MAX_IDLE:
                self._store.close_sitting(row["id"])
                self._end_sitting(session_id)  # idempotent; clears any same-process maps
                row = None
        if row is None:
            tag, data = self.start(session_id, now=now)
            if tag == "say" and data.get("frontdoor"):
                # The return visit is not amnesiac (§2f review P10): one muted line above the
                # ask. Houses = the all-time converged log; "regions alight" quotes the RENDERED
                # count of the village she last SAW (the frozen learner_view — batch-review fold:
                # counting territories here could contradict the close copy). No terrain yet, or
                # nothing rendered → houses only; a seed-stage world is not "alight".
                rows = self._store.converged_log()
                if rows:
                    n = len(rows)
                    houses = "house" if n == 1 else "houses"
                    line = f"Your world so far: {n} {houses}."
                    terrain = self._store.latest_terrain()
                    if terrain:
                        m = sum(1 for r in terrain if r.get("render") == "rendered")
                        if m:
                            regions = "region" if m == 1 else "regions"
                            line = f"Your world so far: {n} {houses}, {m} {regions} alight."
                    data["returning"] = line
            return (tag, data)
        return self._resume(session_id, row, now)

    def _resume(self, session_id: str, row: dict, now: datetime) -> tuple[str, dict]:
        sit = row["id"]
        with self._lock:
            self._sitting_id[session_id] = sit
        st = self._store.read_state(sit)
        turns = [
            {"kind": t["kind"], "text": t["payload"].get("text", "")}
            for t in self._store.turns(sit)
        ]
        ch = self._ch.get(session_id)
        honesty = ""
        menu_block = None
        frontdoor_block = None

        if ch is not None and not ch.terminal:
            # States 1–3 (same process, live worker): queues intact — nothing restarts.
            rec = self._last_record.get(session_id)
            mode = "converse" if ch.record is not None else "engine"
            if ch.inflight_exp is None and ch.record is None and ch.last_menu:
                # State 3: parked at the front door (the loop that holds the doors) —
                # re-derive from the live channel (same nonce: it is the same pending menu;
                # the reloaded tab must be able to answer it). The question re-serves over her
                # visible turns (§2g's mid-front-door state, same-process face) — the question
                # ACTUALLY pending: at the honest-fit beat the plain ask would invite a fresh
                # situation that the parked worker then consumes as consent to the OLD mapping
                # (triage fold, 2026-07-03). Accepted residual (review-confirmed by executed
                # repro): while the MAPPING call itself is in flight — a full model call,
                # seconds wide, not the instruction-scale inflight_exp class — pending is None
                # and the plain ask re-serves over the same consent hazard; the deferred
                # mid-flight ticket owns that class.
                menu_block = {
                    "problems": list(ch.last_menu),
                    "nonce": self._menu_nonce.get(session_id, 0),
                }
                frontdoor_block = {
                    "text": ch.frontdoor_pending or _FRONTDOOR_ASK,
                    "menu": menu_block,
                }
                mode = "engine"
        else:
            # States 4–8: terminal channel (done/error) or a different process entirely.
            rec = self._rebuild(session_id)
            inflight = st["inflight"]
            lost = inflight is not None
            if lost:
                self._lost_ref[session_id] = inflight.get("ledger_ref", "")
                self._lost_exp_id[session_id] = inflight.get("experience_id", "")
                died_here = ch is not None  # a terminal ERROR channel in this process
                honesty = (
                    _HONESTY_DOOR_FAILED
                    if died_here
                    else (_HONESTY_RESTART_LANDED if rec is not None else _HONESTY_RESTART_FIRST)
                )
            mode = "converse" if rec is not None else "engine"
            if rec is None:
                # Nothing landed: embed a fresh way forward (states 6-no-record / 7, and the
                # NEW state 8 — mid-front-door across a restart: a world row may exist, no
                # inflight, no record; the fresh boot re-serves the static ask over her
                # visible turns, honestly). The composer must never dead-end.
                tag, data = self.start(session_id, now=now)
                if tag == "error":
                    return (tag, data)
                if tag == "say" and data.get("frontdoor"):
                    menu_block = {
                        "problems": data["menu"]["problems"],
                        "nonce": data["menu"].get("nonce", 0),
                    }
                    frontdoor_block = {"text": data["text"], "menu": menu_block}

        rec = self._last_record.get(session_id)
        end_visible = rec is not None
        next_title = ""
        next_desc = ""
        next_kind = "pressure"
        pick = st["next_pick"]
        if pick is not None:
            ref, title = pick
            if ref in self._store.converged_within(now) or (
                # territory grain too (batch-review fold): a forge-convergence of this door's
                # TERRITORY logs a gen: ref that never matches the curated pick ref
                self._ref_territories(ref) & self._store.territories_within(now)
            ):
                pick = None  # a since-converged door: drop honestly (MF-3 path on continue)
                self._store.write_state(sit, next_pick=None)
        if pick is not None and rec is not None:
            self._next_pick[session_id] = pick[0]
            self._next_pick_title[session_id] = pick[1]
            next_title = pick[1]
        if rec is not None and self._store.read_world(sit) is not None:
            # A world sitting's Continue: SHORT title + muted description + kind (§2d); recomputed
            # here (the window may have moved). next_kind from the ONE _story predicate — a resumed
            # Continue keeps the right label across a restart with no schema change (review pt 3).
            target = self._next_territory(session_id, now)
            next_title = self._territory_title(target) if target else ""
            next_desc = _territory_subtitle(target) if target else ""
            next_kind = "chapter" if self._story(sit) is not None else "pressure"
        payload = {
            "turns": turns,
            "next_title": next_title,
            "next_desc": next_desc,
            "next_kind": next_kind,
            "end_visible": end_visible,
            "mode": mode,
            "theme": st["theme"] or {},
            "honesty": honesty,
        }
        if menu_block is not None:
            payload["menu"] = menu_block
        if frontdoor_block is not None:
            # The block re-serves the ask — drop a trailing identical transcript turn so the
            # replay never shows the ask twice (founder live dogfood 2026-07-02: the doubled
            # intro was the first thing on his screen).
            if (
                turns
                and turns[-1]["kind"] == "vera"
                and turns[-1]["text"] == frontdoor_block["text"]
            ):
                turns.pop()
            payload["frontdoor"] = frontdoor_block
        return ("resume", payload)

    def _rebuild(self, session_id: str) -> dict | None:
        """Lazily rebuild the landed record from the durable state (cross-restart): model from the
        factory (stateless), exp from the L-1 content library by id — a miss degrades (exp=None:
        statics only, never an unscreened author, never a 500). Idempotent under the lock; the
        in-memory `continued` flag initializes ABSENT (a continuation cannot survive the process
        that held its worker — persisting it would brick Continue, spec §2a)."""
        with self._lock:
            rec = self._last_record.get(session_id)
            if rec is not None:
                return rec
            sit = self._sitting_id.get(session_id)
            if sit is None:
                return None
            ser = self._store.read_state(sit)["record"]
            if ser is None:
                return None
            try:
                exp = next(
                    (e for e in load_library() if e.experience_id == ser["experience_id"]), None
                )
            except Exception:
                exp = None  # content library unreadable: degrade, don't die
            ser_ref = ser.get("ledger_ref", "") or ""
            if exp is not None and ser_ref.startswith("gen:"):
                # Rebuild fidelity (§2f review M2): a forged segment rebuilds over the
                # GENERATED scenario — post-restart converse/close must never author about the
                # curated prompt beneath her generated conversation. A missing instance row
                # degrades to statics (exp=None), matching every other rebuild failure.
                row = self._store.read_generated_problem(ser_ref)
                exp = (
                    None
                    if row is None
                    else exp.model_copy(
                        update={"prompt": row["scenario"], "ledger_ref": ser_ref, "scene": None}
                    )
                )
            rec = {
                "model": self._model_factory(),
                "posture": ser.get("posture"),
                "exp": exp,
                "ledger_ref": ser_ref or (exp.ledger_ref if exp is not None else ""),
                "recent": [tuple(t) for t in ser.get("recent", [])],
                "stop_reason": ser.get("stop_reason", "converged"),
                "terrain": ser.get("terrain", []),
                # Frozen beside the terrain at the landing (L5); pre-L5 records rebuild with
                # no houses — the shell's zero-house copy owns that state honestly.
                "houses": ser.get("houses", []),
            }
            self._last_record[session_id] = rec
            return rec

    def _persist_emit(self, session_id: str, ch: _Channel, tag: str, data: dict) -> None:
        """Write-through at the PROJECTION layer (spec §2b): only what the client renders is
        persisted — vera text for says (menus, errors, and raw registry data never land; error
        text can carry frame codes, L-14). The pending seam is consumed by the next say (the
        opening of a continued segment) and rides the response for the shell to render; the
        pending bridge (heard-you / fallback) rides the forged opening the same way. The
        worker-set channel attributes consumed here (mapped_rank, forged, pending_bridge,
        inflight_exp) are ordered before this read by the queue put.

        The sitting is the CHANNEL's (stamped at birth), never re-read from the session map: a
        late emission dequeued after a mid-flight close + fresh sitting must write to its own
        sitting (the deferred cross-write class, fixed 2026-07-04). When the channel is STALE
        (the session moved on), the durable writes still land — on ch.sit, their truthful home
        — but session-keyed side effects (rank cache, seam/bridge attachment, swallow flags)
        belong to the NEW flow and are skipped."""
        sit = ch.sit
        if sit is None:
            return
        stale = self._ch.get(session_id) is not ch
        now = datetime.now(timezone.utc)
        if tag == "say" and data.get("frontdoor"):
            # The front door is signage + doors. A continue-boot's ask is INTERNAL (the boot
            # auto-picks past it; the user never sees it): nothing persists and a pending seam
            # survives to the opening say. A RENDERED front door persists the ask and CLEARS
            # any pending seam (§2g: the seam attaches to the forged opening; a Continue that
            # re-enters the front door clears it).
            if not stale and session_id in self._frontdoor_swallow:
                return
            if not stale:
                self._seam_pending.pop(session_id, None)
            # Dedupe the durable ask (founder live dogfood 2026-07-02: reload-at-the-door replays
            # the persisted ask AND re-serves it — the transcript must hold ONE): skip when the
            # tail turn is already this exact ask.
            prior = self._store.turns(sit)
            if not (
                prior
                and prior[-1]["kind"] == "vera"
                and prior[-1]["payload"].get("text") == data["text"]
            ):
                self._store.append_turn(sit, "vera", {"text": data["text"]}, now)
            if data.get("theme"):
                self._store.write_state(sit, theme=data["theme"])
            return
        if tag == "say":
            if ch.mapped_rank is not None:
                rank = list(ch.mapped_rank)
                if not stale:
                    with self._lock:
                        self._territory_rank[session_id] = rank
                ch.mapped_rank = None
                # Restart-durable (triage fold, 2026-07-03): without the row, a mid-world
                # restart's Continue targeting silently fell back to library order. State
                # table, not turns — the inflight_json precedent (L-14 untouched); the write
                # stays at this dequeue layer (queue handshake preserved).
                self._store.write_state(sit, territory_rank=rank)
            seam = None if stale else self._seam_pending.pop(session_id, None)
            if seam:
                self._store.append_turn(sit, "seam", {"text": seam}, now)
                data["seam"] = seam
            if ch.pending_bridge:
                bridge = ch.pending_bridge
                ch.pending_bridge = None
                self._store.append_turn(sit, "bridge", {"text": bridge}, now)
                data["bridge"] = bridge
            if ch.forged is not None:
                # The instance row (§2f): persisted at the dequeue layer, before the opening
                # turn lands — the rebuild key exists the moment the segment is visible.
                ref, eid, scenario = ch.forged
                ch.forged = None
                self._store.add_generated_problem(ref, sit, eid, scenario, now)
            if ch.inflight_exp is not None and (
                stale or self._inflight_synced.get(session_id) != ch.inflight_exp
            ):
                eid, ref = ch.inflight_exp
                self._store.write_state(sit, inflight={"experience_id": eid, "ledger_ref": ref})
                if not stale:
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
        # A pending seam must die with the errored segment (batch-review C5) — otherwise a stale
        # reopen line renders (and durably persists) on a completely unrelated later door.
        self._seam_pending.pop(session_id, None)
        # A continue-target queued for a worker that died before decide() consumed it must not
        # leak into a later boot (it would silently skip that boot's front door).
        with self._lock:
            self._continue_target.pop(session_id, None)

    def _on_done(self, session_id: str, ch: _Channel, data: dict) -> None:
        # Sitting bookkeeping (MF-1): bank the converged ref; the offered next door is the
        # highest-ranked proposal NOT already converged this sitting; if all repeat -> no door
        # (the within-sitting clock is frozen — same-day retention/staleness are zero — so the
        # policy alone cannot rotate a just-worked item away; the guard lives HERE, engine untouched).
        # The sitting is the CHANNEL's (cross-write class fix, 2026-07-04): a done dequeued
        # from a REPLACED channel banks its durable truth (convergence, record, landing) to its
        # OWN sitting and must not touch the session-keyed maps — they belong to the new flow.
        now = datetime.now(timezone.utc)
        sit = ch.sit
        stale = self._ch.get(session_id) is not ch
        world = self._store.read_world(sit) if sit is not None else None
        if ch.record is not None:
            # Bounded difficulty (§2e): one step per converged move, snap back one step on any
            # non-converged stop. Stepped BEFORE this convergence is logged so a derive-on-miss
            # (restart) sees the same pre-landing history the in-memory walk saw.
            if not stale:
                lvl = self._level_idx.get(session_id)
                if lvl is None:
                    lvl = self._derive_level_idx(session_id)
                if ch.record.get("stop_reason") == "converged":
                    lvl = min(lvl + 1, len(LEVELS) - 1)
                else:
                    lvl = max(lvl - 1, 0)
                self._level_idx[session_id] = lvl
                self._last_record[session_id] = ch.record
            # Instance-grain identity (§1): forged segments bank/log their gen:{sitting}:{n}
            # ref + the territory's experience_id (the window/houses key); curated segments
            # carry their curated ref, and logging their experience_id windows the SAME
            # territory a forge over that rubric would (the five doors are the five territories).
            rec_ref = ch.record.get("ledger_ref") or ch.record["exp"].ledger_ref
            # F1: the dedupe banks CONVERGED refs ONLY — a plateaued/budget/errored problem was not
            # built into a house and may legitimately be re-offered (spec §6).
            # A STALE convergence is a superseded flow's (the user closed this segment mid-flight
            # and never saw it land): it must NOT bank — the durable log feeds the STATUS-BLIND
            # cross-sitting reads (converged_within's 24h window, converged_log's village count),
            # so banking it to a closed ch.sit would leak into the NEXT live sitting and suppress
            # a door / inflate the village for work the user walked away from (cross-write review
            # 2026-07-04, finding 1; L-4: reward arrival, and they never arrived). The record
            # still persists to ch.sit below — an inert row on a closed sitting, never re-read.
            if ch.record.get("stop_reason") == "converged" and not stale:
                self._sitting_done.setdefault(session_id, set()).add(rec_ref)
                if sit is not None:
                    self._store.log_converged(sit, rec_ref, now, ch.record["exp"].experience_id)
            # Houses are converged segments (living sitting §2f, L5): compose the cumulative
            # village HERE — beside the frozen terrain, from the SAME post-session state — so
            # the close payload's terrain and houses can never disagree (the log is read AFTER
            # the just-converged row lands; a plateau recomposes over an unchanged log and adds
            # none). Frozen into the record, so a restarted registry serves the same houses in
            # the same order. A drift emission without a state (the defensive _drain path)
            # leaves the record's houses alone — never a degraded recompose over nothing.
            state = data.get("state")
            if state is not None:
                ch.record["houses"] = self._compose_houses(state, now)
            else:
                ch.record.setdefault("houses", [])
            if sit is not None:
                # The landed record + cleared inflight marker, one honest boundary (spec §2b).
                self._store.write_state(sit, record=_serialize_record(ch.record), inflight=None)
                if not stale:
                    self._inflight_synced[session_id] = None
        if stale:
            # The next-door bookkeeping and lost-context clears below belong to the SESSION's
            # current flow; a replaced channel's done only banks its durable truth above. The
            # landing still persists — to the channel's own sitting.
            if sit is not None and data.get("landing"):
                reason = (ch.record or {}).get("stop_reason", "")
                self._store.append_turn(
                    sit, "landing", {"text": data["landing"], "stop_reason": reason}, now
                )
            return
        if world is not None:
            # The living sitting's Continue (§2c/§2d): the next TERRITORY, labeled with its SHORT
            # title + a muted description; `next_kind` (chapter|pressure) from the ONE _story
            # predicate so the label and the sequel forge can never disagree (review pt 3). No ref
            # pick persists — the target is recomputed at continue time against the live window.
            target = self._next_territory(session_id, now)
            data["next_title"] = self._territory_title(target) if target else ""
            data["next_desc"] = _territory_subtitle(target) if target else ""
            data["next_kind"] = "chapter" if self._story(sit) is not None else "pressure"
            self._next_pick[session_id] = None
            self._next_pick_title[session_id] = data["next_title"]
            if sit is not None:
                self._store.write_state(sit, next_pick=None)
        else:
            # The guard window: this sitting's converged refs UNION anything converged within the
            # rolling 24h across sittings/processes (spec §2e; the union keeps :memory: registries —
            # whose durable log is inert — on today's behavior).
            done_refs = self._sitting_done.get(session_id, set()) | self._store.converged_within(
                now
            )
            pick = next(((r, t) for r, t in ch.next_menu if r not in done_refs), None)
            self._next_pick[session_id] = pick[0] if pick else None
            self._next_pick_title[session_id] = pick[1] if pick else ""
            data["next_title"] = pick[1] if pick else ""
            if sit is not None:
                self._store.write_state(sit, next_pick=pick if pick else None)
        # A landing supersedes any restart-lost context: the tip of the sitting is this record.
        self._lost_ref.pop(session_id, None)
        self._lost_exp_id.pop(session_id, None)
        if sit is not None and data.get("landing"):
            # stop_reason rides the landing payload SERVER-side only (the resume projection
            # whitelists kind+text): _positions must tell a committed landing from an honest
            # non-converged one (triage fold, 2026-07-03).
            reason = (ch.record or {}).get("stop_reason", "")
            self._store.append_turn(
                sit, "landing", {"text": data["landing"], "stop_reason": reason}, now
            )

    def step(self, session_id: str, value) -> tuple[str, dict]:
        ch = self._ch.get(session_id)
        if ch is None:
            # A tab from a previous process: fail SOFT (a refresh resumes the sitting) — never a
            # KeyError 500 (spec §2c stale-tab rule).
            return ("nudge", {"message": _STALE_NUDGE})
        if ch.terminal:
            if ch.record is None:
                # The segment ERRORED (founder live dogfood 2026-07-02: a truncated model call
                # killed the worker and every reply dead-ended into 'session already ended').
                # Durable sittings make refresh an honest resume — say THAT.
                return ("nudge", {"message": _DOOR_FAILED_NUDGE})
            return ("error", {"message": "session already ended"})
        sit = self._sitting_id.get(session_id)
        if sit is not None and isinstance(value, str):
            # The user's words persist even if the segment later errors — she DID say them and the
            # client rendered them (menu indexes are not user text; choose() persists the title).
            self._store.append_turn(sit, "you", {"text": value}, datetime.now(timezone.utc))
        self._step_begin(session_id)
        try:
            ch.to_worker.put(value)
            tag, data = ch.from_worker.get()
        finally:
            self._step_end(session_id)
        if tag == "menu":
            self._cache_menu(session_id, ch, data)
        elif tag == "say" and isinstance(data.get("menu"), dict):
            self._cache_menu(session_id, ch, data["menu"])  # embedded doors (front door)
        self._persist_emit(session_id, ch, tag, data)
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag == "error":
            self._unstick_continue(session_id)
        if tag in ("done", "error"):
            ch.terminal = True
        return tag, data

    def choose(self, session_id: str, idx: int, nonce: int | None = None) -> tuple[str, dict]:
        """A CLIENT-initiated menu choice: persist what the user did (marker + chosen title —
        titles only, never refs), then step. continue_session's internal auto-step bypasses this
        deliberately — the user never saw that menu (spec §2b: no fabricated turns). Guards
        (batch-review C10/C11): honored only while a menu is actually PENDING (worker parked in
        decide) — otherwise a stale click could inject a menu-index int into the graded gate/
        respond loop or fabricate turns for a door that never opened; a stale nonce re-serves the
        pending menu; an accepted choose ROTATES the nonce so a second tab's identical click
        cannot replay it."""
        ch = self._ch.get(session_id)
        if ch is None:
            return ("nudge", {"message": _STALE_NUDGE})
        pending = (
            not ch.terminal and ch.record is None and ch.inflight_exp is None and bool(ch.last_menu)
        )
        if not pending:
            return ("nudge", {"message": _STALE_NUDGE})
        if nonce is not None and nonce != self._menu_nonce.get(session_id):
            return (
                "menu",
                {
                    "problems": list(ch.last_menu),
                    "nonce": self._menu_nonce.get(session_id, 0),
                },
            )
        if not (0 <= idx < len(ch.last_menu)):
            # A crafted index must never reach the worker (review fold 2026-07-04, probe: -1
            # silently forged the LAST door via negative indexing; 99 IndexError'd the
            # segment). Re-serve the pending menu; the nonce is not burned by a bad click.
            return (
                "menu",
                {
                    "problems": list(ch.last_menu),
                    "nonce": self._menu_nonce.get(session_id, 0),
                },
            )
        with self._lock:  # accepted: consume the menu — a replayed identical click must not pass
            self._menu_nonce[session_id] = self._menu_nonce.get(session_id, 0) + 1
        sit = self._sitting_id.get(session_id)
        if sit is not None and 0 <= idx < len(ch.last_menu):
            now = datetime.now(timezone.utc)
            self._store.append_turn(sit, "muted", {"text": "door chosen"}, now)
            self._store.append_turn(sit, "you", {"text": ch.last_menu[idx]}, now)
        lost_ref = self._lost_ref.get(session_id)
        lost_eid = self._lost_exp_id.get(session_id)
        reopened = (0 <= idx < len(ch.last_menu_refs) and ch.last_menu_refs[idx] == lost_ref) or (
            # eid-grain too (batch-review fold, M8's door-click half): a forged lost segment's
            # ref is gen:-grain and never matches a curated door ref
            bool(lost_eid)
            and 0 <= idx < len(ch.last_menu_eids)
            and ch.last_menu_eids[idx] == lost_eid
        )
        if reopened:
            # Re-entering the interrupted door: the seam says so honestly (spec §2c).
            self._seam_pending[session_id] = _REOPEN_SEAM
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
            self._cache_menu(session_id, ch, data)
        if tag == "done":
            self._on_done(session_id, ch, data)
        if tag == "error":
            self._unstick_continue(session_id)
        if tag in ("done", "error"):
            ch.terminal = True

    def continue_session(
        self, session_id: str, menu: bool = False, work_anyway: bool = False
    ) -> tuple[str, dict]:
        """Chained sittings: start the NEXT bounded session in the same thread. On a WORLD
        sitting (living sitting §2c) the one-click path forges the next territory over the same
        world (no picker, no front door); all-windowed serves the informed re-serve — a
        question, never a false door — and work_anyway=True honors its first choice on the
        least-recent territory. On a curated sitting the one-click path auto-picks the door the
        button NAMED (the guarded next pick); menu=True re-enters the front door (doors +
        composer). Idempotent per converged segment (MF-6); reaps a live prior worker (MF-4);
        an absent pick returns the front door, never a silent door-0 (MF-3)."""
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
        now = datetime.now(timezone.utc)
        sit = self._sitting_id.get(session_id)
        world = self._store.read_world(sit) if sit is not None else None

        if world is not None and not menu:
            # The living sitting's forge path (§2c). A servable pending steer (captured at converse,
            # §2b) consumes DETERMINISTICALLY here — no model call: re-check the window cheaply, then
            # forge the pre-mapped territory with her distilled pressure as focus. Else rotation.
            with self._lock:
                steer = self._steer_pending.pop(session_id, None)
                self._steer_consume.pop(session_id, None)  # stale guard
            target = None
            if steer is not None and steer[2] not in self._store.territories_within(now):
                target = steer[2]  # the pre-mapped eid — label == delivery
                with self._lock:
                    self._steer_consume[session_id] = steer[1]  # distilled pressure -> forge focus
                _log.info("chapter: steered -> %s", target)
            if target is None:
                target = self._next_territory(session_id, now)
                if target is None and work_anyway:
                    target = self._least_recent_territory(session_id, now)
                if target is None:
                    # Informed re-serve (P3): a QUESTION, not a segment — the continuation is not
                    # consumed, so both of its answers (work_anyway / tomorrow) stay available.
                    with self._lock:
                        rec.pop("continued", None)
                    return ("reserve", {"copy": _RESERVE_COPY, "choices": list(_RESERVE_CHOICES)})
                _log.info("chapter: rotation -> %s", target)
            # Reopen honesty keys on the TERRITORY (review M8): a forged lost segment's gen:
            # ref never equals a menu ref, but its experience_id names the same pressure.
            self._seam_pending[session_id] = (
                _REOPEN_SEAM if target == self._lost_exp_id.get(session_id) else _SEAM_TEXT
            )
            with self._lock:
                self._continue_target[session_id] = target
            if sit is not None:
                self._store.append_turn(
                    sit, "muted", {"text": f"Continue → {_territory_subtitle(target)}"}, now
                )
            self._step_begin(session_id)
            try:
                return self.start(session_id)
            finally:
                self._step_end(session_id)
                with self._lock:  # decide pops both; belt-and-suspenders against an early error
                    self._continue_target.pop(session_id, None)
                    self._steer_consume.pop(session_id, None)

        # Any continue path that is NOT the world-forge steered consume (other doors, curated pick,
        # menu re-entry) supersedes a pending steer (§2d picker interaction) — cleared, re-typable.
        with self._lock:
            self._steer_pending.pop(session_id, None)
            self._steer_consume.pop(session_id, None)

        pick = self._next_pick.get(session_id)
        if pick is not None and (
            pick in self._store.converged_within(now)
            or self._ref_territories(pick) & self._store.territories_within(now)
        ):
            # The persisted pick was converged since it was offered (another sitting, this window;
            # territory grain covers forge-convergences whose gen: refs never match) — drop to the
            # doors: MF-3's honest path, never a silent converged re-serve (spec §2e).
            pick = None
            self._next_pick[session_id] = None
            self._next_pick_title[session_id] = ""
        # Durable sittings: the seam line rides the NEXT opening say (one-click or via the
        # front-door picker; a RENDERED front door clears it per §2g); the one-click marker
        # mirrors the button the user pressed (spec §2b).
        self._seam_pending[session_id] = (
            _REOPEN_SEAM
            if pick is not None and pick == self._lost_ref.get(session_id)
            else _SEAM_TEXT
        )
        if not menu and pick is not None:
            if sit is not None:
                title = self._next_pick_title.get(session_id, "")
                self._store.append_turn(
                    sit, "muted", {"text": f"Continue → {title}" if title else "Continue"}, now
                )
            # The boot's front-door emission is INTERNAL on the auto-pick path: the user never
            # sees the ask, so it must not persist (a swallowed ask in the transcript would be
            # a fabricated turn) and the seam must survive to the opening say.
            self._frontdoor_swallow.add(session_id)
        elif sit is not None:
            # A RENDERED-front-door continue (the picker, or a dropped pick): its ask persists,
            # so mark the boundary — otherwise _sitting_segments sweeps the ask into the
            # previous segment's wind-down tail (triage fold, 2026-07-03).
            self._store.append_turn(sit, "muted", {"text": "Continue"}, now)
        # The whole boot window counts as in-flight (batch-review C4): a concurrent close must not
        # pill the NEW channel in the gap between start()'s dequeue and the auto-pick step — the
        # pill would be consumed as the decide input and the step would block forever.
        self._step_begin(session_id)
        try:
            tag, data = self.start(session_id)
            if tag != "say" or not data.get("frontdoor") or menu or pick is None:
                return (tag, data)
            try:
                idx = self.menu_index(session_id, pick)
            except ValueError:
                # The offered door vanished: show the doors honestly (MF-3). This front door
                # WAS swallowed at the dequeue (edge: its ask is unpersisted); the pending
                # seam must not leak onto an unrelated later say.
                self._seam_pending.pop(session_id, None)
                return (tag, data)
            return self.step(session_id, idx)
        finally:
            self._step_end(session_id)
            self._frontdoor_swallow.discard(session_id)

    def menu_index(self, session_id: str, ledger_ref: str) -> int:
        return self._ch[session_id].last_menu_refs.index(ledger_ref)

    def _ref_territories(self, ref: str) -> set[str]:
        """The territory ids a curated ledger_ref belongs to (window checks need BOTH grains —
        a forge-convergence logs gen: refs that never match a curated door ref)."""
        try:
            return {e.experience_id for e in load_library() if e.ledger_ref == ref}
        except Exception:
            return set()

    def _lost_context(self, session_id: str) -> tuple[str, str] | None:
        """(ledger_ref, experience_id) of a segment that died before landing — from the in-memory
        resume bookkeeping OR the persisted inflight discriminator (batch-review C3: same-process
        errored tails never pass through _resume, so the memory maps alone are blind to them). A
        LIVE segment is not lost — close()'s reap branch owns that state."""
        ref, eid = self._lost_ref.get(session_id), self._lost_exp_id.get(session_id)
        if ref or eid:
            return (ref or "", eid or "")
        ch = self._ch.get(session_id)
        if ch is not None and not ch.terminal:
            return None
        sit = self._sitting_id.get(session_id)
        if sit is None:
            return None
        inflight = self._store.read_state(sit)["inflight"]
        if inflight is None:
            return None
        return (inflight.get("ledger_ref", ""), inflight.get("experience_id", ""))

    def converse(self, session_id: str, value) -> tuple[str, dict]:
        """Post-convergence engaged turn — engine-free, served from the SITTING's last converged
        record (survives chained segments AND restarts via the lazy rebuild); never touches the
        terminal-guarded worker queue."""
        rec = self._last_record.get(session_id) or self._rebuild(session_id)
        if rec is None:
            if self._ch.get(session_id) is None:
                return ("nudge", {"message": _STALE_NUDGE})  # a previous process's tab
            return ("error", {"message": "session has not converged"})
        sit = self._sitting_id.get(session_id)
        if rec.get("exp") is None:
            # Degraded rebuild (content drift): the honest static — never an unscreened author,
            # and never the SAFE_CONTRACT lie ("I'll push") on a dead engine (spec §2c).
            return ("say", {"text": voice._CONVERSE_DONE_FRESH})
        reply, next_pressure = voice.converse(
            rec["model"],
            rec["exp"],
            rec["recent"],
            value,
            rec["posture"],
            rec.get("stop_reason", "converged"),
            has_sequel=self._story(sit) is not None,
        )
        lost = self._lost_context(session_id)
        if lost is not None and lost[1]:
            # Interrupted-adjacent converse (spec §2c): the honesty line invites talk about the
            # LOST problem, whose moves the record's own egress screen is blind to — screen the
            # union. The lost exp was NOT converged, so it may re-offer within the window; an
            # unscreened reply could hand its move and prime the future intake. FAIL CLOSED
            # (batch-review C9): an unresolvable lost exp cannot be screened, so the safe static
            # serves — matching the rebuild-failure doctrine everywhere else in this build.
            try:
                lost_exp = next((e for e in load_library() if e.experience_id == lost[1]), None)
            except Exception:
                lost_exp = None
            if lost_exp is None or not voice.egress_safe_reply(rec["model"], lost_exp, reply):
                # Fail closed to the HONEST static, never SAFE_CONTRACT's "I'll push" lie on a
                # dead engine (spec §2c consistency fold, 2026-07-05): equally safe (a static,
                # performs no move), just not a lie. Fresh variant — an interrupted/lost state
                # is not the place to promise a next chapter.
                reply = voice._CONVERSE_DONE_FRESH
        now = datetime.now(timezone.utc)
        # Don't capture a steer on an interrupted/degraded turn (adversarial-review fold F3): the
        # reply may have fail-closed to the honest static, and steering does not belong in a
        # lost-context state — she re-types after resume. The rec["exp"] is None path already
        # returned above; this covers the lost-context fail-close.
        interrupted = lost is not None and bool(lost[1])
        if (
            next_pressure
            and not interrupted
            and sit is not None
            and self._store.read_world(sit) is not None
        ):
            # The mapper gate at CAPTURE (user-steered chapters §2b): a servable fresh pressure
            # becomes the pending steer (raw words + distilled pressure + pre-mapped territory).
            self._capture_steer(session_id, sit, value, next_pressure, now, rec["model"])
        rec["recent"].append(("student", value))
        rec["recent"].append(("Vera", reply))
        if sit is not None:
            # Persist the pair AND rewrite the record in the same short transaction window —
            # otherwise a second restart makes Vera forget conversation visible on screen (§2b).
            self._store.append_turn(sit, "you", {"text": value}, now)
            self._store.append_turn(sit, "vera", {"text": reply}, now)
            self._store.write_state(sit, record=_serialize_record(rec))
        data = {"text": reply}
        self._attach_converse_label(session_id, sit, now, data)
        return ("say", data)

    def close(self, session_id: str) -> tuple[str, dict]:
        """User-owned close: author the honest close from the SITTING's last converged record and
        return it with that record's terrain (the village, cumulative). Engine-free; no step().
        MF-5: an in-flight segment past the last convergence gets an honest STATIC sign-off — a
        mirrored close would reflect the PREVIOUS problem while the current turns vanish — and the
        parked worker is reaped (MF-4)."""
        self._drain(session_id)
        rec = self._last_record.get(session_id) or self._rebuild(session_id)
        if rec is None:
            if self._ch.get(session_id) is None:
                return ("nudge", {"message": _STALE_NUDGE})  # a previous process's tab
            return ("error", {"message": "session has not converged"})
        ch = self._ch.get(session_id)
        # The village payload (living sitting §2f, L5): the frozen terrain + its houses — both
        # composed at the SAME landing (_on_done), so they can never disagree at the close.
        village = {"terrain": rec["terrain"], "houses": rec.get("houses", [])}
        if ch is not None and not ch.terminal and ch.record is None:
            # An in-flight segment past the last convergence: the static sign-off (MF-5). The
            # worker reap itself happens in _end_sitting (guarded against in-flight requests).
            result = ("close", {"close": _STATIC_SITTING_CLOSE, **village})
        elif self._lost_context(session_id) is not None:
            # MF-5 across restart AND same-process errored tails (batch-review C3): the
            # interrupted tail is persisted state, not channel state — a mirrored close would
            # reflect the previous problem beneath the interrupted problem's visible turns.
            result = ("close", {"close": _STATIC_RESTART_CLOSE, **village})
        elif rec.get("exp") is None:
            # Degraded rebuild: static close + the persisted village — never an unscreened author.
            result = ("close", {"close": _STATIC_SITTING_CLOSE, **village})
        else:
            sit = self._sitting_id.get(session_id)
            world = self._store.read_world(sit) if sit is not None else None
            if world is not None:
                # The sitting-level close (§2f): the world's story over every landed segment,
                # ONE union egress screen over the sitting's territories' moves (M13).
                close_text = voice.sitting_close(
                    rec["model"],
                    world,
                    self._sitting_segments(sit),
                    self._sitting_exps(sit, rec),
                    rec["posture"],
                )
            else:
                close_text = voice.close(rec["model"], rec["exp"], rec["recent"], rec["posture"])
            result = ("close", {"close": close_text, **village})
        self._end_sitting(session_id)
        return result

    # ---- Living-sitting helpers (spec §2c/§2e/§2f): durable-history readers ------------------

    def _compose_houses(self, state, now: datetime) -> list[dict]:
        """The cumulative village (§2f, L5): one house per converged row — every sitting's, the
        village is as cumulative as the terrain's own engine state — with region membership
        computed against the SAME projection that freezes the record's terrain, so house region
        ordinals and the terrain wire can never disagree. Territory membership comes from the
        L-1 content library (experience_id -> rubric frame codes + decision_frame); an unreadable
        library degrades to compose_houses' ref/region-0 fallbacks, never a die. Inert stores
        have an empty log -> no houses (the `:memory:` shell tests stay untouched)."""
        try:
            frames_of = {
                e.experience_id: (
                    [f.frame_code for f in e.rubric.frames],
                    e.rubric.decision_frame,
                )
                for e in load_library()
                if e.rubric is not None
            }
        except Exception:
            frames_of = {}
        return compose_houses(
            project_terrain(state, now).regions, self._store.converged_log(), frames_of
        )

    def _positions(self, sit: str | None) -> list[str]:
        """Her committed positions for the forge brief (§2b review D3): the final substantive
        STUDENT turn per CONVERGED segment — never any Vera-authored text. Post-Earned-Landing
        every stop lands, so a landing alone is not commitment: an honest non-converged landing
        (plateau/budget) closes over a hedge, and shipping that hedge as "her committed
        position" would misbrief the forge (triage fold, 2026-07-03). Landing rows persisted
        before stop_reason existed read as converged (they predate honest non-converged
        landings' positions reaching the brief). Empty by construction at a sitting's first
        door."""
        if sit is None:
            return []
        out: list[str] = []
        last_you: str | None = None
        for t in self._store.turns(sit):
            if t["kind"] == "you":
                last_you = t["payload"].get("text", "")
            elif t["kind"] == "landing":
                # a landing always consumes the pending turn — a hedge must not carry over
                # and surface at a LATER converged landing either
                if last_you and t["payload"].get("stop_reason", "converged") == "converged":
                    out.append(last_you)
                last_you = None
        return out

    def _engaged_frames(self, sit: str | None) -> list[str]:
        """Frame codes engaged this sitting (§2b review D1's union screen): the frames of every
        territory this sitting TOUCHED — converged (the log) AND forged-but-not-landed
        (plateaued/errored segments' dialogue still feeds the brief; batch-review fold) —
        server-side only; the brief never sees them (the forge resolves details behind its own
        gate)."""
        if sit is None:
            return []
        eids = {
            r["experience_id"]
            for r in self._store.converged_log()
            if r["sitting_id"] == sit and r["experience_id"]
        } | self._store.generated_territories(sit)
        if not eids:
            return []
        codes: list[str] = []
        for e in load_library():
            if e.rubric is not None and e.experience_id in eids:
                for f in e.rubric.frames:
                    if f.frame_code not in codes:
                        codes.append(f.frame_code)
        return codes

    def _level(self, session_id: str) -> str:
        """The bounded difficulty enum (§2e review P8): base/firm/tight, one step per move,
        snap-back on any non-converged stop, base for a new world. In-memory walk, derived
        from durable history on a miss (restart)."""
        with self._lock:
            idx = self._level_idx.get(session_id)
        if idx is None:
            idx = self._derive_level_idx(session_id)
            with self._lock:
                self._level_idx[session_id] = idx
        return LEVELS[idx]

    def _derive_level_idx(self, session_id: str) -> int:
        """Deterministic from the durable rows: min(convergences this sitting, top), one step
        back if the last persisted record stopped non-converged. (Consecutive earlier
        non-converged stops beyond the last record are not reconstructable — the log holds
        convergences only; documented approximation, coarse by design.)"""
        sit = self._sitting_id.get(session_id)
        if sit is None:
            return 0
        converged = sum(1 for r in self._store.converged_log() if r["sitting_id"] == sit)
        idx = min(converged, len(LEVELS) - 1)
        ser = self._store.read_state(sit)["record"]
        if ser is not None and ser.get("stop_reason") != "converged":
            idx = max(idx - 1, 0)
        return idx

    def _next_instance_n(self, session_id: str, sit: str | None) -> int:
        """The forge instance counter, seeded PAST the store's max persisted n so a restarted
        process can never upsert-overwrite a prior instance row (§2f/M2)."""
        with self._lock:
            n = self._forge_n.get(session_id)
            if n is None:
                n = self._store.max_generated_n(sit) if sit is not None else 0
            n += 1
            self._forge_n[session_id] = n
            return n

    def _territory_order(self, session_id: str) -> list[str]:
        """Continue targeting order (§2c review M10, rank-based): the mapper's ranking where we
        have it — restored from the durable state row on an in-memory miss (restart; triage
        fold, 2026-07-03) — else the policy's post-session proposal order (next_menu),
        completed by the library order so every territory is always reachable."""
        with self._lock:
            rank = list(self._territory_rank.get(session_id, ()))
        open_exps = [e for e in load_library() if e.regime is Regime.open_ended]
        if not rank:
            sit = self._sitting_id.get(session_id)
            if sit is not None:
                stored = self._store.read_state(sit)["territory_rank"] or []
                known_eids = {e.experience_id for e in open_exps}
                # parity with the mapper's hallucination filter: a library-removed eid must
                # never become a forge target through the durable row
                rank = [eid for eid in stored if eid in known_eids]
                if rank:
                    with self._lock:
                        self._territory_rank[session_id] = rank
        if not rank:
            ch = self._ch.get(session_id)
            if ch is not None and ch.next_menu:
                by_ref: dict[str, list[str]] = {}
                for e in open_exps:
                    by_ref.setdefault(e.ledger_ref, []).append(e.experience_id)
                for ref, _title in ch.next_menu:
                    for eid in by_ref.get(ref, []):
                        if eid not in rank:
                            rank.append(eid)
        return rank + [e.experience_id for e in open_exps if e.experience_id not in rank]

    def _story(self, sit: str | None) -> str | None:
        """The prior chapter's scenario for a sequel forge (spec §2b) — the SINGLE predicate for
        sequel-vs-fresh (the label kind and the wind-down copy read it too, never re-derive it).
        None when the last landed record is not forged+converged (a correct fresh forge). A
        forged+converged record whose instance row is MISSING is a storage FAULT (P1 in disguise,
        cross-write review 2026-07-05 pt 2) — logged LOUDLY, then None (fresh forge, never a
        crash). Durable read (read_state), restart-safe, no in-memory dependence."""
        if sit is None:
            return None
        rec = self._store.read_state(sit)["record"]
        if rec is None:
            return None
        ref = rec.get("ledger_ref", "") or ""
        if not (ref.startswith("gen:") and rec.get("stop_reason") == "converged"):
            return None  # nothing to continue — a correct fresh forge
        row = self._store.read_generated_problem(ref)
        if row is None:
            _log.error(
                "sequel story fault: forged+converged record %s has no instance row (sitting %s)"
                " — falling back to a fresh forge",
                ref,
                sit,
            )
            return None
        return row["scenario"]

    def _territory_title(self, eid: str) -> str:
        """The target territory's SHORT curated display title (the same label the door shows) —
        for the readable Continue label (spec §2d). The veldra: ref never reaches the client."""
        try:
            exp = next(e for e in load_library() if e.experience_id == eid)
            return voice.display_titles().get(exp.ledger_ref, eid.replace("_", " ").title())
        except Exception:
            return eid.replace("_", " ").title()

    def _next_territory(self, session_id: str, now: datetime) -> str | None:
        """The highest-ranked territory outside the rolling window (§2c review M3: within a
        sitting the policy clock is frozen — the window is the ONLY rotation). None when every
        territory is windowed (the informed re-serve owns that state)."""
        windowed = self._store.territories_within(now)
        return next((eid for eid in self._territory_order(session_id) if eid not in windowed), None)

    def _capture_steer(
        self,
        session_id: str,
        sit: str,
        raw_user_text: str,
        next_pressure: str,
        now: datetime,
        model,
    ) -> None:
        """Map a non-empty next_pressure and bank a SERVABLE result as the pending steer (§2b):
        verdict=decision AND confidence=high AND the territory NOT windowed. One map call per
        genuine fresh pressure (chatter is next_pressure="" — no call, F1). last-SERVABLE-wins:
        an unservable turn (topic / low-confidence / windowed / hallucinated) leaves any prior
        steer untouched (returns without touching it)."""
        open_exps = [e for e in load_library() if e.regime is Regime.open_ended]
        territories = [(e.experience_id, load_territory_text(e.experience_id)) for e in open_exps]
        known = {eid for eid, _ in territories}
        tmap = model.map_territories(next_pressure, territories)
        ranked = [eid for eid in tmap.ranked if eid in known]
        if not ranked:
            return  # a hallucinated ranking cannot pick a door — leave any prior steer
        eid = ranked[0]
        servable = (
            tmap.verdict == "decision"
            and tmap.confidence.strip().lower() == "high"
            and eid not in self._store.territories_within(now)
        )
        if servable:
            with self._lock:
                self._steer_pending[session_id] = (raw_user_text, next_pressure, eid)

    def _attach_converse_label(
        self, session_id: str, sit: str | None, now: datetime, data: dict
    ) -> None:
        """The wind-down Continue label (§2c). A servable steer pending -> next_kind='steer', the
        button a fixed short lead, next_desc = HER raw words (never the distillation, L-13/F2).
        Else on a world sitting -> the recomputed rotation-sequel label (chapter|pressure), so the
        label tracks the live window; on a curated sitting -> leave the prior label unchanged.

        The steer label RE-CHECKS the window (adversarial-review fold F2): a steer whose territory
        windowed AFTER capture must not keep promising "press what you raised" — consume would then
        fall back to rotation, breaking the agreement invariant. A windowed pending steer shows the
        rotation label instead; it stays pending (the window is effectively frozen within a
        wind-down, so it does not spuriously resurrect, but the pending steer is not destroyed by a
        transient read)."""
        with self._lock:
            steer = self._steer_pending.get(session_id)
        if steer is not None and steer[2] not in self._store.territories_within(now):
            data["next_kind"] = "steer"
            data["next_title"] = ""
            data["next_desc"] = _clip80(steer[0])  # HER raw words
            return
        if sit is not None and self._store.read_world(sit) is not None:
            target = self._next_territory(session_id, now)
            data["next_title"] = self._territory_title(target) if target else ""
            data["next_desc"] = _territory_subtitle(target) if target else ""
            data["next_kind"] = "chapter" if self._story(sit) is not None else "pressure"

    def _least_recent_territory(self, session_id: str, now: datetime) -> str:
        """work-anyway's target (§2c review P3): the territory converged longest ago — the
        least echo. Falls back to the targeting order's head if the log carries no territories."""
        last: dict[str, str] = {}
        for r in self._store.converged_log():  # oldest-first: the last write is the latest
            if r["experience_id"]:
                last[r["experience_id"]] = r["converged_at"]
        order = self._territory_order(session_id)
        known = [eid for eid in order if eid in last]
        if not known:
            return order[0]
        return min(known, key=lambda eid: last[eid])

    def _sitting_segments(self, sit: str | None) -> list[list[tuple[str, str]]]:
        """The sitting-close author's input (§2f): you/vera turns per segment, split on landing
        turns and relabeled to the author-facing student/Vera convention every other brief uses
        (the store's wire kinds stay you/vera — the relabel lives at this read boundary only).
        Post-landing converse attaches to the segment it is ABOUT — the one that just landed —
        until a boundary marker (muted/seam/bridge: the Continue click, the next door's seam)
        ends the wind-down tail; splitting on landings alone wove the previous problem's
        wind-down into the NEXT problem's chapter of the story (triage fold, 2026-07-03)."""
        if sit is None:
            return []
        segments: list[list[tuple[str, str]]] = []
        current: list[tuple[str, str]] = []
        tail = False
        for t in self._store.turns(sit):
            kind = t["kind"]
            if kind in ("you", "vera"):
                turn = ("student" if kind == "you" else "Vera", t["payload"].get("text", ""))
                if tail and segments:
                    segments[-1].append(turn)
                else:
                    current.append(turn)
            elif kind == "landing":
                if current:
                    segments.append(current)
                    current = []
                tail = True
            else:  # muted/seam/bridge — a segment boundary marker; the wind-down tail ends here
                tail = False
        if current:
            segments.append(current)
        return segments

    def _sitting_exps(self, sit: str | None, rec: dict) -> list:
        """The union-egress move sources for the sitting close (§2f/M13): every territory this
        sitting TOUCHED — converged AND forged-but-not-landed (batch-review fold: plateaued
        segments' turns reach the close author too) — plus the record's own experience. Curated
        rubrics, loaded from the library (a forged clone's rubric is byte-equal to its base's)."""
        eids = set()
        if sit is not None:
            eids = {
                r["experience_id"]
                for r in self._store.converged_log()
                if r["sitting_id"] == sit and r["experience_id"]
            } | self._store.generated_territories(sit)
        exps = [e for e in load_library() if e.experience_id in eids]
        exp = rec.get("exp")
        if exp is not None and exp.experience_id not in eids:
            exps.append(exp)
        return exps

    def _end_sitting(self, session_id: str) -> None:
        """The sitting is over: mark it closed (rows retained, L-3) and clear the per-sid state —
        including the CHANNEL (batch-review C1/C14), so a stale post-close request gets the honest
        refresh nudge instead of hanging on a reaped worker's queue or claiming the sitting 'has
        not converged'. The menu nonce deliberately survives (monotonic per process, C18): a new
        sitting's first menu must not reuse a nonce a stale tab still holds."""
        sit = self._sitting_id.pop(session_id, None)
        if sit is not None:
            self._store.close_sitting(sit)
        # Reap a live worker before dropping its channel (batch-review C1/C2): pill + terminal so
        # its store closes and any late request short-circuits. SKIPPED while a request is in
        # flight for this sid (C4): a to_worker pill in that window can be consumed as the
        # request's expected input, hanging it — a leaked connection beats a hung request (the
        # known deferred mid-flight ticket).
        ch = self._ch.get(session_id)
        if ch is not None and not ch.terminal:
            with self._lock:
                stepping = session_id in self._stepping
            if not stepping:
                ch.to_worker.put(_ABANDON)
                ch.terminal = True
        self._ch.pop(session_id, None)
        self._last_record.pop(session_id, None)
        self._fit_variant_idx.pop(session_id, None)
        self._sitting_done.pop(session_id, None)
        self._next_pick.pop(session_id, None)
        self._next_pick_title.pop(session_id, None)
        self._seam_pending.pop(session_id, None)
        self._inflight_synced.pop(session_id, None)
        self._lost_ref.pop(session_id, None)
        self._lost_exp_id.pop(session_id, None)
        # Living-sitting state is sitting-scoped: a new world opens at base with a fresh rank
        # and a fresh instance counter (the sitting id changes, so refs cannot collide anyway).
        self._territory_rank.pop(session_id, None)
        self._level_idx.pop(session_id, None)
        self._forge_n.pop(session_id, None)
        self._frontdoor_swallow.discard(session_id)
        self._steer_pending.pop(session_id, None)
        self._steer_consume.pop(session_id, None)
        with self._lock:
            self._continue_target.pop(session_id, None)
