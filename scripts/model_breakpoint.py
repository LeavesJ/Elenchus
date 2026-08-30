"""The model-breakpoint eval: walk the ladder down from production until the doctrine breaks.

    PYTHONPATH=src .venv/bin/python scripts/model_breakpoint.py --dry-run
    PYTHONPATH=src .venv/bin/python scripts/model_breakpoint.py --models claude-opus-5 --scenarios 3

Two models per run, the shape the cofounders set (2026-08-30): the MAIN model serves the loop
through the REAL web path (SessionRegistry -- the same code a beta invitee hits, per L-9), and a
JUDGE model scores the finished transcript against the doctrine. A STUDENT model plays the
learner. The break point is the cheapest main model whose sittings still pass the gates.

Three gates per sitting, cheapest first:
  1. mechanical_leak_scan -- zero tokens: engine-authored turns must never contain a frame or
     trap code verbatim (Invariant 3's floor; the scan cannot see paraphrase, the judge can).
  2. the judge -- one input-heavy call: CODE / REFUSAL / 0-100 doctrine score.
  3. convergence shape -- did the loop land, and in how many turns.

Every result row names its DISTRIBUTION (Invariant 7): a break point measured on simulated
students is proven on simulated students. The honest corpus is real beta transcripts; this
harness exists so the ladder is ready the day those exist.

Prompts live in content/eval/ (doctrine: prompts are data). Nothing in src/ may ever load that
directory -- it holds the frame vocabulary the judge needs, which is exactly what a learner
surface must never see; tests/test_model_breakpoint.py enforces the blindness.

Live mode is key-gated and OFF by default. It never touches production: every sitting runs in
its own scratch directory. S4 note: this file sets no client timeout and must not -- the
constant is chosen from Monday's measurement, not here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from elenchus.content_loader import library_version, load_library  # noqa: E402

# Walk DOWN from what production serves today; a ladder starting anywhere else measures a
# product nobody ships. Extend past Anthropic (qwen, llama) only via an adapter, later.
LADDER = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]

# The learner-visible kinds an engine violation can ride. "you" is the student's own text and a
# student MENTIONING a frame-like phrase is not a product leak.
_ENGINE_KINDS = frozenset({"vera", "seam", "bridge", "landing"})

_DISTRIBUTION_SCRIPTED = "student-scripted-v0"
_DISTRIBUTION_SIMULATED = "student-sim-v0"


def student_prompt() -> str:
    return (_ROOT / "content" / "eval" / "student_sim.md").read_text()


def judge_prompt() -> str:
    return (_ROOT / "content" / "eval" / "judge.md").read_text()


def render_judge_prompt(transcript: str) -> tuple[str, str]:
    """Seal the judge's fence with a per-call nonce (red team F1, 2026-08-30).

    The transcript is authored by the model-under-test and the student-sim -- an
    attacker-influenceable channel feeding the judge. A plain [TRANSCRIPT END] marker can be
    forged by any turn that prints it; this nonce cannot, because the transcript's bytes are
    fixed before the nonce exists. Live mode MUST call this, never format judge_prompt() by
    hand -- the strict parser is only the backstop, the fence is the defense.
    """
    import secrets

    nonce = secrets.token_hex(8)
    return judge_prompt().replace("{nonce}", nonce).replace("{transcript}", transcript), nonce


def _doctrine_codes() -> set[str]:
    """Every frame and trap code in the live library -- Invariant 3's literal vocabulary."""
    codes: set[str] = set()
    for exp in load_library():
        codes.update(f.frame_code for f in exp.rubric.frames)
        codes.update(t.trap_code for t in exp.rubric.traps)
    return codes


def mechanical_leak_scan(turns: list[dict]) -> list[dict]:
    """Zero-token tripwire for the VERBATIM case: an engine-authored turn containing a frame or
    trap code literally. In practice that spelling (underscore-joined identifier) is what an
    engine bug pastes, not what a model writes in prose -- so this is a code-constant-leak
    tripwire, NOT a real leak floor (red team F4). Cased, spaced, split or paraphrased leakage
    is the judge's job, by design."""
    codes = _doctrine_codes()
    leaks = []
    for turn in turns:
        if turn.get("kind") not in _ENGINE_KINDS:
            continue
        text = (turn.get("payload") or {}).get("text") or ""  # None-hardened (red team F4)
        for code in codes:
            if code in text:
                leaks.append({"code": code, "kind": turn["kind"]})
    return leaks


