"""The server log is the only record of what the model calls cost and how often they were refused.

Every line these tests parse is produced by DRIVING THE REAL EMITTER through the REAL entrypoint
formatter -- never by hand-writing a string that looks like one. L-9: a green test over a
synthetic fixture can hide a dead production path, and this instrument's whole job is to read
what production actually wrote.
"""

import io
import logging

import pytest

from elenchus import call_log


def _capture(fn):
    """Run `fn` with a handler carrying the ENTRYPOINT'S OWN format attached to elenchus.model,
    and return the exact text that would have landed in <slug>/server.log."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(call_log.SERVER_LOG_FORMAT))
    logger = logging.getLogger("elenchus.model")
    logger.addHandler(handler)
    prior = logger.level
    logger.setLevel(logging.INFO)
    try:
        fn()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prior)
    return stream.getvalue()


class _FakeMessages:
    def create(self, **kwargs):
        return "created"

    def parse(self, **kwargs):
        return "parsed"


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessages()


def test_parses_a_timing_line_the_real_timing_shim_emitted():
    """The production path is _TimedMessages.create/parse -> _log.info('model_call %s %.2fs').
    Drives that wrapper for real (no network, no key -- it is a pure shim over a client) and
    parses what came out."""
    from elenchus.model import _TimedMessages

    text = _capture(
        lambda: (
            _TimedMessages(_FakeClient()).create(model="x"),
            _TimedMessages(_FakeClient()).parse(model="x"),
        )
    )

    calls = call_log.parse_calls(text.splitlines())
    assert [t.kind for t in calls.timings] == ["create", "parse"]
    assert all(t.seconds >= 0.0 for t in calls.timings)


class _Details:
    category = "general_harms"
    explanation = "declined to produce the requested content"


class _RefusedResponse:
    stop_reason = "refusal"
    parsed_output = None
    stop_details = _Details()


def test_parses_a_refusal_line_the_real_require_branch_emitted():
    """The production path is _require -> _log_refusal -> _log.warning('model refusal in %s: ...').
    Drives the real branch (which raises, by design) and parses what it logged on the way out."""
    from elenchus.model import ModelError, _require

    def drive():
        with pytest.raises(ModelError):
            _require(_RefusedResponse())

    calls = call_log.parse_calls(_capture(drive).splitlines())
    assert [(r.where, r.category) for r in calls.refusals] == [("_require", "general_harms")]


def test_a_clean_response_logs_no_refusal_so_the_numerator_cannot_be_inflated():
    """L-33, scope: _log_refusal early-returns unless stop_reason is actually 'refusal'. _require
    ALSO fires on parsed_output is None, so an unscoped log would record refusals that never
    happened and poison the count this instrument exists to produce."""
    from elenchus.model import ModelError, _require

    class _EmptyButNotRefused:
        stop_reason = "end_turn"
        parsed_output = None

    def drive():
        with pytest.raises(ModelError):
            _require(_EmptyButNotRefused())

    assert call_log.parse_calls(_capture(drive).splitlines()).refusals == []


def test_the_booted_entrypoint_emits_lines_this_parser_can_read(tmp_path):
    """THE GUARD THAT MATTERS (L-9). Everything above drives the emitters in-process with a
    handler this test attached. That proves the regexes match the emitters -- it does NOT prove
    the SHIPPING process writes anything a reader can find, which is the exact failure that hid
    here once already: the model_call lines logged at INFO, logging's last-resort handler dropped
    them, and the suite's caplog stayed green while the production process discarded the data.

    So: boot the REAL `elenchus.web.__main__` in a subprocess exactly as `serve_invitee.py` does,
    drive the REAL timing shim and the REAL refusal branch, and parse the actual bytes that reach
    stderr -- which is byte-for-byte what lands in <root>/<slug>/server.log."""
    import subprocess
    import sys
    import textwrap
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    driver = textwrap.dedent(
        """
        import elenchus.web.__main__  # noqa: F401  -- booting it IS the thing under test
        from elenchus.model import _TimedMessages, _log_refusal

        class M:
            def create(self, **k):
                return 1

            def parse(self, **k):
                return 2

        class C:
            messages = M()

        class D:
            category = "cyber"
            explanation = "nope"

        class R:
            stop_reason = "refusal"
            stop_details = D()

        t = _TimedMessages(C())
        t.create(model="x")
        t.parse(model="x")
        _log_refusal("_require", R())
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", driver],
        env={
            "PYTHONPATH": str(src),
            "PATH": "/usr/bin:/bin",
            "ELENCHUS_DB": str(tmp_path / "probe.db"),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr

    calls = call_log.parse_calls(out.stderr.splitlines())
    assert [t.kind for t in calls.timings] == ["create", "parse"], (
        f"the shipping process's own stderr did not yield timings: {out.stderr!r}"
    )
    assert [r.category for r in calls.refusals] == ["cyber"], (
        f"the shipping process's own stderr did not yield the refusal: {out.stderr!r}"
    )


def test_the_entrypoint_and_this_parser_read_one_format_constant():
    """Belt on the same seam: the format lives in exactly one place. Two literals -- one in the
    entrypoint's basicConfig and one here -- drift apart silently, and the symptom is an
    instrument that reports zero rather than an error."""
    entrypoint = (
        __import__("pathlib").Path(__file__).resolve().parents[1] / "src/elenchus/web/__main__.py"
    ).read_text()
    assert "SERVER_LOG_FORMAT" in entrypoint, (
        "the entrypoint carries its own format literal instead of call_log.SERVER_LOG_FORMAT"
    )


def _timing_text(pairs):
    """Real emitted lines for a chosen set of (kind, seconds) — driven through the real logger
    and the real format, never hand-written. `_TimedMessages` times a real clock, so a test that
    needs SPECIFIC durations has to log them directly; the shape is still the production one
    because it goes through `_log.info` with the production format string."""
    import logging as _logging

    def emit():
        log = _logging.getLogger("elenchus.model")
        for kind, secs in pairs:
            log.info("model_call %s %.2fs", kind, secs)

    return _capture(emit)


def test_stats_report_the_tail_a_timeout_has_to_clear():
    """S4 is measure-then-pick: the decision is a client timeout, so the numbers that matter are
    the TAIL, per kind. `parse` carries structured output and adaptive thinking and is the slow
    one; a timeout picked off a blended median would cut it off."""
    text = _timing_text(
        [("create", 1.0), ("create", 2.0), ("parse", 10.0), ("parse", 20.0), ("parse", 60.0)]
    )
    calls = call_log.parse_calls(text.splitlines())

    by_kind = call_log.stats(calls.timings)
    assert by_kind["parse"].count == 3
    assert by_kind["parse"].max == 60.0
    assert by_kind["create"].max == 2.0
    assert by_kind["parse"].median == 20.0


def test_percentiles_use_nearest_rank_because_interpolation_is_false_precision_here():
    """Nearest-rank on the sorted sample, deliberately: three dogfood sittings produce tens of
    calls, not thousands, and an interpolated p95 over ~30 points invents a number no call ever
    took. Every percentile this reports IS an observed duration."""
    text = _timing_text([("parse", float(n)) for n in range(1, 21)])
    calls = call_log.parse_calls(text.splitlines())

    s = call_log.stats(calls.timings)["parse"]
    assert s.p95 == 19.0  # ceil(0.95*20) = 19th of 20
    assert s.p95 in [t.seconds for t in calls.timings]


def test_report_names_the_distribution_it_was_measured_on():
    """Invariant 7: a safety or latency property is a property of gate TIMES DISTRIBUTION. A
    timeout chosen from founder dogfood is not a timeout justified for invitee traffic, and the
    printed number has to carry that or it will be quoted without it."""
    text = _timing_text([("parse", 12.0), ("create", 3.0)])
    out = call_log.report(
        call_log.parse_calls(text.splitlines()), sources=["data/tenants/rehearsal/server.log"]
    )

    assert "data/tenants/rehearsal/server.log" in out  # WHICH log, not just "the log"
    assert "2 model calls" in out


def test_report_discloses_that_the_log_carries_no_timestamps():
    """The entrypoint's format is name/level/message with NO asctime, and serve_invitee APPENDS
    across restarts. So one file can hold several runs with nothing to separate them, and no call
    can be tied to a sitting or a wall-clock hour. A reader who does not know that will read a
    week's file as one session."""
    out = call_log.report(call_log.parse_calls(_timing_text([("parse", 1.0)])), sources=["x.log"])

    assert "no timestamp" in out.lower()
    assert "append" in out.lower()  # ...and therefore may span several runs


def test_report_says_a_failed_call_is_still_timed():
    """_TimedMessages times in a `finally`, so a call that RAISED contributes its duration. For a
    timeout decision that is the right behaviour and the wrong thing to leave unsaid: the tail may
    be a call that died, not a call that was served."""
    out = call_log.report(call_log.parse_calls(_timing_text([("parse", 1.0)])), sources=["x.log"])

    assert "raised" in out.lower() or "failed" in out.lower()


def test_the_script_reads_a_real_tenant_tree_end_to_end(tmp_path):
    """The second real caller, exercised the way it will actually be run at 9am: over the
    <root>/<slug>/server.log layout serve_invitee.py creates."""
    import subprocess
    import sys
    from pathlib import Path

    tenants = tmp_path / "tenants"
    for slug, text in {
        "rehearsal": _timing_text([("parse", 27.0), ("create", 4.0)]),
        "invitee2": _timing_text([("parse", 9.0)]),
    }.items():
        log = tenants / slug / "server.log"
        log.parent.mkdir(parents=True)
        log.write_text(text)

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "call_report.py"), str(tenants)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"},
        timeout=60,
    )

    assert out.returncode == 0, out.stderr
    assert "rehearsal" in out.stdout and "invitee2" in out.stdout  # names the distribution
    assert "27.00s" in out.stdout  # the tail a timeout has to clear
    assert "no timestamp" in out.stdout.lower()


