from __future__ import annotations

import os
from pathlib import Path

import logging

from ..call_log import SERVER_LOG_FORMAT
from .app import create_app
from .runtime import resolve_runtime

# Entrypoint-owned logging config (L-9's logging variant, found live 2026-08-30): with no
# config, logging's last-resort handler drops below WARNING, so the model_call timing lines --
# the exact data the S4 measurement reads -- were silently discarded while the suite's caplog
# stayed green. INFO on stderr; uvicorn adds its own handlers independently.
#
# The format comes from call_log, which is the module that READS these lines back. Two literals,
# one here and one in the parser, drift apart in silence: the symptom of that drift is an
# instrument reporting zero calls, which is indistinguishable from a quiet week.
logging.basicConfig(level=logging.INFO, format=SERVER_LOG_FORMAT)

_ROOT = Path(__file__).resolve().parents[3]


def _load_dotenv(path: Path) -> None:
    """Best-effort: load simple KEY=VALUE lines from .env into the process env so
    `python -m elenchus.web` finds ANTHROPIC_API_KEY without the caller sourcing .env first.
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

# Which invitee's database, and what this process serves. Override-only: with nothing set this is
# byte-for-byte the previous behaviour (data/elenchus.db on 127.0.0.1:8000), so the founder's own
# instance does not move. Resolved AFTER _load_dotenv so .env can carry these too, and it raises
# rather than defaulting -- see runtime.py for why every available fallback is worse than not
# starting.
DB, HOST, PORT = resolve_runtime(os.environ)
app = create_app(db_path=DB)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
