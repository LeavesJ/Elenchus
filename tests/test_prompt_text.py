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


def test_bulleted_renders_one_item_per_line():
    """A2 (boundary-8 review): pins `bulleted`'s stated contract -- one item, one bullet line --
    which the column-0 test above cannot certify on its own: collapsing every item onto a single
    joined line (e.g. `"  - " + " ".join(items)`) still keeps every payload byte off column 0, so
    that test alone would stay green under such a collapse, and every OTHER test in this file
    passes a single-element tuple, so none of them exercise the multi-item join at all. Checked on
    plain single-line items (no embedded separator) so the join itself is the only thing under
    test.

    boundary-9 review: a trailing `rendered.count("\\n") == 2` assertion used to follow the
    byte-exact equality below. It could never fail independently -- any string that passes the
    equality check already has exactly two newlines by construction, so the count assertion only
    ever ran once the stronger check had already passed. Removed rather than kept as decoration;
    the equality assertion alone is what proves the multi-item join is not collapsed onto one
    line."""
    rendered = bulleted(("first", "second", "third"))
    assert rendered == "  - first\n  - second\n  - third"  # not collapsed onto one line


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
# call to `prompt_text.bulleted`/`labelled`/`indent_after_first` standing between the raw value and
# the brace (`generate_push` called through model.py's own `_bulleted` wrapper until boundary-7
# Fix 2 deleted it as a redundant second copy of `prompt_text.bulleted`; it now calls straight
# through, so every compliant site names the same three seam functions). Every compliant site today
# passes the raw variable as a plain ARGUMENT to one of those calls and only ever interpolates the
# RESULT (bound to a different name — `said`, `blocks`, the return of `labelled(...)`), so this one pattern is
# enough to catch the careless mistake: pasting `{response}` straight into a prompt string instead
# of routing it through the seam. This holds whether the f-string is single/double-quoted OR
# TRIPLE-quoted (`f"""...{response}..."""`): `_strip_noise` only blanks a `"""..."""` span when it
# carries no `f`/`rf`/`fr` prefix, so an f-prefixed triple-quoted string is never mistaken for a
# docstring and stays visible to the brace-scanning regex below — PROVIDED `_extract_function`
# actually delivers that line to it in the first place (see the next section's bullet on this).
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
# - Text built with `str.format()` or %-STYLE formatting splits into two OPPOSITE failures, not
#   one. A POSITIONAL or empty template — `"Reply:\n{}".format(response)` — or %-style —
#   `"Reply:\n%s" % response` — never puts `response` inside `{...}` at all, so the brace-scanning
#   regex misses it exactly as it misses concatenation: a real violation goes uncaught. A KEYWORD
#   template is the opposite: `"Reply:\n{response}".format(response=rendered)` puts the LITERAL
#   text `{response}` inside braces in the template string regardless of what `rendered` actually
#   is, so the regex FIRES even when the raw variable was already routed through the seam and only
#   its safe, wrapped result feeds the named argument — a false positive (a misfire, not a miss)
#   that tells an already-compliant line to route through a seam it already uses. See the tests
#   below for both directions.
# - A multi-line string (triple-quoted or otherwise) whose UNINDENTED continuation line —
#   starting at column 0, the common style for a triple-quoted block, e.g.
#   `f"""Student reply:\n{response}"""` written across two real physical lines — lands at or
#   below `_extract_function`'s own indentation. That function slices a body by breaking on the
#   first non-blank line whose indentation is `<= base` (the `def` line's own column), with no
#   awareness that a column-0 line might be the INSIDE of an still-open string literal rather
#   than code after the function; the body is truncated before that line is even handed to
#   `_strip_noise` or the brace scan, so anything on or after it — this interpolation included —
#   is invisible. Verified directly: `_strip_noise` itself, given the untruncated body, correctly
#   leaves an `f"""..."""` interpolation intact; the miss is `_extract_function`'s, not
#   `_strip_noise`'s. A single-physical-line triple-quoted f-string, or one whose continuation
#   stays indented past `base` (both realistic styles), is unaffected and IS caught — including
#   when a `#` sits on that continuation line (boundary-9 closed that separately, see
#   `_strip_noise`'s docstring; before that fix this bullet's "IS caught" claim had a live
#   counterexample in exactly this shape) — see the tests below, now including the `#`-bearing
#   variant. Fixing the column-0 case for real requires `_extract_function` to track open-quote
#   state line-by-line, which this file's regex/indentation style was deliberately kept free of;
#   not done here.
# - A learner-text variable under a name NOT in `_KNOWN_LEARNER_SITES` at all. `screen_moves`'
#   `text` is a documented case in point (model.py's own comment on `screen_moves`): most callers
#   pass Vera-authored text, one caller passes real learner text, and the guard cannot tell which
#   call site produced a given string — it only checks that `screen_moves` itself never interpolates
#   `text` bare, which is necessary but not sufficient for every caller's payload to be safe.
#
# HOW THIS GUARD ALREADY PAID FOR ITSELF: building it surfaced three more places in `model.py`
# interpolating a learner-text-named parameter directly and unwrapped — `grade_sharper`'s
# `response`, `concierge_sitting_close`'s `situation` (and the per-turn `text` in its transcript
# loop), and `grade_answer`'s `answer` (the `cs_technical` checkable regime). None were among the
# nine sites this branch's earlier tasks migrated, so the guard could not have caught them; a human
# reading the allowlist found them. Task 6 sealed all three and added their rows below, so they were
# watched from here on. That is the honest shape of this guard's value: it does not DISCOVER sites,
# it stops known ones from regressing — and the act of writing down what is known is what turns up
# what is missing.
#
# `grade_sharper`'s `response` row was later REMOVED (T2, measured prompt-injection fix): the fix
# for that site was to stop wrapping `response` in a seam at all, not to keep wrapping it, so the
# thing this guard checks for stopped being the right check at that one site. See the block
# directly below `_KNOWN_LEARNER_SITES` for the honest replacement.

