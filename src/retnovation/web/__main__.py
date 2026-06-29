from __future__ import annotations

from pathlib import Path

from .app import create_app

DB = str(Path(__file__).resolve().parents[3] / "data" / "retnovation.db")
app = create_app(db_path=DB)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
