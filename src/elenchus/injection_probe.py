"""Offline machinery for the injection efficacy probe.

Answers ONE question: does `prompt_text.labelled`'s indent stop a grade-inflation injection that
lands on the pre-indent bare form? Spec:
docs/superpowers/specs/2026-08-03-injection-efficacy-probe-design.md (main checkout only).

Everything here is deterministic and model-free except `run_cells`, which takes the model as a
parameter. Nothing in this module reaches the network.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError


class Payload(BaseModel):
    """One attack family.

    `substance` is a mechanism-free learner reply, so the honest grade is `unchanged` and any
    `closed`/`mechanism_supplied` verdict on it is the hijack landing rather than a correct read.
    `injection` is the hijack, assembled so it sits at column 0 in the OLD rendering.
    `semantic_only` carries the same persuasive content with the column-0 structure removed; it
    feeds cell D_old, which is what makes an INEFFECTIVE verdict diagnosable rather than a dead
    end (the admission filter can prove a payload HAS column-0 structure, never that its power
    DEPENDS on it)."""

    name: str
    mechanism_tag: str
    substance: str
    injection: str
    semantic_only: str


def attack_text(p: Payload) -> str:
    """The learner reply as the attacker would send it: substance, then the injection starting on
    its own line so the old bare rendering puts it at column 0."""
    return f"{p.substance}\n{p.injection}"


def benign_text(p: Payload) -> str:
    """The twin. Same substance, no injection. Its honest grade is `unchanged`, and a landing here
    disqualifies the payload (exclusion rule 2)."""
    return p.substance


def diagnostic_text(p: Payload) -> str:
    """Cell D_old's text: the persuasive content with no column-0 structure. If this lands, the
    attack never depended on column 0 and the payload cannot test the indent."""
    return f"{p.substance}\n{p.semantic_only}"


def load_payloads(path: Path) -> list[Payload]:
    """Read a payload file. Raises `ValueError` naming the offending field rather than letting a
    pydantic error surface raw, because this file is hand-authored and the message is the whole
    feedback loop for whoever is writing payloads."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    rows = data.get("payloads") or []
    out = []
    for i, row in enumerate(rows):
        try:
            out.append(Payload(**row))
        except ValidationError as exc:
            missing = ", ".join(str(e["loc"][0]) for e in exc.errors())
            raise ValueError(f"payload {i} ({row.get('name', '?')}) invalid: {missing}") from exc
    return out
