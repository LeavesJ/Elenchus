from __future__ import annotations

from ..model import Model
from ..types import EntryClass, Experience

SAFE_CONTRACT = (
    "I won't explain the move or hand you the answer — that's the point. "
    "Take a real position on the problem and reason it out, and I'll push."
)


def _performs(model: Model, move: str, text: str) -> bool:
    """Does `text` PERFORM the hidden move (not merely touch its topic)? Reuses
    check_injection_expressed ('performs the move, not the topic'): a Socratic probe that
    questions an angle does not perform it; naming the principle or handing the answer does."""
    return model.check_injection_expressed(move, text).expressed


def _moves(exp: Experience) -> list[str]:
    """Every hidden 'move' a learner-facing surface must not perform (L-5: never name the move):
    the rubric's frame details AND trap details — naming a trap hands reasoning just as naming a
    frame does. (The unprompted-read signal is frames-only, so trap coverage hardens the doctrine
    backstop without affecting the signal.)"""
    if not exp.rubric:
        return []
    return [f.frame_detail for f in exp.rubric.frames] + [t.trap_detail for t in exp.rubric.traps]


def egress_safe_reply(model: Model, exp: Experience, text: str) -> bool:
    """For a Doorman authored reply (orientation only — NO push baseline): safe iff it performs
    NONE of the experience's hidden moves (frames and traps). A door turn legitimately performs
    zero moves, so the flat check has no false-positive risk here."""
    return not any(_performs(model, m, text) for m in _moves(exp))


def echo(model: Model, exp: Experience, push_text: str, recent: list[tuple[str, str]]) -> str:
    """Re-voice the engine's canonical push onto the user's words (display only). Gate = ADDED
    REVELATION: fall back to the verbatim push only if the re-voice performs a hidden move the
    canonical push did NOT already perform. The push baseline is essential — a faithful probe
    legitimately orbits the angle's vocabulary, so judging the re-voice against the bare move
    detail would force a verbatim fallback every turn (Echo silently no-ops; review #3)."""
    candidate = model.echo_push(push_text, recent)
    if not candidate:
        return push_text
    for m in _moves(exp):
        if _performs(model, m, candidate) and not _performs(model, m, push_text):
            return push_text  # added revelation beyond the push -> hard fallback
    return candidate


def door(
    model: Model, exp: Experience, opening: str, recent: list[tuple[str, str]]
) -> tuple[EntryClass, str | None]:
    """Front door: classify the turn and either enter the engine (substantive) or author an
    egress-safe conversational reply. A leaking author reply is replaced by SAFE_CONTRACT."""
    ec = model.classify_entry(exp.prompt, opening, recent)
    if ec.entry_class is EntryClass.substantive:
        return (EntryClass.substantive, None)
    reply = ec.reply if (ec.reply and egress_safe_reply(model, exp, ec.reply)) else SAFE_CONTRACT
    return (ec.entry_class, reply)
