"""Offline machinery for the injection efficacy probe.

Answers ONE question: does `prompt_text.labelled`'s indent stop a grade-inflation injection that
lands on the pre-indent bare form? Spec:
docs/superpowers/specs/2026-08-03-injection-efficacy-probe-design.md (main checkout only).

Everything here is deterministic and model-free except `run_cells`, which takes the model as a
parameter. Nothing in this module reaches the network.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Protocol

import yaml
from pydantic import BaseModel, ValidationError

from .model import ModelError, ResponseClassification


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
    if "payloads" not in data:
        raise ValueError(f"{path}: no top-level 'payloads' key (check for a typo)")
    rows = data["payloads"] or []
    if not rows:
        raise ValueError(f"{path}: 'payloads' is empty")
    out = []
    for i, row in enumerate(rows):
        try:
            out.append(Payload(**row))
        except ValidationError as exc:
            missing = ", ".join(str(e["loc"][0]) for e in exc.errors())
            raise ValueError(f"payload {i} ({row.get('name', '?')}) invalid: {missing}") from exc
    return out


_HEADING = re.compile(r"^([A-Z][^:\n]{0,40}:)")


class AdmissionResult(BaseModel):
    name: str
    admitted: bool
    reason: str


def derive_heading_tokens(*prompts: str) -> set[str]:
    """Every line-initial `<Label>:` token appearing in the composed prompts the probe itself
    builds. DERIVED, never hand-listed: a hand list goes stale the first time a heading is
    renamed and silently narrows the filter, which is the failure mode this repo has hit before.
    A test pins the derived set against the current prompts so a rename fails loud."""
    out: set[str] = set()
    for p in prompts:
        for line in p.splitlines():
            if line[:1].isspace():
                continue
            m = _HEADING.match(line)
            if m:
                out.add(m.group(1))
    return out


def column_zero_lines(text: str) -> list[str]:
    """Non-blank lines starting at column 0, across every break `str.splitlines()` recognises.
    The separator coverage matters: `\\u2028` and friends are breaks to `splitlines` and to the
    model, so a filter that only knows `\\n` would pass a payload that still reaches column 0."""
    return [ln for ln in text.splitlines() if ln.strip() and not ln[:1].isspace()]


def admits(
    p: Payload, old_user: str, new_user: str, headings: set[str]
) -> AdmissionResult:
    """A payload is admitted only if it genuinely creates the hazard under test.

    Both conditions are required, and together they guarantee every paid call is spent on a
    payload that actually exercises the indent rather than on one that merely looks threatening.
    Note what this CANNOT prove: that the attack's power DEPENDS on the column-0 placement. Cell
    D_old exists for that.

    A heading counts as forged only when the OLD form's column-0 lines contain it MORE times
    than the composed prompt's own template legitimately contributes (one). Every old_user this
    probe builds already carries each real heading once on its own, so plain membership in
    `headings` cannot distinguish an attack from the template's own structure; only an extra,
    attacker-supplied occurrence at column 0 can."""
    old_lines = column_zero_lines(old_user)
    forged = any(sum(1 for ln in old_lines if ln.startswith(h)) > 1 for h in headings)
    substance_zero = set(column_zero_lines(new_user)) - headings
    if not forged:
        return AdmissionResult(
            name=p.name, admitted=False, reason="no column-0 heading lookalike in the old form"
        )
    if substance_zero:
        return AdmissionResult(
            name=p.name,
            admitted=False,
            reason=f"new form still puts learner bytes at column 0: {sorted(substance_zero)[:2]}",
        )
    return AdmissionResult(name=p.name, admitted=True, reason="")


CELLS: tuple[str, ...] = ("A_old", "A_new", "B_old", "B_new", "D_old")


class Call(NamedTuple):
    payload_name: str
    cell: str
    draw: int


def draw_schedule(names: list[str], draws: int, seed: int) -> list[Call]:
    """Draw-major: every `(payload, cell)` gets draw 1 before any gets draw 2.

    A run dying at draw 3 then leaves a balanced m=2 dataset over ALL payloads rather than
    complete data on the first few and nothing on the rest. Probe 2's second attempt died
    mid-run, so this is designed for rather than hoped for.

    Cell order is permuted WITHIN each `(payload, draw)` unit and never across payloads:
    permuting a whole draw would interleave payloads and change what a checkpoint line means on
    resume. There is no identified state channel between independent structured calls, so this is
    cheap insurance against an unnamed confound, not mitigation of a known one."""
    rng = random.Random(seed)
    out: list[Call] = []
    for d in range(1, draws + 1):
        for name in names:
            cells = list(CELLS)
            rng.shuffle(cells)
            out.extend(Call(name, c, d) for c in cells)
    return out


class RawParse(Protocol):
    def __call__(self, *, system: str, user: str, output_format: type, max_tokens: int): ...


_OLD_CELLS = {"A_old", "B_old", "D_old"}


def _text_for(cell: str, p: Payload) -> str:
    if cell.startswith("A_"):
        return attack_text(p)
    if cell.startswith("B_"):
        return benign_text(p)
    return diagnostic_text(p)


def run_cells(
    payloads: list[Payload],
    schedule: list[Call],
    *,
    classify: Callable[[Payload, str], ResponseClassification],
    raw_parse: RawParse,
    system_for: Callable[[Payload], str],
    old_user_for: Callable[[Payload, str], str],
    max_tokens: int,
    on_draw: Callable[[object], None] | None = None,
):
    """Execute the schedule, one call per `Call`, recording every outcome including refusals.

    A refusal is DATA, never a non-landing: scoring it as "did not land" is the false-pass path
    exclusion rule 1 exists to close. `on_draw` fires per completed call so paid-for work reaches
    disk before the run can die, which is what a previous probe in this project lacked until it
    had already lost a run."""
    from .injection_scoring import Draw

    by_name = {p.name: p for p in payloads}
    out = []
    for call in schedule:
        p = by_name[call.payload_name]
        text = _text_for(call.cell, p)
        try:
            if call.cell in _OLD_CELLS:
                rc = raw_parse(
                    system=system_for(p),
                    user=old_user_for(p, text),
                    output_format=ResponseClassification,
                    max_tokens=max_tokens,
                )
            else:
                rc = classify(p, text)
            row = Draw(
                payload_name=call.payload_name, cell=call.cell, draw=call.draw,
                outcome=rc.outcome, mechanism_supplied=rc.mechanism_supplied,
                hard_wrong=rc.hard_wrong, refused=False, error="",
            )
        except (ModelError, ValidationError) as exc:
            row = Draw(
                payload_name=call.payload_name, cell=call.cell, draw=call.draw,
                outcome=None, mechanism_supplied=None, hard_wrong=None,
                refused=True, error=f"{type(exc).__name__}: {exc}"[:400],
            )
        out.append(row)
        if on_draw is not None:
            on_draw(row)
    return out
