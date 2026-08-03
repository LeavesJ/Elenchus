"""Probe 1 entrypoint: the push screen's false-positive rate on real `generate_push` output.

**Spends real money on the Anthropic API.** Pure logic and corpus construction live in
push_screen_probe.py and live_corpus.py, tested offline; this module is the only place that
touches the network, and it never does so without an explicit typed confirmation (`_confirm`)
that states the probe name, the model, and the exact call count first.

Run: `PYTHONPATH=src .venv/bin/python -m elenchus.run_push_screen_probe`
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_denylist, load_library
from .live_corpus import read_learner_turns
from .push_screen_probe import Probe1Result, build_cases, run_push_screen_probe
from .types import Regime

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "push_screen_probe"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "elenchus.db"
MODEL_ID = "claude-opus-5"


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

    records = run_push_screen_probe(
        experiences,
        model,
        positions_pool=positions_pool,
        framework_denylist=framework_denylist,
        scaffold_denylist=scaffold_denylist,
    )
    result = Probe1Result(
        model_id=MODEL_ID,
        corpus_source=corpus_source,
        positions_pool_size=len(positions_pool),
        framework_denylist=framework_denylist,
        scaffold_denylist=scaffold_denylist,
        records=records,
    )
    if now is None:
        now = datetime.now(timezone.utc)
    data_dir.mkdir(parents=True, exist_ok=True)
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
    print(f"total pushes: {summary.total}")
    print(f"new bar (shipped _push_label_leak) rejected: {summary.new_bar_rejected}")
    for phrase, count in summary.new_bar_rejected_phrases.items():
        print(f"  {phrase!r}: {count}")
    print(f"old bar (validate_scene's four checks) rejected: {summary.old_bar_rejected}")
    for check, count in summary.old_bar_rejected_by_check.items():
        print(f"  {check}: {count}")


if __name__ == "__main__":
    main()
