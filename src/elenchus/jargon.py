"""The jargon gate's matcher (spec 2026-07-29-jargon-gate-design §4.3).

Presence is a fact. Adequacy is a judgment. Only the first can live in a deterministic gate, which
is why this module answers "is this listed term present" and nothing else — no gloss detection, no
model call, no network. That is what lets the gate be free.
"""

from __future__ import annotations

import re

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def compact(text: str | None) -> str:
    """Casefold and drop every non-alphanumeric character.

    `83(b)`, `83 (b)` and `Section 83(b)` all reduce to a string containing `83b`, which is the
    whole reason the matcher can be a substring test rather than a parser. The cost is that
    entries must be distinctive enough to survive losing their spacing — see the canary."""
    return _NON_ALNUM_RE.sub("", (text or "").lower())


def offending_terms(text: str | None, terms: list[tuple[str, list[str]]]) -> list[str]:
    """Every listed term present in `text`, in `terms` order, else [].

    `terms` carries variants ALREADY compacted (the loader does it once at load, not per call).
    An empty `terms` makes this a no-op, which is how a missing list goes inert instead of
    blocking every forge. Reports ALL matches, not just the first (T2 review, Fix 3) — a scenario
    naming two listed terms burned the caller's single retry fixing one and still fell back on
    the other when only the first hit was visible."""
    hay = compact(text)
    if not hay:
        return []
    return [term for term, variants in terms if any(v and v in hay for v in variants)]
