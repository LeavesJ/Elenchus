"""Probe 2 entrypoint: does the reformatted graded prompt (`prompt_text.labelled`'s indent) shift
a `classify_response` or `map_territories` decision on real (push, response) pairs and real
situations.

**Spends real money on the Anthropic API.** Pure logic and corpus construction live in
prompt_shift_probe.py and live_corpus.py, tested offline; this module is the only place that
touches the network, and it never does so without an explicit typed confirmation (`_confirm`,
reused from run_push_screen_probe.py -- it already takes the probe name as a parameter, so this
is its second real caller, not a copy) that states the probe name, the model, and the exact call
count first.

Three arms per corpus item (A: the current prompt; B: the current prompt again, the control; C:
the pre-change prompt, reconstructed) across both halves (classify_response, map_territories) --
see prompt_shift_probe.py's module docstring for why three arms, not two.

A single item's `ModelError` (the documented `classify_response` stochastic refusal, model.py's
`_parse_required` docstring) no longer aborts the run: `run_classify_probe`/`run_territory_probe`
record that item as failed and continue, and `run()` checkpoints every item (record or failure)
to a `.checkpoint.jsonl` file the moment it completes, so a crash this module does NOT catch
(anything other than `ModelError`) still leaves every already-paid-for item readable on disk.
Resuming a run FROM a checkpoint is not implemented -- see `.superpowers/sdd/probes-report.md`
for why, and what to do after a partial run instead.

Run: `PYTHONPATH=src .venv/bin/python -m elenchus.run_prompt_shift_probe`
"""

from __future__ import annotations

import functools
import json
from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_library, load_prompt, load_territory_text
from .live_corpus import read_push_response_pairs, read_situations
from .model import _CLASSIFY_MAX_TOKENS, _MED_PARAMS, _PARAMS, _situation_block, _target_detail
from .prompt_shift_probe import (
    ClassifyFailure,
    ClassifyItem,
    ClassifyRecord,
    Probe2Result,
    TerritoryFailure,
    TerritoryRecord,
    build_classify_corpus,
    build_territory_corpus,
    run_classify_probe,
    run_territory_probe,
    summarize_disagreement,
)
from .run_push_screen_probe import _confirm
from .types import Regime

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prompt_shift_probe"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "elenchus.db"
MODEL_ID = "claude-opus-5"

# A first run should be cheap. push_screen_probe's whole corpus (5 open-ended experiences, no
# live db needed) is 64 calls; this probe's corpora instead scale with whatever the live db
# holds -- every real (push, response) pair, every real situation -- which is unbounded. 20 items
# per half (classify_response, map_territories) keeps a first run at 3 * (20 + 20) = 120 calls:
# enough to see a nonzero disagreement rate on both halves without the founder discovering the
# true size of the live corpus by paying for all of it on the first try.
DEFAULT_LIMIT = 20

# same_prompt_disagreement (arm A vs arm B) is pure re-sampling noise from calling the IDENTICAL
# prompt twice; new_vs_old_disagreement (arm A vs arm C) is that same noise plus whatever the
# indent actually changed. At DEFAULT_LIMIT's scale (~20 items/half), a disagreement rate around
# 0.2-0.3 has a per-arm binomial standard error on the order of 0.09-0.10, so the standard error
# of the DIFFERENCE between two such rates is roughly sqrt(2) times that, ~0.13-0.14. A margin
# set below that floor would claim a shift on sampling noise alone; 0.15 sits just above it -- a
# deliberately conservative default that trades false negatives for false positives at this
# sample size, since wrongly claiming the indent changed a grading decision is the more
# expensive mistake to make by default. ASSUMED, not measured: no real corpus has been run
# through this probe yet (that is what it is for), so this is reasoned from binomial-noise
# arithmetic alone, not calibrated against data -- it would be falsified by an actual run whose
# same_prompt_disagreement routinely exceeds ~0.15 on its own.
DEFAULT_MARGIN = 0.15


def _checkpoint_line(
    probe: str, item: ClassifyRecord | ClassifyFailure | TerritoryRecord | TerritoryFailure
) -> str:
    """One JSON line naming which half (`probe`: "classify"|"territory") and outcome
    (`ClassifyRecord`/`TerritoryRecord` -> "record", `ClassifyFailure`/`TerritoryFailure` ->
    "failure") `item` is, plus its full field data -- self-contained, so the checkpoint file
    alone (no companion result file needed) tells a reader exactly which items completed, which
    failed, and why, if the process dies before `run()` ever reaches its own `path.write_text`."""
    outcome = "record" if isinstance(item, (ClassifyRecord, TerritoryRecord)) else "failure"
    return json.dumps({"probe": probe, "outcome": outcome, "data": item.model_dump(mode="json")})


