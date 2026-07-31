"""The learner text boundary: one seam for text a learner authored to cross into a composed
model prompt.

Imports nothing from `model.py` or `forge.py`, so the dependency direction stays trivial: this
module serves those two, never the reverse. It has no callers yet; the tasks that migrate the
nine existing sites land separately.

Both `bulleted` and `labelled` split on `str.splitlines()`, not a literal `"\\n"` split, even
though the composed prompt that finally reaches the wire only ever breaks lines on `"\\n"`.
`splitlines()` recognises a wider set (`\\v`, `\\f`, the file/group/record separators, NEL,
U+2028, U+2029) than the wire's own line terminator. That width is deliberate: those characters
are still capable of being rendered or tokenised as a line break by whatever reads the prompt on
the other side, and this module's job is to keep learner text off column 0 in that reader's eyes,
not merely off column 0 of the raw Python string. Splitting on the narrower `"\\n"` alone would
leave a learner-supplied U+2028 (for example) glued mid-string to the following payload word
with no indent in front of it — invisible to a `"\\n"`-only check, but a fresh, unindented line
to anything that treats U+2028 as a break. `splitlines()` closes that gap by treating every
separator it recognises as a place requiring an indent, then this module re-emits the result
joined on plain `"\\n"`, so the wire format is exactly what downstream code expects."""

LEARNER_INDENT = "    "


def indent_after_first(text: str, first: str, rest: str) -> str:
    """Split `text` on every line break `str.splitlines()` recognises, prefix the first
    resulting line with `first`, and every later line with `rest`. Total: `text` may be empty,
    whitespace-only, or made entirely of separators, and this never raises.

    Public: it has three callers, `bulleted` and `labelled` below plus `model._render_turns`,
    which needed this exact primitive for a dialogue turn's `"{role}: "` prefix -- a shape
    neither `bulleted` nor `labelled` fits. A third caller in another module reaching for a
    leading-underscore name is the smell this project extracts on; this rename is that
    extraction, not a new layer."""
    lines = text.splitlines() or [""]
    out = [f"{first}{lines[0]}"]
    out.extend(f"{rest}{line}" for line in lines[1:])
    return "\n".join(out)


def bulleted(items: tuple[str, ...] | list[str]) -> str:
    """Render learner items as a list no learner line can escape.

    The first line of each item carries the bullet, every later line is indented past it, so a
    newline in a learner's reply cannot place text at column 0 where a composed prompt's own
    headings live. A single-line item renders byte-identically to `f"  - {item}"`, which is what
    makes this safe to apply to an already-tuned prompt."""
    return "\n".join(indent_after_first(item, "  - ", LEARNER_INDENT) for item in items)


def labelled(label: str, text: str) -> str:
    """Render learner text under a heading, with EVERY line indented, including the first.

    Unlike `bulleted`, the first line here would otherwise sit at column 0, indistinguishable
    from a heading the engine composed. Indenting it is therefore not optional, and it means a
    single-line input renders differently from the bare `f"{label}\\n{text}"` it replaces."""
    return f"{label}\n{indent_after_first(text, LEARNER_INDENT, LEARNER_INDENT)}"
