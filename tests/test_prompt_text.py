"""Tests for the learner text boundary seam (`prompt_text.py`).

`bulleted`/`labelled` now have real callers in `model.py` and `forge.py` (tasks 2-4). The
load-bearing test in the first half of this file is the column-0 property test, not the example
tests: it proves no byte the learner supplies can ever open a line at column 0 of the composed
prompt, over the full separator matrix `str.splitlines()` recognises, using a private-use-area
alphabet (U+E000+) the composer's own template text never contains, so any payload character
surviving at column 0 is unambiguous proof of a leak, not a coincidence of overlapping alphabets.

The second half (task 5) is a different kind of test: it reads the SOURCE of `model.py` and
`forge.py` rather than calling anything, to enforce that a known learner-text variable at a known
compose site is never interpolated straight into an f-string, bypassing the seam above. See that
section's own docstring for what it can and cannot catch.
"""

import re
from pathlib import Path

import pytest

from elenchus.prompt_text import LEARNER_INDENT, bulleted, labelled

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Every line-break character/sequence str.splitlines() recognises. \n, \r\n, and \r are the
# ordinary ones; the rest (\v \f \x1c \x1d \x1e \x85 U+2028 U+2029) are the ones a naive
# text.split("\n") would silently miss. Built with chr() rather than literal source characters
# so the separator being tested never has to sit, raw, inside this file.
_LINE_BREAKS = [
    "\n",
    "\r\n",
    "\r",
    chr(0x0B),  # \v, vertical tab
    chr(0x0C),  # \f, form feed
    chr(0x1C),  # file separator
    chr(0x1D),  # group separator
    chr(0x1E),  # record separator
    chr(0x85),  # NEL
    chr(0x2028),  # LINE SEPARATOR
    chr(0x2029),  # PARAGRAPH SEPARATOR
]

# Learner content drawn from the private-use area: a range the composer's own bullet markers,
# indents, and labels never contain. Any of these characters surviving as the leading
# non-whitespace character of an output line is unambiguous: it can only have come from the
# learner's payload, never from this module's own template text.
_PAYLOAD = [chr(0xE000 + i) for i in range(6)]

# The totality matrix the brief specifies: empty string, whitespace only, a leading newline, a
# string of only newlines, \r\n, bare \r, a tab, and every splitlines()-recognised separator.
_TOTALITY_MATRIX = [
    "",
    "   ",
    "\nrest",
    "\n\n\n",
    "\r\n",
    "\r",
    "\t",
    *_LINE_BREAKS,
]


def _joined_with(sep: str) -> str:
    """Every payload character on its own logical line, joined by `sep`."""
    return sep.join(_PAYLOAD)


def _leading_nonspace_chars(rendered: str) -> list[str]:
    """The leading character of every line of `rendered`, split on the wire's own separator
    ("\\n"), that begins with a non-whitespace character. Empty lines and lines starting with
    whitespace are excluded because they can never carry a column-0 leak."""
    out = []
    for line in rendered.split("\n"):
        if line and not line[0].isspace():
            out.append(line[0])
    return out


# ---------------------------------------------------------------------------
# Column-0 property: no learner byte ever opens a line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sep", _LINE_BREAKS)
def test_bulleted_no_payload_byte_reaches_column_0(sep):
    item = _joined_with(sep)
    rendered = bulleted((item,))
    leaders = _leading_nonspace_chars(rendered)
    assert not any(char in _PAYLOAD for char in leaders)


@pytest.mark.parametrize("sep", _LINE_BREAKS)
def test_labelled_no_payload_byte_reaches_column_0(sep):
    text = _joined_with(sep)
    rendered = labelled("Student reply:", text)
    leaders = _leading_nonspace_chars(rendered)
    assert not any(char in _PAYLOAD for char in leaders)


def test_bulleted_no_payload_byte_reaches_column_0_across_multiple_items():
    items = tuple(_joined_with(sep) for sep in _LINE_BREAKS)
    rendered = bulleted(items)
    leaders = _leading_nonspace_chars(rendered)
    assert not any(char in _PAYLOAD for char in leaders)