MODEL_PATH = Path("src/elenchus/model.py")
FORGE_PATH = Path("src/elenchus/forge.py")

# (file, governing function, learner-text variable name) — hand-maintained; see the docstring
# above for exactly how and when this rots. boundary-8 review: an earlier version of this comment
# had `_render_turns` and `generate_push` backwards. `_render_turns` calls `indent_after_first`
# directly and has done so since this module was hours old (the reason `indent_after_first` was
# made public -- see its own docstring's "third caller") -- it is the PRE-EXISTING seam consumer.
# `generate_push` is the opposite: it carried its own independent reimplementation of `bulleted`
# (a local `_bulleted`) for most of this branch's life and only started calling the real seam
# directly in the commit that sealed the thirteenth site below -- it is the NEWLY migrated one,
# not one of an original nine.
_KNOWN_LEARNER_SITES = (
    (MODEL_PATH, "generate_push", "positions"),
    (MODEL_PATH, "classify_entry", "opening"),
    (MODEL_PATH, "screen_moves", "text"),
    (MODEL_PATH, "map_territories", "situation"),
    (MODEL_PATH, "_render_turns", "text"),
    (FORGE_PATH, "build_brief", "situation"),
    # `build_brief`'s "focus" and "positions" rows were removed here (boundary-8 review): neither
    # violation shape ever puts the bare variable name inside `{...}` in this function, so the
    # brace-scanning regex below returns None whether the code is sealed or not -- `focus` is
    # appended to `lines` as a plain list element, never inside an f-string, and `positions` is
    # destructured into a per-item loop variable (`p`) before anything reaches a brace, so the
    # collection name itself never appears there. A row green in both the sealed and unsealed
    # state certifies nothing. Both sites are covered instead by BEHAVIORAL tests in
    # tests/test_forge.py that exercise build_brief's actual rendered output and would catch a
    # regression to the pre-seam form directly: test_build_brief_focus_newline_no_column_0_leak
    # and test_build_brief_focus_is_labelled_and_indented for focus;
    # test_build_brief_position_uses_the_seam_bulleted_form for positions.
    # Task 6: the three sites "HOW THIS GUARD ALREADY PAID FOR ITSELF" (above) found while this
    # guard was being built. They are sealed now, so the guard can finally watch them;
    # `concierge_sitting_close` gets two rows because it carries two learner surfaces, the
    # situation blob and each segment's turn text.
    (MODEL_PATH, "grade_answer", "answer"),
    (MODEL_PATH, "concierge_sitting_close", "situation"),
    (MODEL_PATH, "concierge_sitting_close", "text"),
)

