"""Entrypoint for the injection efficacy probe. The ONLY module here that touches the network,
and it never does so without a typed confirmation.

`classify`, `raw_parse`, `system_for`, and `old_user_for` are injected rather than built here, so
every code path in `run()` is provable against a fake model -- the same shape as
`run_prompt_shift_probe.py` and `run_push_screen_probe.py`. Real wiring to `AnthropicModel`
(building `system_for` from the same pieces `AnthropicModel.classify_response` calls, and a real
`raw_parse` over `Model._parse_required`) is a separate change; until it lands, `run()` still works
end to end against any four callables a caller supplies.

Two properties this module exists to guarantee:

- The cost guard (`confirm`) is told the EXACT remaining call count (`len(schedule)`), so an
  invocation prices exactly the schedule it was handed rather than silently re-authorizing a full
  budget. There is no automatic checkpoint-aware resume: after a partial run, the next invocation
  draws and prices its own fresh schedule from scratch, matching `run_prompt_shift_probe.py`'s
  disclaimer (`.superpowers/sdd/probes-report.md`). The earlier `.checkpoint.jsonl` is left on
  disk for its data, not consumed.
- Every completed draw is checkpointed to `<timestamp>.checkpoint.jsonl` BEFORE the final
  `<timestamp>.json` result file is written. `run_cells`'s `on_draw` hook appends one line per call
  as it completes, so a crash mid-run still leaves every already-paid-for draw on disk -- a
  previous probe in this project lost an entire paid run to exactly that gap.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .injection_probe import CELLS, Payload, draw_schedule, load_payloads, run_cells
from .injection_scoring import adjudicate, screen, tally, truncate_to_complete_draw
from .model import _CLASSIFY_MAX_TOKENS
from .prompt_shift_probe import reconstruct_old_classify_response_user
from .run_push_screen_probe import _confirm

DEFAULT_DRAWS = 3
DEFAULT_SEED = 20260803
MODEL_ID = "claude-opus-5"

# The push text used to reconstruct the OLD (pre-indent) `classify_response` user message. The
# probe's own payloads carry no push text of their own -- only `substance`/`injection`/
# `semantic_only`, the learner side of the exchange -- so every cell in a run shares this one fixed
# push, matching `system_for` being shared across both arms of a payload (Task 8's contract).
_PUSH = "What is the mechanism that closes the gap you just named?"

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "injection_probe"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "elenchus.db"
PAYLOAD_PATH = Path(__file__).resolve().parents[2] / "data" / "injection_payloads.yaml"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run(
    *,
    payloads: list[Payload] | None = None,
    data_dir: Path = DATA_DIR,
    classify=None,
    raw_parse=None,
    system_for=None,
    old_user_for=None,
    confirm=_confirm,
    draws: int = DEFAULT_DRAWS,
    seed: int = DEFAULT_SEED,
    model_id: str = MODEL_ID,
    now: datetime | None = None,
) -> tuple[Path, dict] | None:
    """Execute the probe. Returns `(artifact_path, result_dict)`, or `None` if unconfirmed.

    The cost guard is told the EXACT remaining call count, so it prices exactly the schedule this
    call draws. There is no automatic resume from a checkpoint: after a partial run, the next call
    draws and prices its own fresh schedule from scratch; the earlier checkpoint file is kept for
    its data, not consumed."""
    payloads = payloads if payloads is not None else load_payloads(PAYLOAD_PATH)
    # `load_payloads` already raises on an empty corpus, but `run(payloads=[...])` can be called
    # directly with one, bypassing that check. Left unguarded, an empty list would run all the way
    # to `truncate_to_complete_draw`, which raises its OWN "needs at least one payload name" error
    # for an unrelated reason (an unbounded `while` loop over an always-satisfied empty subset) --
    # a confusing error from the wrong layer, past a confirm prompt that should never have been
    # shown. Fail loud here instead, at the actual boundary, before anything is asked or spent.
    if not payloads:
        raise ValueError("run() got an empty payload list -- nothing to probe")

    if old_user_for is None:
        def old_user_for(p, text):
            return reconstruct_old_classify_response_user(_PUSH, text)

    schedule = draw_schedule([p.name for p in payloads], draws=draws, seed=seed)
    if not confirm("injection_efficacy", len(schedule), model_id):
        print("not confirmed; no calls made")
        return None

    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    ckpt = data_dir / f"{stamp}.checkpoint.jsonl"
    print(f"checkpointing every draw to {ckpt} as it completes")

    def _append(row):
        with ckpt.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row.model_dump(mode="json")) + "\n")

    rows = run_cells(
        payloads, schedule, classify=classify, raw_parse=raw_parse,
        system_for=system_for, old_user_for=old_user_for,
        max_tokens=_CLASSIFY_MAX_TOKENS, on_draw=_append,
    )
    names = [p.name for p in payloads]
    kept, depth = truncate_to_complete_draw(rows, names)
    tallies = tally(kept, names)
    screened = screen(tallies)
    verdict = adjudicate(tallies, screened)

    doc = {
        "model_id": model_id,
        "seed": seed,
        "draws": draws,
        "kept_draw_depth": depth,
        "truncated": depth < draws,
        "cells": list(CELLS),
        "prompt_hashes": {
            # Hash what the run ACTUALLY sends, by calling the injected `old_user_for`. Calling
            # `reconstruct_old_classify_response_user("PUSH", "REPLY")` directly instead would
            # bypass both `_PUSH` and any caller-supplied `old_user_for`, so the recorded hash
            # would stay byte-identical no matter how the real prompt changed. A provenance field
            # insensitive to the thing it claims to record is worse than no field at all.
            "old_user_template": _sha(old_user_for(payloads[0], "REPLY")),
            "classify_system": _sha(system_for(payloads[0])),
        },
        "denominators": {
            "admitted": len(payloads),
            "scorable": verdict.n_scorable,
            "excluded": {s.payload_name: s.excluded_by for s in screened if not s.scorable},
        },
        "verdict": verdict.model_dump(mode="json"),
        "tallies": [t.model_dump(mode="json") for t in tallies],
    }
    path = data_dir / f"{stamp}.json"
    path.write_text(json.dumps(doc, indent=2))
    print(f"verdict: {verdict.verdict} ({verdict.reason})")
    print(f"wrote {path}")
    return path, doc