def _append_checkpoint(path: Path, probe: str, item) -> None:
    """Append-and-close per item (not one held-open handle for the whole run): each call is a
    complete, independent write, so a crash on item N+1 cannot corrupt or truncate what item N
    already put on disk. Granularity is per ITEM, not per arm -- the earliest point at which a
    `ClassifyRecord`/`TerritoryRecord` exists is once all three arms of that item have
    succeeded, and a `ClassifyFailure`/`TerritoryFailure` exists the moment an item is
    abandoned, so every item this probe ever spends money on lands here exactly once, win or
    lose, before the loop moves on (`prompt_shift_probe.run_classify_probe`/
    `run_territory_probe`'s `on_item` hook calls this once per item)."""
    with path.open("a", encoding="utf-8") as f:
        f.write(_checkpoint_line(probe, item) + "\n")


def _classify_system_for(item: ClassifyItem) -> str:
    """Reproduces `AnthropicModel.classify_response`'s system composition (model.py) exactly, by
    calling the SAME building blocks that method calls (`load_prompt`, `_situation_block`,
    `_target_detail`) rather than hand-copying their assembly, so this can never silently drift
    from what arms A/B actually send. Pinned in tests/test_run_prompt_shift_probe.py against a
    real `AnthropicModel(client=fake).classify_response` call's captured `system=`."""
    detail = _target_detail(item.exp.rubric, item.kind, item.code)
    return (
        load_prompt("response")
        + (("\n\n" + load_prompt("response_stress")) if item.stress else "")
        + _situation_block(item.exp)
        + f"\n\nMode: {item.exp.rubric.mode.value}"
        + f"\nBinding constraint: {item.exp.rubric.binding_constraint}"
        + f"\nTarget angle: {detail}"
    )


# map_territories' system (model.py) carries no per-item data, so it needs no function -- but
# unlike classify_response's pieces above, it is a literal composed inline in the method body,
# with no importable symbol to call through. Copied verbatim and pinned in
# tests/test_run_prompt_shift_probe.py against a real `AnthropicModel(client=fake).
# map_territories` call's captured `system=`.
_MAP_TERRITORIES_SYSTEM = (
    "You map a person's real situation onto the numbered territories below — each names "
    "a kind of decision. Return: `ranked` — every territory id, best fit first, ids "
    'exactly as given in brackets; `confidence` — "high" if the best territory\'s kind '
    'of decision is plainly the kind she is facing, else "low"; `verdict` — "decision" '
    "if she describes a decision, a dilemma, or a situation she must act in; "
    '"topic" if she instead asks a question, seeks advice, or names a subject of '
    "curiosity; `reflection` — ONE line reflecting what she is facing, in her own words "
    'wherever possible (on "topic", reflect the subject she raised). The reflection '
    "describes her situation only: never advice, never analysis vocabulary, never the "
    'territory text. `conversion` — empty unless verdict is "topic"; then ONE sentence '
    "that engages her subject in her own words, plus ONE question asking for the "
    "concrete call she faces inside that subject. The conversion never answers her "
    "question, never recommends, never names a territory, never judges the question, "
    "and never declares anything out of scope. "
    "`fit` — ALWAYS fill it: ONE noun phrase naming the sharpest decision the best-fit "
    'territory can press INSIDE her own situation, in her own words (e.g. "how you set '
    'your pricing tiers against a competitor already saturating your market"). It is the '
    "EDGE of HER subject, phrased as the thing she must decide — never the generic kind of "
    "decision, never the territory text, never advice, never analysis vocabulary, never a "
    'question. It reads naturally after "the sharpest pressure I can put on it: ".'
)


def _raw_parse_classify(model, *, system: str, user: str, output_format: type, max_tokens: int):
    """Arm C's raw parse for classify_response items. `model.classify_response` cannot be reused
    here -- it COMPOSES the new, indented prompt itself, which is exactly what arm C must not
    send. `_parse_required` (model.py) is the private helper `classify_response` itself calls
    once it has composed a `system`/`messages` pair; reaching past the public method for it is
    the only way to send a hand-built `user` through the real single-retry structured-parse path
    (budget-doubled retry on truncation, plain retry on refusal) instead of a bare client call
    that would silently skip that behavior. `_PARAMS` matches classify_response's own
    reasoning-effort choice."""
    return model._parse_required(
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=output_format,
        **_PARAMS,
    )


def _raw_parse_territory(model, *, system: str, user: str, output_format: type, max_tokens: int):
    """map_territories' twin of `_raw_parse_classify` -- same reasoning (`map_territories` also
    composes its own new user message, so arm C must bypass it and reach `_parse_required`
    directly), but `_MED_PARAMS` because `map_territories` itself calls `_parse_required` with
    `_MED_PARAMS`, not `_PARAMS`."""
    return model._parse_required(
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=output_format,
        **_MED_PARAMS,
    )


