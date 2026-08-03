"""Probe 1 entrypoint: the push screen's false-positive rate on real `generate_push` output.

**Spends real money on the Anthropic API.** Pure logic and corpus construction live in
push_screen_probe.py and live_corpus.py, tested offline; this module is the only place that
touches the network, and it never does so without an explicit typed confirmation (`_confirm`)
that states the probe name, the model, and the exact call count first.

A single case's `ModelError` from `generate_push` -- which, unlike `classify_response`/
`map_territories`, has NO retry at all (see `PushScreenFailure`'s docstring) -- no longer aborts
the run: `run_push_screen_probe` records that case as failed and continues, and `run()`
checkpoints every case to a `.checkpoint.jsonl` file the moment it completes. This probe's clean
completion on its first real run was not evidence this exposure did not apply here; it applies
identically (see `.superpowers/sdd/probes-report.md`).

Run: `PYTHONPATH=src .venv/bin/python -m elenchus.run_push_screen_probe`
"""

from __future__ import annotations

import functools
import json
from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_denylist, load_library
from .live_corpus import read_learner_turns
from .push_screen_probe import (
    Probe1Result,
    PushScreenFailure,
    PushScreenRecord,
    build_cases,
    run_push_screen_probe,
)
from .types import Regime

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "push_screen_probe"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "elenchus.db"
MODEL_ID = "claude-opus-5"


def _append_checkpoint(path: Path, item: PushScreenRecord | PushScreenFailure) -> None:
    """push_screen_probe's twin of run_prompt_shift_probe._append_checkpoint -- one line per
    case, appended and closed immediately so a crash on case N+1 cannot touch what case N
    already wrote. `generate_push` is this probe's only model call and, per `PushScreenFailure`'s
    docstring, has no retry at all -- probe 1 completing cleanly on its first real run was not
    evidence this exposure was absent, only that it was not hit yet."""
    outcome = "record" if isinstance(item, PushScreenRecord) else "failure"
    line = json.dumps({"outcome": outcome, "data": item.model_dump(mode="json")})
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _confirm(probe: str, n_calls: int, model_id: str) -> bool:
    """The gate: print what is about to happen, then require the caller to type the literal word
    'yes' (case/whitespace-insensitive) at a real `input()` prompt. Chosen over a CLI flag
    because a flag can be baked into a saved command and replayed by habit -- `input()` forces a
    human to be at the keyboard for every run, and it fails loud (EOFError) in a non-interactive
    context instead of silently proceeding."""
    print(f"probe: {probe}")
    print(f"model: {model_id}")
    print(f"about to make {n_calls} real Anthropic API call(s). This spends real money.")
    answer = input("Type 'yes' to proceed: ")
    return answer.strip().lower() == "yes"


def run(
    *,
    model=None,
    db_path: Path = DB_PATH,
    data_dir: Path = DATA_DIR,
    now: datetime | None = None,
    confirm=_confirm,
) -> tuple[Path, Probe1Result] | None:
    experiences = [e for e in load_library() if e.regime is Regime.open_ended]
    framework_denylist = load_denylist("framework_denylist")
    scaffold_denylist = load_denylist("scaffold_denylist")

    positions_pool = read_learner_turns(db_path)
    corpus_source = "live_db" if positions_pool else "empty_fallback"
    if corpus_source == "empty_fallback":
        print(f"no learner turns found at {db_path} -- falling back to empty positions")

    if model is None:
        n_calls = len(build_cases(experiences))
        if not confirm("push_screen_probe", n_calls, MODEL_ID):
            print("declined -- no calls made")
            return None
        from .model import AnthropicModel  # lazy: tests never need the SDK or network

        model = AnthropicModel(model=MODEL_ID)

    # Resolved before the probe runs, and printed, so the checkpoint exists and its location is
    # known before the first real call -- see run_prompt_shift_probe.run's identical reasoning.
    if now is None:
        now = datetime.now(timezone.utc)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = data_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.checkpoint.jsonl"
    print(f"checkpointing every case to {checkpoint_path} as it completes")

    records, failures = run_push_screen_probe(
        experiences,
        model,
        positions_pool=positions_pool,
        framework_denylist=framework_denylist,
        scaffold_denylist=scaffold_denylist,
        on_item=functools.partial(_append_checkpoint, checkpoint_path),
    )
    result = Probe1Result(
        model_id=MODEL_ID,
        corpus_source=corpus_source,
        positions_pool_size=len(positions_pool),
        framework_denylist=framework_denylist,
        scaffold_denylist=scaffold_denylist,
        records=records,
        failures=failures,
    )
    path = data_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(result.model_dump_json(indent=2))
    return path, result


def main() -> None:
    outcome = run()
    if outcome is None:
        return
    path, result = outcome
    print(f"wrote {path}")
    print(f"corpus source: {result.corpus_source} ({result.positions_pool_size} learner turns)")
    summary = result.summarize()
    print(
        f"cases: attempted {summary.attempted_n}, comparable {summary.comparable_n}, "
        f"failed {summary.failed_n}"
    )
    print(f"refusal rate: {summary.refusal_rate:.3f} ({summary.refused_n}/{summary.attempted_n})")
    print(f"new bar (shipped _push_label_leak) rejected: {summary.new_bar_rejected}")
    for phrase, count in summary.new_bar_rejected_phrases.items():
        print(f"  {phrase!r}: {count}")
    print(f"old bar (validate_scene's four checks) rejected: {summary.old_bar_rejected}")
    for check, count in summary.old_bar_rejected_by_check.items():
        print(f"  {check}: {count}")


if __name__ == "__main__":
    main()
