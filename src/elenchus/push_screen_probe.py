"""Pure logic for probe 1: the push screen's false-positive rate on real `generate_push` output.

The push screen was narrowed from `generator.validate_scene`'s full four-part bar to
`assessment.judgment_loop._push_label_leak`'s label-only bar. Two prior corpora disagreed on the
old bar's false-positive rate and neither was real `generate_push` output, so the honest rate is
still unmeasured. This module builds a real corpus (every frame/trap angle in every rubric under
content/rubrics/, each pushed once blind and once with real learner positions) and screens each
output through both bars so they are compared on the same sample. The only network call in the
whole probe is `model.generate_push`; everything else here is deterministic and model-free.
"""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel

from .assessment.judgment_loop import _push_label_leak
from .generator import WRAPPER_WORDS, _strip_emphasis, frame_trap_phrases, phrase_leak
from .model import Model
from .types import Experience, Positions, Rubric


class PushTarget(NamedTuple):
    kind: str  # "frame" | "trap"
    code: str
    stress: bool


def push_targets(rubric: Rubric) -> list[PushTarget]:
    """Every angle a real session eventually presses on this rubric: each frame twice (an
    ordinary push toward it, `stress=False`, and the harder push once it already reads
    present_reasoned, `stress=True` -- assessment/judgment_loop.py's own
    `stress = kind == "frame" and frame_states.get(code) is FrameState.present_reasoned`), each
    trap once (traps never take a stress push: `assess` never sets `stress=True` for
    `kind == "trap"`)."""
    targets = [PushTarget("frame", f.frame_code, s) for f in rubric.frames for s in (False, True)]
    targets += [PushTarget("trap", t.trap_code, False) for t in rubric.traps]
    return targets


class PushCase(NamedTuple):
    experience_id: str
    kind: str
    code: str
    stress: bool
    position_mode: str  # "blind" | "positioned"


def build_cases(experiences: list[Experience]) -> list[PushCase]:
    """Every `push_targets` angle across `experiences`, each doubled into a "blind" case (no
    prior positions -- the shape of a session's very first push) and a "positioned" case (real
    learner positions attached -- the shape of every push after the first). Both are real
    distributions `assess` produces; measuring only one would silently pick a sample."""
    cases = []
    for exp in experiences:
        for t in push_targets(exp.rubric):
            for mode in ("blind", "positioned"):
                cases.append(PushCase(exp.experience_id, t.kind, t.code, t.stress, mode))
    return cases


def sample_positions(pool: list[str], *, on_angle_n: int = 3, elsewhere_n: int = 2) -> Positions:
    """A deterministic (on_angle, elsewhere) split off the front of `pool`. `pool` need not be
    tagged by angle -- the db carries no per-frame label for a learner turn -- this only needs to
    hand `generate_push` real learner prose to react to, which is what on_angle/elsewhere is FOR
    (giving the push author real words, not correctly-attributed ones). Empty when `pool` is
    empty; tolerates a pool smaller than requested."""
    if not pool:
        return Positions()
    on_angle = tuple(pool[:on_angle_n])
    elsewhere = tuple(pool[on_angle_n : on_angle_n + elsewhere_n])
    return Positions(on_angle=on_angle, elsewhere=elsewhere)


def old_bar_checks(
    text: str, rubric: Rubric, framework_denylist: list[str], scaffold_denylist: list[str]
) -> dict[str, str | None]:
    """`generator.validate_scene`'s bar, split into its four constituent checks and run against
    push TEXT directly -- validate_scene itself only ever runs against an authored Scene's
    prompt+situation, and only ever raises at the FIRST failing check, so it can never say a
    push failed more than one. `label_leak` folds two phrase sources (`framework_denylist`,
    `frame_trap_phrases`) behind one `phrase_leak` call; split here so a push that trips both is
    reported against BOTH, not just whichever phrase source happened to be scanned first.

    Returns each check's matched phrase, or None; a push is old-bar-rejected iff any value is
    not None (see `PushScreenRecord.old_bar_rejected`)."""
    text_lc = _strip_emphasis(text).lower()
    return {
        "named_framework": phrase_leak(text, framework_denylist),
        "frame_trap_code_leak": phrase_leak(text, frame_trap_phrases(rubric)),
        "type_hint_scaffold": phrase_leak(text, scaffold_denylist),
        "cosmetic_wrapper_word": next((w for w in WRAPPER_WORDS if w in text_lc), None),
    }


class PushScreenRecord(BaseModel):
    experience_id: str
    kind: str
    code: str
    stress: bool
    position_mode: str
    push_text: str
    new_bar_hit: str | None  # assessment.judgment_loop._push_label_leak's result
    old_bar_checks: dict[str, str | None]  # this module's old_bar_checks' result

    @property
    def old_bar_rejected(self) -> bool:
        return any(v is not None for v in self.old_bar_checks.values())


def run_push_screen_probe(
    experiences: list[Experience],
    model: Model,
    *,
    positions_pool: list[str],
    framework_denylist: list[str],
    scaffold_denylist: list[str],
) -> list[PushScreenRecord]:
    """Pure orchestration over the Model protocol (elicitation.run_elicitation_probe's shape):
    author a push for every case `build_cases` derives from `experiences`, screen it through
    both bars, and return one record per push. `generate_push` is the only model call."""
    experiences_by_id = {e.experience_id: e for e in experiences}
    records = []
    for case in build_cases(experiences):
        exp = experiences_by_id[case.experience_id]
        positions = (
            Positions() if case.position_mode == "blind" else sample_positions(positions_pool)
        )
        push_text = model.generate_push(
            exp, case.kind, case.code, stress=case.stress, positions=positions
        )
        records.append(
            PushScreenRecord(
                experience_id=case.experience_id,
                kind=case.kind,
                code=case.code,
                stress=case.stress,
                position_mode=case.position_mode,
                push_text=push_text,
                new_bar_hit=_push_label_leak(push_text, exp.rubric),
                old_bar_checks=old_bar_checks(
                    push_text, exp.rubric, framework_denylist, scaffold_denylist
                ),
            )
        )
    return records


class Probe1Summary(BaseModel):
    total: int
    new_bar_rejected: int
    new_bar_rejected_phrases: dict[str, int]
    old_bar_rejected: int
    old_bar_rejected_by_check: dict[str, int]


class Probe1Result(BaseModel):
    model_id: str
    corpus_source: str  # "live_db" | "empty_fallback"
    positions_pool_size: int
    framework_denylist: list[str]
    scaffold_denylist: list[str]
    records: list[PushScreenRecord]

    def summarize(self) -> Probe1Summary:
        new_phrases: dict[str, int] = {}
        old_by_check: dict[str, int] = {}
        new_rejected = 0
        old_rejected = 0
        for r in self.records:
            if r.new_bar_hit is not None:
                new_rejected += 1
                new_phrases[r.new_bar_hit] = new_phrases.get(r.new_bar_hit, 0) + 1
            if r.old_bar_rejected:
                old_rejected += 1
                for check, hit in r.old_bar_checks.items():
                    if hit is not None:
                        old_by_check[check] = old_by_check.get(check, 0) + 1
        return Probe1Summary(
            total=len(self.records),
            new_bar_rejected=new_rejected,
            new_bar_rejected_phrases=new_phrases,
            old_bar_rejected=old_rejected,
            old_bar_rejected_by_check=old_by_check,
        )
