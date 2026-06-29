from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_STATIC = Path(__file__).parent / "static"


def create_app(db_path: str, model_factory=None) -> FastAPI:
    app = FastAPI(title="Retnovation — Cartographer MVP")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app
