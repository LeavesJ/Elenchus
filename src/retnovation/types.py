from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Strength(str, Enum):
    weak = "weak"
    forming = "forming"
    strong = "strong"


class Regime(str, Enum):
    open_ended = "open_ended"
    cs_technical = "cs_technical"


class Mode(str, Enum):
    genuinely_open = "genuinely_open"
    bounded_error = "bounded_error"


class FrameState(str, Enum):
    absent = "absent"
    present_asserted = "present_asserted"
    present_reasoned = "present_reasoned"


class TrapState(str, Enum):
    not_tripped = "not_tripped"
    tripped = "tripped"
    repaired = "repaired"


class StopReason(str, Enum):
    converged = "converged"
    bounded_error_violation = "bounded_error_violation"
    plateau = "plateau"
    regression = "regression"
    budget = "budget"


class GateCode(str, Enum):
    recoverable_label = "recoverable_label"
    pre_named_framework = "pre_named_framework"
    type_hint_scaffold = "type_hint_scaffold"
    softened_ambiguity = "softened_ambiguity"
    cosmetic_engagement = "cosmetic_engagement"
    owned_or_real = "owned_or_real"
    process_layer_load = "process_layer_load"
    insufficient_interrogation_depth = "insufficient_interrogation_depth"


class CheckType(str, Enum):
    deterministic = "deterministic"
    model_graded = "model_graded"


class Frame(BaseModel):
    frame_code: str
    frame_detail: str
    paired_trap: str | None = None


class Trap(BaseModel):
    trap_code: str
    trap_detail: str


class Rubric(BaseModel):
    frames: list[Frame]
    traps: list[Trap]
    mode: Mode
    binding_constraint: str | None = None


class CheckableQuestion(BaseModel):
    question_id: str
    concept: str
    prompt: str
    check_type: CheckType
    choices: list[str] = Field(default_factory=list)
    answer_key: list[str] = Field(default_factory=list)
    criteria: str | None = None


class CheckableSet(BaseModel):
    questions: list[CheckableQuestion]


class ConceptResult(BaseModel):
    concept: str
    question_id: str
    correct: bool
    check_type: CheckType


class CheckableAssessment(BaseModel):
    results: list[ConceptResult]


class CheckableGrade(BaseModel):
    correct: bool


class Aim(BaseModel):
    posture: str
    process_dial: int
    content_core: list[str] | None = None


class Core(BaseModel):
    process_frames: list[str]
    declarative_seed: list[str]
    content_core: list[str] | None = None


class Experience(BaseModel):
    experience_id: str
    prompt: str
    ledger_ref: str
    regime: Regime
    rubric: Rubric | None = None
    checkable: CheckableSet | None = None
    scene: Scene | None = None

    @model_validator(mode="after")
    def _regime_payload_invariant(self) -> "Experience":
        if self.regime is Regime.open_ended:
            if self.rubric is None or self.checkable is not None:
                raise ValueError("open_ended experience requires a rubric and no checkable")
        elif self.regime is Regime.cs_technical:
            if self.checkable is None or self.rubric is not None:
                raise ValueError("cs_technical experience requires a checkable and no rubric")
        return self


class GateResult(BaseModel):
    passed: bool
    rejects: list[GateCode]
    downgrades: list[GateCode]
    angle_count: int


class Push(BaseModel):
    target_code: str
    kind: str
    text: str
    response_classification: str
    response: str = ""


class FrameDelta(BaseModel):
    code: str
    before: FrameState
    after: FrameState


class SharperVerdict(BaseModel):
    sharper: bool
    reason: str


class SharperAuditItem(BaseModel):
    code: str
    kind: str
    instructor_sharper: bool
    grader_sharper: bool
    confirmed: bool
    grader_reason: str


class Assessment(BaseModel):
    trajectory: list[Push]
    frame_deltas: list[FrameDelta]
    frames_closed_under_pressure: list[str]
    hard_wrong_flags: list[str]
    stop_reason: StopReason
    sharper_audit: list[SharperAuditItem] = Field(default_factory=list)


class FrameStrength(BaseModel):
    strength: Strength
    last_seen: datetime
    due: datetime
    last_evidence: str


class TrapOccurrence(BaseModel):
    experience_id: str
    occurred_at: datetime
    detail: str


class SpacedItem(BaseModel):
    concept: str
    due: datetime
    interval_days: int


class LearnerState(BaseModel):
    frames: dict[str, FrameStrength] = Field(default_factory=dict)
    trap_gallery: dict[str, list[TrapOccurrence]] = Field(default_factory=dict)
    declarative_seed: dict[str, SpacedItem] = Field(default_factory=dict)


class LedgerEntry(BaseModel):
    id: str
    owned_problem: str
    links_to_experiences: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    prompt: str
    situation: str


class CorpusEntry(BaseModel):
    ledger_ref: str
    domain: str
    why_owned: str
    unlabeled: str
    provenance: str
    corpus_pointers: list[str] = Field(default_factory=list)
    scene: Scene | None = None


class NextExperienceSpec(BaseModel):
    # target codes for the next experience: process frames for open_ended, content concepts
    # for cs_technical. Overloaded by name (not renamed) to avoid a persisted-queue migration.
    target_frames: list[str]
    ledger_ref: str
    regime: Regime


@dataclass
class Work:
    opening: str
    respond: Callable[[str], str]
