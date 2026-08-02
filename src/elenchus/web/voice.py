from __future__ import annotations

from ..model import Model, ModelError
from ..types import EntryClass, Experience, hidden_move_details

SAFE_CONTRACT = (
    "I won't explain the move or hand you the answer — that's the point. "
    "Take a real position on the problem and reason it out, and I'll push."
)

_INVITE = "The call's yours. Take a position and reason it out — I'll push, I won't hand it over."

# Post-landing wind-down fallback (spec §2c): the diagnostic is DONE — never promise a push (the
# old SAFE_CONTRACT fallback lied: "reason it out and I'll push" with no engine behind it). Branch
# on whether a sequel is actually available (review pt 4 — never promise a chapter that won't
# exist).
_CONVERSE_DONE_STORY = (
    "That's the edge of this one — and that thread carries into the next chapter. "
    "Continue when you're ready."
)
_CONVERSE_DONE_FRESH = (
    "That's as far as this one goes. The other doors are below when you want the next one."
)


def _moves(exp: Experience) -> list[str]:
    """The L-5 hidden-move list — delegates to the single source of truth in types (the
    doctrine docstring lives there); the name stays for its many call/test sites."""
    return hidden_move_details(exp)


def _performed(model: Model, exp: Experience, text: str) -> set[int]:
    """Which of the experience's hidden moves does `text` PERFORM — name the principle or hand the
    answer, not merely touch the topic? ONE batched egress screen over the whole move list (was one
    check_injection_expressed call per move). Empty when there are no moves or none are performed.
    Out-of-range indices from the judge are dropped so a hallucinated number can't gate."""
    moves = _moves(exp)
    if not moves:
        return set()
    valid = range(1, len(moves) + 1)
    return {i for i in model.screen_moves(moves, text).performed if i in valid}


def egress_safe_reply(model: Model, exp: Experience, text: str) -> bool:
    """For a Doorman authored reply (orientation only — NO push baseline): safe iff it performs
    NONE of the experience's hidden moves (frames and traps). A door turn legitimately performs
    zero moves, so the flat check has no false-positive risk here. One model call.

    boundary-6 Fix 1: a screen that CANNOT run (ModelError from screen_moves — the text was too
    large to screen reliably) means "not safe", never "kill the segment". Returning False here
    routes every caller — close/opening/converse, plus turn's re-invite branch, all of which
    already gate on this return value — straight to the honest static fallback they already have,
    the same fallback a leak would have produced. Fail closed, not fail dead."""
    try:
        return not _performed(model, exp, text)
    except ModelError:
        return False


_STATIC_CLOSE = (
    "That's the read. You took a position and reasoned the trade-offs — that's the work."
)

# Honest-generic fallback: safe across every stop reason — no verdict (L-4), no move (L-13), and no
# manufactured "you arrived" for a user who never engaged. Used on refusal/empty/leak.
_STATIC_LAND = (
    "That's where we'll leave it. What you did with the problem is yours to sit with now."
)


def gate(model: Model, exp: Experience, opening: str, recent: list[tuple[str, str]]) -> EntryClass:
    """Entrance gate only: has the student taken a real position yet? (The engine needs a
    substantive opening before it can grade.) Authoring is voice.turn — never classify_entry.reply."""
    return model.classify_entry(exp.prompt, opening, recent).entry_class


def turn(
    model: Model,
    exp: Experience,
    push: str,
    recent: list[tuple[str, str]],
    posture: str | None = None,
    arc: tuple[int, int] | None = None,
) -> str:
    """Author one engaged visible turn. push != "" -> PROBE: pursue the engine's angle, grounded in
    the student's words; egress = added-revelation vs the push baseline, fallback the verbatim push.
    push == "" -> RE-INVITE: acknowledge + invite a real position; egress = flat (perform no move),
    fallback SAFE_CONTRACT. A refused/empty author also takes the fallback. arc=(n, cap) is the
    frame-blind position hint (probe turns only — the stance doctrine in concierge.md eases on it).

    boundary-6 Fix 1: on the PROBE branch, a screen that CANNOT run (ModelError) is treated as
    added revelation — fail closed to the documented fallback (the verbatim push), never let the
    raise unwind past it."""
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_turn(exp.prompt, push, recent, arc=arc, voice=v)
    if not text:
        return push or SAFE_CONTRACT
    if push:
        try:
            added_revelation = _performed(model, exp, text) - _performed(model, exp, push)
        except ModelError:
            added_revelation = True  # screen couldn't run -> not safe -> the verbatim push
        if added_revelation:
            return push
        return text
    if not egress_safe_reply(model, exp, text):
        return SAFE_CONTRACT
    return text


