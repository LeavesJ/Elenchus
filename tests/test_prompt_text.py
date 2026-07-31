"""Tests for the learner text boundary seam (`prompt_text.py`).

No caller of `bulleted`/`labelled` exists yet — this task builds only the seam. The load-bearing
test is the column-0 property test below, not the example tests: it proves no byte the learner
supplies can ever open a line at column 0 of the composed prompt, over the full separator matrix
`str.splitlines()` recognises, using a private-use-area alphabet (U+E000+) the composer's own
template text never contains, so any payload character surviving at column 0 is unambiguous proof
of a leak, not a coincidence of overlapping alphabets.
"""

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
