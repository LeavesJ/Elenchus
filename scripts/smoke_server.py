"""Zero-token manual smoke server (Phase C T4).

Runs the real FastAPI app (`create_app`) wired to the deterministic, scripted
`make_world_model` FakeModel (tests/conftest.py) instead of the real Anthropic model — a human
can click through the whole front-door/living-sitting flow in a browser with no API calls and no
cost. This is NOT a test; it's a manual verification tool. The battery of clicks/screenshots run
against it is controller-driven, separately, after this file lands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tests"))

from conftest import make_world_model  # noqa: E402 — needs the sys.path insert above
from elenchus.web.app import create_app  # noqa: E402

_DEFAULT_DB = _ROOT / "data" / "smoke.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Zero-token smoke server (scripted world fake).")
    parser.add_argument(
        "--db", default=str(_DEFAULT_DB), help="SQLite db path (default: %(default)s)"
    )
    parser.add_argument(
        "--port", type=int, default=8123, help="port to bind (default: %(default)s)"
    )
    parser.add_argument(
        "--fresh", action="store_true", help="delete the db file before starting (clean state)"
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.fresh and db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    app = create_app(db_path=str(db_path), model_factory=make_world_model)
    uvicorn.run(app, host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