def close(
    model: Model, exp: Experience, recent: list[tuple[str, str]], posture: str | None = None
) -> str:
    """Author the closing synthesis (reflect the student's reasoning back; no score, no named move).
    Flat egress; fallback to a safe static close on refusal/empty/leak."""
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_close(exp.prompt, recent, voice=v)
    if not text or not egress_safe_reply(model, exp, text):
        return _STATIC_CLOSE
    return text


def sitting_close(
    model: Model,
    situation: str,
    segments: list[list[tuple[str, str]]],
    exps: list[Experience],
    posture: str | None = None,
) -> str:
    """Author the whole-sitting close (living sitting §2f): the world's story over every landed
    segment — retrospective, no verdicts (L-4; correctness is never supplied). Egress is ONE
    batched screen over the UNION of the sitting's territories' moves (D1/M13 — the caller
    passes the territory experiences; the scale is measured @live before it is trusted). Flat
    check — a close performs no move — with the safe static close on refusal/empty/leak.

    boundary-6 Fix 1: a screen that CANNOT run (ModelError) takes the same static fallback as a
    screen that flags a leak — "not safe" either way, never an unhandled raise that kills the
    close."""
    v = resolve_presentation(posture, None)["voice"]
    text = model.concierge_sitting_close(situation, segments, voice=v)
    if not text:
        return _STATIC_CLOSE
    union: list[str] = []
    for exp in exps:
        for move in _moves(exp):
            if move not in union:
                union.append(move)
    if union:
        valid = range(1, len(union) + 1)
        try:
            performed = model.screen_moves(union, text).performed
        except ModelError:
            return _STATIC_CLOSE
        if any(i in valid for i in performed):
            return _STATIC_CLOSE
    return text


_RETRY_STEER = (
    "Your previous attempt restated the problem's mechanism too plainly. Land again without "
    "describing any mechanism or move — point at what THEY said and what it cost them, never at "
    "what it means."
)


def _student_text(recent: list[tuple[str, str]]) -> str:
    return " ".join(t for role, t in recent if role == "student")


def land(
    model: Model,
    exp: Experience,
    recent: list[tuple[str, str]],
    stop_reason: str,
    posture: str | None = None,
) -> str:
    """Author the felt landing at convergence/stop — a short, present-tense arrival, honest by
    stop_reason. It rewards movement/rigor, NEVER correctness (L-4 — only concierge_land's doctrine
    enforces that). L-13 gate (founder call, 2026-07-01 live evidence): the crux mirror inevitably
    touches the move's territory, so a FLAT screen kills most good landings — instead the landing may
    perform only moves the STUDENT's own dialogue already performed (added-revelation vs THEIR words,
    the probe gate's logic — you cannot hand someone what they already hold). A flagged landing is
    re-authored ONCE with a no-mechanism steer; then the honest static. Screened in the worker before
    the done payload.

    boundary-6 Fix 1: the student baseline join has no code-level cap (real, unbounded learner
    text — see `_TURN_RENDER_CAP`'s comment) and can legitimately exceed the screen's threshold on
    an ordinary long, rigorous session — the CRITICAL regression this fix closes. A ModelError
    anywhere in this function (the baseline call or either landing attempt's screen) means the
    screen could not run, which is "not safe", never "kill the segment" — the whole segment's state
    is already banked by the time this runs (orchestration.run_session's store.save_state, BEFORE
    the caller reaches voice.land), so unwinding past `_STATIC_LAND` would split the commit between
    the engine state and the sitting record. Fail closed to the honest static instead."""
    v = resolve_presentation(posture, exp)["voice"]
    student = _student_text(recent)
    try:
        baseline = _performed(model, exp, student) if student else set()
        for steer in ("", _RETRY_STEER):
            text = model.concierge_land(exp.prompt, recent, stop_reason, steer=steer, voice=v)
            if text and not (_performed(model, exp, text) - baseline):
                return text
    except ModelError:
        pass
    return _STATIC_LAND


