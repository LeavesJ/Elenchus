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
    work_anyway: bool = False  # the informed re-serve's first choice (living sitting §2c)


def _default_model():
    from ..model import AnthropicModel

    return AnthropicModel()


def _build_stamp() -> str:
    """Best-effort build identity (durable sittings §2f): tonight's incident was undiagnosable in
    the tab because nothing said WHICH build the process was running. Never raises."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            capture_output=True,
            timeout=1,
            text=True,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


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
    if tag == "say" and data.get("frontdoor"):
        # The cold beat (living sitting §2a/§2g): the static ask + the small doors. The
        # embedded menu is projected title-only — refs stay server-side (L-13).
        out = {
            "kind": "frontdoor",
            "text": data["text"],
            "menu": {
                "problems": data["menu"]["problems"],
                "nonce": data["menu"].get("nonce", 0),
            },
            "theme": data.get("theme", {}),
        }
        if data.get("returning"):  # the return-visit muted line (§2f review P10)
            out["returning"] = data["returning"]
        return out
    if tag == "say":  # every Concierge-authored visible turn (opening, re-invite, probe)
        out = {"kind": "say", "text": data["text"]}
        if "theme" in data:  # the opening say carries the role atmosphere (two-phase)
            out["theme"] = data["theme"]
        if "seam" in data:  # a continued segment's static seam line (durable sittings §2d)
            out["seam"] = data["seam"]
        if "bridge" in data:  # the heard-you / fallback bridge on a forged opening (§2a/§2b)
            out["bridge"] = data["bridge"]
        return out
    if tag == "reserve":  # every territory windowed: the informed re-serve question (§2c P3)
        return {
            "kind": "reserve",
            "copy": data.get("copy", ""),
            "choices": data.get("choices", []),
        }
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
    build = _build_stamp()

    @app.get("/api/health")
    def health():
        return {"ok": True, "build": build}

    @app.get("/")
    def index():
        # no-store kills the stale-shell class structurally (durable sittings §2f) — a cached
        # shell that predates kind:"resume" would render every page load as an error line.
        return FileResponse(_STATIC / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.post("/api/session")
    def start():
        # Durable sittings: a live sitting RESUMES (same room, whole conversation) — the
        # unconditional cold start was the founder's amnesia incident (spec §0).
        out = _emit(reg, *reg.resume_or_start(_SID))
        out["build"] = build  # visible in the tab (console/#mark tooltip) — §2f
        return out

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
        # Chained sittings: the next bounded engine session in the same thread (one-click or
        # menu); work_anyway honors the informed re-serve's first choice (living sitting §2c).
        return _emit(reg, *reg.continue_session(_SID, body.menu, work_anyway=body.work_anyway))

    @app.post("/api/session/{sid}/close")
    def close_session(sid: str):
        return _emit(reg, *reg.close(_SID))

    return app