# ---------------------------------------------------------------------------
# splitlines() vs a naive "\n" split: separators other than \n / \r\n / \r must still be
# recognised as line breaks and indented, not left glued to the following payload word.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sep", _LINE_BREAKS)
def test_bulleted_indents_every_splitlines_recognised_break(sep):
    item = f"{_PAYLOAD[0]}{sep}{_PAYLOAD[1]}"
    rendered = bulleted((item,))
    lines = rendered.split("\n")
    assert lines[0] == f"  - {_PAYLOAD[0]}"
    assert f"{LEARNER_INDENT}{_PAYLOAD[1]}" in lines


@pytest.mark.parametrize("sep", _LINE_BREAKS)
def test_labelled_indents_every_splitlines_recognised_break(sep):
    text = f"{_PAYLOAD[0]}{sep}{_PAYLOAD[1]}"
    rendered = labelled("Student reply:", text)
    lines = rendered.split("\n")
    assert lines[0] == "Student reply:"
    assert lines[1] == f"{LEARNER_INDENT}{_PAYLOAD[0]}"
    assert f"{LEARNER_INDENT}{_PAYLOAD[1]}" in lines


# ---------------------------------------------------------------------------
# Byte-stability: the property that makes `bulleted` safe to drop into an already-tuned prompt
# ---------------------------------------------------------------------------


def test_bulleted_single_line_item_is_byte_identical_to_the_old_inline_form():
    assert bulleted(("ARGUED HERE",)) == "  - ARGUED HERE"


def test_bulleted_empty_item_list_renders_empty_string():
    assert bulleted(()) == ""


def test_labelled_single_line_input_differs_from_the_bare_form_it_replaces():
    """Unlike `bulleted`, `labelled` is NOT byte-stable on single-line input: this is documented
    in its docstring and is exactly why the graded sites that use it get their own task."""
    label = "Student reply:"
    text = "ARGUED HERE"
    bare = f"{label}\n{text}"
    rendered = labelled(label, text)
    assert rendered != bare
    assert rendered == f"{label}\n{LEARNER_INDENT}{text}"


def test_labelled_empty_label_still_indents_the_text():
    assert labelled("", "x") == f"\n{LEARNER_INDENT}x"


# ---------------------------------------------------------------------------
# Totality: neither function raises, over the full matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", _TOTALITY_MATRIX)
def test_bulleted_never_raises(text):
    bulleted((text,))


@pytest.mark.parametrize("text", _TOTALITY_MATRIX)
def test_labelled_never_raises(text):
    labelled("Label:", text)


