"""Pure logic for probe 2: does the reformatted graded prompt shift a decision.

Four prompts changed format for single-line input when learner text started being indented
(`prompt_text.labelled`, which indents every line of a label block, including the first --
`_TURN_RENDER_CAP`'s sibling change in the same wave). Two of them decide things that matter:
`classify_response`, whose outcome moves durable learner state
(assessment/judgment_loop.py:264-310), and `map_territories`, which picks the territory a learner
enters (web/session_runner.py:889-890).

A naive old-vs-new comparison cannot attribute a difference to the indent, because both calls
sample: a fraction of outcomes differ between two runs of the identical prompt. This module runs
three arms per corpus item -- A (current prompt), B (current prompt again, the control), C (the
pre-change prompt, reconstructed) -- and reports `same_prompt_disagreement` (A vs B) against
`new_vs_old_disagreement` (A vs C). A shift is claimed only when the latter exceeds the former by
more than a stated margin (`verdict`).

The pre-change composition (`git show 5d05267:src/elenchus/model.py`) no longer exists in the
code; `reconstruct_old_classify_response_user`/`reconstruct_old_map_territories_user` rebuild it
explicitly and are pinned against that commit's literal f-strings in
tests/test_prompt_shift_probe.py. The two `_system` reconstructions that let arm C be sent
through the SAME system prompt as arms A/B (unchanged by the indent fix) live in
run_prompt_shift_probe.py, the I/O entrypoint, pinned there against the real AnthropicModel's
composed system text -- this module never imports model.py, so every function below is provable
without a model, per Model or `raw_parse` double.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Protocol

from pydantic import BaseModel

from .model import Model, ResponseClassification
from .types import Experience, TerritoryMap


def reconstruct_old_classify_response_user(push: str, response: str) -> str:
    """The pre-indent `classify_response` user message, verbatim from
    `git show 5d05267:src/elenchus/model.py` -- `f"Push:\\n{push}\\n\\nStudent reply:\\n{response}"`,
    no `prompt_text.labelled`, no indent, no cap. Pinned in
    tests/test_prompt_shift_probe.py against that literal."""
    return f"Push:\n{push}\n\nStudent reply:\n{response}"


def reconstruct_old_map_territories_user(situation: str, territories: list[tuple[str, str]]) -> str:
    """The pre-indent `map_territories` user message, verbatim from
    `git show 5d05267:src/elenchus/model.py` -- `f"Her situation:\\n{situation}\\n\\nTerritories:
    \\n{numbered}"`. The numbered-territories line is unchanged between old and new code (only the
    situation label gained the indent), so it is built the same way here as in `model.py`."""
    numbered = "\n".join(f"{i + 1}. [{eid}] {desc}" for i, (eid, desc) in enumerate(territories))
    return f"Her situation:\n{situation}\n\nTerritories:\n{numbered}"


def classify_response_disagree(a: ResponseClassification, b: ResponseClassification) -> bool:
    """True when `a`/`b` would drive `assessment.judgment_loop.assess` down different branches.
    That function (lines 264-310) branches on all three fields: `hard_wrong` (with
    `mode.bounded_error`) stops the loop outright; `outcome == "regressed"` lowers the frame
    state; `outcome == "closed" and mechanism_supplied` raises it to present_reasoned. A change
    in any one of the three can change which branch fires."""
    return (a.outcome, a.mechanism_supplied, a.hard_wrong) != (
        b.outcome,
        b.mechanism_supplied,
        b.hard_wrong,
    )


def territory_head(ranked: list[str], known_ids: list[str]) -> str:
    """The territory a learner actually enters, replicating web/session_runner.py:889-890's
    fallback exactly: the first of `ranked` that names a real territory, or `known_ids`' own
    order when the map named none of them ("a hallucinated ranking cannot pick the door")."""
    filtered = [e for e in ranked if e in known_ids]
    return (filtered or known_ids)[0]


def territories_disagree(a: TerritoryMap, b: TerritoryMap, known_ids: list[str]) -> bool:
    """True when the territory `a`/`b` would each land the learner in differs -- compares only
    `territory_head`, the field that actually picks the door, not the full `ranked` list (a
    reorder past the head changes nothing a learner experiences)."""
    return territory_head(a.ranked, known_ids) != territory_head(b.ranked, known_ids)


def verdict(same_prompt_disagreement: float, new_vs_old_disagreement: float, margin: float) -> bool:
    """A shift is claimed only when new-vs-old disagreement exceeds same-prompt disagreement by
    MORE than `margin` -- strict, so equal rates (and a gap that only meets the margin) never
    claim a shift. Pure: no model, no corpus, just the two measured rates and the threshold the
    caller chose."""
    return (new_vs_old_disagreement - same_prompt_disagreement) > margin


# ---------------------------------------------------------------------------
# classify_response corpus + orchestration
# ---------------------------------------------------------------------------


class ClassifyItem(NamedTuple):
    exp: Experience
    kind: str
    code: str
    stress: bool
    push: str
    response: str


def build_classify_corpus(
    pairs: list[tuple[str, str]], experiences: list[Experience], *, limit: int | None = None
) -> list[ClassifyItem]:
    """Round-robins each real (push, response) pair across `experiences`' `decision_frame` (the
    one frame code guaranteed present on every rubric under content/rubrics/ as of this writing),
    so `classify_response` gets a real rubric/target/system, not an invented one. Which frame is
    chosen doesn't change what's under test -- the indent, not the target angle -- it only needs
    to be a real code the rubric actually carries. An experience with no `decision_frame` is
    skipped for the items that would have landed on it."""
    if not experiences:
        return []
    items = pairs if limit is None else pairs[:limit]
    out = []
    for i, (push, response) in enumerate(items):
        exp = experiences[i % len(experiences)]
        code = exp.rubric.decision_frame
        if code is None:
            continue
        out.append(ClassifyItem(exp, "frame", code, False, push, response))
    return out


class ClassifyRecord(BaseModel):
    experience_id: str
    kind: str
    code: str
    push: str
    response: str
    arm_a: ResponseClassification
    arm_b: ResponseClassification
    arm_c: ResponseClassification
    same_prompt_disagree: bool
    new_vs_old_disagree: bool


class RawParse(Protocol):
    def __call__(self, *, system: str, user: str, output_format: type, max_tokens: int): ...


def run_classify_probe(
    items: list[ClassifyItem],
    model: Model,
    raw_parse: RawParse,
    system_for: Callable[[ClassifyItem], str],
    *,
    max_tokens: int,
) -> list[ClassifyRecord]:
    """Pure orchestration over the Model protocol plus `raw_parse`, the one seam outside it: arm
    C sends the RECONSTRUCTED pre-indent prompt, which no shipped method composes anymore, so it
    goes through a caller-supplied raw parse function instead of `model.classify_response`.
    `system_for` supplies the exact system text `model` would use for `it`'s
    `(exp, kind, code, stress)` -- unchanged by the indent fix, so arms A/B/C all see the SAME
    system and only `user` differs."""
    records = []
    for it in items:
        arm_a = model.classify_response(
            it.exp, it.kind, it.code, it.push, it.response, stress=it.stress
        )
        arm_b = model.classify_response(
            it.exp, it.kind, it.code, it.push, it.response, stress=it.stress
        )
        arm_c = raw_parse(
            system=system_for(it),
            user=reconstruct_old_classify_response_user(it.push, it.response),
            output_format=ResponseClassification,
            max_tokens=max_tokens,
        )
        records.append(
            ClassifyRecord(
                experience_id=it.exp.experience_id,
                kind=it.kind,
                code=it.code,
                push=it.push,
                response=it.response,
                arm_a=arm_a,
                arm_b=arm_b,
                arm_c=arm_c,
                same_prompt_disagree=classify_response_disagree(arm_a, arm_b),
                new_vs_old_disagree=classify_response_disagree(arm_a, arm_c),
            )
        )
    return records


# ---------------------------------------------------------------------------
# map_territories corpus + orchestration
# ---------------------------------------------------------------------------


class TerritoryItem(NamedTuple):
    situation: str
    territories: tuple[tuple[str, str], ...]


def build_territory_corpus(
    situations: list[str], territories: list[tuple[str, str]], *, limit: int | None = None
) -> list[TerritoryItem]:
    """Every real situation paired with the SAME curated territory list -- the real front door
    maps every situation against the same five territories (web/session_runner.py:870-871), it
    never varies per learner."""
    items = situations if limit is None else situations[:limit]
    frozen = tuple(territories)
    return [TerritoryItem(s, frozen) for s in items]


class TerritoryRecord(BaseModel):
    situation: str
    arm_a: TerritoryMap
    arm_b: TerritoryMap
    arm_c: TerritoryMap
    same_prompt_disagree: bool
    new_vs_old_disagree: bool


def run_territory_probe(
    items: list[TerritoryItem],
    model: Model,
    raw_parse: RawParse,
    system_text: str,
    *,
    max_tokens: int,
) -> list[TerritoryRecord]:
    """Pure orchestration, `map_territories`' shape of `run_classify_probe`. `system_text` is
    fixed across every item (map_territories' system carries no per-item data -- only `user`
    does), so the caller supplies it once."""
    records = []
    for it in items:
        territories = list(it.territories)
        known_ids = [eid for eid, _ in territories]
        arm_a = model.map_territories(it.situation, territories)
        arm_b = model.map_territories(it.situation, territories)
        arm_c = raw_parse(
            system=system_text,
            user=reconstruct_old_map_territories_user(it.situation, territories),
            output_format=TerritoryMap,
            max_tokens=max_tokens,
        )
        records.append(
            TerritoryRecord(
                situation=it.situation,
                arm_a=arm_a,
                arm_b=arm_b,
                arm_c=arm_c,
                same_prompt_disagree=territories_disagree(arm_a, arm_b, known_ids),
                new_vs_old_disagree=territories_disagree(arm_a, arm_c, known_ids),
            )
        )
    return records


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------


class ProbeRates(BaseModel):
    sample_size: int
    same_prompt_disagreement: float
    new_vs_old_disagreement: float
    margin: float
    shift_claimed: bool


def summarize_disagreement(records: list, margin: float) -> ProbeRates:
    """The two disagreement rates plus the verdict, over any record sequence carrying
    `same_prompt_disagree`/`new_vs_old_disagree` bools -- `ClassifyRecord` and `TerritoryRecord`
    both do, and this is the one place that turns per-item flags into the two rates `verdict`
    compares, so both decision points read it off the identical computation."""
    n = len(records)
    if n == 0:
        same = 0.0
        new_old = 0.0
    else:
        same = sum(1 for r in records if r.same_prompt_disagree) / n
        new_old = sum(1 for r in records if r.new_vs_old_disagree) / n
    return ProbeRates(
        sample_size=n,
        same_prompt_disagreement=same,
        new_vs_old_disagreement=new_old,
        margin=margin,
        shift_claimed=verdict(same, new_old, margin),
    )


class Probe2Result(BaseModel):
    model_id: str
    margin: float
    classify_corpus_source: str  # "live_db" | "empty_fallback"
    classify_records: list[ClassifyRecord]
    classify_rates: ProbeRates
    territory_corpus_source: str  # "live_db" | "empty_fallback"
    territory_records: list[TerritoryRecord]
    territory_rates: ProbeRates
