from __future__ import annotations

from ..model import Model
from ..types import EntryClass, Experience

SAFE_CONTRACT = (
    "I won't explain the move or hand you the answer — that's the point. "
    "Take a real position on the problem and reason it out, and I'll push."
)

_INVITE = "The call's yours. Take a position and reason it out — I'll push, I won't hand it over."


def _moves(exp: Experience) -> list[str]:
    """Every hidden 'move' a learner-facing surface must not perform (L-5: never name the move):
    the rubric's frame details AND trap details — naming a trap hands reasoning just as naming a
    frame does. (The unprompted-read signal is frames-only, so trap coverage hardens the doctrine
    backstop without affecting the signal.)"""
    if not exp.rubric:
        return []
    return [f.frame_detail for f in exp.rubric.frames] + [t.trap_detail for t in exp.rubric.traps]


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
    zero moves, so the flat check has no false-positive risk here. One model call."""
    return not _performed(model, exp, text)


_STATIC_CLOSE = (
    "That's the read. You took a position and reasoned the trade-offs — that's the work."
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
) -> str:
    """Author one engaged visible turn. push != "" -> PROBE: pursue the engine's angle, grounded in
    the student's words; egress = added-revelation vs the push baseline, fallback the verbatim push.
    push == "" -> RE-INVITE: acknowledge + invite a real position; egress = flat (perform no move),
    fallback SAFE_CONTRACT. A refused/empty author also takes the fallback."""
    v = resolve_presentation(posture, exp)["voice"]
    text = model.concierge_turn(exp.prompt, push, recent, voice=v)
    if not text:
        return push or SAFE_CONTRACT
    if push:
        if _performed(model, exp, text) - _performed(model, exp, push):  # added revelation
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
) -> str:
    """Post-convergence, engine-free continuation: acknowledge the user's latest and keep them
    reasoning — no engine push (the diagnostic is done), frame-blind. Reuses the re-invite turn
    (flat egress, fallback SAFE_CONTRACT); the comprehension gear in the craft governs here too."""
    return turn(model, exp, "", recent + [("student", user_text)], posture=posture)


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