# ---------------------------------------------------------------------------
# Task 5: the enforcement test — a tenth site cannot skip the seam quietly
#
# Style: textual, source-reading, following `tests/test_confirming_door.py`'s
# `_fn`/`_strip_comments` pair (extract a function's body by indentation off the raw file text,
# strip noise, then regex/substring-check the body) — the established way this repo enforces an
# invariant by reading source rather than exercising it (`test_confirming_door.py`'s
# `test_a_topic_correction_asks_instead_of_asserting` etc; also
# `tests/test_wx_law_static.py`, `tests/test_web_api.py`'s banned-phrase scans). No test in this
# repo uses `ast` for this kind of guard (grepped `tests/` and `src/` for `ast.parse`/`ast.walk`
# before choosing) and the same read-and-slice-the-source style already covers every other
# structural invariant here, so this follows suit rather than introducing an AST-based style with
# no precedent. A regex is also the more auditable choice for the specific thing being checked —
# "does `{varname}` appear inside braces" reads directly off the pattern, where an AST walk over
# `JoinedStr`/`FormattedValue` nodes would hide the same check behind an extra layer of API a
# future author has to learn before they can trust what it does or does not cover.
#
# WHAT THIS CATCHES, HONESTLY:
#
# A known learner-text variable, in a KNOWN function this guard has been told to watch, appearing
# literally inside `{...}` braces in that function's body (an f-string interpolation slot) with no
# call to `prompt_text.bulleted`/`labelled`/`indent_after_first` (or model.py's own `_bulleted`
# wrapper) standing between the raw value and the brace. Every compliant site today passes the raw
# variable as a plain ARGUMENT to one of those calls and only ever interpolates the RESULT (bound
# to a different name — `said`, `blocks`, the return of `labelled(...)`), so this one pattern is
# enough to catch the careless mistake: pasting `{response}` straight into a prompt string instead
# of routing it through the seam.
#
# WHAT IT CANNOT CATCH, ALSO HONESTLY:
#
# - A TENTH FUNCTION this guard has never heard of. `_KNOWN_LEARNER_SITES` below is a hand-written
#   allowlist of (file, function, variable) triples, not a scan of every function in the two
#   files. A brand-new compose method added next month is invisible until a human adds its row
#   here — the exact "must be updated by hand, and rots silently" allowlist risk the brief asked
#   this docstring to name. The realistic case this still catches is the more common one: an
#   EXISTING guarded function edited to add a second, unwrapped interpolation of its own learner
#   parameter — that function is already on the list, so the new line is caught the next time the
#   suite runs.
# - Text that reaches the prompt through a HELPER function, not directly: if `response` is passed
#   to some `_prep(response)` first and the wrapped f-string interpolates the helper's return
#   value under a new name, this guard sees a call, not a bare `{response}`, and says nothing.
# - A variable RENAMED at the boundary — `student_text = response` followed by `f"{student_text}"`
#   — defeats the name-based check entirely; the guard only recognises the exact names in the
#   allowlist.
# - Text built by STRING CONCATENATION instead of an f-string: `"Reply:\n" + response` never puts
#   `response` inside `{}`, so the brace-scanning regex never sees it.
# - A learner-text variable under a name NOT in `_KNOWN_LEARNER_SITES` at all. `screen_moves`'
#   `text` is a documented case in point (model.py's own comment on `screen_moves`): most callers
#   pass Vera-authored text, one caller passes real learner text, and the guard cannot tell which
#   call site produced a given string — it only checks that `screen_moves` itself never interpolates
#   `text` bare, which is necessary but not sufficient for every caller's payload to be safe.
#
# A NOTE ON SCOPE, NOT A FIX: while building this guard, three more places in `model.py` were found
# interpolating a learner-text-named parameter directly and unwrapped — `grade_sharper`'s
# `response`, `concierge_sitting_close`'s `situation` (and the per-turn `text` in its transcript
# loop), and `grade_answer`'s `answer` (the `cs_technical` checkable regime). None of the three
# were among the nine sites this branch's earlier tasks migrated, so none are in
# `_KNOWN_LEARNER_SITES` — deliberately: this task's file scope is `tests/test_prompt_text.py`
# only, and adding them to the allowlist without also fixing `model.py` would make the guard fail
# on the current tree, which the brief for this task requires to pass. Sealing them is a follow-up,
# not folded in here.

MODEL_PATH = Path("src/elenchus/model.py")
FORGE_PATH = Path("src/elenchus/forge.py")

# (file, governing function, learner-text variable name) — the nine sites tasks 2-4 migrated
# through the seam, plus `_render_turns` (a tenth, pre-existing seam consumer named in
# `prompt_text.indent_after_first`'s own docstring as a third caller). Hand-maintained; see the
# docstring above for exactly how and when this rots.
_KNOWN_LEARNER_SITES = (
    (MODEL_PATH, "generate_push", "positions"),
    (MODEL_PATH, "classify_response", "response"),
    (MODEL_PATH, "classify_entry", "opening"),
    (MODEL_PATH, "screen_moves", "text"),
    (MODEL_PATH, "map_territories", "situation"),
    (MODEL_PATH, "_render_turns", "text"),
    (FORGE_PATH, "build_brief", "situation"),
    (FORGE_PATH, "build_brief", "focus"),
    (FORGE_PATH, "build_brief", "positions"),
)


def _extract_function(src: str, name: str) -> tuple[str, int]:
    """Return `(body, start_line)` for `def {name}(`'s block, sliced by indentation off the START
    of the def line (never the `def` keyword itself — see `test_confirming_door.py._fn`'s own
    docstring for why that distinction matters: slicing at the keyword makes a nested/indented def
    look top-level and the extraction runs to EOF).

    Uses `rindex`, the LAST occurrence of `def {name}(` in the file, not the first: `model.py`
    defines `generate_push`/`classify_response`/`classify_entry`/`screen_moves`/`map_territories`
    three times each — once as a `Protocol` stub, once on `FakeModel` (the test double), once on
    `AnthropicModel` (the real caller that reaches the wire). `AnthropicModel` is the last class in
    the file, so the last occurrence is always the one this guard means to check.

    The signature itself is skipped by matching parens, not by indentation: `classify_response`'s
    own signature runs eight lines with its closing `) -> ResponseClassification:` back at the
    SAME indentation as `def` (a plain method with keyword-only args), which the naive
    indentation-break `test_confirming_door.py._fn` uses would misread as the end of the function
    -- verified against a bite-check that silently passed for the wrong reason before this existed.
    Only lines AFTER the signature are subject to the indentation break. `start_line` is 1-indexed,
    matching the file's own line numbers, for the failure message."""
    i = src.rindex(f"def {name}(")
    start = src.rfind("\n", 0, i) + 1  # rfind, not rindex: -1 + 1 == 0 when def opens the file
    start_line = src.count("\n", 0, start) + 1
    base = i - start
    paren_start = src.index("(", i)
    depth = 0
    j = paren_start
    while True:
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    colon = src.index(":", j)
    body_start = src.index("\n", colon) + 1
    out = [src[start:body_start]]  # the whole signature, unconditionally
    for ln in src[body_start:].splitlines(True):
        if ln.strip() and (len(ln) - len(ln.lstrip())) <= base:
            break
        out.append(ln)
    return "".join(out), start_line


