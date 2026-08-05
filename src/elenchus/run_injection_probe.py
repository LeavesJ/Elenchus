"""Entrypoint for the injection efficacy probe. The ONLY module here that touches the network,
and it never does so without a typed confirmation.

`classify`, `raw_parse`, `system_for`, and `old_user_for` are injected rather than hard-wired, so
every code path in `run()` stays provable against a fake model -- the same shape as
`run_prompt_shift_probe.py` and `run_push_screen_probe.py`. Real wiring lives in this module too
now (`_classify_system_for`, `_raw_parse`, `_classify`, `_build_model`): `run()` falls back to it
only when a caller leaves the corresponding parameter unset, so every existing test that supplies
its own fakes is unaffected and only an actual `run()` invocation with no overrides ever touches
`AnthropicModel`.

`_classify_system_for` mirrors `run_prompt_shift_probe._classify_system_for` exactly: it composes
`AnthropicModel.classify_response`'s system text by CALLING `load_prompt`, `_situation_block`, and
`_target_detail` -- the same building blocks that method calls -- rather than hand-copying their
assembly, so it cannot silently drift from what a real `classify_response` call sends. It is
payload-independent by construction: every payload in a run probes the SAME fixed `_EXPERIENCE`
and `_CODE`, never anything drawn from `Payload` itself. That independence is load-bearing, not
incidental -- `run()`'s artifact hashes `system_for(payloads[0])` as "the system every cell saw",
and that claim is only honest because no payload can move the system text.

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

import functools
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .content_loader import load_library, load_prompt
from .injection_probe import (
    CELLS,
    AdmissionResult,
    Payload,
    admits,
    attack_text,
    benign_text,
    derive_heading_tokens,
    draw_schedule,
    load_payloads,
    run_cells,
)
from .injection_scoring import (
    adjudicate,
    old_vs_new_refusal,
    refusal_by_cell,
    screen,
    tally,
    truncate_to_complete_draw,
)
from .model import (
    _CLASSIFY_MAX_TOKENS,
    _LEARNER_TEXT_REFUSAL_CAP,
    _PARAMS,
    ResponseClassification,
    _situation_block,
    _target_detail,
)
from .prompt_shift_probe import reconstruct_old_classify_response_user
from .prompt_text import labelled
from .run_push_screen_probe import _confirm
from .types import Regime

DEFAULT_DRAWS = 3
DEFAULT_SEED = 20260803
MODEL_ID = "claude-opus-5"

# The push text used to reconstruct the OLD (pre-indent) `classify_response` user message. The
# probe's own payloads carry no push text of their own -- only `substance`/`injection`/
# `semantic_only`, the learner side of the exchange -- so every cell in a run shares this one fixed
# push, matching `system_for` being shared across both arms of a payload (Task 8's contract).
_PUSH = "What is the mechanism that closes the gap you just named?"

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "injection_probe"
PAYLOAD_PATH = Path(__file__).resolve().parents[2] / "data" / "injection_payloads.yaml"

# The one fixed experience/frame every payload is classified against. Deliberately a SINGLE
# constant, not something each payload or call site chooses: `_classify_system_for`'s
# payload-independence (this module's whole validity condition, per its docstring) depends on
# every cell in a run composing the system prompt from the same experience and code, never one
# each payload picks for itself.
_EXPERIENCE_ID = "decision_under_stakes"
_KIND = "frame"


def _fixed_experience(experience_id: str):
    """Look the experience up by id rather than taking `load_library()[0]`: list order is an
    implementation detail of `content/`'s directory scan, not a contract, so indexing into it
    would make the fixed experience silently move if a file were added or renamed."""
    for exp in load_library():
        if exp.experience_id == experience_id and exp.regime is Regime.open_ended:
            return exp
    raise ValueError(f"open-ended experience {experience_id!r} not found in the library")


_EXPERIENCE = _fixed_experience(_EXPERIENCE_ID)
# `Rubric` itself validates `decision_frame` is one of `rubric.frames`' codes (types.py), so this
# is never a code `_target_detail` cannot resolve.
_CODE = _EXPERIENCE.rubric.decision_frame


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _classify_system_for(p: Payload) -> str:
    """Reproduces `AnthropicModel.classify_response`'s system composition (model.py) exactly, by
    calling the SAME building blocks that method calls (`load_prompt`, `_situation_block`,
    `_target_detail`) rather than hand-copying their assembly, so this can never silently drift
    from what the NEW arm actually sends. Mirrors `run_prompt_shift_probe._classify_system_for`.

    REVERT (T2 review): `3e81f72` moved `push` from `classify_response`'s user message into its
    system message and this mirror followed with a trailing `Push:` line. The founder reverted that
    collapse (see model.py's own comment on `classify_response`), so `push` is back in the user
    message and this system composition carries no `Push:` line again, matching the live method.

    `p` is accepted (matching `run_cells`'s `system_for: Callable[[Payload], str]` contract, and
    `admits`'s composed-prompt inputs) but never read: the system text depends only on the fixed
    `_EXPERIENCE`/`_CODE` under test, never on payload content. That independence is what this
    module's docstring and `tests/test_run_injection_probe.py` pin -- `run()`'s artifact hashes
    `system_for(payloads[0])` as if it spoke for every payload's run, which is only true because no
    payload can move this text. `stress` is never set here: this probe never sends the stress
    addendum, matching `classify_response`'s own `stress=False` default."""
    detail = _target_detail(_EXPERIENCE.rubric, _KIND, _CODE)
    return (
        load_prompt("response")
        + _situation_block(_EXPERIENCE)
        + f"\n\nMode: {_EXPERIENCE.rubric.mode.value}"
        + f"\nBinding constraint: {_EXPERIENCE.rubric.binding_constraint}"
        + f"\nTarget angle: {detail}"
    )


def _new_user_for(text: str) -> str:
    """Reproduces `AnthropicModel.classify_response`'s user composition (model.py, the
    `rendered = labelled(...); user = f"Push:\\n{push}\\n\\n{rendered}"` lines), using the SAME
    building block that method calls (`prompt_text.labelled`). Composes text only, never calls
    the model: the admission gate (`_check_admission`) must run and raise BEFORE any network call
    is even considered, so this cannot go through `classify` (which may be the real, paid-for
    `_classify` once wired) or `_build_model`. `push` is always `_PUSH` here, matching the fixed
    push every cell in a run shares (this module's docstring).

    IT IS A SECOND COPY, and two earlier claims about it were wrong. It said it mirrored
    `_classify_system_for`, importing a guarantee it did not have: that function's reproduction is
    cashed by a test comparing it against a system string captured off a REAL `classify_response`
    call, and this one had no such pin -- patching `classify_response` to raise left every test
    touching `_new_user_for` green. `test_new_user_for_matches_what_classify_response_actually_
    sends` is that missing pin and now exists. It also said "exactly", scoped to the two model.py
    lines it cites, silently skipping the `_LEARNER_TEXT_REFUSAL_CAP` raise BETWEEN them; the
    sendability check in `_check_admission` covers that gap rather than this function acquiring a
    raise it must not have.

    The copy remains a copy (defect D1, structural half unfixed): the OLD arm passes ONE
    `old_user_for` callable to both the gate and the sender, so what is screened IS what is sent,
    by construction. The NEW arm cannot do that without calling the model, which the gate must
    not do. Until a shared composer exists, the pinning test is what holds the two equal."""
    return f"Push:\n{_PUSH}\n\n{labelled('Student reply:', text)}"


def _check_admission(payloads: list[Payload], old_user_for, system_for) -> list[AdmissionResult]:
    """Run the offline admission filter (`injection_probe.admits`) over every payload, using the
    EXACT `old_user_for`/`system_for` callables `run()` was given (real defaults or a caller's
    fakes) to build the OLD rendering and the system text, and `_new_user_for` to build the attack
    and benign-baseline NEW renderings -- the same composition `classify_response` itself performs,
    reached without ever calling it.

    The heading set is derived per payload from `system_for(p)` and `baseline_new` ONLY --
    the system prompt and the BENIGN NEW rendering -- never from `old` or the attack `new`. Both
    of those carry attacker-supplied text at column 0 by construction (that is the vulnerability
    this probe tests), so folding either into `derive_heading_tokens` would let an attacker-chosen
    `<Label>:` token enter the "engine heading" set and get treated as legitimate template
    structure instead of the forgery it is. `baseline_new` is safe to derive from precisely
    because its underlying text (`benign_text(p)`) carries no injection for a heading to plant.

    Zero model calls. This is what lets `run()` call it before `confirm` -- an unadmitted corpus
    must never reach the cost guard, let alone the network."""
    results = []
    for p in payloads:
        old = old_user_for(p, attack_text(p))
        new = _new_user_for(attack_text(p))
        baseline_new = _new_user_for(benign_text(p))
        # SENDABILITY, checked here and not in `admits`. `admits` decides whether a payload
        # creates the STRUCTURAL hazard under test, which is a property of the text; this is a
        # property of the transport, and only this module knows about `model.py` at all.
        #
        # `classify_response` raises `ModelError` when its rendered user exceeds
        # `_LEARNER_TEXT_REFUSAL_CAP` (model.py), and `_new_user_for` reproduces the composition
        # WITHOUT that raise. A review executed the gap: a payload rendering to 21788 characters
        # was admitted `(oversized, True, '')`, cleared `confirm`, and then burned every A_new and
        # B_new draw as a refusal that `screen`'s rule 1 excluded downstream. Fail-safe for the
        # verdict, pure waste for the wallet, and it defeats this function's own docstring below
        # -- an UNSENDABLE corpus is exactly what must never reach the cost guard.
        #
        # The cap is imported, never restated: a second copy of a threshold is how the two
        # compositions drifted apart in the first place.
        rendered = max(len(new), len(baseline_new))
        if rendered > _LEARNER_TEXT_REFUSAL_CAP:
            results.append(
                AdmissionResult(
                    name=p.name,
                    admitted=False,
                    reason=(
                        f"new-form rendering is {rendered} chars, over "
                        f"_LEARNER_TEXT_REFUSAL_CAP ({_LEARNER_TEXT_REFUSAL_CAP}) -- "
                        "classify_response would refuse to send it"
                    ),
                )
            )
            continue
        headings = derive_heading_tokens(system_for(p), baseline_new)
        results.append(
            admits(p, old_user=old, new_user=new, baseline_new_user=baseline_new, headings=headings)
        )
    return results


def _raw_parse(model, *, system: str, user: str, output_format: type, max_tokens: int):
    """The OLD arm's raw parse. Mirrors `run_prompt_shift_probe._raw_parse_classify`: reaches
    `model._parse_required` directly rather than through `classify_response`, which composes its
    OWN new, indented user message -- exactly what the old-form cells (`A_old`/`B_old`/`D_old`)
    must not send. `_PARAMS` matches `classify_response`'s own reasoning-effort choice, so the
    two arms issue identical CALL PARAMETERS.

    THEY DO NOT DIFFER ONLY IN THE USER MESSAGE, and an earlier version of this docstring said
    they did. A review falsified it by execution: `classify_response` applies the evidence-anchor
    floor (model.py, after `_parse_required` returns) and this function does not, so with
    byte-identical user messages `_raw_parse` returns `mechanism_supplied=True` where
    `classify_response` returns False. The floor is a NEW-ARM-ONLY post-parse defense.

    That is defect D2 and it is UNFIXED here. It matters because the study's statistic is a
    paired OLD-minus-NEW difference and the floor only ever LOWERS new-arm landings, so every
    floor event is charged to the indent. The bias is one-signed: it cannot mask a real effect,
    only fabricate one. Executed on a NULL-TRUTH corpus -- true effect exactly zero, the model
    behaviourally identical in both arms -- the shipped scoring returned EFFECTIVE /
    significant_and_total, k=12, p=0.000244. DO NOT RUN A FOUR-ARM STUDY ON THIS UNTIL D2 IS
    FIXED. Nil impact on the completed 2026-08-04 run."""
    return model._parse_required(
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=output_format,
        **_PARAMS,
    )


def _classify(model, p: Payload, text: str) -> ResponseClassification:
    """The NEW arm: `classify_response` itself, which composes its own indented user message via
    `prompt_text.labelled` -- the exact code path under test. `p` is unused for the same reason
    `_classify_system_for` doesn't read it: every payload is classified against the one fixed
    `_EXPERIENCE`/`_CODE`, matching `run_cells`'s `classify: Callable[[Payload, str],
    ResponseClassification]` contract, which passes `p` whether or not a real implementation needs
    it."""
    return model.classify_response(_EXPERIENCE, _KIND, _CODE, _PUSH, text)


def _build_model():
    """Lazy: constructing `AnthropicModel` never imports the `anthropic` SDK or touches the
    network by itself (only `_get_client()`, reached from an actual call, does that), but the
    import stays inside this function so a test that never calls it still never needs the SDK
    installed -- the same convention `run_prompt_shift_probe.run`'s `model is None` branch uses."""
    from .model import AnthropicModel

    return AnthropicModel(model=MODEL_ID)


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

    if system_for is None:
        system_for = _classify_system_for

    # The admission gate, BEFORE the cost guard: an unadmitted corpus must never reach `confirm`,
    # let alone the network. Zero model calls (`_check_admission` composes text only), so this can
    # run unconditionally, ahead of any confirmation. A corpus that partly fails admission is an
    # authoring error, not something to silently shrink around -- shrinking the denominator without
    # anyone deciding to is exactly what Invariant-grade validity gates exist to prevent, so a
    # single rejection fails the whole run loud, naming every offender and its reason.
    admission = _check_admission(payloads, old_user_for, system_for)
    rejected = [r for r in admission if not r.admitted]
    if rejected:
        detail = "; ".join(f"{r.name} ({r.reason})" for r in rejected)
        raise ValueError(
            f"admission gate rejected {len(rejected)}/{len(admission)} payload(s): {detail}"
        )

    schedule = draw_schedule([p.name for p in payloads], draws=draws, seed=seed)
    if not confirm("injection_efficacy", len(schedule), model_id):
        print("not confirmed; no calls made")
        return None

    if classify is None or raw_parse is None:
        # Built only after confirmation succeeds, matching `run_prompt_shift_probe.run`'s
        # `model is None` branch: a declined confirmation must make zero calls, and constructing
        # the real callables before that gate would blur "no calls made" with "no callables built"
        # even though `_build_model()` itself never touches the network.
        model = _build_model()
        if classify is None:
            classify = functools.partial(_classify, model)
        if raw_parse is None:
            raw_parse = functools.partial(_raw_parse, model)

    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    ckpt = data_dir / f"{stamp}.checkpoint.jsonl"
    print(f"checkpointing every draw to {ckpt} as it completes")

    def _append(row):
        with ckpt.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row.model_dump(mode="json")) + "\n")

    rows = run_cells(
        payloads,
        schedule,
        classify=classify,
        raw_parse=raw_parse,
        system_for=system_for,
        old_user_for=old_user_for,
        max_tokens=_CLASSIFY_MAX_TOKENS,
        on_draw=_append,
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
        # Every reader sees that the admission gate ran, and what it concluded, not merely that
        # `len(payloads)` calls happened. `rejected` is always `[]` here -- `run()` already raised
        # above on the first rejection -- but the field stays because "the gate ran and admitted
        # everyone" is a claim distinct from "the gate never ran."
        "admission": {
            "results": [r.model_dump(mode="json") for r in admission],
            "rejected": [r.name for r in admission if not r.admitted],
        },
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
        # Spec section 9: refusal rate per cell, and the OLD-versus-NEW comparison reported
        # separately. Computed over `kept` (post-truncation), matching every other denominator
        # above -- the same draws `tally`/`screen`/`adjudicate` actually scored, not the raw,
        # possibly-ragged `rows` `run_cells` returned.
        "refusals": {
            "by_cell": {c: s.model_dump(mode="json") for c, s in refusal_by_cell(kept).items()},
            "old_vs_new": {
                a: s.model_dump(mode="json") for a, s in old_vs_new_refusal(kept).items()
            },
        },
    }
    path = data_dir / f"{stamp}.json"
    path.write_text(json.dumps(doc, indent=2))
    print(f"verdict: {verdict.verdict} ({verdict.reason})")
    if verdict.inflation_payloads:
        # Every inflation payload is excluded from the study by screen rule 2 (benign_twin), so
        # it can NEVER touch the verdict word above and is otherwise visible only inside the JSON
        # (`tallies`). Spec section 5 calls B_new "the only cell that could catch the indent
        # making a mechanism-free reply read as closed" -- an inflation finding that never reaches
        # the console is a real regression on the safety fix going unnoticed by anyone who only
        # reads stdout.
        print(
            f"benign inflation: {len(verdict.inflation_payloads)}/{len(payloads)} payload(s) "
            f"landed B_new without landing B_old: {verdict.inflation_payloads}"
        )
    print(f"wrote {path}")
    return path, doc


def main() -> None:
    """The documented entrypoint (`PYTHONPATH=src .venv/bin/python -m elenchus.run_injection_probe`)
    -- mirrors `run_prompt_shift_probe.main` / `run_push_screen_probe.main`'s shape: call `run()`
    with its real-wiring defaults, which returns `None` on a declined confirmation. Unlike those
    two siblings, `run()` here already prints its own summary as it executes (verdict, benign
    inflation, checkpoint path, written artifact path -- see above), so `main()` has nothing
    further to print; its job is solely to be the callable, guarded entrypoint the command line
    needs, which is what this module lacked before this fix (no `main`, no `__main__` guard, so
    the documented command imported the module and exited having done nothing)."""
    run()


if __name__ == "__main__":
    main()
