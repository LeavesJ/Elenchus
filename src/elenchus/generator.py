from __future__ import annotations

import re

from .content_loader import (
    load_checkable_library,
    load_denylist,
    load_experience,
    load_library,
    load_min_angle_count,
)
from .types import CorpusEntry, Experience, GateCode, GateResult, Mode, Regime, Rubric, Scene

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


def _strip_emphasis(text: str) -> str:
    """Drop markdown emphasis (* and `) so legible bolding cannot split a banned phrase past the
    anti-label checks (e.g. `**Lead** with what you refuse to do`). `_` is kept — snake_case frame
    codes legitimately use it. Both prompt gates run text through this before matching."""
    return text.replace("*", "").replace("`", "")


def _contains_phrase(text_lc: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text_lc) is not None


def frame_trap_phrases(rubric: Rubric) -> list[str]:
    """Every frame and trap code this rubric carries, in both snake and spaced form, lowercased.

    Public because two callers now need it: `label_leak` below, and
    `judgment_loop._label_steer`, which tests a leak's matched phrase against exactly this list to
    decide whether it is a code for THIS rubric (never name it) or something else -- a framework
    or a category cue (safe to name)."""
    phrases: list[str] = []
    for code in [f.frame_code for f in rubric.frames] + [t.trap_code for t in rubric.traps]:
        phrases.append(code.lower())
        phrases.append(code.replace("_", " ").lower())
    return phrases


def phrase_leak(text: str, phrases: list[str]) -> str | None:
    """The first phrase present in `text` as a whole phrase, or None.

    Exists because two callers need the same strip-and-scan over different phrase lists: label_leak,
    which scans the framework denylist plus this rubric's frame and trap codes, and
    judgment_loop._push_label_leak, which additionally scans the push category denylist. Returns the
    matched phrase so a caller can put it in the ledger."""
    text_lc = _strip_emphasis(text).lower()
    for phrase in phrases:
        if _contains_phrase(text_lc, phrase):
            return phrase
    return None


def label_leak(text: str, rubric: Rubric, framework_denylist: list[str]) -> str | None:
    """The label bar alone: a named framework, or a frame/trap code in snake or spaced form.

    Returns the MATCHED PHRASE so a caller can put it in the ledger, or None.

    This exists because three callers need exactly this half: validate_scene, which adds the
    scaffold and wrapper bars on top for authored scenes; anti_label_gate, which maps it to
    GateCode.pre_named_framework; and judgment_loop._push_label_leak, which screens a PUSH, where
    scaffold and wrapper vocabulary is ordinary English. Measured against the twelve-push corpus
    in tests/test_judgment_loop.py::test_push_label_leak_clears_ordinary_pushes_on_real_content,
    run against the real rubric content/rubrics/license_continuity.yaml: the full bar (this check
    plus the scaffold and wrapper bars) rejects 5 of 12, this bar alone rejects 0 of 12, and this
    bar still catches all three real cases (a named framework, a snake frame code, a spaced frame
    code)."""
    phrases = [t.lower() for t in framework_denylist] + frame_trap_phrases(rubric)
    return phrase_leak(text, phrases)


def validate_scene(
    scene: Scene,
    rubric: Rubric,
    *,
    framework_denylist: list[str],
    scaffold_denylist: list[str],
) -> None:
    """The concrete prompt the student SEES — and the situation woven into the instructor's
    pushes (whose text the student also sees) — must clear the same anti-label bar: no named
    framework, no leaked frame/trap code, no type-hint scaffold, no cosmetic wrapper word.

    Scenes are authored as legible markdown (bold key terms), so emphasis markers are stripped
    (via `_strip_emphasis`) before the checks — otherwise `**Lead** with what you refuse to do`
    would split a banned phrase and slip past."""
    text = f"{scene.prompt}\n{scene.situation}"
    if label_leak(text, rubric, framework_denylist) is not None:
        raise GateError("scene names a framework or leaks a frame/trap code")
    text_lc = _strip_emphasis(text).lower()
    if any(_contains_phrase(text_lc, p) for p in scaffold_denylist):
        raise GateError("scene contains a type-hint scaffold")
    if any(w in text_lc for w in WRAPPER_WORDS):
        raise GateError("scene contains a cosmetic wrapper word")


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
    prompt_lc = _strip_emphasis(exp.prompt).lower()
    rubric = exp.rubric

    # recoverable_label: anchored to a curated owned-problem with a non-empty unlabeled rationale.
    if corpus_entry is None or not corpus_entry.unlabeled.strip():
        rejects.append(GateCode.recoverable_label)

    # pre_named_framework: no named method, and no leaked frame/trap code (snake or spaced).
    if label_leak(exp.prompt, rubric, framework_denylist) is not None:
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


def load_gated_library(corpus, root=None):
    """Load every authored experience and gate it. Raise on any hard reject (fail loud at load)."""
    min_angle = load_min_angle_count(root)
    fw = load_denylist("framework_denylist", root)
    sc = load_denylist("scaffold_denylist", root)
    by_ref = {c.ledger_ref: c for c in corpus}
    out: list[tuple[Experience, GateResult]] = []
    for exp in load_library(root):
        res = anti_label_gate(
            exp,
            by_ref.get(exp.ledger_ref),
            min_angle_count=min_angle,
            framework_denylist=fw,
            scaffold_denylist=sc,
        )
        if not res.passed:
            raise GateError(
                f"{exp.experience_id} failed the gate: {[c.value for c in res.rejects]}"
            )
        out.append((exp, res))
    return out


def _coverage(exp: Experience, target_frames: list[str]) -> int:
    codes = {f.frame_code for f in exp.rubric.frames}
    return sum(1 for tf in target_frames if tf in codes)


def select_open_ended(core, state, ledger, corpus, spec, root=None) -> Experience:
    if spec is not None and spec.ledger_ref.startswith("gen:"):
        # Living-sitting seam (spec §2b / review M1): a gen: spec pops the forged Experience
        # the worker registered pre-selection (instance grain, "gen:{sitting}:{n}"). FIRST
        # branch on purpose — forged specs also carry the base experience_id, and the curated
        # bypass below would otherwise serve the curated prompt from disk. Late import: forge
        # imports this module's validate_scene/GateError (a top-level import would cycle).
        from .forge import forge_registry

        return forge_registry.pop(spec.ledger_ref)
    if spec is not None and spec.experience_id is not None:
        return load_experience(
            spec.experience_id, root
        )  # the exact (frame, experience) the policy scored
    gated = [(e, r) for (e, r) in load_gated_library(corpus, root) if e.regime is Regime.open_ended]
    if not gated:
        raise GateError("no shippable open_ended experience in the library")
    target = spec.target_frames if spec is not None else []
    # Rank: most target-frame coverage first; clean experiences before downgraded; then id.
    ranked = sorted(
        gated,
        key=lambda er: (-_coverage(er[0], target), len(er[1].downgrades), er[0].experience_id),
    )
    return ranked[0][0]


def _concept_coverage(exp: Experience, targets: list[str]) -> int:
    concepts = {q.concept for q in exp.checkable.questions}
    return sum(1 for t in targets if t in concepts)


def select_cs_technical(core, state, ledger, corpus, spec, root=None) -> Experience:
    lib = load_checkable_library(root)
    if not lib:
        raise GateError("no cs_technical experience in the checkable library")
    if spec is not None and spec.target_frames:
        targets = spec.target_frames
    elif core is not None and core.content_core:
        targets = core.content_core
    else:
        targets = []
    ranked = sorted(lib, key=lambda e: (-_concept_coverage(e, targets), e.experience_id))
    return ranked[0]