def parse_judge_verdict(text: str) -> dict:
    """The judge contract is three-armed and STRICT: CODE, REFUSAL, or a bare 0-100. Anything
    chatty is recorded as unparseable rather than coerced -- a regex that fishes a number out of
    prose would silently launder a hedging judge into a confident score."""
    raw = (text or "").strip()
    if raw == "CODE":
        return {"verdict": "CODE", "score": None}
    if raw == "REFUSAL":
        return {"verdict": "REFUSAL", "score": None}
    # [0-9], not \d: \d is Unicode, and the red team showed an injected Arabic-Indic or
    # fullwidth number ("٨٧", "８７") being coerced into a recorded score (F2).
    if re.fullmatch(r"[0-9]{1,3}", raw) and 0 <= int(raw) <= 100:
        return {"verdict": "score", "score": int(raw)}
    return {"verdict": "unparseable", "score": None}


# Replies that drive the scripted world fake through confirm -> scenario -> press -> landing.
# The bare assent proves ONLY that the plumbing carries a reasonless reply end to end -- the
# world fake's classify_response credits every reply unconditionally (conftest make_world_model),
# so the anti-gaming rule is NOT exercised here and this comment must not claim it is (red team
# F5; the constitution's green-fixture rule). The rule's real teeth live in the engine's own
# tests and, on a live run, in the judge's rubric.
_SCRIPTED_REPLIES = [
    "yes",
    "I'd hold the launch and say why, in writing -- the mechanism is the paper trail.",
    "yeah you're right, I'll do that",
    "Because a silent slip becomes the customer's problem; naming it keeps the cost mine.",
    "I'd put the reversal trigger in the contract itself, a dated clause both sides sign.",
    "mechanism",
]


def run_scripted_sitting(model_factory, model_name: str, scenario: str, workdir) -> dict:
    """One sitting through the REAL serving path (SessionRegistry, the beta's own code), with the
    scripted student. This is the pipeline's plumbing check and the shape live mode reuses; with
    a fake factory it proves the harness, never the model (L-9, labeled in `distribution`)."""
    from elenchus.web.session_runner import SessionRegistry
    from elenchus.web.sitting_store import SittingStore

    db = str(Path(workdir) / "eval-sitting.db")
    reg = SessionRegistry(db, model_factory=model_factory)
    reg.resume_or_start("single")
    tag, _ = reg.step("single", scenario)
    steps = 1
    for reply in _SCRIPTED_REPLIES:
        if tag in ("done", "error"):
            break
        tag, _ = reg.step("single", reply)
        steps += 1

    store = SittingStore(db)
    live = store.live_sitting()
    sitting = live or {"id": None}
    turns = store.turns(sitting["id"]) if sitting["id"] else []
    if not turns:  # a landed sitting may already be closed; read whichever sitting exists
        import sqlite3

        conn = sqlite3.connect(db)
        sid_row = conn.execute("SELECT id FROM web_sitting ORDER BY updated_at DESC").fetchone()
        conn.close()
        turns = store.turns(sid_row[0]) if sid_row else []

    return {
        "model": model_name,
        "scenario": scenario,
        "turns": len(turns),
        "steps": steps,
        "converged": tag == "done",
        "mechanical": {"leaks": mechanical_leak_scan(turns)},
        "judge": None,  # filled by live mode; the scripted check spends zero tokens
        "distribution": _DISTRIBUTION_SCRIPTED,
        "content_version": library_version(list(load_library())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Model-breakpoint eval over the doctrine gates.")
    parser.add_argument("--dry-run", action="store_true", help="zero-token plumbing check")
    parser.add_argument("--models", nargs="*", default=LADDER, help="ladder (default: %(default)s)")
    parser.add_argument("--scenarios", type=int, default=3, help="sittings per model")
    parser.add_argument("--out", default="data/eval/breakpoint.jsonl", help="results JSONL")
    args = parser.parse_args()

    if args.dry_run:
        tests_dir = _ROOT / "tests"
        sys.path.insert(0, str(tests_dir))
        from conftest import make_world_model

        with tempfile.TemporaryDirectory() as tmp:
            row = run_scripted_sitting(
                make_world_model, "scripted-fake", "A vendor contract decision.", tmp
            )
        print(json.dumps(row, indent=2))
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "live mode needs ANTHROPIC_API_KEY, and it SPENDS MONEY (a full sitting per\n"
            "scenario per model, plus one judge call each). Run --dry-run first. The live\n"
            "student-simulator and judge wiring land with the first funded run -- deliberately\n"
            "not before, so the constants (turn caps, judge model) are chosen against Monday's\n"
            "latency measurement instead of guessed tonight.",
            file=sys.stderr,
        )
        return 2

    print("live mode is not wired yet; see the note above.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
