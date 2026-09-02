"""What the server log says about the model calls: how long they took, and how often they were refused.

Two numbers the beta cannot be read without, and until now nothing read either one.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# The entrypoint's logging format, owned HERE so the emitter and the reader cannot drift apart.
# Two real callers: elenchus.web.__main__ configures logging with it, and this module's parser
# is written against exactly what it produces. A format literal duplicated at both ends is the
# failure this constant exists to make impossible.
SERVER_LOG_FORMAT = "%(name)s %(levelname)s %(message)s"

# `search`, not `match`, and anchored only at the RIGHT: uvicorn attaches its own handlers to the
# root logger independently of the entrypoint's basicConfig, so a record can reach server.log with
# a prefix this module does not control. Anchoring on the left would silently drop every line the
# day that prefix changes -- and a parser that silently reads zero looks exactly like a quiet week.
# What a refusal on each branch actually cost the learner. `_log_refusal`'s `where` is the only
# thing in the log that distinguishes them, and pooling them into one integer answers a different
# question than the one the safety floor needs (ledgered item 1, 2026-08-30).
_REFUSAL_BRANCHES = {
    "_parse_required": "_parse_required = a FIRST attempt that was then retried; the learner may never have seen it.",
    "_require": "_require = a FINAL refusal; it raised, and the segment died.",
    "concierge_turn": 'concierge_turn = S1\'s fail-safe branch; it returned "" and a held static was served.',
}

_TIMING = re.compile(r"model_call (\S+) ([0-9]+\.[0-9]+)s\s*$")
_REFUSAL = re.compile(r"model refusal in (\S+?): category=(\S*) explanation=(.*)$")
# Our OWN ceiling firing, which is not the same event as Anthropic's classifier declining. One is
# a doctrine signal and one is an operations signal, and pooling them would answer neither.
_BUDGET = re.compile(r"spend budget refused a (\S+) call")


@dataclass(frozen=True)
class Timing:
    kind: str
    seconds: float


@dataclass(frozen=True)
class Refusal:
    where: str
    category: str
    explanation: str


@dataclass
class ModelCalls:
    timings: list[Timing] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    budget_refusals: list[str] = field(default_factory=list)


def parse_calls(lines) -> ModelCalls:
    calls = ModelCalls()
    for line in lines:
        # Refusal FIRST. Its `explanation` is classifier-authored free text and can end in
        # anything, including a model_call-shaped tail; the timing regex is unanchored on the
        # left and would claim that line as a billed call and drop the refusal -- a wrong count,
        # silently, in both headline numbers (pre-merge review, 2026-09-02). A timing line can
        # never contain "model refusal in", so this order is safe in one direction only.
        m = _REFUSAL.search(line)
        if m:
            calls.refusals.append(
                Refusal(where=m.group(1), category=m.group(2), explanation=m.group(3).strip())
            )
            continue
        m = _BUDGET.search(line)
        if m:
            calls.budget_refusals.append(m.group(1))
            continue
        m = _TIMING.search(line)
        if m:
            calls.timings.append(Timing(kind=m.group(1), seconds=float(m.group(2))))
    return calls


@dataclass(frozen=True)
class Stats:
    """One kind's observed durations. Every field is an OBSERVED value, never an interpolated one.

    Nearest-rank percentiles on the sorted sample: three dogfood sittings produce tens of calls,
    not thousands, and an interpolated p95 over ~30 points reports a duration no call ever took.
    A timeout picked off an invented number is picked off nothing.
    """

    count: int
    median: float
    p95: float
    max: float


def _nearest_rank(ordered: list[float], q: float) -> float:
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def stats(timings: list[Timing]) -> dict[str, Stats]:
    """Per KIND, because the kinds are not one distribution. `parse` carries structured output and
    adaptive thinking; `create` does not. A timeout picked off the two blended together is picked
    off a distribution nothing samples from (Invariant 7)."""
    by_kind: dict[str, list[float]] = {}
    for t in timings:
        by_kind.setdefault(t.kind, []).append(t.seconds)
    out = {}
    for kind, secs in by_kind.items():
        ordered = sorted(secs)
        out[kind] = Stats(
            count=len(ordered),
            median=_nearest_rank(ordered, 0.5),
            p95=_nearest_rank(ordered, 0.95),
            max=ordered[-1],
        )
    return out


def report(calls: ModelCalls, sources: list[str]) -> str:
    """The printed block a timeout decision gets made from, with every limit that decision
    inherits printed beside it rather than left for the reader to know.

    Two real callers: `scripts/call_report.py` and `tests/test_call_log.py`.
    """
    lines = [
        "MODEL CALL REPORT",
        "",
        f"read from: {', '.join(sources)}",
        f"{len(calls.timings)} model call{'' if len(calls.timings) == 1 else 's'}, "
        f"{len(calls.refusals)} refusal{'' if len(calls.refusals) == 1 else 's'}",
        "",
    ]

    by_kind = stats(calls.timings)
    if by_kind:
        lines.append(f"{'kind':<10}{'n':>5}{'median':>10}{'p95':>10}{'max':>10}")
        for kind in sorted(by_kind):
            st = by_kind[kind]
            lines.append(f"{kind:<10}{st.count:>5}{st.median:>9.2f}s{st.p95:>9.2f}s{st.max:>9.2f}s")
        lines.append("")

    if calls.budget_refusals:
        lines += [
            f"the per-process spend ceiling refused {len(calls.budget_refusals)} call(s). That is "
            "OUR bound firing, not the model declining -- either a room is being driven far "
            "harder than a sitting needs, or the ceiling is set too low for real use.",
            "",
        ]

    if calls.refusals:
        seen: dict[str, int] = {}
        for r in calls.refusals:
            seen[f"{r.where}/{r.category}"] = seen.get(f"{r.where}/{r.category}", 0) + 1
        lines.append("refusals by branch/category (the branch is what the refusal COST):")
        lines += [f"  {k}: {n}" for k, n in sorted(seen.items())]
        lines += [
            "",
            f"  {_REFUSAL_BRANCHES['_parse_required']}",
            f"  {_REFUSAL_BRANCHES['_require']}",
            f"  {_REFUSAL_BRANCHES['concierge_turn']}",
        ]
        lines.append("")
        if not calls.timings:
            lines += [
                "  NOTE: refusals with ZERO timings means this log was written WITHOUT the",
                "  entrypoint's logging config -- the refusal logs at WARNING and survives the",
                "  last-resort handler, the timing logs at INFO and does not. cli.py and the probe",
                "  scripts spend real money in exactly that state. This is a missing denominator,",
                "  NOT a refusal on every call.",
                "",
            ]

    lines += [
        "WHY THERE IS NO REFUSAL RATE HERE",
        "  Four verified reasons the ratio is not computable from this log, so it is not printed:",
        "  1. `_parse_required` retries, so ONE logical call can emit TWO refusal lines.",
        "  2. `model_call` is emitted from a finally, so a call that never reached the API (a",
        "     connection error, a 401) is in the denominator and can never be in the numerator.",
        "  3. The Anthropic SDK retries internally INSIDE the timed region, so one `model_call`",
        "     line can cover up to three HTTP requests.",
        "  4. The two lines log at different levels, so a log written without the entrypoint's",
        "     config carries the numerator and none of the denominator.",
        "  What IS countable: the branch tallies above. Also note these count only stop_reason ==",
        "  'refusal', i.e. Anthropic's own safety classifier. A model that declines in ORDINARY",
        "  PROSE returns end_turn and is invisible here.",
        "",
        "WHAT THIS NUMBER IS NOT",
        "  - Not a property of invitee traffic. A latency or refusal figure is a property of",
        "    gate TIMES DISTRIBUTION (Invariant 7); name the sittings above before quoting it.",
        "  - The log carries NO timestamp: the entrypoint formats name/level/message only, and",
        "    serve_invitee APPENDS across restarts. One file may span several runs, and no call",
        "    here can be tied to a sitting, a learner, or an hour.",
        "  - A call that RAISED is still timed (_TimedMessages times in a finally), so the tail",
        "    may be a call that failed rather than one that was served. For picking a timeout",
        "    that is the right sample; for quoting 'how long a turn takes' it is not.",
        "  - A duration can include the SDK's OWN retries and their exponential backoff sleeps:",
        "    anthropic retries up to DEFAULT_MAX_RETRIES times inside the call this wrapper",
        "    times. So the tail may be backoff, not model time -- which is still the right",
        "    sample for a CLIENT timeout, and the wrong one for 'how fast is the model'.",
    ]
    return "\n".join(lines)