def test_the_script_fails_loudly_when_pointed_at_a_tree_with_no_logs(tmp_path):
    """A typo'd root printing "0 calls" is indistinguishable from a real reading of zero, and the
    difference decides whether the 9am measurement happened at all. Same failure discipline
    retention.read_visit_starts already applies to a missing tenant file."""
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    out = subprocess.run(
        [sys.executable, str(src.parent / "scripts" / "call_report.py"), str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin"},
        timeout=60,
    )

    assert out.returncode != 0
    assert "server.log" in out.stderr


def _refusal_text(wheres):
    import logging as _logging

    def emit():
        log = _logging.getLogger("elenchus.model")
        for where in wheres:
            log.warning(
                "model refusal in %s: category=%s explanation=%s", where, "general_harms", "no"
            )

    return _capture(emit)


def test_the_report_never_prints_a_refusal_RATE():
    """Four independently verified reasons the ratio is not computable from this log
    (emission audit, 2026-08-31), so the instrument must refuse it rather than print a number
    with footnotes that get dropped the moment it is quoted:

      1. `_parse_required` retries, so ONE logical call can emit TWO refusal lines.
      2. `model_call` is emitted from a `finally`, so calls that never reached the API — connection
         error, 401 — sit in the denominator and can never contribute to the numerator.
      3. The Anthropic SDK retries up to 2 times INSIDE the timed region, so one `model_call` line
         can cover three HTTP requests.
      4. `model_call` is INFO and the refusal is WARNING, so any log written without the
         entrypoint's config has the numerator and no denominator at all.
    """
    calls = call_log.parse_calls(
        (_timing_text([("parse", 3.0)]) + _refusal_text(["_require"])).splitlines()
    )
    out = call_log.report(calls, sources=["x.log"])

    import re as _re

    assert "%" not in out, "a percentage appeared; every one of the four reasons above forbids it"
    # no computed ratio in any form: "0.25", "1/4", "1 in 4", "one per N calls"
    assert not _re.search(r"\b\d+\s*/\s*\d+\b", out), "a ratio was printed"
    assert not _re.search(r"\b0\.\d+\b", out), "a fraction was printed"
    # and it says so, so the absence reads as a decision rather than an oversight
    assert "NO REFUSAL RATE" in out


def test_refusals_are_reported_by_what_they_COST_not_just_by_count():
    """The branch name is the signal ledgered item 1 actually asked for. `_parse_required` logged
    a first attempt that was then RETRIED — the learner may never have seen it. `_require` logged
    a FINAL refusal, which raised and killed the segment. `concierge_turn` is S1's fail-safe
    branch, which returns "" and serves a held static. Pooling them into one integer answers a
    different question than the one the safety floor needs."""
    calls = call_log.parse_calls(
        _refusal_text(["_parse_required", "_require", "concierge_turn"]).splitlines()
    )
    out = call_log.report(calls, sources=["x.log"])

    assert "_parse_required" in out and "_require" in out and "concierge_turn" in out
    assert "retried" in out.lower()
    assert "segment" in out.lower()


def test_refusals_with_no_timings_are_named_as_a_broken_log_not_a_catastrophic_rate():
    """model_call is INFO, the refusal is WARNING, and only the web entrypoint configures logging.
    cli.py and the probe scripts spend real money with no config, so their stderr carries refusals
    and NO timings. A reader who divides gets n/0; a reader who eyeballs sees "all refusals"."""
    out = call_log.report(
        call_log.parse_calls(_refusal_text(["_require"]).splitlines()), sources=["x.log"]
    )

    assert "without the entrypoint" in out.lower() or "no logging config" in out.lower()


def test_latency_disclosure_names_the_sdk_retry_contamination():
    """DEFAULT_MAX_RETRIES is 2 in anthropic 0.120.2 and the retries happen INSIDE `fn(**kwargs)`,
    i.e. inside the timed region. So a logged duration can span three HTTP attempts plus the
    SDK's exponential backoff sleeps. A client timeout picked off this tail without knowing that
    is picked off backoff, not off model time."""
    out = call_log.report(
        call_log.parse_calls(_timing_text([("parse", 30.0)]).splitlines()), sources=["x.log"]
    )

    assert "backoff" in out.lower() or "retries" in out.lower()
