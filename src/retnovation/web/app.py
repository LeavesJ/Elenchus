from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .session_runner import SessionRegistry

_STATIC = Path(__file__).parent / "static"
_SID = "single"  # one user, one session (MVP)

# D1: a blank opening/reply must never reach classify_intake/classify_response — the live
# Anthropic API rejects empty content with a 400 ("user messages must have non-empty content"),
# which the worker surfaces as a terminal error and bricks the session. Guard at the HTTP
# boundary (defense-in-depth alongside the frontend) so the engine is never called with blank
# input and the session stays alive. (Placeholder copy; the conversational front door supersedes
# this with real orientation.)
_BLANK_NUDGE = {
    "kind": "nudge",
    "message": "Take a position — even a rough first instinct. An empty answer can't be read.",
}


class _Choice(BaseModel):
    index: int | None = None
    nonce: int | None = None  # stale-menu guard: mismatch re-serves the menu (durable sittings)


class _Text(BaseModel):
    text: str


class _Cont(BaseModel):
    menu: bool = False


def _default_model():
    from ..model import AnthropicModel

    return AnthropicModel()


def _emit(reg: SessionRegistry, tag: str, data: dict) -> dict:
    if tag == "menu":
        out = {"kind": "menu", "problems": data["problems"], "theme": data.get("theme", {})}
        if "nonce" in data:
            out["nonce"] = data["nonce"]
        return out
    if tag == "resume":  # durable sittings: the whole room, verbatim (already-projected payload)
        return {"kind": "resume", **data}
    if tag == "nudge":  # soft fail (stale tab) — the shell shows the message and recovers
        return {"kind": "nudge", "message": data.get("message", "")}
    if tag == "say":  # every Concierge-authored visible turn (opening, re-invite, probe)
        out = {"kind": "say", "text": data["text"]}
        if "theme" in data:  # the opening say carries the role atmosphere (two-phase)
            out["theme"] = data["theme"]
        if "seam" in data:  # a continued segment's static seam line (durable sittings §2d)
            out["seam"] = data["seam"]
        return out
    if tag == "done":  # the engine converged — the SESSION does not end; the user owns closure. The
        # felt landing rides the payload; the guarded next door (chained sittings) rides with it.
        return {
            "kind": "done",
            "terminal": True,
            "landing": data.get("landing", ""),
            "next_title": data.get("next_title", ""),
        }
    if tag == "close":  # user-driven end: the honest close + the frozen-at-convergence terrain
        return {"kind": "close", "close": data.get("close", ""), "terrain": data.get("terrain", [])}
    return {"kind": "error", "message": data.get("message", "")}


def create_app(db_path: str, model_factory=None) -> FastAPI:
    app = FastAPI(title="Retnovation — Cartographer MVP")

    reg = SessionRegistry(db_path, model_factory or (lambda: _default_model()))

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.post("/api/session")
    def start():
        # Durable sittings: a live sitting RESUMES (same room, whole conversation) — the
        # unconditional cold start was the founder's amnesia incident (spec §0).
        return _emit(reg, *reg.resume_or_start(_SID))

    @app.post("/api/session/{sid}/choose")
    def choose(sid: str, body: _Choice):
        # choose() (not step) so the CLIENT-made choice persists to the sitting transcript.
        return _emit(
            reg, *reg.choose(_SID, body.index if body.index is not None else 0, nonce=body.nonce)
        )

    @app.post("/api/session/{sid}/say")
    def say(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE  # blank input never reaches the engine (D1 guard)
        return _emit(reg, *reg.step(_SID, body.text))

    @app.post("/api/session/{sid}/converse")
    def converse(sid: str, body: _Text):
        if not body.text.strip():
            return _BLANK_NUDGE  # blank never reaches the model (D1 guard); engine-free path
        return _emit(reg, *reg.converse(_SID, body.text))

    @app.post("/api/session/{sid}/continue")
    def continue_(sid: str, body: _Cont):
        # Chained sittings: the next bounded engine session in the same thread (one-click or menu).
        return _emit(reg, *reg.continue_session(_SID, body.menu))

    @app.post("/api/session/{sid}/close")
    def close_session(sid: str):
        return _emit(reg, *reg.close(_SID))

    return app
