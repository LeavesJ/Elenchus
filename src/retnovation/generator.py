from __future__ import annotations

import re

from .types import CorpusEntry, Experience, GateCode, GateResult, Mode, Rubric

ARTIFACT_DIMENSIONS = (
    4  # rigor, completeness, internal consistency, defensible assumptions (FounderCEO §2)
)
WRAPPER_WORDS = ("streak", "points", "badge", "leaderboard", "timer", "reward", "level up")

HARD_REJECTS = frozenset(
    {
        GateCode.recoverable_label,
        GateCode.pre_named_framework,
        GateCode.type_hint_scaffold,
        GateCode.softened_ambiguity,
        GateCode.cosmetic_engagement,
        GateCode.insufficient_interrogation_depth,
    }
)
QUALITY_FLOORS = frozenset({GateCode.owned_or_real, GateCode.process_layer_load})


class GateError(RuntimeError):
    """Raised when no shippable experience exists, or a rubric fails the gate at load."""


def angle_count(rubric: Rubric) -> int:
    binding = 1 if rubric.binding_constraint else 0
    return len(rubric.frames) + len(rubric.traps) + binding + ARTIFACT_DIMENSIONS


def _contains_phrase(text_lc: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text_lc) is not None


def _frame_trap_phrases(rubric: Rubric) -> list[str]:
    phrases: list[str] = []
    for code in [f.frame_code for f in rubric.frames] + [t.trap_code for t in rubric.traps]:
        phrases.append(code.lower())
        phrases.append(code.replace("_", " ").lower())
    return phrases


def anti_label_gate(
    exp: Experience,
    corpus_entry: CorpusEntry | None,
    *,
    min_angle_count: int,
    framework_denylist: list[str],
    scaffold_denylist: list[str],
) -> GateResult:
    rejects: list[GateCode] = []
    downgrades: list[GateCode] = []
    prompt_lc = exp.prompt.lower()
    rubric = exp.rubric

    # recoverable_label: anchored to a curated owned-problem with a non-empty unlabeled rationale.
    if corpus_entry is None or not corpus_entry.unlabeled.strip():
        rejects.append(GateCode.recoverable_label)

    # pre_named_framework: no named method, and no leaked frame/trap code (snake or spaced).
    banned = [t.lower() for t in framework_denylist] + _frame_trap_phrases(rubric)
    if any(_contains_phrase(prompt_lc, p) for p in banned):
        rejects.append(GateCode.pre_named_framework)

    # type_hint_scaffold: no category-cueing scaffold phrase.
    if any(_contains_phrase(prompt_lc, p) for p in scaffold_denylist):
        rejects.append(GateCode.type_hint_scaffold)

    # softened_ambiguity: mode honesty — genuinely_open ⇒ no binding; bounded_error ⇒ a binding.
    has_binding = rubric.binding_constraint is not None
    if (rubric.mode is Mode.genuinely_open and has_binding) or (
        rubric.mode is Mode.bounded_error and not has_binding
    ):
        rejects.append(GateCode.softened_ambiguity)

    # cosmetic_engagement: real stakes present (corpus.why_owned) and no wrapper/gamification words.
    no_stakes = corpus_entry is None or not corpus_entry.why_owned.strip()
    if no_stakes or any(w in prompt_lc for w in WRAPPER_WORDS):
        rejects.append(GateCode.cosmetic_engagement)

    # insufficient_interrogation_depth (hard, user floor)
    ac = angle_count(rubric)
    if ac < min_angle_count:
        rejects.append(GateCode.insufficient_interrogation_depth)

    # quality floors (downgrade, never reject)
    if corpus_entry is None or not corpus_entry.provenance.strip():
        downgrades.append(GateCode.owned_or_real)
    if len(rubric.frames) < 1:
        downgrades.append(GateCode.process_layer_load)

    return GateResult(
        passed=len(rejects) == 0, rejects=rejects, downgrades=downgrades, angle_count=ac
    )