# T2 (measured prompt-injection fix) REMOVED two rows that lived here: `(MODEL_PATH,
# "classify_response", "response")` and `(MODEL_PATH, "grade_sharper", "response")`. This is not a
# silent weakening -- read the reasoning before assuming it is.
#
# This guard's premise is "a known learner-text variable must route through
# `bulleted`/`labelled`/`indent_after_first` before it reaches the composed prompt", proved by
# showing the raw variable is never spliced bare inside `{...}`. `classify_response` and
# `grade_sharper` no longer call any of those three functions on `response` AT ALL: the composed
# user message IS `response`, unwrapped, with no label and no indent (see model.py's own comment on
# both sites for why -- the prior `Push:`/`Student reply:` template was itself the forgeable
# surface a measured attack exploited, so it was removed rather than defended). A row for either
# site would now pass this guard VACUOUSLY: `_bare_interpolation` finds no `{response}` brace
# splice, not because the seam wraps it, but because there is no f-string interpolation of it left
# to find. That is a real property (there is no unwrapped bare splice), but it is NOT the property
# this guard exists to prove (that the seam was called), and leaving the row here would let a
# reader believe the latter from the former.
#
# The property that actually matters post-change -- the composed user message is EXACTLY the
# learner's reply, no engine-authored heading, no added structure -- is a BEHAVIORAL claim this
# source-reading guard cannot express at all (it reads text, it does not compose a message and
# inspect it). tests/test_anthropic_model.py proves it directly instead, one test per site:
# `test_classify_response_user_message_is_exactly_the_learner_reply` and
# `test_grade_sharper_user_message_is_exactly_the_learner_reply` (plus a forged-heading variant
# each) capture the real composed `user` via a fake client and assert byte equality with the raw
# reply. Those tests are what makes this exemption honest: they fail loudly the day anyone adds
# engine text back into either message, which is the regression this allowlist row used to guard
# against here.
#
# Column 0 is also no longer the hazard for these two sites specifically: the guard's other
# premise -- "learner text must never open a line at column 0, where the composed prompt's own
# headings live" -- assumed the message had engine headings to collide with. After this change the
# learner's reply IS the whole user message, trivially at column 0 from its very first byte, and
# that is safe ONLY because no engine structure shares the message with it for a forged line to
# imitate. Every OTHER row in `_KNOWN_LEARNER_SITES` above still composes learner text alongside
# real engine headings in the same message, so the indent discipline those rows check remains load-
# bearing there, unchanged.


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
    matching the file's own line numbers, for the failure message.

    boundary-8 review (C5): a renamed/removed `name` used to raise a bare `ValueError` straight
    out of `str.rindex`, which fails closed (right) but leaves the author staring at a traceback
    into this helper's internals instead of the one-line remedy. Caught and re-raised below with
    that remedy named directly."""
    try:
        i = src.rindex(f"def {name}(")
    except ValueError as e:
        raise ValueError(
            f"no `def {name}(` found in this source — if `{name}` was renamed or removed, update "
            f"the matching row in tests/test_prompt_text.py's _KNOWN_LEARNER_SITES (or this call) "
            f"to the new name rather than chase a traceback into _extract_function."
        ) from e
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


_TRIPLE_QUOTED = re.compile(r'([A-Za-z]{0,2})(""".*?""")', re.S)


def _blank_unless_f_prefixed(m: re.Match) -> str:
    """`re.sub` replacement for `_TRIPLE_QUOTED`: blank a triple-quoted span to preserve line
    count, UNLESS its prefix (the 0-2 letters immediately before the opening triple-quote — the
    only characters valid Python syntax permits there) contains an `f`. An f- or rf-prefixed
    triple-quoted string is a real interpolation site, not a docstring, and must stay visible to
    the brace-scanning regex in `_bare_interpolation` below."""
    prefix, quoted = m.group(1), m.group(2)
    if "f" in prefix.lower():
        return m.group(0)
    return "\n" * quoted.count("\n")


def _strip_hash_comment(line: str) -> str:
    """Strip a `#...` comment from one physical `line`, but only a `#` that sits OUTSIDE a
    single/double-quoted string.

    boundary-8 review (C1): the old approach (`re.sub(r"#[^\\n]*", "", body)`) stripped from the
    FIRST `#` on a line to end of line with no string-context awareness at all, so a composing
    line whose own string payload contains a `#` — a prompt heading like "Segment #1" or
    "Move #2" — would truncate away everything after it, including a real `{varname}`
    interpolation later on that same physical line. That shape was previously ABSENT from the
    "WHAT IT CANNOT CATCH" list above, which made the list itself wrong, not merely incomplete —
    a blind spot this guard did not even know it had. Closed here rather than documented: quote
    state is tracked char-by-char (handling backslash escapes) rather than reaching for a full
    tokenizer/AST, matching the rest of this file's regex/slice style.

    This function only ever sees ONE physical line and starts every call with `quote = None` — it
    has no memory of a string still being open from the line before. That is fine for an ordinary
    single/double-quoted string, which Python syntax never lets span a raw newline unescaped, but
    it is NOT fine for a multi-line triple-quoted span: see `_strip_noise`'s docstring (boundary-9
    review) for why callers must never hand this function a line that sits inside one."""
    quote = None
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 2  # the escaped character can never close (or misread) the open quote
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#":
            return line[:i]
        i += 1
    return line


def _strip_hash_lines(chunk: str) -> str:
    """Run `_strip_hash_comment` over each physical line of `chunk`. Callers must only pass a
    `chunk` known to sit entirely OUTSIDE any surviving (f-prefixed) triple-quoted span — see
    `_strip_noise`, the only caller."""
    return "\n".join(_strip_hash_comment(line) for line in chunk.split("\n"))


def _strip_noise(body: str) -> str:
    """Blank out `#` comments and triple-quoted docstrings without changing the line count, so a
    line number computed against the result still matches the original file. An f/rf-prefixed
    triple-quoted string is left untouched (see `_blank_unless_f_prefixed`) — it is an
    interpolation site the guard must still see, not prose to discard.

    Without this, `_render_turns`' own docstring — which quotes `f"{role}: {text}"` as prose,
    describing the OLD bare form it replaced — would trip the `text` check below on a sentence
    about the fix, not on code. `test_confirming_door.py._strip_comments` strips `#` comments only;
    this adds docstrings because that specific false positive lives in one.

    boundary-9 review: `#` comments used to be stripped by splitting the WHOLE body on `\\n` and
    running `_strip_hash_comment` per line, unconditionally. `_strip_hash_comment` only tracks
    quote state within one physical line (see its own docstring) and starts fresh at every `\\n`,
    so a surviving f-prefixed triple-quoted span that happens to run across more than one physical
    line lost its "still inside a string" state at each line break: an f-prefixed triple-quoted
    string opening with "Reply:" on its first physical line and continuing on a second line
    reading "Segment #1: " followed by a brace-interpolated `response` read that continuation
    line's `#1` as a real comment start with quote state reset to closed, and deleted the
    interpolation right along with it -- a real violation going uncaught, the opposite of what
    this guard exists for. A `#` inside a triple-quoted span can
    NEVER be a real comment, whatever line of the span it falls on -- it is always payload inside
    the string literal, the same reason a `#` inside an ordinary quoted string is payload. So
    every span `_TRIPLE_QUOTED` still matches after the docstring-blanking substitution below
    (all f-prefixed at that point; a plain docstring was already replaced with bare newlines) is
    now passed straight through, whole, and only the code OUTSIDE those spans is handed to
    `_strip_hash_comment` at all -- no `\\n` inside a live span can ever reach it and reset state
    that was never really closed."""
    body = _TRIPLE_QUOTED.sub(_blank_unless_f_prefixed, body)
    out = []
    pos = 0
    for m in _TRIPLE_QUOTED.finditer(body):
        out.append(_strip_hash_lines(body[pos : m.start()]))
        out.append(m.group(0))  # an f-prefixed span: no `#` inside it is ever a real comment
        pos = m.end()
    out.append(_strip_hash_lines(body[pos:]))
    return "".join(out)


def _bare_interpolation(src: str, func_name: str, varname: str) -> tuple[int, str] | None:
    """Search `func_name`'s body in `src` for `varname` sitting bare inside `{...}` — an f-string
    interpolation slot with no seam call between the raw variable and the brace.

    Returns `(line_number, matched_text)` on a hit, `None` when clean. Every compliant call site in
    this codebase passes the raw learner variable as a plain ARGUMENT to `bulleted`/`labelled`/
    `indent_after_first` and only interpolates the RESULT, bound to a different name — so a bare
    `{varname...}` is not merely correlated with a violation here, it IS one."""
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


def test_bare_interpolation_detector_fires_on_a_triple_quoted_f_string_splice():
    """The same violation as the test above, wrapped in a TRIPLE-quoted f-string instead of a
    plain one — the exact shape `_strip_noise` used to blank unconditionally, as if it were a
    docstring, making the violation invisible (the hole this test seals; see `_strip_noise`'s
    docstring and `_blank_unless_f_prefixed`). Single physical line, matching the convention the
    test above already uses, so `_extract_function`'s own separate column-0-continuation-line
    truncation (see the docstring bullet on it above) never enters into this proof."""
    src = 'def classify_response(self, response):\n    user = f"""Student reply: {response}"""\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    assert "response" in hit[1]


def test_bare_interpolation_detector_fires_on_an_rf_prefixed_triple_quoted_splice():
    """The `rf`/`fr` combined-prefix variant of the triple-quoted shape above — still a real
    interpolation site, so it must stay visible too, not just the bare `f` prefix."""
    src = 'def classify_response(self, response):\n    user = rf"""Student reply: {response}"""\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    assert "response" in hit[1]


def test_bare_interpolation_detector_fires_on_a_multiline_triple_quoted_splice_when_indented():
    """The genuinely multi-line case — a real physical line break inside the triple-quoted
    f-string — with the continuation line indented past the `def` line's own column, the shape
    `_extract_function` does not mistake for the end of the function. Proves the `_strip_noise`
    fix reaches real multi-line f-strings, not just the single-physical-line case above."""
    src = (
        'def classify_response(self, response):\n    user = f"""Student reply:\n    {response}"""\n'
    )
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    assert hit[0] == 3
    assert "response" in hit[1]


def test_strip_noise_alone_preserves_the_exact_unindented_multiline_reviewer_example():
    """`_strip_noise`, fed the reviewer's exact reproduction directly (a real newline, the
    continuation line unindented at column 0) — bypassing `_extract_function` entirely — proves
    the fix targeted at `_strip_noise` is itself complete: it does not blank this f-string. The
    end-to-end `_bare_interpolation` call over the same source still misses it, because
    `_extract_function` truncates the body before this line ever reaches `_strip_noise` (see the
    docstring bullet above); this test isolates which of the two functions the miss belongs to.

    Asserts full byte-equality, not a substring of `"response"` — the parameter name and the
    function name (`classify_response`) both already contain that substring in the untouched
    signature line, so a weaker `"response" in ...` check would pass even if `_strip_noise` still
    blanked the f-string body: identical in the passing and failing case, so it would prove
    nothing."""
    body = 'def classify_response(self, response):\n    user = f"""Student reply:\n{response}"""\n'
    # Nothing to blank: no comments, and the one triple-quoted span is f-prefixed, so it must
    # come back byte-for-byte untouched.
    assert _strip_noise(body) == body


def test_strip_noise_still_blanks_a_plain_triple_quoted_docstring():
    """Closing the f-string hole must not reopen the false positive `_strip_noise` exists to
    prevent: an ordinary (non-f-prefixed) docstring that merely MENTIONS `{response}` in prose
    must still be blanked, or this guard would fail on its own commentary, not on code."""
    src = (
        "def classify_response(self, response):\n"
        '    """Docstring mentioning {response} in prose, not code."""\n'
        '    user = _cap_rendered_turn(labelled("Student reply:", response))\n'
    )
    assert _bare_interpolation(src, "classify_response", "response") is None


def test_bare_interpolation_detector_is_silent_when_the_seam_wraps_the_variable():
    """The compliant counterpart to the test above: same function name, same variable name, the
    raw value passed to `labelled` as an argument rather than spliced into `{}` directly."""
    src = (
        "def classify_response(self, response):\n"
        '    user = _cap_rendered_turn(labelled("Student reply:", response))\n'
    )
    assert _bare_interpolation(src, "classify_response", "response") is None


def test_bare_interpolation_detector_fires_when_a_hash_inside_the_string_precedes_the_brace():
    """C1 (boundary-8 review): the shape `_strip_hash_comment` exists to catch. The `#` sits
    INSIDE the f-string's own quotes, before `{response}`, not in a trailing comment — the old
    line-blind `#`-to-end-of-line strip would have deleted `{response}` along with it and this
    detector would have missed a real violation."""
    src = 'def classify_response(self, response):\n    user = f"Segment #1: {response}"\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    assert "response" in hit[1]


def test_strip_noise_leaves_a_hash_inside_a_string_untouched_but_still_strips_a_real_comment():
    """The other half of the C1 fix, tested directly on `_strip_noise` rather than end-to-end: a
    `#` inside quotes is payload and must survive untouched, while a REAL trailing comment on the
    same line — outside the quotes — must still be stripped, exactly as before this fix."""
    body = 'user = f"Segment #1: {response}"  # a real trailing comment mentioning {response}\n'
    cleaned = _strip_noise(body)
    assert "Segment #1: {response}" in cleaned
    assert "a real trailing comment" not in cleaned


def test_bare_interpolation_detector_fires_on_a_hash_inside_a_multiline_triple_quoted_splice():
    """boundary-9 review: the C1 fix above only tracks quote state within a SINGLE physical line
    (see `_strip_hash_comment`'s own docstring), so it reset to "outside a string" at every `\\n`
    and missed this same shape once the `#` fell on a continuation line of a multi-line
    triple-quoted f-string instead of the opening one. Reviewer's exact reproduction: a `#`
    identical to the one the single-line C1 test above already covers, moved one physical line
    down. Before the boundary-9 fix this returned `None` -- a real violation going uncaught,
    silently, exactly like the C1 gap it was supposed to have already closed."""
    src = 'def classify_response(self, response):\n    user = f"""Reply:\n    Segment #1: {response}"""\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None
    assert "response" in hit[1]


def test_strip_noise_leaves_a_hash_untouched_across_a_multiline_triple_quoted_splice():
    """The other half of the boundary-9 fix, tested directly on `_strip_noise`: a `#` on a
    CONTINUATION line of a multi-line f-prefixed triple-quoted span must survive untouched (it can
    never be a real comment inside a string literal), the same guarantee
    `test_strip_noise_leaves_a_hash_inside_a_string_untouched_but_still_strips_a_real_comment`
    already pins for the single-line case -- while a real trailing comment AFTER the span still
    closes and still gets stripped, proving the fix does not simply stop stripping altogether."""
    body = 'user = f"""Reply:\n    Segment #1: {response}"""  # a real trailing comment\n'
    cleaned = _strip_noise(body)
    assert "Segment #1: {response}" in cleaned
    assert "a real trailing comment" not in cleaned


def test_bare_interpolation_detector_misfires_on_a_keyword_format_placeholder():
    """C2 (boundary-8 review): the opposite direction of the `.format()` bullet above. A KEYWORD
    placeholder whose name matches the tracked variable puts the LITERAL text `{response}` inside
    braces in the template string itself, regardless of what actually feeds it — so the guard
    fires even though the raw variable was already routed through the seam and only its wrapped,
    safe result reaches `.format()`'s keyword argument. A known false positive (a misfire), not
    evidence of a real violation — documented, not "fixed", since the correct fix (route this
    exact shape through the seam anyway, or teach the guard `.format()` call sites) is out of
    this task's scope."""
    src = (
        "def classify_response(self, response):\n"
        '    safe = labelled("Student reply:", response)\n'
        '    user = "Reply:\\n{response}".format(response=safe)\n'
    )
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is not None  # the misfire: a false positive, not a real violation


def test_bare_interpolation_detector_misses_a_positional_format_splice():
    """The MISS direction of the `.format()`/%-style bullet above -- the opposite of the misfire
    test above. A real violation: the raw learner variable spliced straight into a template with
    no seam call in between, through a POSITIONAL/empty `.format()` placeholder. That never puts
    `response` inside `{...}` in the template string itself (the placeholder is bare `{}`), so the
    brace-scanning regex has nothing to match and reports clean even though the line is not --
    documented, not "fixed", for the same out-of-scope reason the misfire above is documented
    rather than closed."""
    src = 'def classify_response(self, response):\n    user = "Reply:\\n{}".format(response)\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is None  # the miss: a real violation, uncaught


def test_bare_interpolation_detector_misses_a_percent_style_splice():
    """The same MISS direction as the test above, through %-style formatting instead of
    `.format()`: `%s` never puts `response` inside `{...}` either, so this is missed the same way
    string concatenation is missed (see the docstring bullet above), not merely correlated with
    the `.format()` case -- both never produce a `{varname...}` shape for the regex to find."""
    src = 'def classify_response(self, response):\n    user = "Reply:\\n%s" % response\n'
    hit = _bare_interpolation(src, "classify_response", "response")
    assert hit is None  # the miss: a real violation, uncaught


def _variable_is_live(src: str, func_name: str, varname: str) -> bool:
    """True if `varname` appears anywhere in `func_name`'s CODE — as a parameter or anywhere in
    the body, docstrings and comments excluded — proving an allowlist row still names something
    real.

    C4 (boundary-8 review): `_bare_interpolation` alone cannot catch a row going vacuous. If
    `varname` is renamed at the parameter boundary, the brace-scan simply finds nothing and
    returns `None` — the SAME result a genuinely clean, sealed site produces, so the row stays
    green forever regardless of what the renamed code actually does. A renamed FUNCTION already
    fails loud (`_extract_function`'s `rindex` raises, see C5 above); a renamed VARIABLE fails
    silently, and nothing before this asserted the variable was ever there to find.

    boundary-9 review: this used to search the RAW body, the same mistake `_strip_noise` exists to
    fix for the brace scan two functions up. `_render_turns`' own docstring quotes the old bare
    form as prose (`` f"{role}: {text}" ``), so renaming `text` away in the code while leaving the
    docstring untouched left `varname` findable in a comment about the fix rather than in the fix
    itself, and this function reported the row live anyway. Noise is stripped first now, the same
    remedy `_bare_interpolation` already applies, so only a real code occurrence counts."""
    body, _ = _extract_function(src, func_name)
    clean = _strip_noise(body)
    return re.search(r"\b" + re.escape(varname) + r"\b", clean) is not None


def test_variable_is_live_false_when_the_parameter_was_renamed_even_with_a_docstring_mention():
    """The failure C4 closes, sharpened by boundary-9 review: a listed variable renamed at the
    parameter boundary, with a DOCSTRING that still mentions the old name in prose -- the exact
    shape `_render_turns` has today (its docstring quotes the old bare `f"{role}: {text}"` form
    while the code itself uses `text` as a live parameter). Before stripping noise,
    `_variable_is_live` found `response` inside the docstring's commentary and reported the row
    live regardless of what the code actually did; this fixture pins that a docstring mention alone
    must not count.

    `_bare_interpolation` on this exact source already returns `None` (nothing named `response` to
    find in the CODE), making the row indistinguishable from a real, sealed site unless
    `_variable_is_live` looks past the docstring and says so."""
    src = (
        "def classify_response(self, reply):\n"
        '    """Renders `reply`, replacing the old bare `f"...{response}..."` form."""\n'
        '    user = _cap_rendered_turn(labelled("Student reply:", reply))\n'
    )
    assert _bare_interpolation(src, "classify_response", "response") is None  # the silent miss
    assert _variable_is_live(src, "classify_response", "response") is False  # now loud instead


def test_extract_function_raises_a_self_explanatory_error_when_the_def_is_missing():
    """C5 (boundary-8 review): renaming a listed FUNCTION used to raise a bare `ValueError`
    straight out of `str.rindex` — fails closed, which is right, but hands the author a traceback
    into this helper's internals rather than the one-line remedy. The message must now name the
    missing function and point at the allowlist to fix."""
    with pytest.raises(ValueError) as exc_info:
        _extract_function("def something_else(self): pass\n", "renamed_function")
    message = str(exc_info.value)
    assert "renamed_function" in message
    assert "_KNOWN_LEARNER_SITES" in message


def test_extract_function_reads_the_last_definition_not_an_earlier_stub_or_fake():
    """A5 (boundary-8 review): `_extract_function`'s own docstring makes a load-bearing claim —
    `rindex`, not `index` — because `model.py` defines several watched functions three times: a
    `Protocol` stub (body `...`), `FakeModel`'s scripted double, and `AnthropicModel`'s real
    implementation, in that order, with `AnthropicModel` last. Untested until now: swapping
    `rindex` for `index` would silently start reading the Protocol stub instead, whose body never
    interpolates anything, and every `_KNOWN_LEARNER_SITES` row against `model.py` would pass
    regardless of what `AnthropicModel` actually does.

    Checked against the real file, not a hand-built fixture — a fixture could not tell `rindex`
    from `index` apart. `classify_response` is defined three times in `model.py`; the extracted
    body must contain `_parse_required`, a call only `AnthropicModel`'s implementation makes (the
    `Protocol` stub's body is a bare `...`, `FakeModel`'s is `return self._responses[code].pop(0)`
    — neither contains it), and `start_line` must land well past where the `Protocol`/`FakeModel`
    definitions sit."""
    src = MODEL_PATH.read_text()
    body, start_line = _extract_function(src, "classify_response")
    assert "_parse_required" in body
    assert start_line > 600


@pytest.mark.parametrize("path, func_name, varname", _KNOWN_LEARNER_SITES)
def test_known_compose_site_routes_learner_text_through_the_seam(path, func_name, varname):
    """The enforcement test itself: reads `path` off disk (not an in-memory fixture — a stale
    read would prove nothing about the tree actually being tested) and fails, naming file, line,
    and variable, the moment `func_name` interpolates `varname` without the seam. See the section
    docstring above for exactly what this can and cannot catch.

    C4: also fails loud, separately, if `varname` no longer appears in `func_name` at all — a
    renamed/removed site would otherwise pass this test vacuously (see `_variable_is_live`)."""
    src = path.read_text()
    assert _variable_is_live(src, func_name, varname), (
        f"{path}: `{varname}` no longer appears anywhere in `{func_name}` — renamed or removed "
        f"out from under this allowlist row, which would otherwise pass vacuously (a bare-"
        f"interpolation search that can never match anything looks identical to a clean site). "
        f"Update the row in _KNOWN_LEARNER_SITES to the new name, or remove it and say what "
        f"covers the site instead."
    )
    hit = _bare_interpolation(src, func_name, varname)
    if hit is not None:
        pytest.fail(_seam_violation_message(path, func_name, varname, hit))