def opening(model: Model, exp: Experience, posture: str | None = None) -> str:
    """Author the concrete opening turn (turn 0 — no dialogue yet): present the problem vividly so a
    cold student has a foothold (obs #4), frame hidden, specifics from the problem text only. Flat
    egress; fallback to the verbatim problem + the static invite on refusal/empty/leak so the
    scenario is never lost. (Named `opening`, not `open`, to avoid shadowing the builtin.)"""
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_open(exp.prompt, voice=v)
    if not text or not egress_safe_reply(model, exp, text):
        return exp.prompt + "\n\n" + _INVITE
    return text


def converse(
    model: Model,
    exp: Experience,
    recent: list[tuple[str, str]],
    user_text: str,
    posture: str | None = None,
    stop_reason: str = "converged",
    has_sequel: bool = False,
) -> tuple[str, str]:
    """Post-stop, engine-free continuation. Returns (reply_text, next_pressure). The diagnostic is
    DONE — WIND DOWN, never re-invite a position (the old re-invite path re-demanded a committed
    answer, DEVLOG 2026-07-01). Honest by stop_reason: on a non-converged stop the author is told the
    student did NOT land the call, so it can't manufacture a commitment that never happened. Author
    via concierge_converse (STRUCTURED — reply + next_pressure). `reply` is flat-egress screened; on
    refusal/empty/leak the fallback is HONEST — it never promises a push (the old SAFE_CONTRACT
    fallback lied), and it promises a next chapter ONLY when `has_sequel` (spec §2c; review pt 4).
    The distilled `next_pressure` is passed up UN-screened (server-side data — the forge screens the
    eventual scenario, not this clause; L-13/F2 hold on the label, which echoes her raw words)."""
    v = resolve_presentation(posture, exp)["voice"]
    turn = model.concierge_converse(
        exp.prompt, recent + [("student", user_text)], stop_reason=stop_reason, voice=v
    )
    reply, next_pressure = turn.reply, turn.next_pressure
    if not reply or not egress_safe_reply(model, exp, reply):
        return (_CONVERSE_DONE_STORY if has_sequel else _CONVERSE_DONE_FRESH), next_pressure
    return reply, next_pressure


def resolve_presentation(posture: str | None, exp: Experience | None) -> dict:
    """Resolve the presentation profile from content: voice = persona + role_register + craft (composed,
    graceful), visual = a public theme {persona_mark, accent, atmosphere_label}. role comes from
    exp.role (None -> no role layer); persona from the posture map (unknown -> vera floor)."""
    from ..content_loader import (
        load_persona_text,
        load_prompt,
        load_role_text,
        load_theme,
        persona_for_posture,
    )

    persona = persona_for_posture(posture)
    role = getattr(exp, "role", None) if exp is not None else None
    parts = [load_persona_text(persona)]
    if role:
        parts.append(load_role_text(role))
    parts.append(load_prompt("voice_craft"))
    voice_text = "\n\n".join(parts)

    visual = {"persona_mark": "V", "accent": "slate", "atmosphere_label": "neutral"}
    visual.update(load_theme("personas", persona))
    if role:
        visual.update(load_theme("voice", f"role_{role}"))
    visual = {k: visual[k] for k in ("persona_mark", "accent", "atmosphere_label")}
    return {"voice": voice_text, "visual": visual}


def display_titles() -> dict[str, str]:
    """Map each open-ended experience's ledger_ref -> a human picker label. Keyed by the internal
    ref (server-side join key); the VALUE is the rubric's display_title, or a humanized
    experience_id fallback. The veldra: ref must never reach the client as a label."""
    from ..content_loader import load_library
    from ..types import Regime

    out: dict[str, str] = {}
    for e in load_library():
        if e.regime is not Regime.open_ended:
            continue
        title = (e.rubric.display_title if e.rubric and e.rubric.display_title else None) or (
            e.experience_id.replace("_", " ").capitalize()
        )
        out[e.ledger_ref] = title
    return out