def _strip_noise(body: str) -> str:
    """Blank out `#` comments and triple-quoted docstrings without changing the line count, so a
    line number computed against the result still matches the original file.

    Without this, `_render_turns`' own docstring — which quotes `f"{role}: {text}"` as prose,
    describing the OLD bare form it replaced — would trip the `text` check below on a sentence
    about the fix, not on code. `test_confirming_door.py._strip_comments` strips `#` comments only;
    this adds docstrings because that specific false positive lives in one."""
    body = re.sub(r'""".*?"""', lambda m: "\n" * m.group(0).count("\n"), body, flags=re.S)
    return re.sub(r"#[^\n]*", "", body)


def _bare_interpolation(src: str, func_name: str, varname: str) -> tuple[int, str] | None:
    """Search `func_name`'s body in `src` for `varname` sitting bare inside `{...}` — an f-string
    interpolation slot with no seam call between the raw variable and the brace.

    Returns `(line_number, matched_text)` on a hit, `None` when clean. Every compliant call site in
    this codebase passes the raw learner variable as a plain ARGUMENT to `bulleted`/`labelled`/
    `indent_after_first`/`_bulleted` and only interpolates the RESULT, bound to a different name —
    so a bare `{varname...}` is not merely correlated with a violation here, it IS one."""
    body, start_line = _extract_function(src, func_name)
    clean = _strip_noise(body)
    m = re.search(r"\{\s*" + re.escape(varname) + r"\b[^}]*\}", clean)
    if not m:
        return None
    line_no = start_line + clean.count("\n", 0, m.start())
    return line_no, m.group(0)


def _seam_violation_message(path: Path, func_name: str, varname: str, hit: tuple[int, str]) -> str:
    line_no, snippet = hit
    return (
        f"{path}:{line_no}: `{func_name}` interpolates `{varname}` directly as {snippet!r} — "
        f"route it through prompt_text.bulleted/labelled/indent_after_first before it reaches "
        f"the composed prompt, the same way every other learner-text site in this function does."
    )


def test_bare_interpolation_detector_fires_on_a_direct_f_string_splice():
    """Proof the detector distinguishes the violating shape from the compliant one (below), on a
    hand-written snippet — not on model.py/forge.py, and not by calling the seam functions to
    build the expected value."""
    src = 'def classify_response(self, response):\n    user = f"Student reply:\\n{response}"\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    line_no, snippet = hit
    assert line_no == 2
    assert "response" in snippet


def test_bare_interpolation_detector_is_silent_when_the_seam_wraps_the_variable():
    """The compliant counterpart to the test above: same function name, same variable name, the
    raw value passed to `labelled` as an argument rather than spliced into `{}` directly."""
    src = (
        "def classify_response(self, response):\n"
        '    user = _cap_rendered_turn(labelled("Student reply:", response))\n'
    )
    assert _bare_interpolation(src, "classify_response", "response") is None


@pytest.mark.parametrize("path, func_name, varname", _KNOWN_LEARNER_SITES)
def test_known_compose_site_routes_learner_text_through_the_seam(path, func_name, varname):
    """The enforcement test itself: reads `path` off disk (not an in-memory fixture — a stale
    read would prove nothing about the tree actually being tested) and fails, naming file, line,
    and variable, the moment `func_name` interpolates `varname` without the seam. See the section
    docstring above for exactly what this can and cannot catch."""
    hit = _bare_interpolation(path.read_text(), func_name, varname)
    if hit is not None:
        pytest.fail(_seam_violation_message(path, func_name, varname, hit))
