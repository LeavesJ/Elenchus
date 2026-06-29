from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..terrain import project_terrain
from .session_runner import SessionRegistry

_STATIC = Path(__file__).parent / "static"
_SID = "single"  # one user, one session (MVP)


class _Choice(BaseModel):
    index: int | None = None
    ledger_ref: str | None = None


class _Text(BaseModel):
    text: str


def _default_model():
    from ..model import AnthropicModel

    return AnthropicModel()


def _emit(reg: SessionRegistry, tag: str, data: dict) -> dict:
    if tag == "done":
        now = datetime.now(timezone.utc)
        view = project_terrain(data["state"], now)
        return {"kind": "done", "terrain": view.learner_view()}
    if tag == "menu":
        return {"kind": "menu", "problems": data["problems"]}
    if tag == "problem":
        return {"kind": "problem", "prompt": data["prompt"], "ledger_ref": data["ledger_ref"]}
    if tag == "push":
        return {"kind": "push", "text": data["text"]}
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
        return _emit(reg, *reg.start(_SID))

    @app.post("/api/session/{sid}/choose")
    def choose(sid: str, body: _Choice):
        idx = body.index if body.index is not None else reg.menu_index(_SID, body.ledger_ref)
        return _emit(reg, *reg.step(_SID, idx))

    @app.post("/api/session/{sid}/open")
    def open_read(sid: str, body: _Text):
        return _emit(reg, *reg.step(_SID, body.text))

    @app.post("/api/session/{sid}/reply")
    def reply(sid: str, body: _Text):
        return _emit(reg, *reg.step(_SID, body.text))

    return app
