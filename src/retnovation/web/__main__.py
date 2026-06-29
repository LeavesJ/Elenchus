from __future__ import annotations

import os
from pathlib import Path

from .app import create_app

_ROOT = Path(__file__).resolve().parents[3]
DB = str(_ROOT / "data" / "retnovation.db")


def _load_dotenv(path: Path) -> None:
    """Best-effort: load simple KEY=VALUE lines from .env into the process env so
    `python -m retnovation.web` finds ANTHROPIC_API_KEY without the caller sourcing .env first.
    Uses setdefault — a real exported var always wins. Never logs values."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.removeprefix("export ").strip()
        if key:
            os.environ.setdefault(key, val.strip().strip('"').strip("'"))


_load_dotenv(_ROOT / ".env")
app = create_app(db_path=DB)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