def run(
    *,
    model=None,
    raw_parse_classify=None,
    raw_parse_territory=None,
    db_path: Path = DB_PATH,
    data_dir: Path = DATA_DIR,
    now: datetime | None = None,
    confirm=_confirm,
    limit: int | None = DEFAULT_LIMIT,
    margin: float = DEFAULT_MARGIN,
) -> tuple[Path, Probe2Result] | None:
    experiences = [e for e in load_library() if e.regime is Regime.open_ended]

    pairs = read_push_response_pairs(db_path)
    classify_corpus_source = "live_db" if pairs else "empty_fallback"
    if classify_corpus_source == "empty_fallback":
        print(f"no push/response pairs at {db_path} -- falling back to an empty classify corpus")

    situations = read_situations(db_path)
    territory_corpus_source = "live_db" if situations else "empty_fallback"
    if territory_corpus_source == "empty_fallback":
        print(f"no situations at {db_path} -- falling back to an empty territory corpus")

    classify_items = build_classify_corpus(pairs, experiences, limit=limit)
    territories = [(e.experience_id, load_territory_text(e.experience_id)) for e in experiences]
    territory_items = build_territory_corpus(situations, territories, limit=limit)

    if model is None:
        # Three arms (A, B, C) per item, across both halves -- exactly what run_classify_probe
        # and run_territory_probe each spend per item below.
        n_calls = 3 * (len(classify_items) + len(territory_items))
        if not confirm("prompt_shift_probe", n_calls, MODEL_ID):
            print("declined -- no calls made")
            return None
        from .model import AnthropicModel  # lazy: tests never need the SDK or network

        model = AnthropicModel(model=MODEL_ID)
        raw_parse_classify = functools.partial(_raw_parse_classify, model)
        raw_parse_territory = functools.partial(_raw_parse_territory, model)

    # Resolved BEFORE either probe runs (not after, as the final result's timestamp used to be)
    # so the checkpoint file exists, and its path is known and printed, before the first real
    # call is made -- the founder's crash lost every already-paid-for call because nothing at
    # all was written until run() returned; a per-item checkpoint fixes that only if it starts
    # writing from item 1, not from whatever survives to the end.
    if now is None:
        now = datetime.now(timezone.utc)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = data_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.checkpoint.jsonl"
    print(f"checkpointing every item to {checkpoint_path} as it completes")

    classify_records, classify_failures = run_classify_probe(
        classify_items,
        model,
        raw_parse_classify,
        system_for=_classify_system_for,
        max_tokens=_CLASSIFY_MAX_TOKENS,
        on_item=functools.partial(_append_checkpoint, checkpoint_path, "classify"),
    )
    classify_rates = summarize_disagreement(classify_records, classify_failures, margin)

    territory_records, territory_failures = run_territory_probe(
        territory_items,
        model,
        raw_parse_territory,
        _MAP_TERRITORIES_SYSTEM,
        max_tokens=_CLASSIFY_MAX_TOKENS,
        on_item=functools.partial(_append_checkpoint, checkpoint_path, "territory"),
    )
    territory_rates = summarize_disagreement(territory_records, territory_failures, margin)

    result = Probe2Result(
        model_id=MODEL_ID,
        margin=margin,
        classify_corpus_source=classify_corpus_source,
        classify_records=classify_records,
        classify_failures=classify_failures,
        classify_rates=classify_rates,
        territory_corpus_source=territory_corpus_source,
        territory_records=territory_records,
        territory_failures=territory_failures,
        territory_rates=territory_rates,
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
    print(
        f"classify corpus source: {result.classify_corpus_source} "
        f"(attempted {result.classify_rates.attempted_n}, "
        f"comparable {result.classify_rates.comparable_n}, "
        f"failed {result.classify_rates.failed_n})"
    )
    print(
        f"classify refusal rate: {result.classify_rates.refusal_rate:.3f} "
        f"({result.classify_rates.refused_n}/{result.classify_rates.attempted_n})"
    )
    print(
        f"classify same-prompt disagreement: {result.classify_rates.same_prompt_disagreement:.3f} "
        f"(of {result.classify_rates.comparable_n} comparable items)"
    )
    print(
        f"classify new-vs-old disagreement: {result.classify_rates.new_vs_old_disagreement:.3f} "
        f"(of {result.classify_rates.comparable_n} comparable items)"
    )
    print(f"classify shift claimed: {result.classify_rates.shift_claimed}")
    print(
        f"territory corpus source: {result.territory_corpus_source} "
        f"(attempted {result.territory_rates.attempted_n}, "
        f"comparable {result.territory_rates.comparable_n}, "
        f"failed {result.territory_rates.failed_n})"
    )
    print(
        f"territory refusal rate: {result.territory_rates.refusal_rate:.3f} "
        f"({result.territory_rates.refused_n}/{result.territory_rates.attempted_n})"
    )
    print(
        f"territory same-prompt disagreement: {result.territory_rates.same_prompt_disagreement:.3f} "
        f"(of {result.territory_rates.comparable_n} comparable items)"
    )
    print(
        f"territory new-vs-old disagreement: {result.territory_rates.new_vs_old_disagreement:.3f} "
        f"(of {result.territory_rates.comparable_n} comparable items)"
    )
    print(f"territory shift claimed: {result.territory_rates.shift_claimed}")


if __name__ == "__main__":
    main()
